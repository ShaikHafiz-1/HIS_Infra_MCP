"""
Unit tests for patient clinical context tool.

Tests cover patient context retrieval, data formatting, authorization,
and error handling.
"""

import pytest
from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.tools.patient_context import PatientContextTool
from mcp_server.database.models import (
    Patient,
    Encounter,
    CareUnit,
    Clinician,
    Device,
    ClinicianAssignment,
)
from mcp_server.utils.validators import ValidationError


@pytest.fixture
async def patient_with_encounter(db_session: AsyncSession) -> tuple[Patient, Encounter]:
    """Create a patient with an active encounter."""
    # Create care unit
    care_unit = CareUnit(
        id="cu-001",
        name="Cardiology",
        code="CARDIO",
        description="Cardiology Department",
        location="Building A, Floor 3",
        unit_type="specialty",
        is_active=True,
    )
    db_session.add(care_unit)

    # Create patient
    patient = Patient(
        id="pat-001",
        first_name="John",
        last_name="Doe",
        date_of_birth=datetime(1980, 5, 15, tzinfo=timezone.utc),
        gender="M",
        mrn="MRN-001",
        phone="555-1234",
        email="john.doe@example.com",
        address="123 Main St",
        is_active=True,
    )
    db_session.add(patient)

    # Create encounter
    encounter = Encounter(
        id="enc-001",
        patient_id="pat-001",
        care_unit_id="cu-001",
        encounter_type="inpatient",
        admission_time=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        discharge_time=None,
        is_active=True,
        chief_complaint="Chest pain",
        admission_diagnosis="Acute coronary syndrome",
    )
    db_session.add(encounter)

    await db_session.commit()
    return patient, encounter


@pytest.fixture
async def clinician_assigned_to_encounter(
    db_session: AsyncSession, patient_with_encounter: tuple[Patient, Encounter]
) -> Clinician:
    """Create a clinician assigned to an encounter."""
    _, encounter = patient_with_encounter

    clinician = Clinician(
        id="clin-001",
        first_name="Jane",
        last_name="Smith",
        email="jane.smith@example.com",
        phone="555-5678",
        role="physician",
        specialty="cardiology",
        license_number="LIC-001",
        is_active=True,
    )
    db_session.add(clinician)

    assignment = ClinicianAssignment(
        id="assign-001",
        clinician_id="clin-001",
        encounter_id=encounter.id,
        role="attending_physician",
        is_active=True,
    )
    db_session.add(assignment)

    await db_session.commit()
    return clinician


@pytest.fixture
async def device_in_encounter(
    db_session: AsyncSession, patient_with_encounter: tuple[Patient, Encounter]
) -> Device:
    """Create a device in an encounter."""
    _, encounter = patient_with_encounter

    device = Device(
        id="dev-001",
        encounter_id=encounter.id,
        device_type="cardiac_monitor",
        device_name="Philips Monitor",
        serial_number="SN-12345",
        manufacturer="Philips",
        model="MP70",
        location="Bed 1",
        is_online=True,
        battery_level=95.0,
        calibration_status="calibrated",
        is_active=True,
    )
    db_session.add(device)

    await db_session.commit()
    return device


