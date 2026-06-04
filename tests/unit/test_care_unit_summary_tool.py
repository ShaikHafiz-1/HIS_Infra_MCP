"""
Unit tests for care unit summary tool.

Tests cover care unit summary retrieval, patient aggregation, critical patient
identification, clinician workload calculation, and error handling.
"""

import pytest
from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.tools.care_unit_summary import CareUnitSummaryTool
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
async def care_unit(db_session: AsyncSession) -> CareUnit:
    """Create a care unit."""
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
    await db_session.commit()
    return care_unit


@pytest.fixture
async def patients_with_encounters(
    db_session: AsyncSession, care_unit: CareUnit
) -> list[tuple[Patient, Encounter]]:
    """Create multiple patients with encounters in a care unit."""
    patients_encounters = []

    for i in range(3):
        patient = Patient(
            id=f"pat-{i:03d}",
            first_name=f"Patient{i}",
            last_name=f"Test{i}",
            date_of_birth=datetime(1980 + i, 5, 15, tzinfo=timezone.utc),
            gender="M" if i % 2 == 0 else "F",
            mrn=f"MRN-{i:03d}",
            phone=f"555-{1000 + i}",
            email=f"patient{i}@example.com",
            is_active=True,
        )
        db_session.add(patient)

        encounter = Encounter(
            id=f"enc-{i:03d}",
            patient_id=patient.id,
            care_unit_id=care_unit.id,
            encounter_type="inpatient",
            admission_time=datetime(2024, 1, 15 + i, 10, 0, 0, tzinfo=timezone.utc),
            discharge_time=None,
            is_active=True,
            chief_complaint=f"Chief complaint {i}",
            admission_diagnosis=f"Diagnosis {i}",
        )
        db_session.add(encounter)

        patients_encounters.append((patient, encounter))

    await db_session.commit()
    return patients_encounters


@pytest.fixture
async def clinicians_assigned(
    db_session: AsyncSession, patients_with_encounters: list[tuple[Patient, Encounter]]
) -> list[Clinician]:
    """Create clinicians assigned to encounters."""
    clinicians = []

    for i in range(2):
        clinician = Clinician(
            id=f"clin-{i:03d}",
            first_name=f"Clinician{i}",
            last_name=f"Test{i}",
            email=f"clinician{i}@example.com",
            phone=f"555-9000 + {i}",
            role="physician" if i == 0 else "nurse",
            specialty="cardiology",
            license_number=f"LIC-{i:03d}",
            is_active=True,
        )
        db_session.add(clinician)
        clinicians.append(clinician)

    await db_session.commit()

    # Assign clinicians to encounters
    for i, (_, encounter) in enumerate(patients_with_encounters):
        clinician = clinicians[i % len(clinicians)]
        assignment = ClinicianAssignment(
            id=f"assign-{i:03d}",
            clinician_id=clinician.id,
            encounter_id=encounter.id,
            role="attending_physician" if clinician.role == "physician" else "nurse",
            is_active=True,
        )
        db_session.add(assignment)

    await db_session.commit()
    return clinicians


@pytest.fixture
async def devices_in_encounters(
    db_session: AsyncSession, patients_with_encounters: list[tuple[Patient, Encounter]]
) -> list[Device]:
    """Create devices in encounters."""
    devices = []

    for i, (_, encounter) in enumerate(patients_with_encounters):
        device = Device(
            id=f"dev-{i:03d}",
            encounter_id=encounter.id,
            device_type="cardiac_monitor" if i % 2 == 0 else "ventilator",
            device_name=f"Device {i}",
            serial_number=f"SN-{i:05d}",
            manufacturer="Philips" if i % 2 == 0 else "Siemens",
            model="MP70" if i % 2 == 0 else "SERVO-i",
            location=f"Bed {i + 1}",
            is_online=True,
            battery_level=95.0 - (i * 5),
            calibration_status="calibrated",
            is_active=True,
        )
        db_session.add(device)
        devices.append(device)

    await db_session.commit()
    return devices


