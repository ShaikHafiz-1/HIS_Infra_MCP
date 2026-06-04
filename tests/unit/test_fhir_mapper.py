"""
Unit tests for FHIR resource mapper.

Tests cover mapping of all FHIR resource types to internal structures,
data consolidation, and error handling.
"""

import pytest
from datetime import datetime, timezone
from typing import Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.ingestion.fhir_mapper import FHIRMapper
from mcp_server.utils.validators import ValidationError


class TestFHIRPatientMapping:
    """Tests for FHIR Patient resource mapping."""

    @pytest.mark.asyncio
    async def test_map_patient_success(self, db_session: AsyncSession):
        """Test successful FHIR Patient mapping."""
        fhir_patient = {
            "id": "fhir-pat-001",
            "resourceType": "Patient",
            "identifier": [
                {
                    "type": {"coding": [{"code": "MR"}]},
                    "value": "MRN-001",
                }
            ],
            "name": [
                {
                    "given": ["John"],
                    "family": "Doe",
                }
            ],
            "birthDate": "1980-05-15",
            "gender": "male",
            "telecom": [
                {"system": "phone", "value": "555-1234"},
                {"system": "email", "value": "john@example.com"},
            ],
            "address": [
                {
                    "line": ["123 Main St"],
                    "city": "Boston",
                    "state": "MA",
                    "postalCode": "02101",
                }
            ],
            "active": True,
        }

        result = await FHIRMapper.map_patient(db_session, fhir_patient)

        assert result["fhir_id"] == "fhir-pat-001"
        assert result["first_name"] == "John"
        assert result["last_name"] == "Doe"
        assert result["mrn"] == "MRN-001"
        assert result["phone"] == "555-1234"
        assert result["email"] == "john@example.com"
        assert result["gender"] == "male"
        assert result["is_active"] is True

    @pytest.mark.asyncio
    async def test_map_patient_missing_id(self, db_session: AsyncSession):
        """Test FHIR Patient mapping with missing ID."""
        fhir_patient = {
            "resourceType": "Patient",
            "name": [{"given": ["John"], "family": "Doe"}],
        }

        with pytest.raises(ValidationError, match="missing ID"):
            await FHIRMapper.map_patient(db_session, fhir_patient)

    @pytest.mark.asyncio
    async def test_map_patient_minimal(self, db_session: AsyncSession):
        """Test FHIR Patient mapping with minimal data."""
        fhir_patient = {
            "id": "fhir-pat-002",
            "resourceType": "Patient",
            "active": True,
        }

        result = await FHIRMapper.map_patient(db_session, fhir_patient)

        assert result["fhir_id"] == "fhir-pat-002"
        assert result["first_name"] == ""
        assert result["last_name"] == ""
        assert result["mrn"] is None

    @pytest.mark.asyncio
    async def test_map_patient_invalid_dob(self, db_session: AsyncSession):
        """Test FHIR Patient mapping with invalid date of birth."""
        fhir_patient = {
            "id": "fhir-pat-003",
            "resourceType": "Patient",
            "birthDate": "invalid-date",
            "active": True,
        }

        result = await FHIRMapper.map_patient(db_session, fhir_patient)

        assert result["date_of_birth"] is None


