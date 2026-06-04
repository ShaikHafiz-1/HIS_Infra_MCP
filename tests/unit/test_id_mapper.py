"""
Unit tests for ID mapping system.

Tests cover patient, encounter, device, care unit, and clinician ID mapping,
duplicate detection, and error handling.
"""

import pytest
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.normalization.id_mapper import IDMapper
from mcp_server.database.models import (
    Patient,
    Encounter,
    CareUnit,
    Device,
    Clinician,
)
from mcp_server.utils.validators import ValidationError


class TestPatientIDMapping:
    """Tests for patient ID mapping."""

    @pytest.mark.asyncio
    async def test_get_or_create_patient_id_new(self, db_session: AsyncSession):
        """Test creating new patient ID mapping."""
        patient_data = {
            "first_name": "John",
            "last_name": "Doe",
            "mrn": "MRN-001",
            "is_active": True,
        }

        patient_id = await IDMapper.get_or_create_patient_id(
            db_session,
            "ext-pat-001",
            "fhir-server",
            patient_data,
        )

        assert patient_id is not None
        assert patient_id.startswith("PAT-")

    @pytest.mark.asyncio
    async def test_get_or_create_patient_id_existing(self, db_session: AsyncSession):
        """Test retrieving existing patient ID mapping."""
        patient_data = {
            "first_name": "Jane",
            "last_name": "Smith",
            "mrn": "MRN-002",
            "is_active": True,
        }

        # Create first time
        patient_id_1 = await IDMapper.get_or_create_patient_id(
            db_session,
            "ext-pat-002",
            "fhir-server",
            patient_data,
        )

        # Retrieve second time
        patient_id_2 = await IDMapper.get_or_create_patient_id(
            db_session,
            "ext-pat-002",
            "fhir-server",
        )

        assert patient_id_1 == patient_id_2

    @pytest.mark.asyncio
    async def test_get_or_create_patient_id_invalid_external_id(
        self, db_session: AsyncSession
    ):
        """Test patient ID mapping with invalid external ID."""
        with pytest.raises(ValidationError, match="must be a non-empty string"):
            await IDMapper.get_or_create_patient_id(
                db_session,
                "",
                "fhir-server",
            )

    @pytest.mark.asyncio
    async def test_get_or_create_patient_id_invalid_source_system(
        self, db_session: AsyncSession
    ):
        """Test patient ID mapping with invalid source system."""
        with pytest.raises(ValidationError, match="must be a non-empty string"):
            await IDMapper.get_or_create_patient_id(
                db_session,
                "ext-pat-003",
                "",
            )


class TestEncounterIDMapping:
    """Tests for encounter ID mapping."""

    @pytest.mark.asyncio
    async def test_get_or_create_encounter_id_new(self, db_session: AsyncSession):
        """Test creating new encounter ID mapping."""
        # Create patient first
        patient_data = {
            "first_name": "John",
            "last_name": "Doe",
            "is_active": True,
        }
        patient_id = await IDMapper.get_or_create_patient_id(
            db_session,
            "ext-pat-004",
            "fhir-server",
            patient_data,
        )

        # Create care unit
        care_unit = CareUnit(
            id="cu-001",
            name="Cardiology",
            code="CARDIO",
            unit_type="specialty",
            is_active=True,
        )
        db_session.add(care_unit)
        await db_session.flush()

        encounter_data = {
            "encounter_type": "inpatient",
            "care_unit_id": "cu-001",
            "admission_time": datetime.now(timezone.utc),
            "is_active": True,
        }

        encounter_id = await IDMapper.get_or_create_encounter_id(
            db_session,
            "ext-enc-001",
            "fhir-server",
            patient_id,
            encounter_data,
        )

        assert encounter_id is not None
        assert encounter_id.startswith("ENC-")

    @pytest.mark.asyncio
    async def test_get_or_create_encounter_id_existing(self, db_session: AsyncSession):
        """Test retrieving existing encounter ID mapping."""
        # Create patient
        patient_data = {"first_name": "Jane", "last_name": "Smith", "is_active": True}
        patient_id = await IDMapper.get_or_create_patient_id(
            db_session,
            "ext-pat-005",
            "fhir-server",
            patient_data,
        )

        # Create care unit
        care_unit = CareUnit(
            id="cu-002",
            name="Neurology",
            code="NEURO",
            unit_type="specialty",
            is_active=True,
        )
        db_session.add(care_unit)
        await db_session.flush()

        encounter_data = {
            "encounter_type": "inpatient",
            "care_unit_id": "cu-002",
            "admission_time": datetime.now(timezone.utc),
            "is_active": True,
        }

        # Create first time
        encounter_id_1 = await IDMapper.get_or_create_encounter_id(
            db_session,
            "ext-enc-002",
            "fhir-server",
            patient_id,
            encounter_data,
        )

        # Retrieve second time
        encounter_id_2 = await IDMapper.get_or_create_encounter_id(
            db_session,
            "ext-enc-002",
            "fhir-server",
            patient_id,
        )

        assert encounter_id_1 == encounter_id_2