class TestCareUnitSummaryRetrieval:
    """Tests for care unit summary retrieval."""

    @pytest.mark.asyncio
    async def test_get_care_unit_summary_success(
        self,
        db_session: AsyncSession,
        care_unit: CareUnit,
        patients_with_encounters: list[tuple[Patient, Encounter]],
        clinicians_assigned: list[Clinician],
        devices_in_encounters: list[Device],
    ):
        """Test successful care unit summary retrieval."""
        summary = await CareUnitSummaryTool.get_care_unit_summary(
            session=db_session,
            care_unit_id=care_unit.id,
        )

        assert summary is not None
        assert summary["care_unit"]["id"] == care_unit.id
        assert summary["care_unit"]["name"] == "Cardiology"
        assert summary["patient_count"] == 3
        assert len(summary["active_patients"]) == 3
        assert summary["confidence_score"] == 0.92

    @pytest.mark.asyncio
    async def test_get_care_unit_summary_includes_patients(
        self,
        db_session: AsyncSession,
        care_unit: CareUnit,
        patients_with_encounters: list[tuple[Patient, Encounter]],
    ):
        """Test care unit summary includes all active patients."""
        summary = await CareUnitSummaryTool.get_care_unit_summary(
            session=db_session,
            care_unit_id=care_unit.id,
        )

        patient_ids = [p["patient_id"] for p in summary["active_patients"]]
        for patient, _ in patients_with_encounters:
            assert patient.id in patient_ids

    @pytest.mark.asyncio
    async def test_get_care_unit_summary_includes_clinicians(
        self,
        db_session: AsyncSession,
        care_unit: CareUnit,
        patients_with_encounters: list[tuple[Patient, Encounter]],
        clinicians_assigned: list[Clinician],
    ):
        """Test care unit summary includes clinician assignments."""
        summary = await CareUnitSummaryTool.get_care_unit_summary(
            session=db_session,
            care_unit_id=care_unit.id,
        )

        assert len(summary["clinician_assignments"]) > 0
        clinician_ids = [c["clinician_id"] for c in summary["clinician_assignments"]]
        for clinician in clinicians_assigned:
            assert clinician.id in clinician_ids

    @pytest.mark.asyncio
    async def test_get_care_unit_summary_includes_devices(
        self,
        db_session: AsyncSession,
        care_unit: CareUnit,
        patients_with_encounters: list[tuple[Patient, Encounter]],
        devices_in_encounters: list[Device],
    ):
        """Test care unit summary includes active devices."""
        summary = await CareUnitSummaryTool.get_care_unit_summary(
            session=db_session,
            care_unit_id=care_unit.id,
        )

        for patient_summary in summary["active_patients"]:
            assert "active_devices" in patient_summary
            assert isinstance(patient_summary["active_devices"], list)

    @pytest.mark.asyncio
    async def test_get_care_unit_summary_care_unit_not_found(
        self, db_session: AsyncSession
    ):
        """Test care unit summary retrieval with nonexistent care unit."""
        with pytest.raises(ValidationError, match="Care unit not found"):
            await CareUnitSummaryTool.get_care_unit_summary(
                session=db_session,
                care_unit_id="nonexistent-care-unit",
            )

    @pytest.mark.asyncio
    async def test_get_care_unit_summary_invalid_care_unit_id(
        self, db_session: AsyncSession
    ):
        """Test care unit summary retrieval with invalid care unit ID."""
        with pytest.raises(ValidationError, match="must be a non-empty string"):
            await CareUnitSummaryTool.get_care_unit_summary(
                session=db_session,
                care_unit_id="",
            )

    @pytest.mark.asyncio
    async def test_get_care_unit_summary_invalid_care_unit_id_type(
        self, db_session: AsyncSession
    ):
        """Test care unit summary retrieval with invalid care unit ID type."""
        with pytest.raises(ValidationError, match="must be a non-empty string"):
            await CareUnitSummaryTool.get_care_unit_summary(
                session=db_session,
                care_unit_id=123,  # type: ignore
            )


class TestCareUnitSummaryFormatting:
    """Tests for care unit summary data formatting."""

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

        formatted = CareUnitSummaryTool._format_care_unit(care_unit)

        assert formatted["id"] == "cu-001"
        assert formatted["name"] == "Cardiology"
        assert formatted["code"] == "CARDIO"
        assert formatted["unit_type"] == "specialty"
        assert formatted["is_active"] is True

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

        formatted = CareUnitSummaryTool._format_device(device)

        assert formatted["id"] == "dev-001"
        assert formatted["device_type"] == "cardiac_monitor"
        assert formatted["is_online"] is True
        assert formatted["battery_level"] == 95.0

    def test_format_clinician_assignment(self):
        """Test formatting clinician assignment."""
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

        assignment = ClinicianAssignment(
            id="assign-001",
            clinician_id="clin-001",
            encounter_id="enc-001",
            role="attending_physician",
            is_active=True,
        )
        assignment.clinician = clinician

        formatted = CareUnitSummaryTool._format_clinician_assignment(assignment)

        assert formatted["clinician_id"] == "clin-001"
        assert formatted["full_name"] == "Jane Smith"
        assert formatted["role"] == "physician"
        assert formatted["assignment_role"] == "attending_physician"


