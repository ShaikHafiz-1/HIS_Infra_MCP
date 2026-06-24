"""
Integration tests for the AI Copilot workflow orchestrator.

Tests cover:
- Intent classification (tool selection from natural language)
- Tool execution with simulator mock data
- RAG retrieval integration
- Safety guardrail application
- Confidence scoring
- CopilotResponse structure and field contracts
- Audit ID generation
- Singleton factory behaviour
- Template fallback when no API key
"""

import asyncio
import math
import pytest

from mcp_server.copilot.workflow import (
    ClinicalCopilot,
    CopilotResponse,
    ToolTrace,
    RAGSource,
    get_copilot,
    _classify_tools,
    _apply_guardrails,
    _confidence_from_rag_and_tools,
    _build_args,
)


# ── Helpers ───────────────────────────────────────────────────────────────

def run(coro):
    """Run a coroutine in tests that can't be async."""
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture(scope="module")
def copilot():
    """Copilot without Anthropic key — uses template fallback."""
    return ClinicalCopilot(mcp_server=None, anthropic_api_key=None)


@pytest.fixture(scope="module")
def pt001_context():
    return {
        "patient_id": "PT-001",
        "care_unit_id": "ICU",
        "elapsed_seconds": 120,
    }


# ── Intent classification ─────────────────────────────────────────────────

class TestIntentClassification:
    def test_alarm_question_selects_alarm_tool(self):
        calls = _classify_tools("Why is Bed ICU-1C alarming?", {"patient_id": "PT-001"})
        tool_names = [t for t, _ in calls]
        assert any("alarm" in t for t in tool_names), \
            f"Expected alarm tool, got: {tool_names}"

    def test_patient_question_selects_context_tool(self):
        calls = _classify_tools("Who is patient PT-002?", {"patient_id": "PT-002"})
        tool_names = [t for t, _ in calls]
        assert "get_patient_clinical_context" in tool_names

    def test_device_question_selects_device_tool(self):
        calls = _classify_tools("The ventilator has gone offline", {"patient_id": "PT-001"})
        tool_names = [t for t, _ in calls]
        assert any("device" in t for t in tool_names)

    def test_timeline_question_selects_timeline_tool(self):
        calls = _classify_tools("What happened in the last 30 minutes?", {"patient_id": "PT-001"})
        tool_names = [t for t, _ in calls]
        assert any("timeline" in t or "event" in t for t in tool_names)

    def test_cardiac_question_selects_cardiology_tool(self):
        calls = _classify_tools("Is this ECG showing arrhythmia?", {"patient_id": "PT-003"})
        tool_names = [t for t, _ in calls]
        assert any("cardiology" in t or "alarm" in t for t in tool_names)

    def test_max_four_tools_selected(self):
        calls = _classify_tools(
            "alarm device timeline patient cardiac ECG arrhythmia",
            {"patient_id": "PT-001"}
        )
        assert len(calls) <= 4

    def test_patient_id_in_context_adds_context_tool(self):
        calls = _classify_tools("What is going on with this patient?",
                                 {"patient_id": "PT-002"})
        tool_names = [t for t, _ in calls]
        assert "get_patient_clinical_context" in tool_names

    def test_no_match_defaults_to_care_unit_summary(self):
        calls = _classify_tools("randomxyzqwerty", {})
        tool_names = [t for t, _ in calls]
        assert "get_care_unit_summary" in tool_names


# ── Argument builder ─────────────────────────────────────────────────────

class TestArgBuilder:
    def test_patient_context_args_include_patient_id(self):
        args = _build_args("get_patient_clinical_context", "",
                           {"patient_id": "PT-005"})
        assert args["patient_id"] == "PT-005"

    def test_care_unit_args_use_context_unit(self):
        args = _build_args("get_care_unit_summary", "",
                           {"care_unit_id": "NEURO-2"})
        assert args["care_unit_id"] == "NEURO-2"

    def test_alarm_args_include_alarm_id(self):
        args = _build_args("get_alarm_context", "",
                           {"patient_id": "PT-001", "alarm_id": "ALM-999"})
        assert args.get("alarm_id") == "ALM-999"


# ── Safety guardrails ─────────────────────────────────────────────────────

