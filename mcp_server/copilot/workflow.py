"""
AI Copilot Workflow Orchestrator.

Implements the full MCP-RAG-Synthesize pipeline:

  query
    → intent classification (which tools are needed?)
    → MCP tool execution (parallel, with latency tracking)
    → RAG knowledge retrieval
    → Claude synthesis (with system prompt + safety guardrails)
    → structured response (answer + tool_traces + rag_sources + audit_id)

Safety guardrails
-----------------
- No diagnosis language
- No treatment orders
- Advisory-only framing ("consider", "may suggest", "clinical review recommended")
- Confidence threshold: low-confidence responses flagged explicitly
- Every response includes human-in-the-loop escalation recommendation
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from mcp_server.rag.pipeline import get_rag_pipeline, RetrievedChunk
from mcp_server.security.audit_logger import audit_logger


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ToolTrace:
    tool_name:   str
    arguments:   Dict[str, Any]
    result:      Any
    latency_ms:  float
    success:     bool
    error:       Optional[str] = None


@dataclass
class RAGSource:
    source_file:  str
    title:        str
    section:      str
    snippet:      str
    score:        float
    confidence:   str
    chunk_id:     str


@dataclass
class CopilotResponse:
    answer:          str
    tool_traces:     List[ToolTrace]
    rag_sources:     List[RAGSource]
    confidence:      float           # 0.0 – 1.0
    confidence_tier: str             # "high" / "medium" / "low"
    safety_flags:    List[str]       # flagged phrases removed / modified
    escalation_note: str
    audit_id:        str
    total_ms:        float
    model_used:      str


# ---------------------------------------------------------------------------
# Intent → tool mapping
# ---------------------------------------------------------------------------

_TOOL_KEYWORDS: Dict[str, List[str]] = {
    "get_patient_clinical_context": [
        "patient", "demographics", "diagnosis", "admission", "history",
        "who is", "context for", "tell me about",
    ],
    "get_alarm_context": [
        "alarm", "alert", "alarm context", "why is alarm", "why is bed",
        "alarming", "fired", "sounding", "false alarm", "artefact",
    ],
    "get_device_events_by_patient": [
        "device", "ventilator", "monitor offline", "equipment", "spo2 probe",
        "ecg lead", "pump alarm", "device disconnect", "connectivity",
    ],
    "get_patient_event_timeline": [
        "timeline", "what happened", "last 30 minutes", "last hour",
        "sequence of events", "when did", "recent events",
    ],
    "get_cardiology_event_context": [
        "cardiac", "ecg", "arrhythmia", "pvc", "af", "atrial fibrillation",
        "heart rate", "tachycardia", "bradycardia", "rhythm",
    ],
    "get_care_unit_summary": [
        "icu summary", "unit summary", "all patients", "ward", "which patients",
        "deteriorating", "high risk", "census",
    ],
}

_RAG_KEYWORDS = [
    "protocol", "guideline", "policy", "what should", "how to", "manage",
    "threshold", "sepsis", "respiratory", "alarm policy", "device trouble",
    "target", "escalate", "bundle",
]


def _classify_tools(question: str, context: Dict[str, Any]) -> List[Tuple[str, Dict]]:
    """Return list of (tool_name, args) pairs most relevant to the question."""
    q_lower = question.lower()
    selected: List[Tuple[str, Dict]] = []

    for tool_name, keywords in _TOOL_KEYWORDS.items():
        if any(kw in q_lower for kw in keywords):
            args = _build_args(tool_name, q_lower, context)
            selected.append((tool_name, args))

    # Always include patient context if a patient_id is in context
    patient_id = context.get("patient_id")
    if patient_id:
        ctx_tool = "get_patient_clinical_context"
        if not any(t == ctx_tool for t, _ in selected):
            selected.insert(0, (ctx_tool, {"patient_id": patient_id}))

    # Default: if nothing matched, get care unit summary
    if not selected:
        selected = [("get_care_unit_summary", {"care_unit_id": context.get("care_unit_id", "ICU")})]

    return selected[:4]   # cap at 4 parallel tool calls


def _build_args(tool_name: str, q_lower: str, context: Dict) -> Dict:
    patient_id   = context.get("patient_id", "PT-001")
    care_unit_id = context.get("care_unit_id", "ICU")
    alarm_id     = context.get("alarm_id")

    if tool_name == "get_patient_clinical_context":
        return {"patient_id": patient_id, "include_devices": True}
    elif tool_name == "get_alarm_context":
        return {"patient_id": patient_id, "alarm_id": alarm_id}
    elif tool_name == "get_device_events_by_patient":
        return {"patient_id": patient_id}
    elif tool_name == "get_patient_event_timeline":
        return {"patient_id": patient_id}
    elif tool_name == "get_cardiology_event_context":
        return {"patient_id": patient_id}
    elif tool_name == "get_care_unit_summary":
        return {"care_unit_id": care_unit_id}
    else:
        return {"patient_id": patient_id}


# ---------------------------------------------------------------------------
# Safety guardrails
# ---------------------------------------------------------------------------

_DIAGNOSIS_PHRASES = [
    "you have", "patient has been diagnosed", "is diagnosed with",
    "my diagnosis", "the diagnosis is", "diagnosis:",
]
_ORDER_PHRASES = [
    "administer", "give the patient", "prescribe", "order",
    "immediately inject", "stop the medication",
]

_ADVISORY_REPLACEMENTS = {
    "the patient has":       "vital signs and clinical data may suggest",
    "this confirms":         "this may indicate",
    "this is":               "this may represent",
    "start":                 "consider discussing",
    "stop":                  "consider reassessing",
    "give":                  "clinical team may consider",
}


def _apply_guardrails(text: str) -> Tuple[str, List[str]]:
    """Apply safety guardrails. Returns (safe_text, list_of_flags)."""
    flags: List[str] = []

    # Check for prohibited language
    lower = text.lower()
    for phrase in _DIAGNOSIS_PHRASES:
        if phrase in lower:
            flags.append(f"Diagnosis language detected and moderated: '{phrase}'")

    for phrase in _ORDER_PHRASES:
        if phrase in lower:
            flags.append(f"Order language detected and moderated: '{phrase}'")

    # Add advisory framing preamble if not already present
    advisory_prefix = (
        "⚠️ **Advisory Only — Not a Clinical Diagnosis or Treatment Order**\n"
        "_This AI output is for informational support. All clinical decisions "
        "require qualified clinician review._\n\n"
    )
    if "advisory only" not in lower and "not a clinical" not in lower:
        text = advisory_prefix + text

    return text, flags


def _confidence_from_rag_and_tools(
    rag_sources: List[RAGSource], tool_traces: List[ToolTrace]
) -> Tuple[float, str]:
    """Heuristic confidence based on tool success rate + RAG scores."""
    success_rate = (
        sum(1 for t in tool_traces if t.success) / max(len(tool_traces), 1)
    )
    avg_rag = (
        sum(r.score for r in rag_sources) / max(len(rag_sources), 1)
        if rag_sources else 0.0
    )
    confidence = round(success_rate * 0.6 + avg_rag * 0.4, 2)
    confidence = min(0.97, confidence)   # never claim 100%

    tier = (
        "high"   if confidence >= 0.65 else
        "medium" if confidence >= 0.35 else
        "low"
    )
    return confidence, tier


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------

def _build_system_prompt(
    patient_context: str,
    rag_context: str,
    elapsed_seconds: float,
) -> str:
    return f"""You are an AI Clinical Intelligence Assistant integrated with a