class TestFHIREncounterMapping:
    """Tests for FHIR Encounter resource mapping."""

    @pytest.mark.asyncio
    async def test_map_encounter_success(self):
        """Test successful FHIR Encounter mapping."""
        fhir_encounter = {
            "id": "fhir-enc-001",
            "resourceType": "Encounter",
            "class": {"code": "inpatient"},
            "period": {
                "start": "2024-01-15T10:00:00Z",
                "end": None,
            },
            "reasonCode": [{"text": "Chest pain"}],
            "location": [
                {
                    "location": {
                        "reference": "Location/cardiology-unit",
                    }
                }
            ],
        }

        result = await FHIRMapper.map_encounter(
            fhir_encounter, "internal-pat-001"
        )

        assert result["fhir_id"] == "fhir-enc-001"
        assert result["patient_id"] == "internal-pat-001"
        assert result["encounter_type"] == "inpatient"
        assert result["chief_complaint"] == "Chest pain"
        assert result["is_active"] is True
        assert result["care_unit_id"] == "cardiology-unit"

    @pytest.mark.asyncio
    async def test_map_encounter_missing_id(self):
        """Test FHIR Encounter mapping with missing ID."""
        fhir_encounter = {
            "resourceType": "Encounter",
            "class": {"code": "inpatient"},
        }

        with pytest.raises(ValidationError, match="missing ID"):
            await FHIRMapper.map_encounter(fhir_encounter, "internal-pat-001")

    @pytest.mark.asyncio
    async def test_map_encounter_discharged(self):
        """Test FHIR Encounter mapping for discharged patient."""
        fhir_encounter = {
            "id": "fhir-enc-002",
            "resourceType": "Encounter",
            "class": {"code": "inpatient"},
            "period": {
                "start": "2024-01-15T10:00:00Z",
                "end": "2024-01-20T14:30:00Z",
            },
        }

        result = await FHIRMapper.map_encounter(
            fhir_encounter, "internal-pat-001"
        )

        assert result["is_active"] is False
        assert result["discharge_time"] is not None


class TestFHIRObservationMapping:
    """Tests for FHIR Observation resource mapping."""

    @pytest.mark.asyncio
    async def test_map_observation_success(self):
        """Test successful FHIR Observation mapping."""
        fhir_observation = {
            "id": "fhir-obs-001",
            "resourceType": "Observation",
            "code": {
                "coding": [
                    {
                        "code": "8480-6",
                        "display": "Systolic blood pressure",
                    }
                ]
            },
            "valueQuantity": {
                "value": 120,
                "unit": "mmHg",
            },
            "effectiveDateTime": "2024-01-15T10:00:00Z",
            "status": "final",
            "referenceRange": [
                {
                    "low": {"value": 90},
                    "high": {"value": 140},
                }
            ],
        }

        result = await FHIRMapper.map_observation(
            fhir_observation, "internal-pat-001"
        )

        assert result["fhir_id"] == "fhir-obs-001"
        assert result["observation_code"] == "8480-6"
        assert result["observation_display"] == "Systolic blood pressure"
        assert result["value"] == 120
        assert result["unit"] == "mmHg"
        assert result["status"] == "final"
        assert result["reference_range"] == "90-140"

    @pytest.mark.asyncio
    async def test_map_observation_missing_id(self):
        """Test FHIR Observation mapping with missing ID."""
        fhir_observation = {
            "resourceType": "Observation",
            "code": {"coding": [{"code": "8480-6"}]},
        }

        with pytest.raises(ValidationError, match="missing ID"):
            await FHIRMapper.map_observation(
                fhir_observation, "internal-pat-001"
            )


class TestFHIRDiagnosticReportMapping:
    """Tests for FHIR DiagnosticReport resource mapping."""

    @pytest.mark.asyncio
    async def test_map_diagnostic_report_success(self):
        """Test successful FHIR DiagnosticReport mapping."""
        fhir_report = {
            "id": "fhir-rep-001",
            "resourceType": "DiagnosticReport",
            "code": {
                "coding": [
                    {
                        "code": "24531-6",
                        "display": "Panel - Chemistry",
                    }
                ]
            },
            "effectiveDateTime": "2024-01-15T10:00:00Z",
            "conclusion": "All values within normal range",
            "status": "final",
            "result": [
                {"reference": "Observation/obs-001"},
                {"reference": "Observation/obs-002"},
            ],
        }

        result = await FHIRMapper.map_diagnostic_report(
            fhir_report, "internal-pat-001"
        )

        assert result["fhir_id"] == "fhir-rep-001"
        assert result["report_code"] == "24531-6"
        assert result["conclusion"] == "All values within normal range"
        assert result["status"] == "final"
        assert len(result["result_ids"]) == 2