class TestSafetyGuardrails:
    def test_advisory_prefix_added(self):
        text, flags = _apply_guardrails("The patient is stable.")
        assert "Advisory Only" in text or "advisory only" in text.lower()

    def test_diagnosis_language_flagged(self):
        text, flags = _apply_guardrails("You have sepsis. The diagnosis is confirmed.")
        assert any("iagnosis" in f for f in flags), f"Expected diagnosis flag, got: {flags}"

    def test_order_language_flagged(self):
        text, flags = _apply_guardrails("Give the patient 1L NS now.")
        assert any("rder" in f or "order" in f.lower() for f in flags), \
            f"Expected order flag, got: {flags}"

    def test_safe_text_not_double_prefixed(self):
        # Already prefixed text should not get a second advisory prefix
        pre_prefixed = "⚠️ **Advisory Only — Not a Clinical Diagnosis or Treatment Order**\nSome text."
        text, _ = _apply_guardrails(pre_prefixed)
        count = text.lower().count("advisory only")
        assert count <= 1, f"Advisory prefix added twice (count={count})"

    def test_returns_tuple_of_str_and_list(self):
        result = _apply_guardrails("Patient vitals are stable.")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], list)


# ── Confidence scoring ────────────────────────────────────────────────────

class TestConfidenceScoring:
    def _make_tools(self, successes):
        return [ToolTrace(
            tool_name="t", arguments={}, result={},
            latency_ms=10, success=s
        ) for s in successes]

    def _make_rag(self, scores):
        return [RAGSource(
            source_file="f", title="T", section="S",
            snippet="x", score=sc, confidence="medium", chunk_id="c"
        ) for sc in scores]

    def test_all_tools_succeeded_raises_confidence(self):
        tools = self._make_tools([True, True, True])
        conf, _ = _confidence_from_rag_and_tools([], tools)
        assert conf > 0.5

    def test_all_tools_failed_lowers_confidence(self):
        tools = self._make_tools([False, False, False])
        conf, _ = _confidence_from_rag_and_tools([], tools)
        assert conf < 0.5

    def test_high_rag_scores_raise_confidence(self):
        tools = self._make_tools([True])
        rag   = self._make_rag([0.8, 0.7])
        conf, tier = _confidence_from_rag_and_tools(rag, tools)
        assert tier == "high"

    def test_low_rag_scores_lower_tier(self):
        tools = self._make_tools([False])
        rag   = self._make_rag([0.05, 0.04])
        conf, tier = _confidence_from_rag_and_tools(rag, tools)
        assert tier in ("low", "medium")

    def test_confidence_never_reaches_100_percent(self):
        tools = self._make_tools([True, True, True, True])
        rag   = self._make_rag([0.99, 0.99, 0.99])
        conf, _ = _confidence_from_rag_and_tools(rag, tools)
        assert conf < 1.0


# ── Full pipeline: CopilotResponse ───────────────────────────────────────

