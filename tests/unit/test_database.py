"""
Unit tests for database connection and models.

Tests cover:
- Database connection pool initialization and lifecycle
- ORM model creation and relationships
- Database schema validation
- Connection health checks
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from mcp_server.database.connection import DatabaseConnection
from mcp_server.database.models import (
    Base,
    Patient,
    Encounter,
    CareUnit,
    Clinician,
    Device,
    ClinicianAssignment,
    PatientIDMapping,
    EncounterIDMapping,
    CareUnitIDMapping,
    DeviceIDMapping,
    ClinicianIDMapping,
)


@pytest.fixture
async def test_db():
    """Create an in-memory SQLite database for testing."""
    # Use SQLite with asyncio support for testing
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with engine.begin() as conn:
        session = AsyncSession(engine, expire_on_commit=False)
        yield session
        await session.close()
    
    await engine.dispose()


@pytest.fixture
async def sample_care_unit(test_db: AsyncSession) -> CareUnit:
    """Create a sample care unit for testing."""
    care_unit = CareUnit(
        id="UNIT-001",
        name="Cardiology",
        code="CARDIO",
        description="Cardiology Department",
        location="Building A, Floor 3",
        unit_type="specialty",
        is_active=True,
    )
    test_db.add(care_unit)
    await test_db.commit()
    return care_unit


@pytest.fixture
async def sample_patient(test_db: AsyncSession) -> Patient:
    """Create a sample patient for testing."""
    patient = Patient(
        id="PAT-001",
        first_name="John",
        last_name="Doe",
        date_of_birth=datetime(1980, 1, 15),
        gender="M",
        mrn="MRN-12345",
        phone="555-1234",
        email="john.doe@example.com",
        address="123 Main St",
        is_active=True,
    )
    test_db.add(patient)
    await test_db.commit()
    return patient


@pytest.fixture
async def sample_clinician(test_db: AsyncSession) -> Clinician:
    """Create a sample clinician for testing."""
    clinician = Clinician(
        id="CLIN-001",
        first_name="Dr.",
        last_name="Smith",
        email="dr.smith@hospital.local",
        phone="555-5678",
        role="physician",
        specialty="Cardiology",
        license_number="LIC-12345",
        is_active=True,
    )
    test_db.add(clinician)
    await test_db.commit()
    return clinician


class TestDatabaseConnection:
    """Tests for database connection management."""

    @pytest.mark.asyncio
    async def test_connection_initialization(self):
        """Test database connection pool initialization."""
        # This test would require a real database
        # For now, we test the connection class structure
        assert hasattr(DatabaseConnection, "initialize")
        assert hasattr(DatabaseConnection, "close")
        assert hasattr(DatabaseConnection, "get_session")
        assert hasattr(DatabaseConnection, "get_engine")
        assert hasattr(DatabaseConnection, "health_check")

    @pytest.mark.asyncio
    async def test_get_session_requires_initialization(self):
        """Test that get_session raises error if not initialized."""
        # Reset the engine
        DatabaseConnection._engine = None
        DatabaseConnection._session_factory = None
        
        with pytest.raises(RuntimeError, match="Database not initialized"):
            async for _ in DatabaseConnection.get_session():
                pass

    @pytest.mark.asyncio
    async def test_get_engine_requires_initialization(self):
        """Test that get_engine raises error if not initialized."""
        # Reset the engine
        DatabaseConnection._engine = None
        
        with pytest.raises(RuntimeError, match="Database not initialized"):
            await DatabaseConnection.get_engine()


class TestPatientModel:
    """Tests for Patient ORM model."""

    @pytest.mark.asyncio
    async def test_patient_creation(self, test_db: AsyncSession, sample_patient: Patient):
        """Test creating a patient record."""
        # Query the patient back
        result = await test_db.execute(
            select(Patient).where(Patient.id == "PAT-001")
        )
        patient = result.scalar_one_or_none()
        
        assert patient is not None
        assert patient.first_name == "John"
        assert patient.last_name == "Doe"
        assert patient.mrn == "MRN-12345"
        assert patient.is_active is True
        assert patient.is_deleted is False

    @pytest.mark.asyncio
    async def test_patient_soft_delete(self, test_db: AsyncSession, sample_patient: Patient):
        """Test soft delete functionality for patients."""
        patient = sample_patient
        patient.is_deleted = True
        patient.deleted_at = datetime.now(timezone.utc)
        await test_db.commit()
        
        # Query active patients
        result = await test_db.execute(
            select(Patient).where(Patient.is_deleted == False)
        )
        patients = result.scalars().all()
        
        assert len(patients) == 0

    @pytest.mark.asyncio
    async def test_patient_audit_fields(self, test_db: AsyncSession, sample_patient: Patient):
        """Test that audit fields are set correctly."""
        patient = sample_patient
        
        assert patient.created_at is not None
        assert patient.updated_at is not None
        assert patient.deleted_at is None
        assert isinstance(patient.created_at, datetime)
        assert isinstance(patient.updated_at, datetime)


class TestEncounterModel:
    """Tests for Encounter ORM model."""

    @pytest.mark.asyncio
    async def test_encounter_creation(
        self, test_db: AsyncSession, sample_patient: Patient, sample_care_unit: CareUnit
    ):
        """Test creating an encounter record."""
        encounter = Encounter(
            id="ENC-001",
            patient_id=sample_patient.id,
            care_unit_id=sample_care_unit.id,
            encounter_type="admission",
            admission_time=datetime.now(timezone.utc),
            is_active=True,
        )
        test_db.add(encounter)
        await test_db.commit()
        
        # Query the encounter back
        result = await test_db.execute(
            select(Encounter).where(Encounter.id == "ENC-001")
        )
        retrieved = result.scalar_one_or_none()
        
        assert retrieved is not None
        assert retrieved.patient_id == sample_patient.id
        assert retrieved.care_unit_id == sample_care_unit.id
        assert retrieved.encounter_type == "admission"

    @pytest.mark.asyncio
    async def test_encounter_relationships(
        self, test_db: AsyncSession, sample_patient: Patient, sample_care_unit: CareUnit
    ):
        """Test encounter relationships with patient and care unit."""
        encounter = Encounter(
            id="ENC-002",
            patient_id=sample_patient.id,
            care_unit_id=sample_care_unit.id,
            encounter_type="admission",
            admission_time=datetime.now(timezone.utc),
            is_active=True,
        )
        test_db.add(encounter)
        await test_db.commit()
        
        # Refresh to load relationships
        await test_db.refresh(encounter)
        
        assert encounter.patient.id == sample_patient.id
        assert encounter.care_unit.id == sample_care_unit.id


class TestCareUnitModel:
    """Tests for CareUnit ORM model."""

    @pytest.mark.asyncio
    async def test_care_unit_creation(self, test_db: AsyncSession, sample_care_unit: CareUnit):
        """Test creating a care unit record."""
        result = await test_db.execute(
            select(CareUnit).where(CareUnit.id == "UNIT-001")
        )
        care_unit = result.scalar_one_or_none()
        
        assert care_unit is not None
        assert care_unit.name == "Cardiology"
        assert care_unit.code == "CARDIO"
        assert care_unit.unit_type == "specialty"

    @pytest.mark.asyncio
    async def test_care_unit_unique_constraints(self, test_db: AsyncSession):
        """Test unique constraints on care unit."""
        care_unit1 = CareUnit(
            id="UNIT-001",
            name="Cardiology",
            code="CARDIO",
            unit_type="specialty",
        )
        test_db.add(care_unit1)
        await test_db.commit()
        
        # Try to create another with same name
        care_unit2 = CareUnit(
            id="UNIT-002",
            name="Cardiology",
            code="CARDIO2",
            unit_type="specialty",
        )
        test_db.add(care_unit2)
        
        with pytest.raises(Exception):  # IntegrityError
            await test_db.commit()


class TestClinicianModel:
    """Tests for Clinician ORM model."""

    @pytest.mark.asyncio
    async def test_clinician_creation(self, test_db: AsyncSession, sample_clinician: Clinician):
        """Test creating a clinician record."""
        result = await test_db.execute(
            select(Clinician).where(Clinician.id == "CLIN-001")
        )
        clinician = result.scalar_one_or_none()
        
        assert clinician is not None
        assert clinician.first_name == "Dr."
        assert clinician.last_name == "Smith"
        assert clinician.role == "physician"
        assert clinician.specialty == "Cardiology"

    @pytest.mark.asyncio
    async def test_clinician_email_unique(self, test_db: AsyncSession):
        """Test unique constraint on clinician email."""
        clinician1 = Clinician(
            id="CLIN-001",
            first_name="Dr.",
            last_name="Smith",
            email="dr.smith@hospital.local",
            role="physician",
        )
        test_db.add(clinician1)
        await test_db.commit()
        
        # Try to create another with same email
        clinician2 = Clinician(
            id="CLIN-002",
            first_name="Dr.",
            last_name="Jones",
            email="dr.smith@hospital.local",
            role="physician",
        )
        test_db.add(clinician2)
        
        with pytest.raises(Exception):  # IntegrityError
            await test_db.commit()


class TestDeviceModel:
    """Tests for Device ORM model."""

    @pytest.mark.asyncio
    async def test_device_creation(
        self, test_db: AsyncSession, sample_patient: Patient, sample_care_unit: CareUnit
    ):
        """Test creating a device record."""
        encounter = Encounter(
            id="ENC-001",
            patient_id=sample_patient.id,
            care_unit_id=sample_care_unit.id,
            encounter_type="admission",
            admission_time=datetime.now(timezone.utc),
        )
        test_db.add(encounter)
        await test_db.commit()
        
        device = Device(
            id="DEV-001",
            encounter_id=encounter.id,
            device_type="cardiac_monitor",
            device_name="Philips Monitor 1",
            serial_number="SN-12345",
            manufacturer="Philips",
            model="MP70",
            location="Bed 1",
            is_online=True,
            battery_level=95.0,
        )
        test_db.add(device)
        await test_db.commit()
        
        result = await test_db.execute(
            select(Device).where(Device.id == "DEV-001")
        )
        retrieved = result.scalar_one_or_none()
        
        assert retrieved is not None
        assert retrieved.device_type == "cardiac_monitor"
        assert retrieved.is_online is True
        assert retrieved.battery_level == 95.0


class TestIDMappingModels:
    """Tests for ID mapping models."""

    @pytest.mark.asyncio
    async def test_patient_id_mapping(self, test_db: AsyncSession, sample_patient: Patient):
        """Test patient ID mapping."""
        mapping = PatientIDMapping(
            id="MAP-001",
            patient_id=sample_patient.id,
            external_id="EXT-PAT-001",
            source_system="HL7",
            id_type="MRN",
        )
        test_db.add(mapping)
        await test_db.commit()
        
        result = await test_db.execute(
            select(PatientIDMapping).where(PatientIDMapping.id == "MAP-001")
        )
        retrieved = result.scalar_one_or_none()
        
        assert retrieved is not None
        assert retrieved.external_id == "EXT-PAT-001"
        assert retrieved.source_system == "HL7"

    @pytest.mark.asyncio
    async def test_encounter_id_mapping(
        self, test_db: AsyncSession, sample_patient: Patient, sample_care_unit: CareUnit
    ):
        """Test encounter ID mapping."""
        encounter = Encounter(
            id="ENC-001",
            patient_id=sample_patient.id,
            care_unit_id=sample_care_unit.id,
            encounter_type="admission",
            admission_time=datetime.now(timezone.utc),
        )
        test_db.add(encounter)
        await test_db.commit()
        
        mapping = EncounterIDMapping(
            id="MAP-002",
            encounter_id=encounter.id,
            external_id="EXT-ENC-001",
            source_system="HL7",
            id_type="VISIT_ID",
        )
        test_db.add(mapping)
        await test_db.commit()
        
        result = await test_db.execute(
            select(EncounterIDMapping).where(EncounterIDMapping.id == "MAP-002")
        )
        retrieved = result.scalar_one_or_none()
        
        assert retrieved is not None
        assert retrieved.external_id == "EXT-ENC-001"

    @pytest.mark.asyncio
    async def test_care_unit_id_mapping(self, test_db: AsyncSession, sample_care_unit: CareUnit):
        """Test care unit ID mapping."""
        mapping = CareUnitIDMapping(
            id="MAP-003",
            care_unit_id=sample_care_unit.id,
            external_code="CARDIO-EXT",
            source_system="HL7",
            code_type="DEPARTMENT_CODE",
        )
        test_db.add(mapping)
        await test_db.commit()
        
        result = await test_db.execute(
            select(CareUnitIDMapping).where(CareUnitIDMapping.id == "MAP-003")
        )
        retrieved = result.scalar_one_or_none()
        
        assert retrieved is not None
        assert retrieved.external_code == "CARDIO-EXT"

    @pytest.mark.asyncio
    async def test_device_id_mapping(
        self, test_db: AsyncSession, sample_patient: Patient, sample_care_unit: CareUnit
    ):
        """Test device ID mapping."""
        encounter = Encounter(
            id="ENC-001",
            patient_id=sample_patient.id,
            care_unit_id=sample_care_unit.id,
            encounter_type="admission",
            admission_time=datetime.now(timezone.utc),
        )
        test_db.add(encounter)
        await test_db.commit()
        
        device = Device(
            id="DEV-001",
            encounter_id=encounter.id,
            device_type="cardiac_monitor",
            device_name="Philips Monitor 1",
        )
        test_db.add(device)
        await test_db.commit()
        
        mapping = DeviceIDMapping(
            id="MAP-004",
            device_id=device.id,
            external_id="EXT-DEV-001",
            source_system="DEVICE_SYSTEM",
            id_type="DEVICE_ID",
        )
        test_db.add(mapping)
        await test_db.commit()
        
        result = await test_db.execute(
            select(DeviceIDMapping).where(DeviceIDMapping.id == "MAP-004")
        )
        retrieved = result.scalar_one_or_none()
        
        assert retrieved is not None
        assert retrieved.external_id == "EXT-DEV-001"

    @pytest.mark.asyncio
    async def test_clinician_id_mapping(self, test_db: AsyncSession, sample_clinician: Clinician):
        """Test clinician ID mapping."""
        mapping = ClinicianIDMapping(
            id="MAP-005",
            clinician_id=sample_clinician.id,
            external_id="EXT-CLIN-001",
            source_system="LDAP",
            id_type="EMPLOYEE_ID",
        )
        test_db.add(mapping)
        await test_db.commit()
        
        result = await test_db.execute(
            select(ClinicianIDMapping).where(ClinicianIDMapping.id == "MAP-005")
        )
        retrieved = result.scalar_one_or_none()
        
        assert retrieved is not None
        assert retrieved.external_id == "EXT-CLIN-001"


class TestClinicianAssignment:
    """Tests for clinician assignment model."""

    @pytest.mark.asyncio
    async def test_clinician_assignment_creation(
        self,
        test_db: AsyncSession,
        sample_clinician: Clinician,
        sample_patient: Patient,
        sample_care_unit: CareUnit,
    ):
        """Test creating a clinician assignment."""
        encounter = Encounter(
            id="ENC-001",
            patient_id=sample_patient.id,
            care_unit_id=sample_care_unit.id,
            encounter_type="admission",
            admission_time=datetime.now(timezone.utc),
        )
        test_db.add(encounter)
        await test_db.commit()
        
        assignment = ClinicianAssignment(
            id="ASSIGN-001",
            clinician_id=sample_clinician.id,
            encounter_id=encounter.id,
            role="attending_physician",
            assigned_at=datetime.now(timezone.utc),
            is_active=True,
        )
        test_db.add(assignment)
        await test_db.commit()
        
        result = await test_db.execute(
            select(ClinicianAssignment).where(ClinicianAssignment.id == "ASSIGN-001")
        )
        retrieved = result.scalar_one_or_none()
        
        assert retrieved is not None
        assert retrieved.role == "attending_physician"
        assert retrieved.is_active is True

    @pytest.mark.asyncio
    async def test_clinician_assignment_unique_constraint(
        self,
        test_db: AsyncSession,
        sample_clinician: Clinician,
        sample_patient: Patient,
        sample_care_unit: CareUnit,
    ):
        """Test unique constraint on clinician-encounter assignment."""
        encounter = Encounter(
            id="ENC-001",
            patient_id=sample_patient.id,
            care_unit_id=sample_care_unit.id,
            encounter_type="admission",
            admission_time=datetime.now(timezone.utc),
        )
        test_db.add(encounter)
        await test_db.commit()
        
        assignment1 = ClinicianAssignment(
            id="ASSIGN-001",
            clinician_id=sample_clinician.id,
            encounter_id=encounter.id,
            role="attending_physician",
        )
        test_db.add(assignment1)
        await test_db.commit()
        
        # Try to create another assignment for same clinician-encounter
        assignment2 = ClinicianAssignment(
            id="ASSIGN-002",
            clinician_id=sample_clinician.id,
            encounter_id=encounter.id,
            role="consulting_physician",
        )
        test_db.add(assignment2)
        
        with pytest.raises(Exception):  # IntegrityError
            await test_db.commit()


class TestDatabaseSchema:
    """Tests for overall database schema."""

    @pytest.mark.asyncio
    async def test_all_tables_created(self, test_db: AsyncSession):
        """Test that all expected tables are created."""
        # Get all table names from metadata
        table_names = {table.name for table in Base.metadata.tables.values()}
        
        expected_tables = {
            "patients",
            "encounters",
            "care_units",
            "clinicians",
            "devices",
            "clinician_assignments",
            "clinician_care_unit_assignments",
            "patient_id_mappings",
            "encounter_id_mappings",
            "care_unit_id_mappings",
            "device_id_mappings",
            "clinician_id_mappings",
        }
        
        assert expected_tables.issubset(table_names)

    @pytest.mark.asyncio
    async def test_foreign_key_relationships(
        self, test_db: AsyncSession, sample_patient: Patient, sample_care_unit: CareUnit
    ):
        """Test that foreign key relationships are properly defined."""
        encounter = Encounter(
            id="ENC-001",
            patient_id=sample_patient.id,
            care_unit_id=sample_care_unit.id,
            encounter_type="admission",
            admission_time=datetime.now(timezone.utc),
        )
        test_db.add(encounter)
        await test_db.commit()
        
        # Verify relationships work
        result = await test_db.execute(
            select(Encounter).where(Encounter.id == "ENC-001")
        )
        retrieved = result.scalar_one_or_none()
        
        assert retrieved.patient_id == sample_patient.id
        assert retrieved.care_unit_id == sample_care_unit.id

