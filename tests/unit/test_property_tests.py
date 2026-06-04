"""
Property tests for MCP platform components.

Tests key invariants:
- Tool responses conform to defined schemas
- Event classification is deterministic
- Confidence scores are always in [0, 1]
- Unauthorized access is always denied
- Invalid inputs are always rejected
- Audit logs capture all events
"""

import pytest
from datetime import datetime, timezone, timedelta
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.context_engine.event_classifier import EventClassifier, VITAL_THRESHOLDS
from mcp_server.context_engine.confidence_scorer import ConfidenceScorer
from mcp_server.context_engine.timeline_builder import TimelineBuilder
from mcp_server.database.models import Patient, Encounter, CareUnit, Device
from mcp_server.mcp_server import MCPServer
from mcp_server.models.schemas import MCPToolDefinition, ToolInputSchema
from mcp_server.security.audit_logger import AuditLogger
from mcp_server.security.authorization import AuthorizationManager
from mcp_server.tools.patient_context import PatientContextTool
from mcp_server.utils.validators import ValidationError


# ---------------------------------------------------------------------------
# Property 1: Tool responses conform to defined schemas
# ---------------------------------------------------------------------------

class TestProperty1ToolResponseSchemas:
    """Tool responses conform to their defined JSON schemas."""

    @pytest.mark.asyncio
    async def test_patient_context_response_has_all_schema_fields(
        self, db_session: AsyncSession
    ):
        """Patient context response must contain all documented fields."""
        patient = Patient(
            id="prop-pat-001", first_name="Schema", last_name="Test",
            mrn="MRN-PROP-001", is_active=True,
        )
        care_unit = CareUnit(
            id="prop-cu-001", name="Test Unit", code="TEST",
            unit_type="general", is_active=True,
        )
        encounter = Encounter(
            id="prop-enc-001", patient_id="prop-pat-001", care_unit_id="prop-cu-001",
            encounter_type="inpatient",
            admission_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
            is_active=True,
        )
        db_session.add_all([care_unit, patient, encounter])
        await db_session.commit()

        result = await PatientContextTool.get_patient_clinical_context(
            session=db_session, patient_id="prop-pat-001"
        )

        # Required top-level keys per schema
        required_keys = [
            "patient", "encounter", "care_unit", "diagnoses", "medications",
            "clinicians", "devices", "recent_abnormal_observations",
            "confidence_score", "source_references",
        ]
        for key in required_keys:
            assert key in result, f"Response missing required field: {key}"

        # Patient sub-schema
        patient_fields = ["id", "mrn", "first_name", "last_name", "full_name", "is_active"]
        for f in patient_fields:
            assert f in result["patient"]

        # Source references structure
        assert isinstance(result["source_references"], list)
        assert len(result["source_references"]) > 0
        for ref in result["source_references"]:
            assert "source" in ref
            assert "timestamp" in ref
            assert "data_types" in ref

    def test_mcp_server_validates_missing_required_argument(self):
        """MCPServer must reject requests missing required fields."""
        server = MCPServer()
        td = MCPToolDefinition(
            name="test_tool",
            description="Test",
            inputSchema=ToolInputSchema(
                type="object",
                properties={"patient_id": {"type": "string"}},
                required=["patient_id"],
                additionalProperties=False,
            ),
        )
        async def dummy_handler(patient_id: str): return {}
        server.register_tool(td, dummy_handler)

        with pytest.raises(ValidationError, match="Missing required argument"):
            server.validate_input("test_tool", {})

    def test_mcp_server_validates_wrong_type(self):
        """MCPServer must reject arguments of wrong type."""
        server = MCPServer()
        td = MCPToolDefinition(
            name="type_test_tool",
            description="Test",
            inputSchema=ToolInputSchema(
                type="object",
                properties={"count": {"type": "integer"}},
                required=["count"],
                additionalProperties=False,
            ),
        )
        async def dummy_handler(count: int): return {}
        server.register_tool(td, dummy_handler)

        with pytest.raises(ValidationError, match="Invalid type"):
            server.validate_input("type_test_tool", {"count": "not-an-integer"})


# ---------------------------------------------------------------------------
# Property 2: Event classification is deterministic
# ---------------------------------------------------------------------------