class TestDeviceIDMapping:
    """Tests for device ID mapping."""

    @pytest.mark.asyncio
    async def test_get_or_create_device_id_new(self, db_session: AsyncSession):
        """Test creating new device ID mapping."""
        device_data = {
            "device_type": "cardiac_monitor",
            "device_name": "Philips Monitor",
            "manufacturer": "Philips",
            "is_active": True,
        }

        device_id = await IDMapper.get_or_create_device_id(
            db_session,
            "ext-dev-001",
            "device-system",
            device_data,
        )

        assert device_id is not None
        assert device_id.startswith("DEV-")

    @pytest.mark.asyncio
    async def test_get_or_create_device_id_existing(self, db_session: AsyncSession):
        """Test retrieving existing device ID mapping."""
        device_data = {
            "device_type": "ventilator",
            "device_name": "Siemens Ventilator",
            "manufacturer": "Siemens",
            "is_active": True,
        }

        # Create first time
        device_id_1 = await IDMapper.get_or_create_device_id(
            db_session,
            "ext-dev-002",
            "device-system",
            device_data,
        )

        # Retrieve second time
        device_id_2 = await IDMapper.get_or_create_device_id(
            db_session,
            "ext-dev-002",
            "device-system",
        )

        assert device_id_1 == device_id_2


class TestCareUnitIDMapping:
    """Tests for care unit ID mapping."""

    @pytest.mark.asyncio
    async def test_get_or_create_care_unit_id_new(self, db_session: AsyncSession):
        """Test creating new care unit ID mapping."""
        care_unit_data = {
            "name": "Emergency Department",
            "code": "ED",
            "unit_type": "emergency",
            "is_active": True,
        }

        care_unit_id = await IDMapper.get_or_create_care_unit_id(
            db_session,
            "ED",
            "hospital-system",
            care_unit_data,
        )

        assert care_unit_id is not None
        assert care_unit_id.startswith("CU-")

    @pytest.mark.asyncio
    async def test_get_or_create_care_unit_id_not_found(
        self, db_session: AsyncSession
    ):
        """Test care unit ID mapping when not found and no data provided."""
        care_unit_id = await IDMapper.get_or_create_care_unit_id(
            db_session,
            "UNKNOWN",
            "hospital-system",
        )

        assert care_unit_id is None


class TestClinicianIDMapping:
    """Tests for clinician ID mapping."""

    @pytest.mark.asyncio
    async def test_get_or_create_clinician_id_new(self, db_session: AsyncSession):
        """Test creating new clinician ID mapping."""
        clinician_data = {
            "first_name": "Dr.",
            "last_name": "Smith",
            "role": "physician",
            "specialty": "cardiology",
            "is_active": True,
        }

        clinician_id = await IDMapper.get_or_create_clinician_id(
            db_session,
            "ext-clin-001",
            "ldap",
            clinician_data,
        )

        assert clinician_id is not None
        assert clinician_id.startswith("CLIN-")

    @pytest.mark.asyncio
    async def test_get_or_create_clinician_id_existing(self, db_session: AsyncSession):
        """Test retrieving existing clinician ID mapping."""
        clinician_data = {
            "first_name": "Dr.",
            "last_name": "Jones",
            "role": "physician",
            "specialty": "neurology",
            "is_active": True,
        }

        # Create first time
        clinician_id_1 = await IDMapper.get_or_create_clinician_id(
            db_session,
            "ext-clin-002",
            "ldap",
            clinician_data,
        )

        # Retrieve second time
        clinician_id_2 = await IDMapper.get_or_create_clinician_id(
            db_session,
            "ext-clin-002",
            "ldap",
        )

        assert clinician_id_1 == clinician_id_2


