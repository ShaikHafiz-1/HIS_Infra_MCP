"""
Unit tests for FHIR connector layer.

All FHIR HTTP calls are mocked via pytest-httpx (or unittest.mock) so these
tests run without a live FHIR server.  Coverage:

  - FHIRConnector auth modes (none, bearer, basic)
  - Sync get_resource / search_resource happy paths
  - Graceful fallback on server error / timeout
  - Normalizer: patient, vitals, conditions, NEWS2 computation
  - fhir_tools business logic (mocked connector)
"""

from __future__ import annotations

import json
import math
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixture: sample FHIR resources
# ---------------------------------------------------------------------------

FHIR_PATIENT = {
    "resourceType": "Patient",
    "id": "pt-hapi-001",
    "name": [{"family": "Doe", "given": ["John"]}],
    "birthDate": "1980-03-15",
    "gender": "male",
    "identifier": [
        {"type": {"coding": [{"code": "MR"}]}, "value": "MRN-12345"}
    ],
}

FHIR_OBSERVATION_HR = {
    "resourceType": "Observation",
    "id": "obs-hr-001",
    "status": "final",
    "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4", "display": "Heart rate"}]},
    "subject": {"reference": "Patient/pt-hapi-001"},
    "effectiveDateTime": "2026-06-30T10:00:00Z",
    "valueQuantity": {"value": 88, "unit": "beats/min"},
}

FHIR_OBSERVATION_SPO2 = {
    "resourceType": "Observation",
    "id": "obs-spo2-001",
    "status": "final",
    "code": {"coding": [{"system": "http://loinc.org", "code": "59408-5", "display": "O2 saturation"}]},
    "subject": {"reference": "Patient/pt-hapi-001"},
    "effectiveDateTime": "2026-06-30T10:00:00Z",
    "valueQuantity": {"value": 94.0, "unit": "%"},
}

FHIR_OBSERVATION_RR = {
    "resourceType": "Observation",
    "id": "obs-rr-001",
    "status": "final",
    "code": {"coding": [{"system": "http://loinc.org", "code": "9279-1", "display": "Respiratory rate"}]},
    "subject": {"reference": "Patient/pt-hapi-001"},
    "effectiveDateTime": "2026-06-30T10:00:00Z",
    "valueQuantity": {"value": 10, "unit": "breaths/min"},
}

FHIR_OBSERVATION_TEMP = {
    "resourceType": "Observation",
    "id": "obs-temp-001",
    "status": "final",
    "code": {"coding": [{"system": "http://loinc.org", "code": "8310-5", "display": "Body temperature"}]},
    "subject": {"reference": "Patient/pt-hapi-001"},
    "effectiveDateTime": "2026-06-30T10:00:00Z",
    "valueQuantity": {"value": 37.2, "unit": "Cel"},
}

FHIR_OBSERVATION_BP = {
    "resourceType": "Observation",
    "id": "obs-bp-001",
    "status": "final",
    "code": {"coding": [{"system": "http://loinc.org", "code": "55284-4", "display": "Blood pressure"}]},
    "subject": {"reference": "Patient/pt-hapi-001"},
    "effectiveDateTime": "2026-06-30T10:00:00Z",
    "component": [
        {
            "code": {"coding": [{"system": "http://loinc.org", "code": "8480-6"}]},
            "valueQuantity": {"value": 118, "unit": "mmHg"},
        },
        {
            "code": {"coding": [{"system": "http://loinc.org", "code": "8462-4"}]},
            "valueQuantity": {"value": 76, "unit": "mmHg"},
        },
    ],
}

FHIR_CONDITION = {
    "resourceType": "Condition",
    "id": "cond-001",
    "code": {
        "coding": [{"system": "http://snomed.info/sct", "code": "698247002", "display": "Cardiac arrhythmia"}],
        "text": "Cardiac arrhythmia",
    },
    "subject": {"reference": "Patient/pt-hapi-001"},
    "clinicalStatus": {"coding": [{"code": "active"}]},
    "onsetDateTime": "2026-01-01",
}