class TestProperty2ClassificationDeterminism:
    """Same event data always produces same classification."""

    def setup_method(self):
        self.clf = EventClassifier()

    @pytest.mark.parametrize("vital_type,value,expected", [
        ("heart_rate", 35, "critical_low"),
        ("heart_rate", 45, "abnormal_low"),
        ("heart_rate", 75, "normal"),
        ("heart_rate", 125, "abnormal_high"),
        ("heart_rate", 155, "critical_high"),
        ("spo2", 83, "critical_low"),
        ("spo2", 88, "abnormal_low"),
        ("spo2", 97, "normal"),
        ("blood_pressure_systolic", 65, "critical_low"),
        ("blood_pressure_systolic", 85, "abnormal_low"),
        ("blood_pressure_systolic", 120, "normal"),
        ("blood_pressure_systolic", 165, "abnormal_high"),
        ("blood_pressure_systolic", 185, "critical_high"),
    ])
    def test_vital_classification_deterministic(self, vital_type, value, expected):
        event = {"type": "vital_sign", "vital_type": vital_type, "value": value}
        r1 = self.clf.classify_event(event)
        r2 = self.clf.classify_event(event)
        assert r1["clinical_significance"] == r2["clinical_significance"] == expected

    @pytest.mark.parametrize("severity,expected", [
        ("critical", "critical"),
        ("high", "abnormal_high"),
        ("medium", "abnormal_low"),
        ("low", "normal"),
    ])
    def test_alarm_classification_deterministic(self, severity, expected):
        event = {"type": "alarm", "alarm_type": "test_alarm", "severity": severity}
        r1 = self.clf.classify_event(event)
        r2 = self.clf.classify_event(event)
        assert r1["clinical_significance"] == r2["clinical_significance"] == expected


# ---------------------------------------------------------------------------
# Property 3: Confidence scores are monotonic with data quality
# ---------------------------------------------------------------------------

