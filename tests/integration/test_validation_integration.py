"""Integration tests for input validation across all tools."""

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
from mcp_server.database.models import Patient, Encounter, CareUnit
from mcp_server.utils.validators import ValidationError


@pytest.fixture
async def val_patient(db_session):
    """Create a minimal patient for validation tests."""
    care_unit = CareUnit(
        id="val-cu-001", name="Validation ICU", code="VAL",
        unit_type="intensive_care", is_active=True,
    )
    patient = Patient(
        id="val-pat-001", first_name="Val", last_name="Patient",
        mrn="VAL-MRN-001", is_active=True,
    )
    encounter = Encounter(
        id="val-enc-001", patient_id="val-pat-001", care_unit_id="val-cu-001",
        encounter_type="inpatient",
        admission_time=datetime(2024, 1, 10, tzinfo=timezone.utc),
        is_active=True,
    )
    db_session.add_all([care_unit, patient, encounter])
    await db_session.commit()
    return {"patient": patient, "encounter": encounter, "care_unit": care_unit}


class TestValidationAcrossTools:
    """Parametrized validation tests across all patient-facing tools."""

    @pytest.mark.asyncio
    async def test_patient_context_rejects_empty_id(self, db_session):
        with pytest.raises((ValidationError, Exception)):
            await PatientContextTool.get_patient_clinical_context(
                session=db_session, patient_id=""
            )

    @pytest.mark.asyncio
    async def test_event_timeline_rejects_empty_id(self, db_session):
        with pytest.raises((ValidationError, Exception)):
            await EventTimelineTool.get_patient_event_timeline(
                session=db_session, patient_id=""
            )

    @pytest.mark.asyncio
    async def test_device_events_rejects_empty_id(self, db_session):
        with pytest.raises((ValidationError, Exception)):
            await DeviceEventsTool.get_device_events_by_patient(
                session=db_session, patient_id=""
            )

    @pytest.mark.asyncio
    async def test_alarm_context_rejects_both_none(self, db_session):
        """alarm_context requires either alarm_id or patient_id."""
        with pytest.raises((ValidationError, Exception)):
            await AlarmContextTool.get_alarm_context(
                session=db_session, patient_id=None, alarm_id=None
            )

    @pytest.mark.asyncio
    async def test_diagnostic_exam_rejects_both_none(self, db_session):
        with pytest.raises((ValidationError, Exception)):
            await DiagnosticExamTool.get_diagnostic_exam_context(
                session=db_session, patient_id=None, exam_id=None
            )

    @pytest.mark.asyncio
    async def test_imaging_summary_rejects_both_none(self, db_session):
        with pytest.raises((ValidationError, Exception)):
            await ImagingStudySummaryTool.get_imaging_study_summary(
                session=db_session, patient_id=None, study_id=None
            )

    @pytest.mark.asyncio
    async def test_anesthesia_rejects_both_none(self, db_session):
        with pytest.raises((ValidationError, Exception)):
            await AnesthesiaCaseTool.get_anesthesia_case_context(
                session=db_session, patient_id=None, procedure_id=None
            )

    @pytest.mark.asyncio
    async def test_neuro_rejects_both_none(self, db_session):
        with pytest.raises((ValidationError, Exception)):
            await NeuroEventTool.get_neuro_event_context(
                session=db_session, patient_id=None, event_id=None
            )

    @pytest.mark.asyncio
    async def test_cardiology_rejects_both_none(self, db_session):
        with pytest.raises((ValidationError, Exception)):
            await CardiologyEventTool.get_cardiology_event_context(
                session=db_session, patient_id=None, event_id=None
            )

    @pytest.mark.asyncio
    async def test_care_unit_id_rejects_empty(self, db_session):
        with pytest.raises((ValidationError, Exception)):
            await CareUnitSummaryTool.get_care_unit_summary(
                session=db_session, care_unit_id=""
            )

    @pytest.mark.asyncio
    async def test_optional_params_accepted_as_none_timeline(self, db_session, val_patient):
        """Timeline tool accepts None for optional start_time and end_time."""
        patient_id = val_patient["patient"].id
        result = await EventTimelineTool.get_patient_event_timeline(
            session=db_session, patient_id=patient_id, start_time=None, end_time=None,
        )
        assert "timeline" in result

    @pytest.mark.asyncio
    async def test_optional_params_accepted_as_none_device_events(
        self, db_session, val_patient
    ):
        """Device events tool accepts None for all optional params."""
        patient_id = val_patient["patient"].id
        result = await DeviceEventsTool.get_device_events_by_patient(
            session=db_session, patient_id=patient_id,
            start_time=None, end_time=None, device_type=None,
        )
        assert "device_events" in result

    @pytest.mark.asyncio
    async def test_optional_params_accepted_as_valid_iso_string(
        self, db_session, val_patient
    ):
        """Timeline tool accepts valid ISO datetime strings for time window."""
        patient_id = val_patient["patient"].id
        result = await EventTimelineTool.get_patient_event_timeline(
            session=db_session, patient_id=patient_id,
            start_time="2024-01-01T00:00:00+00:00",
            end_time="2024-12-31T23:59:59+00:00",
        )
        assert "timeline" in result
        assert result["time_window"]["start_time"].startswith("2024-01-01")