class TestPatientContextRetrieval:
    """Tests for patient context retrieval."""

    @pytest.mark.asyncio
    async def test_get_patient_clinical_context_success(
        self, db_session: AsyncSession, patient_with_encounter: tuple[Patient, Encounter]
    ):
        """Test successful patient context retrieval."""
        patient, encounter = patient_with_encounter

        context = await PatientContextTool.get_patient_clinical_context(
            session=db_session,
            patient_id=patient.id,
        )

        assert context is not None
        assert context["patient"]["id"] == patient.id
        assert context["patient"]["mrn"] == "MRN-001"
        assert context["patient"]["first_name"] == "John"
        assert context["patient"]["last_name"] == "Doe"
        assert context["encounter"]["id"] == encounter.id
        assert context["encounter"]["is_active"] is True
        assert context["care_unit"]["name"] == "Cardiology"
        assert context["confidence_score"] == 0.95

    @pytest.mark.asyncio
    async def test_get_patient_clinical_context_with_clinicians(
        self,
        db_session: AsyncSession,
        patient_with_encounter: tuple[Patient, Encounter],
        clinician_assigned_to_encounter: Clinician,
    ):
        """Test patient context retrieval includes assigned clinicians."""
        patient, _ = patient_with_encounter

        context = await PatientContextTool.get_patient_clinical_context(
            session=db_session,
            patient_id=patient.id,
        )

        assert len(context["clinicians"]) == 1
        assert context["clinicians"][0]["id"] == "clin-001"
        assert context["clinicians"][0]["first_name"] == "Jane"
        assert context["clinicians"][0]["role"] == "physician"

    @pytest.mark.asyncio
    async def test_get_patient_clinical_context_with_devices(
        self,
        db_session: AsyncSession,
        patient_with_encounter: tuple[Patient, Encounter],
        device_in_encounter: Device,
    ):
        """Test patient context retrieval includes active devices."""
        patient, _ = patient_with_encounter

        context = await PatientContextTool.get_patient_clinical_context(
            session=db_session,
            patient_id=patient.id,
            include_devices=True,
        )

        assert len(context["devices"]) == 1
        assert context["devices"][0]["id"] == "dev-001"
        assert context["devices"][0]["device_type"] == "cardiac_monitor"
        assert context["devices"][0]["is_online"] is True

    @pytest.mark.asyncio
    async def test_get_patient_clinical_context_exclude_devices(
        self,
        db_session: AsyncSession,
        patient_with_encounter: tuple[Patient, Encounter],
        device_in_encounter: Device,
    ):
        """Test patient context retrieval can exclude devices."""
        patient, _ = patient_with_encounter

        context = await PatientContextTool.get_patient_clinical_context(
            session=db_session,
            patient_id=patient.id,
            include_devices=False,
        )

        assert len(context["devices"]) == 0

    @pytest.mark.asyncio
    async def test_get_patient_clinical_context_patient_not_found(
        self, db_session: AsyncSession
    ):
        """Test patient context retrieval with nonexistent patient."""
        with pytest.raises(ValidationError, match="Patient not found"):
            await PatientContextTool.get_patient_clinical_context(
                session=db_session,
                patient_id="nonexistent-patient",
            )

    @pytest.mark.asyncio
    async def test_get_patient_clinical_context_invalid_patient_id(
        self, db_session: AsyncSession
    ):
        """Test patient context retrieval with invalid patient ID."""
        with pytest.raises(ValidationError, match="must be a non-empty string"):
            await PatientContextTool.get_patient_clinical_context(
                session=db_session,
                patient_id="",
            )

    @pytest.mark.asyncio
    async def test_get_patient_clinical_context_invalid_patient_id_type(
        self, db_session: AsyncSession
    ):
        """Test patient context retrieval with invalid patient ID type."""
        with pytest.raises(ValidationError, match="must be a non-empty string"):
            await PatientContextTool.get_patient_clinical_context(
                session=db_session,
                patient_id=123,  # type: ignore
            )


class TestPatientFormatting:
    """Tests for patient data formatting."""

    def test_format_patient_with_all_fields(self):
        """Test formatting patient with all fields."""
        patient = Patient(
            id="pat-001",
            first_name="John",
            last_name="Doe",
            date_of_birth=datetime(1980, 5, 15, tzinfo=timezone.utc),
            gender="M",
            mrn="MRN-001",
            phone="555-1234",
            email="john.doe@example.com",
            address="123 Main St",
            is_active=True,
        )

        formatted = PatientContextTool._format_patient(patient)

        assert formatted["id"] == "pat-001"
        assert formatted["mrn"] == "MRN-001"
        assert formatted["first_name"] == "John"
        assert formatted["last_name"] == "Doe"
        assert formatted["full_name"] == "John Doe"
        assert formatted["gender"] == "M"
        assert formatted["phone"] == "555-1234"
        assert formatted["email"] == "john.doe@example.com"
        assert formatted["is_active"] is True
        assert formatted["age"] is not None
        assert formatted["age"] > 0

    def test_format_patient_without_dob(self):
        """Test formatting patient without date of birth."""
        patient = Patient(
            id="pat-001",
            first_name="John",
            last_name="Doe",
            date_of_birth=None,
            gender="M",
            mrn="MRN-001",
            is_active=True,
        )

        formatted = PatientContextTool._format_patient(patient)

        assert formatted["date_of_birth"] is None
        assert formatted["age"] is None


class TestEncounterFormatting:
    """Tests for encounter data formatting."""

    def test_format_encounter_active(self):
        """Test formatting active encounter."""
        encounter = Encounter(
            id="enc-001",
            patient_id="pat-001",
            care_unit_id="cu-001",
            encounter_type="inpatient",
            admission_time=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            discharge_time=None,
            is_active=True,
            chief_complaint="Chest pain",
            admission_diagnosis="Acute coronary syndrome",
        )

        formatted = PatientContextTool._format_encounter(encounter)

        assert formatted["id"] == "enc-001"
        assert formatted["patient_id"] == "pat-001"
        assert formatted["encounter_type"] == "inpatient"
        assert formatted["is_active"] is True
        assert formatted["chief_complaint"] == "Chest pain"
        assert formatted["discharge_time"] is None

    def test_format_encounter_discharged(self):
        """Test formatting discharged encounter."""
        encounter = Encounter(
            id="enc-001",
            patient_id="pat-001",
            care_unit_id="cu-001",
            encounter_type="inpatient",
            admission_time=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            discharge_time=datetime(2024, 1, 20, 14, 30, 0, tzinfo=timezone.utc),
            is_active=False,
            discharge_diagnosis="Stable",
        )

        formatted = PatientContextTool._format_encounter(encounter)

        assert formatted["is_active"] is False
        assert formatted["discharge_time"] is not None