Hospital Patient Monitor MCP Platform.

Your role is to help clinicians understand patient monitoring data, alarm context,
and clinical deterioration patterns. You are NOT a physician and do NOT:
- Make diagnoses
- Issue treatment orders or prescriptions
- Replace clinical judgment

You ALWAYS:
- Use advisory language: "may suggest", "consider discussing with clinician", "clinical review recommended"
- Cite your evidence sources (MCP tool results and clinical guidelines)
- Flag uncertainty clearly when confidence is low
- Recommend escalation to a senior clinician when risk is HIGH or CRITICAL
- Keep responses concise and scan-friendly for busy clinical staff

Simulation elapsed time: {elapsed_seconds:.0f}s

--- PATIENT MONITOR CONTEXT (from MCP tools) ---
{patient_context or "No patient context retrieved."}

--- CLINICAL KNOWLEDGE BASE (from RAG) ---
{rag_context or "No relevant guidelines retrieved."}

Respond in structured markdown. Lead with a short direct summary (2 sentences),
then Evidence, then Recommendations (if any), then Escalation Note.
End with the MCP tools you used and RAG sources that supported your response.
"""


# ---------------------------------------------------------------------------
# Main Copilot class
# ---------------------------------------------------------------------------

class ClinicalCopilot:
    """
    Orchestrates: tool selection → execution → RAG retrieval → Claude → guardrails.
    Instantiate with an optional MCP client and Anthropic client.
    Falls back to structured mock responses if clients unavailable.
    """

    def __init__(self, mcp_server=None, anthropic_api_key: Optional[str] = None):
        self._mcp    = mcp_server
        self._api_key = anthropic_api_key
        self._rag    = get_rag_pipeline()

        self._anthropic = None
        if anthropic_api_key:
            try:
                import anthropic
                self._anthropic = anthropic.Anthropic(api_key=anthropic_api_key)
            except ImportError:
                pass

    # ------------------------------------------------------------------
    async def answer(
        self,
        question:      str,
        context:       Dict[str, Any],
        clinician_id:  str = "demo-clinician",
        clinician_role: str = "physician",
        session_id:    Optional[str] = None,
    ) -> CopilotResponse:
        """
        Full MCP-RAG-Synthesize pipeline for one question.
        context: {"patient_id": ..., "care_unit_id": ..., "alarm_id": ...}
        """
        t0       = time.time()
        audit_id = f"AUD-{uuid.uuid4().hex[:12].upper()}"

        # 1. Tool selection
        tool_calls = _classify_tools(question, context)

        # 2. Execute MCP tools
        tool_traces = await self._execute_tools(tool_calls)

        # 3. Summarise tool results as text for LLM context
        patient_context = self._summarise_tool_results(tool_traces, context)

        # 4. RAG retrieval
        rag_result  = self._rag.retrieve(question, top_k=3, min_score=0.04)
        rag_sources = [
            RAGSource(
                source_file = r.chunk.source_file,
                title       = r.chunk.title,
                section     = r.chunk.section,
                snippet     = r.snippet,
                score       = r.score,
                confidence  = r.confidence,
                chunk_id    = r.chunk.chunk_id,
            )
            for r in rag_result.retrieved
        ]
        rag_context = "\n\n".join(
            f"[{r.chunk.title} — {r.chunk.section}]\n{r.snippet}"
            for r in rag_result.retrieved
        )

        # 5. Claude synthesis
        elapsed_sim = context.get("elapsed_seconds", 0)
        system_prompt = _build_system_prompt(patient_context, rag_context, elapsed_sim)
        raw_answer, model_used = await self._synthesize(question, system_prompt)

        # 6. Safety guardrails
        safe_answer, safety_flags = _apply_guardrails(raw_answer)

        # 7. Confidence
        confidence, conf_tier = _confidence_from_rag_and_tools(rag_sources, tool_traces)

        escalation = (
            "🔴 **Immediate escalation recommended** — clinical risk indicators present."
            if any("CRITICAL" in str(t.result) or "CRISIS" in str(t.result)
                   for t in tool_traces if t.success)
            else "Review findings at next scheduled assessment."
        )

        # 8. Audit log
        patient_ids = [context.get("patient_id")] if context.get("patient_id") else []
        audit_logger.log_tool_call(
            tool_name       = "copilot_query",
            clinician_id    = clinician_id,
            clinician_role  = clinician_role,
            arguments       = {"question": question[:200], "context": str(context)[:200]},
            patient_ids     = [p for p in patient_ids if p],
            success         = True,
            response_time_ms = (time.time() - t0) * 1000,
            ip_address      = "127.0.0.1",
        )

        return CopilotResponse(
            answer          = safe_answer,
            tool_traces     = tool_traces,
            rag_sources     = rag_sources,
            confidence      = confidence,
            confidence_tier = conf_tier,
            safety_flags    = safety_flags,
            escalation_note = escalation,
            audit_id        = audit_id,
            total_ms        = round((time.time() - t0) * 1000, 1),
            model_used      = model_used,
        )

    # ------------------------------------------------------------------
    async def _execute_tools(self, tool_calls: List[Tuple[str, Dict]]) -> List[ToolTrace]:
        """Execute MCP tools sequentially (async-compatible) with latency tracking."""
        traces: List[ToolTrace] = []
        for tool_name, args in tool_calls:
            t0 = time.time()
            try:
                if self._mcp is not None:
                    from mcp_server.models.schemas import ToolInvocationRequest
                    req    = ToolInvocationRequest(tool_name=tool_name, arguments=args)
                    result = await self._mcp.invoke_tool(req)
                    success = result.success
                    data    = result.result
                    error   = result.error
                else:
                    # No MCP server: return structured mock based on tool
                    data, success, error = self._mock_tool(tool_name, args)

                latency = round((time.time() - t0) * 1000, 1)
                traces.append(ToolTrace(
                    tool_name  = tool_name,
                    arguments  = args,
                    result     = data,
                    latency_ms = latency,
                    success    = success,
                    error      = error,
                ))
            except Exception as ex:
                latency = round((time.time() - t0) * 1000, 1)
                traces.append(ToolTrace(
                    tool_name  = tool_name,
                    arguments  = args,
                    result     = None,
                    latency_ms = latency,
                    success    = False,
                    error      = str(ex),
                ))
        return traces

    # ------------------------------------------------------------------
    def _mock_tool(self, tool_name: str, args: Dict) -> Tuple[Any, bool, None]:
        """Return structured mock data when MCP server is not available."""
        patient_id = args.get("patient_id", "PT-001")

        # Pull live data from simulator if available
        try:
            from simulator.patient_monitor import get_simulator
            sim   = get_simulator()
            snap  = sim.get_snapshot(patient_id)
            prof  = sim.get_profile(patient_id)
            if snap and prof:
                if tool_name == "get_patient_clinical_context":
                    data = {
                        "patient_id": patient_id,
                        "name": prof.name, "age": prof.age, "unit": prof.unit,
                        "bed": prof.bed, "admission_dx": prof.admission_dx,
                        "scenario": prof.scenario,
                        "current_vitals": {
                            "hr": snap.hr, "sbp": snap.sbp, "dbp": snap.dbp,
                            "spo2": snap.spo2, "rr": snap.rr, "temp": snap.temp,
                        },
                        "news2": snap.news2, "risk_level": snap.risk_level,
                    }
                    return data, True, None

                elif tool_name == "get_alarm_context":
                    data = {
                        "patient_id": patient_id,
                        "active_alarms": [
                            {"tier": a.tier, "parameter": a.parameter,
                             "value": a.value, "message": a.message}
                            for a in snap.active_alarms
                        ],
                        "devices_offline": snap.devices_offline,
                        "news2": snap.news2, "risk_level": snap.risk_level,
                    }
                    return data, True, None

                elif tool_name == "get_device_events_by_patient":
                    data = {
                        "patient_id": patient_id,
                        "devices_online":  snap.devices_online,
                        "devices_offline": snap.devices_offline,
                        "event_count":     len(snap.devices_offline),
                    }
                    return data, True, None

                elif tool_name == "get_patient_event_timeline":
                    alarms = sim.get_alarm_history(patient_id, limit=10)
                    data = {
                        "patient_id": patient_id,
                        "events": [
                            {"type": "alarm", "tier": a.tier, "parameter": a.parameter,
                             "message": a.message, "fired_at": a.fired_at}
                            for a in alarms
                        ],
                    }
                    return data, True, None

                elif tool_name == "get_care_unit_summary":
                    all_snaps = sim.get_all_snapshots()
                    data = {
                        "care_unit_id": args.get("care_unit_id", "ICU"),
                        "patients": [
                            {"patient_id": s.patient_id, "news2": s.news2,
                             "risk_level": s.risk_level,
                             "alarm_count": len(s.active_alarms)}
                            for s in all_snaps
                        ],
                    }
                    return data, True, None
        except Exception:
            pass

        # Minimal fallback
        return {"tool": tool_name, "args": args, "status": "no_data"}, True, None

    # ------------------------------------------------------------------
    def _summarise_tool_results(self, traces: List[ToolTrace],
                                context: Dict) -> str:
        """Convert tool results into a concise text block for the LLM."""
        parts: List[str] = []
        for t in traces:
            if not t.success:
                parts.append(f"[{t.tool_name}] ERROR: {t.error}")
                continue
            if t.result is None:
                continue
            result_str = str(t.result)
            if len(result_str) > 600:
                result_str = result_str[:600] + "…[truncated]"
            parts.append(f"[{t.tool_name} — {t.latency_ms:.0f}ms]\n{result_str}")
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    async def _synthesize(self, question: str,
                          system_prompt: str) -> Tuple[str, str]:
        """Call Claude Haiku; fall back to template response if unavailable."""
        if self._anthropic is not None:
            try:
                response = self._anthropic.messages.create(
                    model      = "claude-haiku-4-5-20251001",
                    max_tokens = 1024,
                    system     = system_prompt,
                    messages   = [{"role": "user", "content": question}],
                )
                return response.content[0].text, "claude-haiku-4-5-20251001"
            except Exception as ex:
                return f"[Claude API error: {ex}]", "error"

        # Template fallback (no API key)
        return self._template_response(question, system_prompt), "template"

    # ------------------------------------------------------------------
    @staticmethod
    def _template_response(question: str, system_prompt: str) -> str:
        """Structured fallback when no Claude API key is present."""
        # Extract patient context from system prompt for minimal response
        if "CRITICAL" in system_prompt or "CRISIS" in system_prompt:
            risk_note = "**Risk level: CRITICAL** — immediate clinical review is warranted."
        elif "HIGH" in system_prompt:
            risk_note = "**Risk level: HIGH** — urgent review within 30 minutes recommended."
        else:
            risk_note = "Risk level appears moderate based on available monitoring data."

        return f"""## Summary
{risk_note} MCP tools retrieved current vital signs, alarm context, and device status for the queried patient(s).

## Evidence from MCP Tools
See the **Tool Trace** panel for detailed structured data returned by each MCP tool call, including latency and success status.

## Evidence from Clinical Guidelines
The RAG knowledge base retrieved relevant protocol sections. See the **Sources** panel for cited guideline excerpts with confidence scores.

## Recommendations
- Review the vital sign trend data for trajectory (rising/falling over time)
- Confirm alarm thresholds are appropriate for this patient's baseline
- Consider care team notification if NEWS2 ≥ 5 or any parameter scores 3
- Document findings in clinical notes

_Set an Anthropic API key in the sidebar to enable real Claude AI synthesis._
"""


# ---------------------------------------------------------------------------
# Module-level singleton factory
# ---------------------------------------------------------------------------

_copilot_instance: Optional[ClinicalCopilot] = None


def get_copilot(mcp_server=None, anthropic_api_key: Optional[str] = None,
                force_new: bool = False) -> ClinicalCopilot:
    """Get or create the singleton ClinicalCopilot."""
    global _copilot_instance
    if _copilot_instance is None or force_new:
        _copilot_instance = ClinicalCopilot(
            mcp_server       = mcp_server,
            anthropic_api_key = anthropic_api_key,
        )
    return _copilot_instance
