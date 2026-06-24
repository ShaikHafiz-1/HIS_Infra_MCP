# Demo Script — Respiratory Deterioration Scenario

**Patient:** Carol Williams, F74 · ICU-1C · Admission Dx: COPD Exacerbation + Pneumonia  
**Scenario:** `respiratory_deterioration` — progressive SpO2 drop, rising RR, device offline  
**Duration:** ~10 minutes from normal to CRISIS alarm  
**Purpose:** Walk reviewers through the full MCP-RAG-AI pipeline end-to-end

---

## Pre-flight Setup

```bash
# Terminal 1 — Start the Streamlit platform
streamlit run enterprise_platform.py

# Browser — open http://localhost:8501
```

The patient simulator starts automatically. Initial vitals: HR=88, SpO2=96.5%, RR=16, NEWS2=2 (LOW risk).

---

## Step-by-Step Demo Walkthrough

### Step 1 — Establish baseline (0:00)

**Page:** Command Center

Point out the census heatmap — ICU-1C shows **Carol Williams** as LOW risk at simulator start.

- NEWS2 = 2 (normal range)
- SpO2 = 96.5%, HR = 88, RR = 16
- Draeger V500 ventilator: ONLINE

> _"This is our baseline. All patients are being streamed live via WebSocket — every 2 seconds, the simulator pushes new vitals and the platform recalculates NEWS2 in real-time."_

---

### Step 2 — SpO2 begins to drift (0:45)

**Page:** Patient Explorer → Carol Williams → Vitals tab

At ~45 seconds elapsed, the respiratory deterioration scenario begins:
- SpO2 drops ~1% every 90s (physiologically realistic desaturation rate)
- RR starts rising ~1 breath/min every 60s
- HR rises ~1 bpm every 45s (compensatory tachycardia)

The Vitals tab shows the trend chart starting to slope:

> _"Notice the SpO2 trend — it's not an abrupt change, it's a gradual 1% decline every 90 seconds. This mirrors real clinical COPD deterioration. The AI is watching this trajectory, not just point-in-time values."_

---

### Step 3 — Draeger V500 goes offline (1:00)

**Page:** Patient Explorer → Devices tab

At elapsed > 60s, the Draeger V500 ventilator loses connectivity (simulating probe disconnect or signal loss).

The Devices tab shows: **✖ OFFLINE: Draeger V500 Ventilator**

> _"A device disconnection alarm fires simultaneously. Now we have two concurrent issues: a deteriorating patient AND offline monitoring equipment. Is this a true desaturation or artefact from the probe disconnect? The AI Copilot can help us differentiate."_

---

### Step 4 — First WARNING alarm fires (~2:30)

**Page:** Command Center → Active Alarms panel

When SpO2 crosses below 90%, a **WARNING alarm** fires:
```
WARNING · SpO2 · Carol Williams · ICU-1C
SpO2=89.8% below warning threshold (90%). Check probe placement.
```

The census heatmap for ICU-1C changes from LOW to **MEDIUM** badge.

> _"The IEC 60601-1-8 WARNING alarm requires response within 60 seconds. The platform has already classified this as a WARNING tier, not CRISIS — because 89.8% is above the CRISIS threshold of 85%."_

---

### Step 5 — Clinical Intelligence finding card generated (~3:00)

**Page:** Clinical Intelligence

A **WARNING-tier finding card** appears with:
- AI finding: "SpO2 Warning — NEWS2=4 Trending"
- Confidence: 72%
- MCP tools called: `get_alarm_context`, `get_patient_clinical_context`, `get_device_events_by_patient`
- RAG sources: *Respiratory Protocol* → "SpO2 target ranges" section + *Device Troubleshooting* → "SpO2 probe displacement"

Expand the finding card to show the full evidence trail.

> _"Every finding shows its evidence chain: which MCP tools ran, what they returned, and which clinical guideline sections were retrieved from the RAG knowledge base. This is fully auditable — we can trace every AI recommendation back to a specific guideline."_

---

### Step 6 — AI Copilot — natural language query (~4:00)

**Page:** AI Copilot

Select patient context: **Carol Williams (PT-001)**

Type or click the suggestion: _"Why is Bed ICU-1C alarming?"_

Watch the right panel — MCP Tool Trace appears:
```
① get_patient_clinical_context  ✓  47ms
② get_alarm_context             ✓  31ms
③ get_device_events_by_patient  ✓  28ms
```

Then the RAG Sources panel populates:
```
📖 Respiratory Monitoring Protocol — SpO2 Target Ranges (score: 0.42, HIGH)
📖 Device Troubleshooting Guide — SpO2 Troubleshooting (score: 0.31, MEDIUM)
```

The AI response (template if no API key, Claude Haiku if configured):

> _"Notice the top of every response: 'Advisory Only — Not a Clinical Diagnosis.' The safety guardrails are hardcoded, not LLM-generated. Every response is framed as advisory. We can see the model used, total latency, confidence score, and the Audit ID that links this query to the HIPAA audit log."_