class TestProperty3ConfidenceScoreMonotonicity:
    """Higher quality data always yields higher or equal confidence scores."""

    def setup_method(self):
        self.scorer = ConfidenceScorer()

    def test_reliable_source_scores_higher_than_unreliable(self):
        reliable = {"source_system": "internal_database"}
        unreliable = {"source_system": "unknown"}
        assert self.scorer.score_observation(reliable) > self.scorer.score_observation(unreliable)

    def test_calibrated_device_scores_higher_than_uncalibrated(self):
        calibrated = {"source_system": "device_telemetry", "calibration_status": "calibrated"}
        uncalibrated = {"source_system": "device_telemetry", "calibration_status": "needs_calibration"}
        assert self.scorer.score_observation(calibrated) > self.scorer.score_observation(uncalibrated)

    def test_recent_data_scores_higher_than_old(self):
        recent = {"source_system": "hl7", "timestamp": datetime.now(timezone.utc).isoformat()}
        old = {"source_system": "hl7",
               "timestamp": (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()}
        assert self.scorer.score_observation(recent) > self.scorer.score_observation(old)

    @pytest.mark.parametrize("source", ["internal_database", "fhir", "hl7", "dicom",
                                         "device_telemetry", "manual_entry", "unknown"])
    def test_all_sources_score_in_valid_range(self, source):
        score = self.scorer.score_observation({"source_system": source})
        assert 0.0 <= score <= 1.0

    def test_aggregate_score_never_outside_range(self):
        contexts = [
            {},
            {"patient": {"id": "x"}},
            {"patient": {"id": "x"}, "encounter": {"id": "e"}},
            {"patient": {"id": "x"}, "observations": [{"source_system": "unknown"}]},
        ]
        for ctx in contexts:
            score = self.scorer.score_aggregated_context(ctx)
            assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Property 4: Unauthorized access is always denied (RBAC)
# ---------------------------------------------------------------------------

class TestProperty4AuthorizationEnforcement:
    """Unauthorized tool access is always denied regardless of role."""

    def setup_method(self):
        self.auth = AuthorizationManager()

    @pytest.mark.parametrize("role,tool,should_allow", [
        # physicians can access most tools
        ("physician", "get_patient_clinical_context", True),
        ("physician", "get_care_unit_summary", True),
        ("physician", "get_anesthesia_case_context", True),
        # nurses can access patient and care unit tools
        ("nurse", "get_patient_clinical_context", True),
        ("nurse", "get_care_unit_summary", True),
        # technicians have limited access
        ("technician", "get_device_events_by_patient", True),
        ("technician", "get_patient_clinical_context", False),
        # administrators access all
        ("administrator", "get_patient_clinical_context", True),
        ("administrator", "get_anesthesia_case_context", True),
    ])
    def test_role_tool_access(self, role, tool, should_allow):
        clinician = {"id": "clin-x", "role": role, "care_units": ["cu-all"]}
        allowed = self.auth.check_tool_access(clinician, tool)
        assert allowed == should_allow

    def test_unknown_role_denied(self):
        clinician = {"id": "clin-x", "role": "unknown_role", "care_units": []}
        allowed = self.auth.check_tool_access(clinician, "get_patient_clinical_context")
        assert allowed is False

    def test_care_unit_restriction_enforced(self):
        clinician = {"id": "clin-x", "role": "nurse", "care_units": ["cu-cardio"]}
        # Should be denied for a care unit the clinician is not assigned to
        allowed = self.auth.check_care_unit_access(clinician, "cu-neuro")
        assert allowed is False

    def test_care_unit_access_granted_for_assigned_unit(self):
        clinician = {"id": "clin-x", "role": "nurse", "care_units": ["cu-cardio"]}
        allowed = self.auth.check_care_unit_access(clinician, "cu-cardio")
        assert allowed is True

    def test_administrator_can_access_all_care_units(self):
        clinician = {"id": "admin-x", "role": "administrator", "care_units": []}
        allowed = self.auth.check_care_unit_access(clinician, "any-unit")
        assert allowed is True


# ---------------------------------------------------------------------------
# Property 5: Audit logging captures all events
# ---------------------------------------------------------------------------

class TestProperty5AuditLoggingCompleteness:
    """All data access must be logged with required information."""

    def setup_method(self):
        self.audit = AuditLogger()

    def test_tool_call_log_has_required_fields(self):
        log_id = self.audit.log_tool_call(
            tool_name="get_patient_clinical_context",
            clinician_id="clin-001",
            clinician_role="physician",
            arguments={"patient_id": "pat-001"},
            patient_ids=["pat-001"],
            success=True,
            response_time_ms=125.5,
        )
        logs = self.audit.get_recent_logs(1)
        entry = logs[0]
        assert entry["log_id"] == log_id
        assert entry["tool_name"] == "get_patient_clinical_context"
        assert entry["clinician_id"] == "clin-001"
        assert "timestamp" in entry
        assert entry["success"] is True

    def test_authentication_log_masks_username(self):
        self.audit.log_authentication_attempt("dr_smith_cardio", success=True)
        logs = self.audit.get_recent_logs(1)
        entry = logs[0]
        # Full username must not appear
        assert "dr_smith_cardio" not in str(entry)
        assert "username_partial" in entry

    def test_failed_auth_is_logged(self):
        self.audit.log_authentication_attempt("user123", success=False, failure_reason="bad password")
        logs = self.audit.get_recent_logs(1)
        entry = logs[0]
        assert entry["success"] is False
        assert entry["failure_reason"] == "bad password"

    def test_authorization_denial_logged(self):
        log_id = self.audit.log_authorization_decision(
            clinician_id="clin-002", clinician_role="nurse",
            tool_name="get_anesthesia_case_context", allowed=False,
            reason="Role nurse cannot access get_anesthesia_case_context",
        )
        logs = [e for e in self.audit.get_recent_logs(10)
                if e.get("log_id") == log_id]
        assert len(logs) == 1
        assert logs[0]["allowed"] is False

    def test_phi_is_masked_in_audit_arguments(self):
        self.audit.log_tool_call(
            tool_name="get_patient_clinical_context",
            clinician_id="clin-001",
            clinician_role="physician",
            arguments={"patient_id": "pat-001", "first_name": "John", "last_name": "Doe"},
            patient_ids=["pat-001"],
            success=True,
            response_time_ms=100.0,
        )
        logs = self.audit.get_recent_logs(1)
        entry = logs[0]
        args = entry["arguments"]
        # PHI fields must be masked
        assert args.get("first_name") == "[MASKED]"
        assert args.get("last_name") == "[MASKED]"
        # Non-PHI must not be masked
        assert args.get("patient_id") == "pat-001"

    def test_logs_retrievable_by_patient(self):
        self.audit.log_tool_call(
            tool_name="get_patient_clinical_context",
            clinician_id="clin-001",
            clinician_role="physician",
            arguments={},
            patient_ids=["pat-unique-001"],
            success=True,
            response_time_ms=50.0,
        )
        patient_logs = self.audit.get_logs_for_patient("pat-unique-001")
        assert len(patient_logs) >= 1

    def test_logs_retrievable_by_clinician(self):
        self.audit.log_tool_call(
            tool_name="get_care_unit_summary",
            clinician_id="clin-unique-001",
            clinician_role="nurse",
            arguments={},
            patient_ids=[],
            success=True,
            response_time_ms=80.0,
        )
        clinician_logs = self.audit.get_logs_for_clinician("clin-unique-001")
        assert len(clinician_logs) >= 1


# ---------------------------------------------------------------------------
# Property 6: Invalid inputs are always rejected
# ---------------------------------------------------------------------------

class TestProperty6InvalidInputRejection:
    """Invalid inputs must always be rejected with ValidationError."""

    @pytest.mark.asyncio
    async def test_empty_patient_id_rejected(self, db_session):
        with pytest.raises(ValidationError):
            await PatientContextTool.get_patient_clinical_context(
                session=db_session, patient_id=""
            )

    @pytest.mark.asyncio
    async def test_none_patient_id_rejected(self, db_session):
        with pytest.raises((ValidationError, TypeError)):
            await PatientContextTool.get_patient_clinical_context(
                session=db_session, patient_id=None  # type: ignore
            )

    def test_mcp_server_rejects_unknown_tool(self):
        server = MCPServer()
        with pytest.raises(ValidationError, match="not found"):
            server.validate_input("nonexistent_tool", {})

    def test_mcp_server_rejects_extra_args_when_not_allowed(self):
        server = MCPServer()
        td = MCPToolDefinition(
            name="strict_tool",
            description="Strict",
            inputSchema=ToolInputSchema(
                type="object",
                properties={"patient_id": {"type": "string"}},
                required=["patient_id"],
                additionalProperties=False,
            ),
        )
        async def h(patient_id: str): return {}
        server.register_tool(td, h)

        with pytest.raises(ValidationError, match="Unexpected argument"):
            server.validate_input("strict_tool", {"patient_id": "x", "unexpected": "y"})


# ---------------------------------------------------------------------------
# Property 7: Timeline is always chronologically sorted
# ---------------------------------------------------------------------------

class TestProperty7TimelineOrder:
    """Timeline entries are always returned in chronological order."""

    def setup_method(self):
        self.builder = TimelineBuilder()
        self.now = datetime.now(timezone.utc)

    def _ts(self, hours: float) -> str:
        return (self.now + timedelta(hours=hours)).isoformat()

    def test_observations_sorted_ascending(self):
        obs = [
            {"vital_type": "hr", "observation_type": "heart_rate", "value": 75, "timestamp": self._ts(-1)},
            {"vital_type": "hr", "observation_type": "heart_rate", "value": 80, "timestamp": self._ts(-3)},
            {"vital_type": "hr", "observation_type": "heart_rate", "value": 70, "timestamp": self._ts(-5)},
        ]
        timeline = self.builder.build_timeline(observations=obs)
        timestamps = [e["timestamp"] for e in timeline]
        assert timestamps == sorted(timestamps)

    def test_mixed_event_types_sorted(self):
        obs = [{"vital_type": "hr", "observation_type": "heart_rate", "value": 75, "timestamp": self._ts(-2)}]
        alarms = [{"alarm_type": "low_spo2", "severity": "high", "timestamp": self._ts(-4)}]
        meds = [{"medication_name": "Aspirin", "administration_time": self._ts(-6)}]
        timeline = self.builder.build_timeline(observations=obs, alarm_events=alarms, medication_events=meds)
        timestamps = [e["timestamp"] for e in timeline]
        assert timestamps == sorted(timestamps)
        assert len(timeline) == 3