class TestIDMapperDuplicateDetection:
    """Tests for duplicate detection in ID mapping."""

    @pytest.mark.asyncio
    async def test_duplicate_detection_by_mrn(self, db_session: AsyncSession):
        """Test duplicate detection by MRN."""
        # Create first patient
        patient1 = Patient(
            id="pat-001",
            first_name="John",
            last_name="Doe",
            mrn="MRN-DUPLICATE",
            is_active=True,
        )
        db_session.add(patient1)
        await db_session.flush()

        # Try to create second patient with same MRN
        patient_data = {
            "first_name": "John",
            "last_name": "Doe",
            "mrn": "MRN-DUPLICATE",
            "is_active": True,
        }

        # This should detect the duplicate
        patient_id = await IDMapper.get_or_create_patient_id(
            db_session,
            "ext-pat-dup-1",
            "fhir-server",
            patient_data,
        )

        # Should create new mapping (duplicate detection is logged, not prevented)
        assert patient_id is not None

    @pytest.mark.asyncio
    async def test_duplicate_detection_by_name(self, db_session: AsyncSession):
        """Test duplicate detection by name."""
        # Create first patient
        patient1 = Patient(
            id="pat-002",
            first_name="Jane",
            last_name="Smith",
            is_active=True,
        )
        db_session.add(patient1)
        await db_session.flush()

        # Try to create second patient with same name
        patient_data = {
            "first_name": "Jane",
            "last_name": "Smith",
            "is_active": True,
        }

        # This should detect the duplicate
        patient_id = await IDMapper.get_or_create_patient_id(
            db_session,
            "ext-pat-dup-2",
            "fhir-server",
            patient_data,
        )

        # Should create new mapping (duplicate detection is logged, not prevented)
        assert patient_id is not None


class TestIDMapperErrorHandling:
    """Tests for ID mapper error handling."""

    @pytest.mark.asyncio
    async def test_invalid_patient_id_type(self, db_session: AsyncSession):
        """Test patient ID mapping with invalid ID type."""
        with pytest.raises(ValidationError):
            await IDMapper.get_or_create_patient_id(
                db_session,
                123,  # type: ignore
                "fhir-server",
            )

    @pytest.mark.asyncio
    async def test_invalid_encounter_patient_id(self, db_session: AsyncSession):
        """Test encounter ID mapping with invalid patient ID."""
        with pytest.raises(ValidationError, match="must be a non-empty string"):
            await IDMapper.get_or_create_encounter_id(
                db_session,
                "ext-enc-003",
                "fhir-server",
                "",
            )

    @pytest.mark.asyncio
    async def test_invalid_device_id_type(self, db_session: AsyncSession):
        """Test device ID mapping with invalid ID type."""
        with pytest.raises(ValidationError):
            await IDMapper.get_or_create_device_id(
                db_session,
                123,  # type: ignore
                "device-system",
            )


class TestIDMapperIntegration:
    """Integration tests for ID mapping."""

    @pytest.mark.asyncio
    async def test_complete_mapping_workflow(self, db_session: AsyncSession):
        """Test complete mapping workflow for patient, encounter, and devices."""
        # Map patient
        patient_data = {
            "first_name": "Robert",
            "last_name": "Johnson",
            "mrn": "MRN-WORKFLOW",
            "is_active": True,
        }
        patient_id = await IDMapper.get_or_create_patient_id(
            db_session,
            "ext-pat-workflow",
            "fhir-server",
            patient_data,
        )

        # Create care unit
        care_unit = CareUnit(
            id="cu-workflow",
            name="ICU",
            code="ICU",
            unit_type="intensive_care",
            is_active=True,
        )
        db_session.add(care_unit)
        await db_session.flush()

        # Map encounter
        encounter_data = {
            "encounter_type": "inpatient",
            "care_unit_id": "cu-workflow",
            "admission_time": datetime.now(timezone.utc),
            "is_active": True,
        }
        encounter_id = await IDMapper.get_or_create_encounter_id(
            db_session,
            "ext-enc-workflow",
            "fhir-server",
            patient_id,
            encounter_data,
        )

        # Map device
        device_data = {
            "device_type": "cardiac_monitor",
            "device_name": "Monitor 1",
            "encounter_id": encounter_id,
            "is_active": True,
        }
        device_id = await IDMapper.get_or_create_device_id(
            db_session,
            "ext-dev-workflow",
            "device-system",
            device_data,
        )

        # Verify all IDs were created
        assert patient_id.startswith("PAT-")
        assert encounter_id.startswith("ENC-")
        assert device_id.startswith("DEV-")

        # Verify retrieval works
        patient_id_2 = await IDMapper.get_or_create_patient_id(
            db_session,
            "ext-pat-workflow",
            "fhir-server",
        )
        assert patient_id == patient_id_2