class TestMCPServerSchemaValidation:
    """Tests for MCP server-level schema validation logic."""

    def test_validation_error_is_exception(self):
        assert issubclass(ValidationError, Exception)

    def test_validation_error_raised_with_message(self):
        msg = "patient_id must be a non-empty string"
        err = ValidationError(msg)
        assert str(err) == msg

    def test_empty_patient_id_raises_validation_error_directly(self):
        from mcp_server.utils.validators import validate_patient_id
        with pytest.raises(ValidationError, match="non-empty"):
            validate_patient_id("")

    def test_none_patient_id_raises_validation_error_directly(self):
        from mcp_server.utils.validators import validate_patient_id
        with pytest.raises(ValidationError):
            validate_patient_id(None)

    def test_oversized_patient_id_raises_validation_error_directly(self):
        from mcp_server.utils.validators import validate_patient_id
        with pytest.raises(ValidationError, match="255"):
            validate_patient_id("x" * 256)

    def test_invalid_character_patient_id_raises_validation_error(self):
        from mcp_server.utils.validators import validate_patient_id
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_patient_id("patient id with spaces")

    def test_valid_patient_id_accepted(self):
        from mcp_server.utils.validators import validate_patient_id
        assert validate_patient_id("PAT-12345") is True
        assert validate_patient_id("patient_001") is True
        assert validate_patient_id("abc123") is True

    @pytest.mark.asyncio
    async def test_required_params_enforced_patient_context_none(self, db_session):
        with pytest.raises((ValidationError, TypeError, Exception)):
            await PatientContextTool.get_patient_clinical_context(
                session=db_session, patient_id=None
            )

    @pytest.mark.asyncio
    async def test_required_params_enforced_timeline_none(self, db_session):
        with pytest.raises((ValidationError, TypeError, Exception)):
            await EventTimelineTool.get_patient_event_timeline(
                session=db_session, patient_id=None
            )

    @pytest.mark.asyncio
    async def test_alarm_context_requires_at_least_one_id(self, db_session):
        with pytest.raises((ValidationError, Exception)):
            await AlarmContextTool.get_alarm_context(
                session=db_session, alarm_id=None, patient_id=None
            )

    @pytest.mark.asyncio
    async def test_diagnostic_exam_requires_at_least_one_id(self, db_session):
        with pytest.raises((ValidationError, Exception)):
            await DiagnosticExamTool.get_diagnostic_exam_context(
                session=db_session, exam_id=None, patient_id=None
            )

    @pytest.mark.asyncio
    async def test_imaging_summary_requires_at_least_one_id(self, db_session):
        with pytest.raises((ValidationError, Exception)):
            await ImagingStudySummaryTool.get_imaging_study_summary(
                session=db_session, study_id=None, patient_id=None
            )

    @pytest.mark.asyncio
    async def test_neuro_context_requires_at_least_one_id(self, db_session):
        with pytest.raises((ValidationError, Exception)):
            await NeuroEventTool.get_neuro_event_context(
                session=db_session, event_id=None, patient_id=None
            )

    @pytest.mark.asyncio
    async def test_cardiology_context_requires_at_least_one_id(self, db_session):
        with pytest.raises((ValidationError, Exception)):
            await CardiologyEventTool.get_cardiology_event_context(
                session=db_session, event_id=None, patient_id=None
            )