class TestCareUnitFormatting:
    """Tests for care unit data formatting."""

    def test_format_care_unit(self):
        """Test formatting care unit."""
        care_unit = CareUnit(
            id="cu-001",
            name="Cardiology",
            code="CARDIO",
            description="Cardiology Department",
            location="Building A, Floor 3",
            unit_type="specialty",
            is_active=True,
        )

        formatted = PatientContextTool._format_care_unit(care_unit)

        assert formatted["id"] == "cu-001"
        assert formatted["name"] == "Cardiology"
        assert formatted["code"] == "CARDIO"
        assert formatted["unit_type"] == "specialty"
        assert formatted["is_active"] is True


class TestClinicianFormatting:
    """Tests for clinician data formatting."""

    def test_format_clinician(self):
        """Test formatting clinician."""
        clinician = Clinician(
            id="clin-001",
            first_name="Jane",
            last_name="Smith",
            email="jane.smith@example.com",
            phone="555-5678",
            role="physician",
            specialty="cardiology",
            license_number="LIC-001",
            is_active=True,
        )

        formatted = PatientContextTool._format_clinician(clinician)

        assert formatted["id"] == "clin-001"
        assert formatted["first_name"] == "Jane"
        assert formatted["last_name"] == "Smith"
        assert formatted["full_name"] == "Jane Smith"
        assert formatted["email"] == "jane.smith@example.com"
        assert formatted["role"] == "physician"
        assert formatted["specialty"] == "cardiology"
        assert formatted["is_active"] is True


class TestDeviceFormatting:
    """Tests for device data formatting."""

    def test_format_device(self):
        """Test formatting device."""
        device = Device(
            id="dev-001",
            encounter_id="enc-001",
            device_type="cardiac_monitor",
            device_name="Philips Monitor",
            serial_number="SN-12345",
            manufacturer="Philips",
            model="MP70",
            location="Bed 1",
            is_online=True,
            battery_level=95.0,
            calibration_status="calibrated",
            is_active=True,
        )

        formatted = PatientContextTool._format_device(device)

        assert formatted["id"] == "dev-001"
        assert formatted["device_type"] == "cardiac_monitor"
        assert formatted["device_name"] == "Philips Monitor"
        assert formatted["serial_number"] == "SN-12345"
        assert formatted["is_online"] is True
        assert formatted["battery_level"] == 95.0
        assert formatted["calibration_status"] == "calibrated"


class TestPatientContextNoEncounter:
    """Tests for patient context when no active encounter exists."""

    @pytest.mark.asyncio
    async def test_get_patient_clinical_context_no_active_encounter(
        self, db_session: AsyncSession
    ):
        """Test patient context retrieval when no active encounter exists."""
        # Create patient without encounter
        patient = Patient(
            id="pat-002",
            first_name="Jane",
            last_name="Smith",
            date_of_birth=datetime(1990, 3, 20, tzinfo=timezone.utc),
            gender="F",
            mrn="MRN-002",
            is_active=True,
        )
        db_session.add(patient)
        await db_session.commit()

        context = await PatientContextTool.get_patient_clinical_context(
            session=db_session,
            patient_id=patient.id,
        )

        assert context["patient"]["id"] == patient.id
        assert context["encounter"] is None
        assert context["care_unit"] is None
        assert len(context["clinicians"]) == 0
        assert len(context["devices"]) == 0


class TestPatientContextResponseStructure:
    """Tests for patient context response structure."""

    @pytest.mark.asyncio
    async def test_response_has_required_fields(
        self, db_session: AsyncSession, patient_with_encounter: tuple[Patient, Encounter]
    ):
        """Test that response has all required fields."""
        patient, _ = patient_with_encounter

        context = await PatientContextTool.get_patient_clinical_context(
            session=db_session,
            patient_id=patient.id,
        )

        # Check required top-level fields
        assert "patient" in context
        assert "encounter" in context
        assert "care_unit" in context
        assert "diagnoses" in context
        assert "medications" in context
        assert "clinicians" in context
        assert "devices" in context
        assert "recent_abnormal_observations" in context
        assert "confidence_score" in context
        assert "source_references" in context

        # Check source references
        assert len(context["source_references"]) > 0
        assert "source" in context["source_references"][0]
        assert "timestamp" in context["source_references"][0]
        assert "data_types" in context["source_references"][0]