FHIR_MEDICATION = {
    "resourceType": "MedicationRequest",
    "id": "med-001",
    "status": "active",
    "intent": "order",
    "medicationCodeableConcept": {
        "coding": [{"display": "Amiodarone 200mg"}],
        "text": "Amiodarone 200mg",
    },
    "subject": {"reference": "Patient/pt-hapi-001"},
    "authoredOn": "2026-06-01",
    "dosageInstruction": [{"text": "200mg once daily"}],
}

FHIR_BUNDLE_VITALS = {
    "resourceType": "Bundle",
    "type": "searchset",
    "total": 2,
    "entry": [
        {"resource": FHIR_OBSERVATION_HR},
        {"resource": FHIR_OBSERVATION_SPO2},
        {"resource": FHIR_OBSERVATION_RR},
        {"resource": FHIR_OBSERVATION_TEMP},
        {"resource": FHIR_OBSERVATION_BP},
    ],
}

FHIR_BUNDLE_PATIENTS = {
    "resourceType": "Bundle",
    "type": "searchset",
    "total": 1,
    "entry": [{"resource": FHIR_PATIENT}],
}

FHIR_BUNDLE_CONDITIONS = {
    "resourceType": "Bundle",
    "type": "searchset",
    "total": 1,
    "entry": [{"resource": FHIR_CONDITION}],
}

FHIR_BUNDLE_MEDICATIONS = {
    "resourceType": "Bundle",
    "type": "searchset",
    "total": 1,
    "entry": [{"resource": FHIR_MEDICATION}],
}

