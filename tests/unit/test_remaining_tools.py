"""
Unit tests for the 7 remaining MCP tools:
- get_patient_event_timeline
- get_alarm_context
- get_diagnostic_exam_context
- get_imaging_study_summary
- get_anesthesia_case_context
- get_neuro_event_context
- get_cardiology_event_context
"""

import pytest
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.database.models import Patient, Encounter, CareUnit, Device, Clinician, ClinicianAssignment
from mcp_server.tools.event_timeline import EventTimelineTool
from mcp_server.tools.alarm_context import AlarmContextTool
from mcp_server.tools.diagnostic_exam import DiagnosticExamTool
from mcp_server.tools.imaging_summary import ImagingStudySummaryTool
from mcp_server.tools.anesthesia_context import AnesthesiaCaseTool
from mcp_server.tools.neuro_context import NeuroEventTool
from mcp_server.tools.cardiology_context import CardiologyEventTool
from mcp_server.utils.validators import ValidationError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def patient_with_data(db_session: AsyncSession):
    """Create a patient with encounter, care unit, clinician, and device."""
    care_unit = CareUnit(
        id="cu-test-001", name="ICU", code="ICU",
        description="Intensive Care Unit", location="Floor 2",
        unit_type="critical_care", is_active=True,
    )
    db_session.add(care_unit)

    patient = Patient(
        id="pat-test-001", first_name="Test", last_name="Patient",
        date_of_birth=datetime(1970, 6, 15, tzinfo=timezone.utc),
        gender="M", mrn="MRN-TEST-001", is_active=True,
    )
    db_session.add(patient)

    encounter = Encounter(
        id="enc-test-001", patient_id="pat-test-001", care_unit_id="cu-test-001",
        encounter_type="inpatient",
        admission_time=datetime(2024, 3, 1, 8, 0, 0, tzinfo=timezone.utc),
        is_active=True,
        chief_complaint="Chest pain",
        admission_diagnosis="ACS",
    )
    db_session.add(encounter)

    device = Device(
        id="dev-test-001", encounter_id="enc-test-001",
        device_type="cardiac_monitor", device_name="Philips Monitor",
        serial_number="SN-TEST-001", manufacturer="Philips", model="MP70",
        location="ICU Bed 3", is_online=True,
        battery_level=90.0, calibration_status="calibrated", is_active=True,
    )
    db_session.add(device)

    await db_session.commit()
    return patient, encounter, care_unit, device


# ---------------------------------------------------------------------------
# EventTimelineTool
# ---------------------------------------------------------------------------

