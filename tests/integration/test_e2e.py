"""
End-to-end integration tests for the Hospital MCP Platform.

Tests complete data flows: data creation → tool retrieval → validation.
Uses in-memory SQLite database via the shared conftest.py fixtures.
"""

import pytest
from datetime import datetime, timezone

from mcp_server.tools.patient_context import PatientContextTool
from mcp_server.tools.event_timeline import EventTimelineTool
from mcp_server.tools.alarm_context import AlarmContextTool
from mcp_server.tools.device_events import DeviceEventsTool
from mcp_server.tools.care_unit_summary import CareUnitSummaryTool
from mcp_server.tools.diagnostic_exam import DiagnosticExamTool
from mcp_server.tools.imaging_summary import ImagingStudySummaryTool
from mcp_server.tools.anesthesia_context import AnesthesiaCaseTool
from mcp_server.tools.neuro_context import NeuroEventTool
from mcp_server.tools.cardiology_context import CardiologyEventTool
from mcp_server.database.models import Patient, Encounter, CareUnit, Device
from mcp_server.utils.validators import ValidationError


# ---------------------------------------------------------------------------
# Local fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def e2e_patient(db_session):
    """Create a patient with encounter and care unit for e2e tests."""
    care_unit = CareUnit(
        id="e2e-cu-001", name="E2E ICU", code="E2E",
        unit_type="intensive_care", is_active=True,
    )
    patient = Patient(
        id="e2e-pat-001", first_name="Jane", last_name="Doe",
        mrn="E2E-MRN-001", is_active=True,
    )
    encounter = Encounter(
        id="e2e-enc-001", patient_id="e2e-pat-001", care_unit_id="e2e-cu-001",
        encounter_type="inpatient",
        admission_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
        is_active=True,
    )
    db_session.add_all([care_unit, patient, encounter])
    await db_session.commit()
    return {"patient": patient, "encounter": encounter, "care_unit": care_unit}


@pytest.fixture
async def two_e2e_patients(db_session):
    """Create two patients in the same care unit."""
    care_unit = CareUnit(
        id="e2e-cu-multi-001", name="E2E Multi ICU", code="EMULTI",
        unit_type="intensive_care", is_active=True,
    )
    patient_a = Patient(
        id="e2e-pat-a-001", first_name="Alice", last_name="Smith",
        mrn="E2E-MRN-A01", is_active=True,
    )
    patient_b = Patient(
        id="e2e-pat-b-001", first_name="Bob", last_name="Jones",
        mrn="E2E-MRN-B01", is_active=True,
    )
    enc_a = Encounter(
        id="e2e-enc-a-001", patient_id="e2e-pat-a-001",
        care_unit_id="e2e-cu-multi-001", encounter_type="inpatient",
        admission_time=datetime(2024, 2, 1, tzinfo=timezone.utc), is_active=True,
    )
    enc_b = Encounter(
        id="e2e-enc-b-001", patient_id="e2e-pat-b-001",
        care_unit_id="e2e-cu-multi-001", encounter_type="inpatient",
        admission_time=datetime(2024, 2, 2, tzinfo=timezone.utc), is_active=True,
    )
    db_session.add_all([care_unit, patient_a, patient_b, enc_a, enc_b])
    await db_session.commit()
    return {
        "care_unit": care_unit,
        "patient_a": patient_a,
        "patient_b": patient_b,
    }


# ---------------------------------------------------------------------------
# TestCompletePatientWorkflow
# ---------------------------------------------------------------------------

class TestCompletePatientWorkflow:
    """Tests full patient data lifecycle across multiple tools."""

    @pytest.mark.asyncio
    async def test_patient_context_then_timeline_consistent(self, db_session, e2e_patient):
        """Patient ID returned by clinical context and timeline must match."""
        patient_id = e2e_patient["patient"].id

        context = await PatientContextTool.get_patient_clinical_context(
            session=db_session, patient_id=patient_id,
        )
        timeline = await EventTimelineTool.get_patient_event_timeline(
            session=db_session, patient_id=patient_id,
        )

        assert context["patient"]["id"] == patient_id
        assert timeline["patient_id"] == patient_id

    @pytest.mark.asyncio
    async def test_device_events_and_alarm_context_for_same_patient(
        self, db_session, e2e_patient
    ):
        """Device events and alarm context both reference the same patient."""
        patient_id = e2e_patient["patient"].id

        device_resp = await DeviceEventsTool.get_device_events_by_patient(
            session=db_session, patient_id=patient_id,
        )
        alarm_resp = await AlarmContextTool.get_alarm_context(
            session=db_session, patient_id=patient_id,
        )

        assert device_resp["patient_id"] == patient_id
        assert alarm_resp["patient"]["id"] == patient_id

    @pytest.mark.asyncio
    async def test_care_unit_summary_includes_active_patients(
        self, db_session, two_e2e_patients
    ):
        """Care unit summary must include both active patients in the unit."""
        care_unit_id = two_e2e_patients["care_unit"].id
        summary = await CareUnitSummaryTool.get_care_unit_summary(
            session=db_session, care_unit_id=care_unit_id,
        )
        assert summary["patient_count"] >= 2


