"""
SQLAlchemy ORM models for Hospital Clinical Intelligence MCP Platform.

This module defines all database models for core clinical entities:
- Patients: Demographics and identifiers
- Encounters: Episodes of care
- Care Units: Hospital departments
- Clinicians: Healthcare providers
- Devices: Medical monitoring/therapeutic equipment
- ID Mapping tables: For normalization across data sources
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class Patient(Base):
    """Patient demographics and core information."""

    __tablename__ = "patients"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Demographics
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    mrn: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, unique=True)

    # Contact information
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    encounters: Mapped[list["Encounter"]] = relationship(
        "Encounter", back_populates="patient", cascade="all, delete-orphan"
    )
    id_mappings: Mapped[list["PatientIDMapping"]] = relationship(
        "PatientIDMapping", back_populates="patient", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("idx_patient_mrn", "mrn"),
        Index("idx_patient_last_name", "last_name"),
        Index("idx_patient_is_active", "is_active"),
        Index("idx_patient_created_at", "created_at"),
    )


class Encounter(Base):
    """Patient encounters (episodes of care)."""

    __tablename__ = "encounters"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Foreign keys
    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patients.id"), nullable=False
    )
    care_unit_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("care_units.id"), nullable=False
    )

    # Encounter information
    encounter_type: Mapped[str] = mapped_column(String(50), nullable=False)
    admission_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    discharge_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Clinical information
    chief_complaint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    admission_diagnosis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    discharge_diagnosis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    patient: Mapped["Patient"] = relationship("Patient", back_populates="encounters")
    care_unit: Mapped["CareUnit"] = relationship("CareUnit", back_populates="encounters")
    devices: Mapped[list["Device"]] = relationship(
        "Device", back_populates="encounter", cascade="all, delete-orphan"
    )
    clinician_assignments: Mapped[list["ClinicianAssignment"]] = relationship(
        "ClinicianAssignment", back_populates="encounter", cascade="all, delete-orphan"
    )
    id_mappings: Mapped[list["EncounterIDMapping"]] = relationship(
        "EncounterIDMapping", back_populates="encounter", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("idx_encounter_patient_id", "patient_id"),
        Index("idx_encounter_care_unit_id", "care_unit_id"),
        Index("idx_encounter_admission_time", "admission_time"),
        Index("idx_encounter_is_active", "is_active"),
        Index("idx_encounter_created_at", "created_at"),
    )


class CareUnit(Base):
    """Hospital care units (departments)."""

    __tablename__ = "care_units"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Care unit information
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Unit type
    unit_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    encounters: Mapped[list["Encounter"]] = relationship(
        "Encounter", back_populates="care_unit", cascade="all, delete-orphan"
    )
    clinicians: Mapped[list["Clinician"]] = relationship(
        "Clinician", secondary="clinician_care_unit_assignments", back_populates="care_units"
    )
    id_mappings: Mapped[list["CareUnitIDMapping"]] = relationship(
        "CareUnitIDMapping", back_populates="care_unit", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("idx_care_unit_code", "code"),
        Index("idx_care_unit_is_active", "is_active"),
    )


class Clinician(Base):
    """Healthcare providers."""

    __tablename__ = "clinicians"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Personal information
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Professional information
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    specialty: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    license_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    care_units: Mapped[list["CareUnit"]] = relationship(
        "CareUnit", secondary="clinician_care_unit_assignments", back_populates="clinicians"
    )
    assignments: Mapped[list["ClinicianAssignment"]] = relationship(
        "ClinicianAssignment", back_populates="clinician", cascade="all, delete-orphan"
    )
    id_mappings: Mapped[list["ClinicianIDMapping"]] = relationship(
        "ClinicianIDMapping", back_populates="clinician", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("idx_clinician_email", "email"),
        Index("idx_clinician_role", "role"),
        Index("idx_clinician_is_active", "is_active"),
    )


class Device(Base):
    """Medical devices (monitors, ventilators, pumps, etc.)."""

    __tablename__ = "devices"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Foreign keys
    encounter_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("encounters.id"), nullable=True
    )

    # Device information
    device_type: Mapped[str] = mapped_column(String(100), nullable=False)
    device_name: Mapped[str] = mapped_column(String(100), nullable=False)
    serial_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Location and status
    location: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    battery_level: Mapped[Optional[Float]] = mapped_column(Float, nullable=True)
    calibration_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    encounter: Mapped[Optional["Encounter"]] = relationship("Encounter", back_populates="devices")
    id_mappings: Mapped[list["DeviceIDMapping"]] = relationship(
        "DeviceIDMapping", back_populates="device", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("idx_device_encounter_id", "encounter_id"),
        Index("idx_device_type", "device_type"),
        Index("idx_device_serial_number", "serial_number"),
        Index("idx_device_is_online", "is_online"),
        Index("idx_device_is_active", "is_active"),
    )


class ClinicianAssignment(Base):
    """Assignment of clinicians to encounters."""

    __tablename__ = "clinician_assignments"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Foreign keys
    clinician_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clinicians.id"), nullable=False
    )
    encounter_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("encounters.id"), nullable=False
    )

    # Assignment information
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    unassigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    clinician: Mapped["Clinician"] = relationship("Clinician", back_populates="assignments")
    encounter: Mapped["Encounter"] = relationship("Encounter", back_populates="clinician_assignments")

    # Indexes
    __table_args__ = (
        Index("idx_clinician_assignment_clinician_id", "clinician_id"),
        Index("idx_clinician_assignment_encounter_id", "encounter_id"),
        Index("idx_clinician_assignment_is_active", "is_active"),
        UniqueConstraint("clinician_id", "encounter_id", name="uq_clinician_encounter"),
    )


class PatientIDMapping(Base):
    """Mapping of external patient IDs to internal patient identifiers."""

    __tablename__ = "patient_id_mappings"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Foreign key
    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patients.id"), nullable=False
    )

    # Mapping information
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)
    id_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    patient: Mapped["Patient"] = relationship("Patient", back_populates="id_mappings")

    # Indexes
    __table_args__ = (
        Index("idx_patient_id_mapping_patient_id", "patient_id"),
        Index("idx_patient_id_mapping_external_id", "external_id"),
        Index("idx_patient_id_mapping_source_system", "source_system"),
        UniqueConstraint(
            "external_id", "source_system", name="uq_patient_external_id_source"
        ),
    )


class EncounterIDMapping(Base):
    """Mapping of external encounter IDs to internal encounter identifiers."""

    __tablename__ = "encounter_id_mappings"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Foreign key
    encounter_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("encounters.id"), nullable=False
    )

    # Mapping information
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)
    id_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    encounter: Mapped["Encounter"] = relationship("Encounter", back_populates="id_mappings")

    # Indexes
    __table_args__ = (
        Index("idx_encounter_id_mapping_encounter_id", "encounter_id"),
        Index("idx_encounter_id_mapping_external_id", "external_id"),
        Index("idx_encounter_id_mapping_source_system", "source_system"),
        UniqueConstraint(
            "external_id", "source_system", name="uq_encounter_external_id_source"
        ),
    )


class CareUnitIDMapping(Base):
    """Mapping of external care unit codes to internal care unit identifiers."""

    __tablename__ = "care_unit_id_mappings"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Foreign key
    care_unit_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("care_units.id"), nullable=False
    )

    # Mapping information
    external_code: Mapped[str] = mapped_column(String(50), nullable=False)
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)
    code_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    care_unit: Mapped["CareUnit"] = relationship("CareUnit", back_populates="id_mappings")

    # Indexes
    __table_args__ = (
        Index("idx_care_unit_id_mapping_care_unit_id", "care_unit_id"),
        Index("idx_care_unit_id_mapping_external_code", "external_code"),
        Index("idx_care_unit_id_mapping_source_system", "source_system"),
        UniqueConstraint(
            "external_code", "source_system", name="uq_care_unit_external_code_source"
        ),
    )


class DeviceIDMapping(Base):
    """Mapping of external device IDs to internal device identifiers."""

    __tablename__ = "device_id_mappings"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Foreign key
    device_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("devices.id"), nullable=False
    )

    # Mapping information
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)
    id_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    device: Mapped["Device"] = relationship("Device", back_populates="id_mappings")

    # Indexes
    __table_args__ = (
        Index("idx_device_id_mapping_device_id", "device_id"),
        Index("idx_device_id_mapping_external_id", "external_id"),
        Index("idx_device_id_mapping_source_system", "source_system"),
        UniqueConstraint(
            "external_id", "source_system", name="uq_device_external_id_source"
        ),
    )


class ClinicianIDMapping(Base):
    """Mapping of external clinician IDs to internal clinician identifiers."""

    __tablename__ = "clinician_id_mappings"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Foreign key
    clinician_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clinicians.id"), nullable=False
    )

    # Mapping information
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)
    id_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    clinician: Mapped["Clinician"] = relationship("Clinician", back_populates="id_mappings")

    # Indexes
    __table_args__ = (
        Index("idx_clinician_id_mapping_clinician_id", "clinician_id"),
        Index("idx_clinician_id_mapping_external_id", "external_id"),
        Index("idx_clinician_id_mapping_source_system", "source_system"),
        UniqueConstraint(
            "external_id", "source_system", name="uq_clinician_external_id_source"
        ),
    )


# Association table for clinician-care_unit many-to-many relationship
from sqlalchemy import Column, Table

clinician_care_unit_assignments = Table(
    "clinician_care_unit_assignments",
    Base.metadata,
    Column("clinician_id", String(36), ForeignKey("clinicians.id"), primary_key=True),
    Column("care_unit_id", String(36), ForeignKey("care_units.id"), primary_key=True),
    Column("assigned_at", DateTime, default=lambda: datetime.now(timezone.utc), nullable=False),
)