class TestEventTimelineTool:

    @pytest.mark.asyncio
    async def test_get_timeline_success(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await EventTimelineTool.get_patient_event_timeline(
            session=db_session, patient_id=patient.id
        )
        assert result["patient_id"] == patient.id
        assert "timeline" in result
        assert isinstance(result["timeline"], list)
        assert "event_count" in result
        assert result["event_count"] >= 0

    @pytest.mark.asyncio
    async def test_get_timeline_required_fields(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await EventTimelineTool.get_patient_event_timeline(
            session=db_session, patient_id=patient.id
        )
        assert "patient_id" in result
        assert "mrn" in result
        assert "full_name" in result
        assert "time_window" in result
        assert "timeline" in result
        assert "event_type_counts" in result
        assert "confidence_score" in result
        assert "source_references" in result

    @pytest.mark.asyncio
    async def test_get_timeline_invalid_patient(self, db_session):
        with pytest.raises(ValidationError, match="Patient not found"):
            await EventTimelineTool.get_patient_event_timeline(
                session=db_session, patient_id="nonexistent"
            )

    @pytest.mark.asyncio
    async def test_get_timeline_invalid_patient_id(self, db_session):
        with pytest.raises(ValidationError):
            await EventTimelineTool.get_patient_event_timeline(
                session=db_session, patient_id=""
            )

    @pytest.mark.asyncio
    async def test_get_timeline_with_time_window(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        now = datetime.now(timezone.utc)
        start = (now - timedelta(hours=12)).isoformat()
        end = now.isoformat()
        result = await EventTimelineTool.get_patient_event_timeline(
            session=db_session, patient_id=patient.id,
            start_time=start, end_time=end
        )
        assert result["patient_id"] == patient.id

    @pytest.mark.asyncio
    async def test_get_timeline_invalid_time_window(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError, match="start_time must be before end_time"):
            await EventTimelineTool.get_patient_event_timeline(
                session=db_session, patient_id=patient.id,
                start_time=now.isoformat(),
                end_time=(now - timedelta(hours=1)).isoformat()
            )

    @pytest.mark.asyncio
    async def test_timeline_entries_sorted(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await EventTimelineTool.get_patient_event_timeline(
            session=db_session, patient_id=patient.id
        )
        timestamps = [e["timestamp"] for e in result["timeline"] if e["timestamp"]]
        assert timestamps == sorted(timestamps)

    @pytest.mark.asyncio
    async def test_timeline_confidence_score_range(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await EventTimelineTool.get_patient_event_timeline(
            session=db_session, patient_id=patient.id
        )
        assert 0.0 <= result["confidence_score"] <= 1.0


# ---------------------------------------------------------------------------
# AlarmContextTool
# ---------------------------------------------------------------------------

class TestAlarmContextTool:

    @pytest.mark.asyncio
    async def test_get_alarm_context_by_patient(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await AlarmContextTool.get_alarm_context(
            session=db_session, patient_id=patient.id
        )
        assert result["patient"]["id"] == patient.id
        assert "alarm" in result
        assert "vitals_before_alarm" in result
        assert "vitals_during_alarm" in result
        assert "vitals_after_alarm" in result

    @pytest.mark.asyncio
    async def test_get_alarm_context_by_alarm_id(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await AlarmContextTool.get_alarm_context(
            session=db_session, alarm_id="alarm-test-001"
        )
        assert "alarm" in result
        assert result["alarm"]["alarm_id"] == "alarm-test-001"

    @pytest.mark.asyncio
    async def test_get_alarm_context_no_params(self, db_session):
        with pytest.raises(ValidationError, match="Either alarm_id or patient_id is required"):
            await AlarmContextTool.get_alarm_context(session=db_session)

    @pytest.mark.asyncio
    async def test_get_alarm_context_invalid_patient(self, db_session):
        with pytest.raises(ValidationError):
            await AlarmContextTool.get_alarm_context(session=db_session, patient_id="nonexistent")

    @pytest.mark.asyncio
    async def test_get_alarm_context_required_fields(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await AlarmContextTool.get_alarm_context(session=db_session, patient_id=patient.id)
        required = ["alarm", "clinical_significance", "annotations", "patient",
                    "vitals_before_alarm", "vitals_during_alarm", "vitals_after_alarm",
                    "diagnoses", "medications", "confidence_score", "source_references"]
        for field in required:
            assert field in result, f"Missing required field: {field}"

    @pytest.mark.asyncio
    async def test_alarm_confidence_score_range(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await AlarmContextTool.get_alarm_context(session=db_session, patient_id=patient.id)
        assert 0.0 <= result["confidence_score"] <= 1.0


# ---------------------------------------------------------------------------
# DiagnosticExamTool
# ---------------------------------------------------------------------------

class TestDiagnosticExamTool:

    @pytest.mark.asyncio
    async def test_get_exam_context_by_patient(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await DiagnosticExamTool.get_diagnostic_exam_context(
            session=db_session, patient_id=patient.id
        )
        assert result["patient"]["id"] == patient.id
        assert "exam" in result
        assert "imaging_studies" in result
        assert "lab_results" in result

    @pytest.mark.asyncio
    async def test_get_exam_context_by_exam_id(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await DiagnosticExamTool.get_diagnostic_exam_context(
            session=db_session, exam_id="exam-test-001"
        )
        assert "exam" in result
        assert result["exam"]["exam_id"] == "exam-test-001"

    @pytest.mark.asyncio
    async def test_get_exam_context_no_params(self, db_session):
        with pytest.raises(ValidationError, match="Either exam_id or patient_id is required"):
            await DiagnosticExamTool.get_diagnostic_exam_context(session=db_session)

    @pytest.mark.asyncio
    async def test_get_exam_context_invalid_patient(self, db_session):
        with pytest.raises(ValidationError):
            await DiagnosticExamTool.get_diagnostic_exam_context(
                session=db_session, patient_id="nonexistent"
            )

    @pytest.mark.asyncio
    async def test_exam_required_fields(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await DiagnosticExamTool.get_diagnostic_exam_context(
            session=db_session, patient_id=patient.id
        )
        required = ["exam", "imaging_studies", "lab_results", "contemporaneous_vitals",
                    "related_events", "indication", "patient", "confidence_score", "source_references"]
        for field in required:
            assert field in result

    @pytest.mark.asyncio
    async def test_lab_results_have_reference_ranges(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await DiagnosticExamTool.get_diagnostic_exam_context(
            session=db_session, patient_id=patient.id
        )
        for lab in result["lab_results"]:
            assert "test_name" in lab
            assert "value" in lab
            assert "reference_range" in lab
            assert "is_abnormal" in lab


# ---------------------------------------------------------------------------
# ImagingStudySummaryTool
# ---------------------------------------------------------------------------

class TestImagingStudySummaryTool:

    @pytest.mark.asyncio
    async def test_get_imaging_summary_by_patient(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await ImagingStudySummaryTool.get_imaging_study_summary(
            session=db_session, patient_id=patient.id
        )
        assert result["patient"]["id"] == patient.id
        assert "study" in result

    @pytest.mark.asyncio
    async def test_get_imaging_summary_by_study_id(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await ImagingStudySummaryTool.get_imaging_study_summary(
            session=db_session, study_id="study-test-001"
        )
        assert result["study"]["study_id"] == "study-test-001"

    @pytest.mark.asyncio
    async def test_get_imaging_summary_no_params(self, db_session):
        with pytest.raises(ValidationError):
            await ImagingStudySummaryTool.get_imaging_study_summary(session=db_session)

    @pytest.mark.asyncio
    async def test_imaging_summary_required_fields(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await ImagingStudySummaryTool.get_imaging_study_summary(
            session=db_session, patient_id=patient.id
        )
        required = ["study", "contemporaneous_vitals", "related_events",
                    "follow_up_recommendations", "patient", "confidence_score", "source_references"]
        for field in required:
            assert field in result

    @pytest.mark.asyncio
    async def test_imaging_study_has_report_status(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await ImagingStudySummaryTool.get_imaging_study_summary(
            session=db_session, patient_id=patient.id
        )
        assert "report_status" in result["study"]
        assert result["study"]["report_status"] in ("preliminary", "final", "amended")


# ---------------------------------------------------------------------------
# AnesthesiaCaseTool
# ---------------------------------------------------------------------------

class TestAnesthesiaCaseTool:

    @pytest.mark.asyncio
    async def test_get_anesthesia_context_by_patient(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await AnesthesiaCaseTool.get_anesthesia_case_context(
            session=db_session, patient_id=patient.id
        )
        assert result["patient"]["id"] == patient.id
        assert "case" in result
        assert "anesthesia_agents" in result

    @pytest.mark.asyncio
    async def test_get_anesthesia_context_by_procedure_id(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await AnesthesiaCaseTool.get_anesthesia_case_context(
            session=db_session, procedure_id="proc-test-001"
        )
        assert "case" in result

    @pytest.mark.asyncio
    async def test_get_anesthesia_no_params(self, db_session):
        with pytest.raises(ValidationError):
            await AnesthesiaCaseTool.get_anesthesia_case_context(session=db_session)

    @pytest.mark.asyncio
    async def test_anesthesia_required_fields(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await AnesthesiaCaseTool.get_anesthesia_case_context(
            session=db_session, patient_id=patient.id
        )
        required = ["case", "anesthesia_agents", "intraoperative_vitals",
                    "ventilator_settings", "ventilator_events", "alarm_events",
                    "recovery_period", "recovery_vitals", "anesthesia_notes",
                    "patient", "confidence_score", "source_references"]
        for field in required:
            assert field in result

    @pytest.mark.asyncio
    async def test_anesthesia_case_has_timing(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await AnesthesiaCaseTool.get_anesthesia_case_context(
            session=db_session, patient_id=patient.id
        )
        assert "anesthesia_start" in result["case"]
        assert "anesthesia_end" in result["case"]
        assert "duration_minutes" in result["case"]
        assert result["case"]["duration_minutes"] > 0


# ---------------------------------------------------------------------------
# NeuroEventTool
# ---------------------------------------------------------------------------

class TestNeuroEventTool:

    @pytest.mark.asyncio
    async def test_get_neuro_context_by_patient(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await NeuroEventTool.get_neuro_event_context(
            session=db_session, patient_id=patient.id
        )
        assert result["patient"]["id"] == patient.id
        assert "seizure_events" in result
        assert "eeg_findings" in result

    @pytest.mark.asyncio
    async def test_get_neuro_context_by_event_id(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await NeuroEventTool.get_neuro_event_context(
            session=db_session, event_id="neuro-test-001"
        )
        assert "seizure_events" in result
        assert result["seizure_events"][0]["event_id"] == "neuro-test-001"

    @pytest.mark.asyncio
    async def test_get_neuro_no_params(self, db_session):
        with pytest.raises(ValidationError):
            await NeuroEventTool.get_neuro_event_context(session=db_session)

    @pytest.mark.asyncio
    async def test_neuro_required_fields(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await NeuroEventTool.get_neuro_event_context(
            session=db_session, patient_id=patient.id
        )
        required = ["patient", "seizure_events", "eeg_findings", "neuroimaging_studies",
                    "vitals_during_event", "vitals_after_event",
                    "seizure_management_medications", "clinical_notes",
                    "confidence_score", "source_references"]
        for field in required:
            assert field in result

    @pytest.mark.asyncio
    async def test_neuro_seizure_has_duration(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await NeuroEventTool.get_neuro_event_context(
            session=db_session, patient_id=patient.id
        )
        for seizure in result["seizure_events"]:
            assert "duration_seconds" in seizure
            assert seizure["duration_seconds"] > 0

    @pytest.mark.asyncio
    async def test_neuro_vitals_during_event_abnormal(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await NeuroEventTool.get_neuro_event_context(
            session=db_session, patient_id=patient.id
        )
        # Vitals during seizure should show abnormal values
        abnormal_vitals = [v for v in result["vitals_during_event"] if v.get("is_abnormal")]
        assert len(abnormal_vitals) > 0


# ---------------------------------------------------------------------------
# CardiologyEventTool
# ---------------------------------------------------------------------------

class TestCardiologyEventTool:

    @pytest.mark.asyncio
    async def test_get_cardiology_context_by_patient(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await CardiologyEventTool.get_cardiology_event_context(
            session=db_session, patient_id=patient.id
        )
        assert result["patient"]["id"] == patient.id
        assert "ecg_events" in result

    @pytest.mark.asyncio
    async def test_get_cardiology_context_by_event_id(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await CardiologyEventTool.get_cardiology_event_context(
            session=db_session, event_id="ecg-test-001"
        )
        assert "ecg_events" in result
        assert result["ecg_events"][0]["event_id"] == "ecg-test-001"

    @pytest.mark.asyncio
    async def test_get_cardiology_no_params(self, db_session):
        with pytest.raises(ValidationError):
            await CardiologyEventTool.get_cardiology_event_context(session=db_session)

    @pytest.mark.asyncio
    async def test_cardiology_required_fields(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await CardiologyEventTool.get_cardiology_event_context(
            session=db_session, patient_id=patient.id
        )
        required = ["patient", "ecg_events", "ecg_waveform_data", "blood_pressure_trend",
                    "spo2_trend", "cardiac_alarm_events", "cardiac_medications",
                    "related_diagnostic_exams", "clinical_notes", "cardiac_assessments",
                    "confidence_score", "source_references"]
        for field in required:
            assert field in result

    @pytest.mark.asyncio
    async def test_ecg_event_has_arrhythmia_type(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await CardiologyEventTool.get_cardiology_event_context(
            session=db_session, patient_id=patient.id
        )
        for ecg in result["ecg_events"]:
            assert "arrhythmia_type" in ecg
            assert "onset_timestamp" in ecg

    @pytest.mark.asyncio
    async def test_bp_trend_is_list(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await CardiologyEventTool.get_cardiology_event_context(
            session=db_session, patient_id=patient.id
        )
        assert isinstance(result["blood_pressure_trend"], list)
        assert len(result["blood_pressure_trend"]) > 0

    @pytest.mark.asyncio
    async def test_cardiology_confidence_score_range(self, db_session, patient_with_data):
        patient, *_ = patient_with_data
        result = await CardiologyEventTool.get_cardiology_event_context(
            session=db_session, patient_id=patient.id
        )
        assert 0.0 <= result["confidence_score"] <= 1.0