class TestCareUnitSummaryAgeCalculation:
    """Tests for age calculation."""

    def test_calculate_age_with_valid_dob(self):
        """Test age calculation with valid date of birth."""
        dob = datetime(1980, 5, 15, tzinfo=timezone.utc)
        age = CareUnitSummaryTool._calculate_age(dob)

        assert age is not None
        assert age > 0
        assert age >= 43  # At least 43 years old

    def test_calculate_age_without_dob(self):
        """Test age calculation without date of birth."""
        age = CareUnitSummaryTool._calculate_age(None)

        assert age is None

    def test_calculate_age_recent_birthday(self):
        """Test age calculation for recent birthday."""
        today = datetime.now(timezone.utc)
        dob = datetime(today.year - 30, today.month, today.day, tzinfo=timezone.utc)
        age = CareUnitSummaryTool._calculate_age(dob)

        assert age == 30

    def test_calculate_age_upcoming_birthday(self):
        """Test age calculation for upcoming birthday."""
        today = datetime.now(timezone.utc)
        dob = datetime(
            today.year - 30,
            today.month + 1 if today.month < 12 else 1,
            today.day,
            tzinfo=timezone.utc,
        )
        age = CareUnitSummaryTool._calculate_age(dob)

        assert age == 29


class TestCareUnitSummaryResponseStructure:
    """Tests for care unit summary response structure."""

    @pytest.mark.asyncio
    async def test_response_has_required_fields(
        self,
        db_session: AsyncSession,
        care_unit: CareUnit,
        patients_with_encounters: list[tuple[Patient, Encounter]],
    ):
        """Test that response has all required fields."""
        summary = await CareUnitSummaryTool.get_care_unit_summary(
            session=db_session,
            care_unit_id=care_unit.id,
        )

        # Check required top-level fields
        assert "care_unit" in summary
        assert "active_patients" in summary
        assert "critical_patients" in summary
        assert "patient_count" in summary
        assert "critical_patient_count" in summary
        assert "clinician_assignments" in summary
        assert "confidence_score" in summary
        assert "source_references" in summary

        # Check source references
        assert len(summary["source_references"]) > 0
        assert "source" in summary["source_references"][0]
        assert "timestamp" in summary["source_references"][0]
        assert "data_types" in summary["source_references"][0]

    @pytest.mark.asyncio
    async def test_patient_summary_has_required_fields(
        self,
        db_session: AsyncSession,
        care_unit: CareUnit,
        patients_with_encounters: list[tuple[Patient, Encounter]],
    ):
        """Test that each patient summary has required fields."""
        summary = await CareUnitSummaryTool.get_care_unit_summary(
            session=db_session,
            care_unit_id=care_unit.id,
        )

        for patient_summary in summary["active_patients"]:
            assert "patient_id" in patient_summary
            assert "mrn" in patient_summary
            assert "first_name" in patient_summary
            assert "last_name" in patient_summary
            assert "full_name" in patient_summary
            assert "age" in patient_summary
            assert "encounter_id" in patient_summary
            assert "is_critical" in patient_summary
            assert "active_devices" in patient_summary
            assert "assigned_clinicians" in patient_summary
            assert "confidence_score" in patient_summary


class TestCareUnitSummaryEmptyCareUnit:
    """Tests for care unit summary with no patients."""

    @pytest.mark.asyncio
    async def test_get_care_unit_summary_empty_care_unit(
        self, db_session: AsyncSession, care_unit: CareUnit
    ):
        """Test care unit summary retrieval for empty care unit."""
        summary = await CareUnitSummaryTool.get_care_unit_summary(
            session=db_session,
            care_unit_id=care_unit.id,
        )

        assert summary["patient_count"] == 0
        assert len(summary["active_patients"]) == 0
        assert summary["critical_patient_count"] == 0
        assert len(summary["critical_patients"]) == 0