# ---------------------------------------------------------------------------
# TestToolInputValidation
# ---------------------------------------------------------------------------

class TestToolInputValidation:
    """Tests validation enforcement across tools."""

    @pytest.mark.asyncio
    async def test_empty_string_patient_id_raises_context(self, db_session):
        with pytest.raises((ValidationError, Exception)):
            await PatientContextTool.get_patient_clinical_context(
                session=db_session, patient_id=""
            )

    @pytest.mark.asyncio
    async def test_empty_string_patient_id_raises_timeline(self, db_session):
        with pytest.raises((ValidationError, Exception)):
            await EventTimelineTool.get_patient_event_timeline(
                session=db_session, patient_id=""
            )

    @pytest.mark.asyncio
    async def test_empty_string_patient_id_raises_device_events(self, db_session):
        with pytest.raises((ValidationError, Exception)):
            await DeviceEventsTool.get_device_events_by_patient(
                session=db_session, patient_id=""
            )

    @pytest.mark.asyncio
    async def test_whitespace_patient_id_rejected_context(self, db_session):
        with pytest.raises(ValidationError):
            await PatientContextTool.get_patient_clinical_context(
                session=db_session, patient_id="   "
            )

    @pytest.mark.asyncio
    async def test_whitespace_patient_id_rejected_device_events(self, db_session):
        with pytest.raises((ValidationError, Exception)):
            await DeviceEventsTool.get_device_events_by_patient(
                session=db_session, patient_id="   "
            )

    @pytest.mark.asyncio
    async def test_very_long_patient_id_rejected_context(self, db_session):
        with pytest.raises(ValidationError):
            await PatientContextTool.get_patient_clinical_context(
                session=db_session, patient_id="x" * 300
            )

    @pytest.mark.asyncio
    async def test_nonexistent_patient_raises_validation_context(self, db_session):
        """Non-existent patient raises ValidationError (patient not found)."""
        with pytest.raises(ValidationError):
            await PatientContextTool.get_patient_clinical_context(
                session=db_session, patient_id="nonexistent-999"
            )

    @pytest.mark.asyncio
    async def test_nonexistent_patient_raises_validation_timeline(self, db_session):
        """Non-existent patient raises ValidationError (patient not found)."""
        with pytest.raises(ValidationError):
            await EventTimelineTool.get_patient_event_timeline(
                session=db_session, patient_id="nonexistent-999"
            )

    @pytest.mark.asyncio
    async def test_all_tools_accept_valid_patient_id(self, db_session, e2e_patient):
        """All tools accept a valid patient_id and return successful responses."""
        patient_id = e2e_patient["patient"].id

        context = await PatientContextTool.get_patient_clinical_context(
            session=db_session, patient_id=patient_id
        )
        assert "patient" in context

        timeline = await EventTimelineTool.get_patient_event_timeline(
            session=db_session, patient_id=patient_id
        )
        assert "patient_id" in timeline

        device_resp = await DeviceEventsTool.get_device_events_by_patient(
            session=db_session, patient_id=patient_id
        )
        assert "patient_id" in device_resp

        alarm_resp = await AlarmContextTool.get_alarm_context(
            session=db_session, patient_id=patient_id
        )
        assert "alarm" in alarm_resp

        diag_resp = await DiagnosticExamTool.get_diagnostic_exam_context(
            session=db_session, patient_id=patient_id
        )
        assert "exam" in diag_resp

        imaging_resp = await ImagingStudySummaryTool.get_imaging_study_summary(
            session=db_session, patient_id=patient_id
        )
        assert "study" in imaging_resp

        anesthesia_resp = await AnesthesiaCaseTool.get_anesthesia_case_context(
            session=db_session, patient_id=patient_id
        )
        assert "case" in anesthesia_resp

        neuro_resp = await NeuroEventTool.get_neuro_event_context(
            session=db_session, patient_id=patient_id
        )
        assert "seizure_events" in neuro_resp

        cardio_resp = await CardiologyEventTool.get_cardiology_event_context(
            session=db_session, patient_id=patient_id
        )
        assert "ecg_events" in cardio_resp


# ---------------------------------------------------------------------------
# TestDataConsistency
# ---------------------------------------------------------------------------