class TestFHIRImagingStudyMapping:
    """Tests for FHIR ImagingStudy resource mapping."""

    @pytest.mark.asyncio
    async def test_map_imaging_study_success(self):
        """Test successful FHIR ImagingStudy mapping."""
        fhir_study = {
            "id": "fhir-img-001",
            "resourceType": "ImagingStudy",
            "started": "2024-01-15T10:00:00Z",
            "series": [
                {
                    "modality": {
                        "coding": [{"code": "CT"}]
                    }
                }
            ],
            "description": "CT Chest with contrast",
            "status": "available",
        }

        result = await FHIRMapper.map_imaging_study(
            fhir_study, "internal-pat-001"
        )

        assert result["fhir_id"] == "fhir-img-001"
        assert result["modality"] == "CT"
        assert result["description"] == "CT Chest with contrast"
        assert result["status"] == "available"
        assert result["series_count"] == 1


class TestFHIRMedicationRequestMapping:
    """Tests for FHIR MedicationRequest resource mapping."""

    @pytest.mark.asyncio
    async def test_map_medication_request_success(self):
        """Test successful FHIR MedicationRequest mapping."""
        fhir_request = {
            "id": "fhir-med-001",
            "resourceType": "MedicationRequest",
            "medicationReference": {
                "reference": "Medication/aspirin",
                "display": "Aspirin 325mg",
            },
            "status": "active",
            "intent": "order",
            "authoredOn": "2024-01-15T10:00:00Z",
            "dosageInstruction": [
                {"text": "Take one tablet by mouth twice daily"}
            ],
            "reasonCode": [
                {"text": "Chest pain prevention"}
            ],
        }

        result = await FHIRMapper.map_medication_request(
            fhir_request, "internal-pat-001"
        )

        assert result["fhir_id"] == "fhir-med-001"
        assert result["medication_display"] == "Aspirin 325mg"
        assert result["status"] == "active"
        assert result["intent"] == "order"
        assert result["dosage"] == "Take one tablet by mouth twice daily"


class TestFHIRProcedureMapping:
    """Tests for FHIR Procedure resource mapping."""

    @pytest.mark.asyncio
    async def test_map_procedure_success(self):
        """Test successful FHIR Procedure mapping."""
        fhir_procedure = {
            "id": "fhir-proc-001",
            "resourceType": "Procedure",
            "code": {
                "coding": [
                    {
                        "code": "92004",
                        "display": "Comprehensive eye exam",
                    }
                ]
            },
            "performedDateTime": "2024-01-15T10:00:00Z",
            "status": "completed",
            "outcome": {"text": "Successful"},
        }

        result = await FHIRMapper.map_procedure(
            fhir_procedure, "internal-pat-001"
        )

        assert result["fhir_id"] == "fhir-proc-001"
        assert result["procedure_code"] == "92004"
        assert result["status"] == "completed"
        assert result["outcome"] == "Successful"


class TestFHIRCarePlanMapping:
    """Tests for FHIR CarePlan resource mapping."""

    @pytest.mark.asyncio
    async def test_map_care_plan_success(self):
        """Test successful FHIR CarePlan mapping."""
        fhir_plan = {
            "id": "fhir-plan-001",
            "resourceType": "CarePlan",
            "title": "Cardiac Rehabilitation",
            "status": "active",
            "intent": "plan",
            "created": "2024-01-15T10:00:00Z",
            "goal": [
                {"description": {"text": "Improve cardiac function"}},
                {"description": {"text": "Reduce risk factors"}},
            ],
            "activity": [
                {"detail": {"description": "Exercise program"}},
                {"detail": {"description": "Dietary counseling"}},
            ],
        }

        result = await FHIRMapper.map_care_plan(
            fhir_plan, "internal-pat-001"
        )

        assert result["fhir_id"] == "fhir-plan-001"
        assert result["title"] == "Cardiac Rehabilitation"
        assert result["status"] == "active"
        assert result["goal_count"] == 2
        assert result["activity_count"] == 2