FHIR_BUNDLE_EMPTY = {
    "resourceType": "Bundle",
    "type": "searchset",
    "total": 0,
    "entry": [],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(payload: dict, status: int = 200):
    """Create a mock httpx.Response-like object."""
    m = MagicMock()
    m.status_code = status
    m.json.return_value = payload
    return m


# ---------------------------------------------------------------------------
# FHIRConnector tests
# ---------------------------------------------------------------------------

class TestFHIRConnector:

    def test_disabled_when_no_base_url(self):
        from mcp_server.fhir.connector import FHIRConnector
        conn = FHIRConnector(base_url="")
        assert not conn.is_enabled()

    def test_enabled_when_base_url_set(self):
        from mcp_server.fhir.connector import FHIRConnector
        conn = FHIRConnector(base_url="https://hapi.fhir.org/baseR4")
        assert conn.is_enabled()

    def test_sandbox_mode_sets_no_auth(self):
        from mcp_server.fhir.connector import FHIRConnector
        conn = FHIRConnector(
            base_url="https://hapi.fhir.org/baseR4",
            sandbox_mode=True,
            auth_type="bearer",
            token="should-be-ignored",
        )
        headers = conn._build_headers()
        assert "Authorization" not in headers

    def test_bearer_auth_header(self):
        from mcp_server.fhir.connector import FHIRConnector
        conn = FHIRConnector(
            base_url="https://example.com/fhir",
            auth_type="bearer",
            token="test-token-abc",
        )
        headers = conn._build_headers()
        assert headers["Authorization"] == "Bearer test-token-abc"

    def test_basic_auth_header(self):
        import base64
        from mcp_server.fhir.connector import FHIRConnector
        conn = FHIRConnector(
            base_url="https://example.com/fhir",
            auth_type="basic",
            username="user",
            password="pass",
        )
        headers = conn._build_headers()
        expected = "Basic " + base64.b64encode(b"user:pass").decode()
        assert headers["Authorization"] == expected

    def test_no_auth_no_authorization_header(self):
        from mcp_server.fhir.connector import FHIRConnector
        conn = FHIRConnector(
            base_url="https://hapi.fhir.org/baseR4",
            auth_type="none",
        )
        headers = conn._build_headers()
        assert "Authorization" not in headers

    def test_get_resource_returns_patient(self):
        from mcp_server.fhir.connector import FHIRConnector
        conn = FHIRConnector(base_url="https://hapi.fhir.org/baseR4")
        with patch("httpx.get", return_value=_mock_response(FHIR_PATIENT)):
            result = conn.get_resource("Patient", "pt-hapi-001")
        assert result is not None
        assert result["resourceType"] == "Patient"
        assert result["id"] == "pt-hapi-001"

    def test_get_resource_returns_none_on_404(self):
        from mcp_server.fhir.connector import FHIRConnector
        conn = FHIRConnector(base_url="https://hapi.fhir.org/baseR4")
        with patch("httpx.get", return_value=_mock_response({}, 404)):
            result = conn.get_resource("Patient", "nonexistent")
        assert result is None

    def test_get_resource_returns_none_on_exception(self):
        from mcp_server.fhir.connector import FHIRConnector
        conn = FHIRConnector(base_url="https://hapi.fhir.org/baseR4")
        with patch("httpx.get", side_effect=Exception("Connection refused")):
            result = conn.get_resource("Patient", "pt-001")
        assert result is None

    def test_search_resource_extracts_bundle_entries(self):
        from mcp_server.fhir.connector import FHIRConnector
        conn = FHIRConnector(base_url="https://hapi.fhir.org/baseR4")
        with patch("httpx.get", return_value=_mock_response(FHIR_BUNDLE_PATIENTS)):
            results = conn.search_resource("Patient", {"name": "Doe"})
        assert len(results) == 1
        assert results[0]["id"] == "pt-hapi-001"

    def test_search_resource_returns_empty_list_on_error(self):
        from mcp_server.fhir.connector import FHIRConnector
        conn = FHIRConnector(base_url="https://hapi.fhir.org/baseR4")
        with patch("httpx.get", return_value=_mock_response({}, 500)):
            results = conn.search_resource("Patient", {"name": "X"})
        assert results == []

    def test_disabled_connector_returns_none_get(self):
        from mcp_server.fhir.connector import FHIRConnector
        conn = FHIRConnector(base_url="")
        result = conn.get_resource("Patient", "123")
        assert result is None

    def test_disabled_connector_returns_empty_search(self):
        from mcp_server.fhir.connector import FHIRConnector
        conn = FHIRConnector(base_url="")
        results = conn.search_resource("Observation", {"patient": "123"})
        assert results == []


# ---------------------------------------------------------------------------
# Normalizer tests
# ---------------------------------------------------------------------------

class TestNormalizer:

    def test_norm_patient_extracts_name(self):
        from mcp_server.fhir.normalizer import norm_patient
        result = norm_patient(FHIR_PATIENT)
        assert result["name"] == "John Doe"

    def test_norm_patient_computes_age(self):
        from mcp_server.fhir.normalizer import norm_patient
        result = norm_patient(FHIR_PATIENT)
        assert result["age"] is not None
        assert 40 <= result["age"] <= 50

    def test_norm_patient_extracts_mrn(self):
        from mcp_server.fhir.normalizer import norm_patient
        result = norm_patient(FHIR_PATIENT)
        assert result["mrn"] == "MRN-12345"

    def test_norm_patient_extracts_gender(self):
        from mcp_server.fhir.normalizer import norm_patient
        result = norm_patient(FHIR_PATIENT)
        assert result["gender"] == "male"

    def test_norm_observations_hr(self):
        from mcp_server.fhir.normalizer import norm_observations_to_vitals
        vitals = norm_observations_to_vitals([FHIR_OBSERVATION_HR])
        assert vitals["hr"] == 88.0

    def test_norm_observations_spo2(self):
        from mcp_server.fhir.normalizer import norm_observations_to_vitals
        vitals = norm_observations_to_vitals([FHIR_OBSERVATION_SPO2])
        assert vitals["spo2"] == 94.0

    def test_norm_observations_rr(self):
        from mcp_server.fhir.normalizer import norm_observations_to_vitals
        vitals = norm_observations_to_vitals([FHIR_OBSERVATION_RR])
        assert vitals["rr"] == 10.0

    def test_norm_observations_temp(self):
        from mcp_server.fhir.normalizer import norm_observations_to_vitals
        vitals = norm_observations_to_vitals([FHIR_OBSERVATION_TEMP])
        assert vitals["temp"] == 37.2

    def test_norm_observations_bp_panel(self):
        from mcp_server.fhir.normalizer import norm_observations_to_vitals
        vitals = norm_observations_to_vitals([FHIR_OBSERVATION_BP])
        assert vitals["sbp"] == 118.0
        assert vitals["dbp"] == 76.0

    def test_norm_observations_derives_map(self):
        from mcp_server.fhir.normalizer import norm_observations_to_vitals
        vitals = norm_observations_to_vitals([FHIR_OBSERVATION_BP])
        assert vitals["map_val"] is not None
        expected_map = round((118 + 2 * 76) / 3, 1)
        assert abs(vitals["map_val"] - expected_map) < 0.5

    def test_norm_observations_all_vitals(self):
        from mcp_server.fhir.normalizer import norm_observations_to_vitals
        obs_list = [
            FHIR_OBSERVATION_HR, FHIR_OBSERVATION_SPO2, FHIR_OBSERVATION_RR,
            FHIR_OBSERVATION_TEMP, FHIR_OBSERVATION_BP,
        ]
        vitals = norm_observations_to_vitals(obs_list)
        assert vitals["hr"] == 88.0
        assert vitals["spo2"] == 94.0
        assert vitals["rr"] == 10.0
        assert vitals["temp"] == 37.2
        assert vitals["sbp"] == 118.0
        assert vitals["dbp"] == 76.0
        assert vitals["news2"] is not None

    def test_norm_condition(self):
        from mcp_server.fhir.normalizer import norm_condition
        result = norm_condition(FHIR_CONDITION)
        assert result["code"] == "698247002"
        assert "arrhythmia" in result["display"].lower()
        assert result["status"] == "active"

    def test_norm_medication(self):
        from mcp_server.fhir.normalizer import norm_medication
        result = norm_medication(FHIR_MEDICATION)
        assert "amiodarone" in result["name"].lower()
        assert result["status"] == "active"
        assert result["dosage"] == "200mg once daily"

    def test_norm_patient_missing_name(self):
        from mcp_server.fhir.normalizer import norm_patient
        pt = {"resourceType": "Patient", "id": "x", "gender": "female"}
        result = norm_patient(pt)
        assert result["name"] is not None
        assert result["age"] is None

    def test_condition_matches_arrhythmia(self):
        from mcp_server.fhir.normalizer import norm_condition, condition_matches_category
        nc = norm_condition(FHIR_CONDITION)
        assert condition_matches_category(nc, "arrhythmia") is True


# ---------------------------------------------------------------------------
# NEWS2 computation tests (mirrors simulator tests)
# ---------------------------------------------------------------------------

class TestNEWS2:

    def test_rr_9_11_scores_1(self):
        from mcp_server.fhir.normalizer import compute_news2
        vitals = {"rr": 10, "spo2": 97, "sbp": 120, "hr": 75, "temp": 36.8}
        assert compute_news2(vitals) == 1  # RR 9-11 → +1

    def test_rr_12_20_scores_0(self):
        from mcp_server.fhir.normalizer import compute_news2
        vitals = {"rr": 16, "spo2": 97, "sbp": 120, "hr": 75, "temp": 36.8}
        assert compute_news2(vitals) == 0

    def test_rr_21_24_scores_2(self):
        from mcp_server.fhir.normalizer import compute_news2
        vitals = {"rr": 22, "spo2": 97, "sbp": 120, "hr": 75, "temp": 36.8}
        assert compute_news2(vitals) == 2

    def test_spo2_below_92_scores_3(self):
        from mcp_server.fhir.normalizer import compute_news2
        vitals = {"rr": 16, "spo2": 88, "sbp": 120, "hr": 75, "temp": 36.8}
        assert compute_news2(vitals) == 3

    def test_insufficient_data_returns_0(self):
        from mcp_server.fhir.normalizer import compute_news2
        vitals = {"rr": None, "spo2": None, "sbp": None}
        assert compute_news2(vitals) == 0

    def test_news2_to_risk_mapping(self):
        from mcp_server.fhir.normalizer import _news2_to_risk
        assert _news2_to_risk(0) == "STABLE"
        assert _news2_to_risk(3) == "MEDIUM"
        assert _news2_to_risk(5) == "HIGH"
        assert _news2_to_risk(7) == "CRITICAL"


# ---------------------------------------------------------------------------
# FHIR tools integration tests (connector mocked)
# ---------------------------------------------------------------------------

class TestFHIRTools:

    def _make_conn(self):
        from mcp_server.fhir.connector import FHIRConnector
        conn = FHIRConnector(base_url="https://hapi.fhir.org/baseR4")
        return conn

    def test_get_patient_by_id_returns_demographics(self):
        from mcp_server.fhir import fhir_tools
        mock_conn = MagicMock()
        mock_conn.is_enabled.return_value = True
        mock_conn.get_patient.return_value = FHIR_PATIENT
        mock_conn.get_vitals.return_value = [FHIR_OBSERVATION_HR, FHIR_OBSERVATION_SPO2]
        mock_conn.get_conditions.return_value = [FHIR_CONDITION]
        mock_conn.get_medications.return_value = [FHIR_MEDICATION]
        mock_conn.get_encounters.return_value = []
        mock_conn.get_devices.return_value = []
        mock_conn.get_allergies.return_value = []
        mock_conn.get_procedures.return_value = []

        with patch("mcp_server.fhir.fhir_tools.get_fhir_connector", return_value=mock_conn):
            result = fhir_tools.get_patient_by_id("pt-hapi-001")

        assert result["source"] == "fhir"
        assert result["name"] == "John Doe"
        assert result["vitals"]["hr"] == 88.0
        assert len(result["conditions"]) == 1

    def test_get_patient_by_id_not_found(self):
        from mcp_server.fhir import fhir_tools
        mock_conn = MagicMock()
        mock_conn.is_enabled.return_value = True
        mock_conn.get_patient.return_value = None

        with patch("mcp_server.fhir.fhir_tools.get_fhir_connector", return_value=mock_conn):
            result = fhir_tools.get_patient_by_id("bad-id")

        assert "error" in result

    def test_get_patient_by_id_disabled(self):
        from mcp_server.fhir import fhir_tools
        mock_conn = MagicMock()
        mock_conn.is_enabled.return_value = False

        with patch("mcp_server.fhir.fhir_tools.get_fhir_connector", return_value=mock_conn):
            result = fhir_tools.get_patient_by_id("any-id")

        assert result["fhir_enabled"] is False
        assert result["source"] == "simulator"

    def test_search_patients_returns_list(self):
        from mcp_server.fhir import fhir_tools
        mock_conn = MagicMock()
        mock_conn.is_enabled.return_value = True
        mock_conn.search_patients.return_value = [FHIR_PATIENT]

        with patch("mcp_server.fhir.fhir_tools.get_fhir_connector", return_value=mock_conn):
            result = fhir_tools.search_patients("Doe")

        assert result["count"] == 1
        assert result["patients"][0]["name"] == "John Doe"

    def test_get_patient_vitals_with_news2(self):
        from mcp_server.fhir import fhir_tools
        mock_conn = MagicMock()
        mock_conn.is_enabled.return_value = True
        mock_conn.get_vitals.return_value = [
            FHIR_OBSERVATION_HR, FHIR_OBSERVATION_SPO2,
            FHIR_OBSERVATION_RR, FHIR_OBSERVATION_TEMP, FHIR_OBSERVATION_BP,
        ]

        with patch("mcp_server.fhir.fhir_tools.get_fhir_connector", return_value=mock_conn):
            result = fhir_tools.get_patient_vitals("pt-hapi-001")

        assert result["hr"] == 88.0
        assert result["spo2"] == 94.0
        assert result["news2"] is not None
        assert result["risk_level"] in ("STABLE", "LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_get_patients_with_low_spo2(self):
        from mcp_server.fhir import fhir_tools
        low_spo2_obs = {
            **FHIR_OBSERVATION_SPO2,
            "subject": {"reference": "Patient/pt-hapi-001"},
            "valueQuantity": {"value": 87.0, "unit": "%"},
        }
        mock_conn = MagicMock()
        mock_conn.is_enabled.return_value = True
        mock_conn.search_resource.return_value = [low_spo2_obs]

        with patch("mcp_server.fhir.fhir_tools.get_fhir_connector", return_value=mock_conn):
            result = fhir_tools.get_patients_with_low_spo2(threshold=90.0)

        assert result["count"] == 1
        assert result["patients"][0]["spo2"] == 87.0
        assert result["threshold"] == 90.0

    def test_get_patients_with_arrhythmia(self):
        from mcp_server.fhir import fhir_tools
        mock_conn = MagicMock()
        mock_conn.is_enabled.return_value = True
        mock_conn.search_resource.return_value = [FHIR_CONDITION]
        mock_conn.get_patient.return_value = FHIR_PATIENT

        with patch("mcp_server.fhir.fhir_tools.get_fhir_connector", return_value=mock_conn):
            result = fhir_tools.get_patients_with_arrhythmia()

        assert result["count"] >= 1
        assert any("arrhythmia" in p["condition"].lower() for p in result["patients"])

    def test_summarize_patient_status(self):
        from mcp_server.fhir import fhir_tools
        mock_conn = MagicMock()
        mock_conn.is_enabled.return_value = True
        mock_conn.base_url = "https://hapi.fhir.org/baseR4"
        mock_conn.get_patient.return_value = FHIR_PATIENT
        mock_conn.get_vitals.return_value = [FHIR_OBSERVATION_HR, FHIR_OBSERVATION_SPO2]
        mock_conn.get_conditions.return_value = [FHIR_CONDITION]
        mock_conn.get_medications.return_value = [FHIR_MEDICATION]
        mock_conn.get_devices.return_value = []
        mock_conn.get_allergies.return_value = []

        with patch("mcp_server.fhir.fhir_tools.get_fhir_connector", return_value=mock_conn):
            result = fhir_tools.summarize_patient_status("pt-hapi-001")

        assert result["source"] == "fhir"
        assert "summary_text" in result
        assert "John Doe" in result["summary_text"]
        assert len(result["conditions"]) == 1

    def test_get_connected_devices_empty(self):
        from mcp_server.fhir import fhir_tools
        mock_conn = MagicMock()
        mock_conn.is_enabled.return_value = True
        mock_conn.get_devices.return_value = []

        with patch("mcp_server.fhir.fhir_tools.get_fhir_connector", return_value=mock_conn):
            result = fhir_tools.get_connected_devices("pt-hapi-001")

        assert result["total"] == 0
        assert result["devices"] == []

    def test_get_patient_timeline_empty(self):
        from mcp_server.fhir import fhir_tools
        mock_conn = MagicMock()
        mock_conn.is_enabled.return_value = True
        mock_conn.get_encounters.return_value = []
        mock_conn.get_vitals.return_value = []
        mock_conn.get_procedures.return_value = []

        with patch("mcp_server.fhir.fhir_tools.get_fhir_connector", return_value=mock_conn):
            result = fhir_tools.get_patient_timeline("pt-hapi-001")

        assert result["count"] == 0
        assert result["events"] == []