class TestCopilotResponse:
    def test_answer_returns_copilot_response(self, copilot, pt001_context):
        resp = run(copilot.answer(
            question="Why is Bed ICU-1C alarming?",
            context=pt001_context,
        ))
        assert isinstance(resp, CopilotResponse)

    def test_answer_field_is_nonempty_string(self, copilot, pt001_context):
        resp = run(copilot.answer(
            question="Summarize the ICU high-risk patients.",
            context=pt001_context,
        ))
        assert isinstance(resp.answer, str)
        assert len(resp.answer) > 10

    def test_tool_traces_is_list(self, copilot, pt001_context):
        resp = run(copilot.answer(
            question="What device events occurred for PT-001?",
            context=pt001_context,
        ))
        assert isinstance(resp.tool_traces, list)

    def test_tool_traces_have_required_fields(self, copilot, pt001_context):
        resp = run(copilot.answer(
            question="Is the alarm real or artefact?",
            context=pt001_context,
        ))
        for t in resp.tool_traces:
            assert isinstance(t.tool_name, str)
            assert isinstance(t.latency_ms, float)
            assert isinstance(t.success, bool)

    def test_rag_sources_is_list(self, copilot, pt001_context):
        resp = run(copilot.answer(
            question="What protocol applies to sepsis?",
            context=pt001_context,
        ))
        assert isinstance(resp.rag_sources, list)

    def test_rag_sources_have_required_fields(self, copilot, pt001_context):
        resp = run(copilot.answer(
            question="SpO2 alarm threshold respiratory protocol",
            context=pt001_context,
        ))
        for r in resp.rag_sources:
            assert r.title
            assert r.snippet
            assert 0.0 <= r.score <= 1.0
            assert r.confidence in ("high", "medium", "low")

    def test_audit_id_is_set(self, copilot, pt001_context):
        resp = run(copilot.answer(
            question="Show me patient PT-001 context",
            context=pt001_context,
        ))
        assert resp.audit_id.startswith("AUD-")
        assert len(resp.audit_id) > 5

    def test_confidence_in_valid_range(self, copilot, pt001_context):
        resp = run(copilot.answer(
            question="Which patients are deteriorating?",
            context=pt001_context,
        ))
        assert 0.0 <= resp.confidence <= 1.0

    def test_confidence_tier_is_valid(self, copilot, pt001_context):
        resp = run(copilot.answer(
            question="NEWS2 score alarm",
            context=pt001_context,
        ))
        assert resp.confidence_tier in ("high", "medium", "low")

    def test_total_ms_is_positive(self, copilot, pt001_context):
        resp = run(copilot.answer(
            question="What changed in the last 30 minutes?",
            context=pt001_context,
        ))
        assert resp.total_ms > 0

    def test_model_used_is_set(self, copilot, pt001_context):
        resp = run(copilot.answer(
            question="Summarize",
            context=pt001_context,
        ))
        assert resp.model_used  # non-empty string

    def test_safety_flags_is_list(self, copilot, pt001_context):
        resp = run(copilot.answer(
            question="NEWS2 alarm vitals",
            context=pt001_context,
        ))
        assert isinstance(resp.safety_flags, list)

    def test_escalation_note_is_string(self, copilot, pt001_context):
        resp = run(copilot.answer(
            question="Is this critical?",
            context=pt001_context,
        ))
        assert isinstance(resp.escalation_note, str)
        assert len(resp.escalation_note) > 0

    def test_template_model_used_without_api_key(self, copilot, pt001_context):
        """Without API key, model_used should be 'template'."""
        resp = run(copilot.answer(
            question="Generic question",
            context=pt001_context,
        ))
        assert resp.model_used == "template"

    def test_no_patient_id_still_succeeds(self, copilot):
        resp = run(copilot.answer(
            question="Summarize all ICU patients",
            context={"care_unit_id": "ICU"},
        ))
        assert isinstance(resp, CopilotResponse)

    def test_empty_question_does_not_raise(self, copilot, pt001_context):
        try:
            resp = run(copilot.answer(
                question="",
                context=pt001_context,
            ))
            assert isinstance(resp, CopilotResponse)
        except Exception as ex:
            pytest.fail(f"Empty question raised: {ex}")


# ── Mock tool data accuracy ───────────────────────────────────────────────

class TestMockToolData:
    def test_patient_context_tool_returns_real_simulator_data(self, copilot):
        """When simulator is running, mock tool should return real patient name."""
        import time
        time.sleep(2.5)  # ensure at least one simulator tick

        result, success, error = copilot._mock_tool(
            "get_patient_clinical_context", {"patient_id": "PT-001"}
        )
        assert success is True
        if isinstance(result, dict) and "name" in result:
            assert result["name"] == "Carol Williams"

    def test_alarm_context_tool_returns_active_alarms(self, copilot):
        result, success, _ = copilot._mock_tool(
            "get_alarm_context", {"patient_id": "PT-001"}
        )
        assert success is True
        if isinstance(result, dict):
            assert "active_alarms" in result
            assert isinstance(result["active_alarms"], list)

    def test_device_tool_returns_device_lists(self, copilot):
        result, success, _ = copilot._mock_tool(
            "get_device_events_by_patient", {"patient_id": "PT-001"}
        )
        assert success is True
        if isinstance(result, dict):
            assert "devices_online" in result or "event_count" in result

    def test_care_unit_summary_returns_patient_list(self, copilot):
        result, success, _ = copilot._mock_tool(
            "get_care_unit_summary", {"care_unit_id": "ICU"}
        )
        assert success is True
        if isinstance(result, dict):
            assert "patients" in result


# ── Singleton factory ─────────────────────────────────────────────────────

class TestCopilotSingleton:
    def test_get_copilot_returns_instance(self):
        c = get_copilot()
        assert isinstance(c, ClinicalCopilot)

    def test_same_instance_returned_without_force_new(self):
        c1 = get_copilot()
        c2 = get_copilot()
        assert c1 is c2

    def test_force_new_returns_different_instance(self):
        c1 = get_copilot()
        c2 = get_copilot(force_new=True)
        assert c1 is not c2