class TestDataConsistency:
    """Tests data consistency and structural guarantees across tool responses."""

    @pytest.mark.asyncio
    async def test_confidence_score_always_in_range(self, db_session, e2e_patient):
        """Patient context confidence_score must be between 0 and 1 inclusive."""
        patient_id = e2e_patient["patient"].id
        context = await PatientContextTool.get_patient_clinical_context(
            session=db_session, patient_id=patient_id
        )
        score = context.get("confidence_score")
        assert score is not None
        assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_source_references_always_present_context(self, db_session, e2e_patient):
        """Patient context must always contain a source_references list."""
        patient_id = e2e_patient["patient"].id
        context = await PatientContextTool.get_patient_clinical_context(
            session=db_session, patient_id=patient_id
        )
        assert "source_references" in context
        assert isinstance(context["source_references"], list)

    @pytest.mark.asyncio
    async def test_source_references_always_present_timeline(self, db_session, e2e_patient):
        """Event timeline must always contain a source_references list."""
        patient_id = e2e_patient["patient"].id
        timeline = await EventTimelineTool.get_patient_event_timeline(
            session=db_session, patient_id=patient_id
        )
        assert "source_references" in timeline
        assert isinstance(timeline["source_references"], list)

    @pytest.mark.asyncio
    async def test_timeline_events_have_timestamps(self, db_session, e2e_patient):
        """All events in the timeline must have a timestamp field."""
        patient_id = e2e_patient["patient"].id
        timeline_resp = await EventTimelineTool.get_patient_event_timeline(
            session=db_session, patient_id=patient_id
        )
        events = timeline_resp.get("timeline", [])
        for event in events:
            assert "timestamp" in event

    @pytest.mark.asyncio
    async def test_timeline_always_chronological(self, db_session, e2e_patient):
        """Timeline events must be sorted in ascending chronological order."""
        patient_id = e2e_patient["patient"].id
        timeline_resp = await EventTimelineTool.get_patient_event_timeline(
            session=db_session, patient_id=patient_id
        )
        events = timeline_resp.get("timeline", [])
        if len(events) < 2:
            pytest.skip("Not enough events to check ordering")
        timestamps = [event["timestamp"] for event in events]
        assert timestamps == sorted(timestamps)

    @pytest.mark.asyncio
    async def test_tool_responses_are_deterministic(self, db_session, e2e_patient):
        """Calling patient context twice must return structurally identical responses."""
        patient_id = e2e_patient["patient"].id
        resp1 = await PatientContextTool.get_patient_clinical_context(
            session=db_session, patient_id=patient_id
        )
        resp2 = await PatientContextTool.get_patient_clinical_context(
            session=db_session, patient_id=patient_id
        )
        assert set(resp1.keys()) == set(resp2.keys())


# ---------------------------------------------------------------------------
# TestMultiplePatientIsolation
# ---------------------------------------------------------------------------

class TestMultiplePatientIsolation:
    """Tests that patient data remains isolated between patients."""

    @pytest.mark.asyncio
    async def test_different_patients_different_contexts(
        self, db_session, two_e2e_patients
    ):
        """Clinical context for patient A must not contain patient B's ID."""
        id_a = two_e2e_patients["patient_a"].id
        id_b = two_e2e_patients["patient_b"].id

        context_a = await PatientContextTool.get_patient_clinical_context(
            session=db_session, patient_id=id_a
        )
        assert context_a["patient"]["id"] == id_a
        assert context_a["patient"]["id"] != id_b

    @pytest.mark.asyncio
    async def test_care_unit_only_shows_assigned_patients(self, db_session):
        """Care unit summary must only include patients assigned to that unit."""
        cu_a = CareUnit(
            id="iso-cu-a-001", name="Isolation Unit A", code="ISOA",
            unit_type="general_ward", is_active=True,
        )
        cu_b = CareUnit(
            id="iso-cu-b-001", name="Isolation Unit B", code="ISOB",
            unit_type="general_ward", is_active=True,
        )
        pat_a = Patient(
            id="iso-pat-a-001", first_name="Isolated", last_name="Alpha",
            mrn="ISO-MRN-A001", is_active=True,
        )
        pat_b = Patient(
            id="iso-pat-b-001", first_name="Isolated", last_name="Beta",
            mrn="ISO-MRN-B001", is_active=True,
        )
        enc_a = Encounter(
            id="iso-enc-a-001", patient_id="iso-pat-a-001",
            care_unit_id="iso-cu-a-001", encounter_type="inpatient",
            admission_time=datetime(2024, 3, 1, tzinfo=timezone.utc), is_active=True,
        )
        enc_b = Encounter(
            id="iso-enc-b-001", patient_id="iso-pat-b-001",
            care_unit_id="iso-cu-b-001", encounter_type="inpatient",
            admission_time=datetime(2024, 3, 2, tzinfo=timezone.utc), is_active=True,
        )
        db_session.add_all([cu_a, cu_b, pat_a, pat_b, enc_a, enc_b])
        await db_session.commit()

        summary_a = await CareUnitSummaryTool.get_care_unit_summary(
            session=db_session, care_unit_id="iso-cu-a-001"
        )
        patient_ids_in_a = [p["patient_id"] for p in summary_a["active_patients"]]
        assert "iso-pat-a-001" in patient_ids_in_a
        assert "iso-pat-b-001" not in patient_ids_in_a