---

### Step 7 — CRISIS alarm fires (~6:00)

**Page:** Command Center

When SpO2 drops below 85% (approximately 6 minutes elapsed):
```
🔴 CRISIS · SpO2 · Carol Williams · ICU-1C
SpO2=84.7% — BELOW CRISIS THRESHOLD (85%). IMMEDIATE attention required.
```

The census heatmap for ICU-1C turns **CRITICAL** (red badge).

The Deterioration Predictions panel shows Carol at ~85% probability.

> _"A CRISIS alarm requires bedside response in ≤10 seconds per IEC 60601-1-8. The platform has escalated the risk level to CRITICAL. Watch the AI Copilot — it now prepends an immediate escalation note to any response about this patient."_

---

### Step 8 — Full AI Copilot response with CRISIS context (~6:30)

**Page:** AI Copilot

Ask: _"Is the SpO2 alarm likely real or artefact?"_

With CRISIS context, the AI response includes:
- Device offline context (Draeger V500) → suggests probe displacement is possible
- SpO2 trend data (steady 1%/90s decline over 6 minutes) → not abrupt like artefact
- RAG evidence from *Device Troubleshooting* (artefact is usually abrupt, not gradual)
- RAG evidence from *Respiratory Protocol* (COPD patients at risk of true desaturation)
- **Escalation note:** "🔴 Immediate escalation recommended — clinical risk indicators present."

> _"This is what MCP-RAG synthesis looks like in practice. The AI has access to real-time device status, alarm history, vital trends, AND clinical knowledge. It can offer an informed assessment that no single data source could provide alone."_

---

### Step 9 — Audit trail verification (~7:00)

**Page:** Compliance & Audit

Show the audit log table:
- Every MCP tool call logged with: timestamp, tool_name, clinician_id, patient_ids, success/failure, latency_ms
- The `copilot_query` tool shows the AI Copilot calls
- PHI fields are masked — patient names never appear in the audit log, only patient IDs
- Download the CSV for export

Compliance Score = 70% — 7/10 controls green, 2 amber (encryption/MFA for demo mode), 1 red (pen test required for production).

> _"Full HIPAA audit trail. Every data access is logged. PHI never enters the log — only patient IDs. The compliance dashboard shows exactly what's production-ready and what requires additional controls before going live."_

---

### Step 10 — MCP Operations observability (~8:00)

**Page:** MCP Operations

Show:
- Tool registry: all 10 tools with p50/p99 latencies
- Recent API calls table (matching what we just did)
- System health: all services green except FHIR (amber — 142ms, within SLA)
- WebSocket connections: 1 active

> _"This is the engineering view. Every tool call is tracked with latency percentiles. The platform is self-observing — you can see exactly which tools are hot, which are slow, and whether the backend is healthy. Production-grade observability out of the box."_

---

## Summary Talking Points

| Layer         | Technology                | What it does                                  |
|---------------|---------------------------|-----------------------------------------------|
| **Streaming** | WebSocket + Simulator     | Live vitals every 2s, 5 scenarios             |
| **MCP Tools** | FastAPI + 10 tools        | Structured clinical data retrieval            |
| **RAG**       | TF-IDF + 4 clinical docs  | Guideline-grounded evidence                   |
| **AI**        | Claude Haiku + guardrails | Advisory synthesis, never diagnosis           |
| **Safety**    | Hardcoded guardrails      | Advisory-only, human-in-the-loop              |
| **Audit**     | HIPAA JSONL log           | PHI masked, every call logged, 7yr retention  |
| **UI**        | Streamlit 6-page app      | Real-time, dark theme, MCP trace panel        |

**Architecture pattern:** Query → Intent classification → Parallel MCP tools → RAG retrieval → LLM synthesis → Safety guardrails → Audit log → Response

---

## Common Reviewer Questions

**"Is this real patient data?"**  
No. All patients are synthetic and generated by a physiological simulator. The simulator uses medically realistic ranges and scenario trajectories, but no real PHI is present anywhere in the codebase.

**"What happens if Claude is not available?"**  
The platform degrades gracefully. Without an API key, every AI Copilot response returns a structured template that still shows the MCP tool traces and RAG sources — the full evidence chain — with a note to configure an API key for Claude synthesis.

**"Can this integrate with a real EHR?"**  
Yes. The MCP tool architecture is designed for this. Replace the simulator mock data in each tool handler with FHIR R4 API calls to Epic, Cerner, or any HL7-compliant system. The tool interface contracts don't change — only the data sources behind them.

**"What's the NEWS2 score?"**  
National Early Warning Score 2 (Royal College of Physicians, 2017). A composite score of 6 vital sign parameters. Score ≥5 = high clinical risk requiring urgent response. The platform calculates it in real-time for all patients.
