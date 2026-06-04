"""
Database module for Hospital Clinical Intelligence MCP Platform.

Provides:
- Async database connection pooling
- SQLAlchemy ORM models
- Database initialization utilities
"""

from mcp_server.database.connection import DatabaseConnection, get_db_session
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
    clinician_care_unit_assignments,
)

__all__ = [
    "DatabaseConnection",
    "get_db_session",
    "Base",
    "Patient",
    "Encounter",
    "CareUnit",
    "Clinician",
    "Device",
    "ClinicianAssignment",
    "PatientIDMapping",
    "EncounterIDMapping",
    "CareUnitIDMapping",
    "DeviceIDMapping",
    "ClinicianIDMapping",
    "clinician_care_unit_assignments",
]