class TestFHIRDataConsolidation:
    """Tests for FHIR data consolidation."""

    @pytest.mark.asyncio
    async def test_consolidate_patient_data_success(self):
        """Test successful patient data consolidation."""
        patients = [
            {
                "fhir_id": "fhir-pat-001",
                "source_system": "fhir-server-1",
                "first_name": "John",
                "last_name": "Doe",
                "mrn": "MRN-001",
                "phone": "555-1234",
                "email": None,
                "address": None,
            },
            {
                "fhir_id": "fhir-pat-002",
                "source_system": "fhir-server-2",
                "first_name": "John",
                "last_name": "Doe",
                "mrn": None,
                "phone": None,
                "email": "john@example.com",
                "address": "123 Main St",
            },
        ]

        result = await FHIRMapper.consolidate_patient_data(patients)

        assert result["first_name"] == "John"
        assert result["last_name"] == "Doe"
        assert result["mrn"] == "MRN-001"
        assert result["phone"] == "555-1234"
        assert result["email"] == "john@example.com"
        assert result["address"] == "123 Main St"
        assert len(result["source_mappings"]) == 2

    @pytest.mark.asyncio
    async def test_consolidate_patient_data_empty(self):
        """Test patient data consolidation with empty list."""
        with pytest.raises(ValidationError, match="No patients"):
            await FHIRMapper.consolidate_patient_data([])

    @pytest.mark.asyncio
    async def test_consolidate_patient_data_single(self):
        """Test patient data consolidation with single patient."""
        patients = [
            {
                "fhir_id": "fhir-pat-001",
                "source_system": "fhir-server-1",
                "first_name": "John",
                "last_name": "Doe",
            }
        ]

        result = await FHIRMapper.consolidate_patient_data(patients)

        assert result["first_name"] == "John"
        assert result["last_name"] == "Doe"
        assert len(result["source_mappings"]) == 1


class TestFHIRMapperErrorHandling:
    """Tests for FHIR mapper error handling."""

    @pytest.mark.asyncio
    async def test_map_patient_invalid_date_format(self, db_session: AsyncSession):
        """Test FHIR Patient mapping with invalid date format."""
        fhir_patient = {
            "id": "fhir-pat-004",
            "resourceType": "Patient",
            "birthDate": "not-a-date",
            "active": True,
        }

        result = await FHIRMapper.map_patient(db_session, fhir_patient)

        assert result["date_of_birth"] is None

    @pytest.mark.asyncio
    async def test_map_observation_no_value(self):
        """Test FHIR Observation mapping without value."""
        fhir_observation = {
            "id": "fhir-obs-002",
            "resourceType": "Observation",
            "code": {"coding": [{"code": "8480-6"}]},
            "status": "final",
        }

        result = await FHIRMapper.map_observation(
            fhir_observation, "internal-pat-001"
        )

        assert result["value"] is None
        assert result["unit"] is None


class TestFHIRMapperIntegration:
    """Integration tests for FHIR mapper."""

    @pytest.mark.asyncio
    async def test_map_complete_patient_record(self, db_session: AsyncSession):
        """Test mapping a complete patient record with multiple resources."""
        # Map patient
        fhir_patient = {
            "id": "fhir-pat-005",
            "resourceType": "Patient",
            "name": [{"given": ["Jane"], "family": "Smith"}],
            "birthDate": "1990-03-20",
            "active": True,
        }

        patient_result = await FHIRMapper.map_patient(db_session, fhir_patient)

        # Map encounter
        fhir_encounter = {
            "id": "fhir-enc-003",
            "resourceType": "Encounter",
            "class": {"code": "inpatient"},
            "period": {"start": "2024-01-15T10:00:00Z"},
        }

        encounter_result = await FHIRMapper.map_encounter(
            fhir_encounter, patient_result["fhir_id"]
        )

        # Map observation
        fhir_observation = {
            "id": "fhir-obs-003",
            "resourceType": "Observation",
            "code": {"coding": [{"code": "8480-6"}]},
            "valueQuantity": {"value": 120, "unit": "mmHg"},
            "status": "final",
        }

        observation_result = await FHIRMapper.map_observation(
            fhir_observation,
            patient_result["fhir_id"],
            encounter_result["fhir_id"],
        )

        assert patient_result["first_name"] == "Jane"
        assert encounter_result["patient_id"] == patient_result["fhir_id"]
        assert observation_result["encounter_id"] == encounter_result["fhir_id"]
