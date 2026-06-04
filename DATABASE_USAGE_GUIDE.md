# Database Usage Guide

## Quick Start

### Initialize Database

```bash
# Create tables
python -m mcp_server.database.init_db init

# Check database health
python -m mcp_server.database.init_db health

# Drop all tables (WARNING: deletes all data)
python -m mcp_server.database.init_db drop
```

### In FastAPI Application

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from mcp_server.database import DatabaseConnection, get_db_session, Patient

# Initialize on startup
@app.on_event("startup")
async def startup():
    await DatabaseConnection.initialize()

# Close on shutdown
@app.on_event("shutdown")
async def shutdown():
    await DatabaseConnection.close()

# Use in route handlers
@app.get("/patients/{patient_id}")
async def get_patient(patient_id: str, session: AsyncSession = Depends(get_db_session)):
    from sqlalchemy import select
    result = await session.execute(
        select(Patient).where(Patient.id == patient_id)
    )
    return result.scalar_one_or_none()
```

### Direct Usage

```python
from mcp_server.database import DatabaseConnection, Patient
from sqlalchemy import select

# Initialize
await DatabaseConnection.initialize()

# Get session
async for session in DatabaseConnection.get_session():
    # Query
    result = await session.execute(select(Patient))
    patients = result.scalars().all()
    
    # Create
    new_patient = Patient(
        id="PAT-001",
        first_name="John",
        last_name="Doe",
        mrn="MRN-12345"
    )
    session.add(new_patient)
    await session.commit()

# Close
await DatabaseConnection.close()
```

## Models

### Patient
```python
from mcp_server.database import Patient

patient = Patient(
    id="PAT-001",
    first_name="John",
    last_name="Doe",
    date_of_birth=datetime(1980, 1, 15),
    gender="M",
    mrn="MRN-12345",
    phone="555-1234",
    email="john@example.com",
    address="123 Main St",
    is_active=True
)
```

### Encounter
```python
from mcp_server.database import Encounter

encounter = Encounter(
    id="ENC-001",
    patient_id="PAT-001",
    care_unit_id="UNIT-001",
    encounter_type="admission",
    admission_time=datetime.utcnow(),
    chief_complaint="Chest pain",
    is_active=True
)
```

### CareUnit
```python
from mcp_server.database import CareUnit

care_unit = CareUnit(
    id="UNIT-001",
    name="Cardiology",
    code="CARDIO",
    description="Cardiology Department",
    location="Building A, Floor 3",
    unit_type="specialty",
    is_active=True
)
```

### Clinician
```python
from mcp_server.database import Clinician

clinician = Clinician(
    id="CLIN-001",
    first_name="Dr.",
    last_name="Smith",
    email="dr.smith@hospital.local",
    phone="555-5678",
    role="physician",
    specialty="Cardiology",
    license_number="LIC-12345",
    is_active=True
)
```

### Device
```python
from mcp_server.database import Device

device = Device(
    id="DEV-001",
    encounter_id="ENC-001",
    device_type="cardiac_monitor",
    device_name="Philips Monitor 1",
    serial_number="SN-12345",
    manufacturer="Philips",
    model="MP70",
    location="Bed 1",
    is_online=True,
    battery_level=95.0
)
```

### ID Mappings

```python
from mcp_server.database import PatientIDMapping, EncounterIDMapping

# Patient ID mapping
patient_mapping = PatientIDMapping(
    id="MAP-001",
    patient_id="PAT-001",
    external_id="EXT-PAT-001",
    source_system="HL7",
    id_type="MRN"
)

# Encounter ID mapping
encounter_mapping = EncounterIDMapping(
    id="MAP-002",
    encounter_id="ENC-001",
    external_id="EXT-ENC-001",
    source_system="HL7",
    id_type="VISIT_ID"
)
```

## Common Queries

### Get Patient with Encounters
```python
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from mcp_server.database import Patient

result = await session.execute(
    select(Patient)
    .where(Patient.id == "PAT-001")
    .options(selectinload(Patient.encounters))
)
patient = result.scalar_one_or_none()
```

### Get Active Encounters for Care Unit
```python
from sqlalchemy import select
from mcp_server.database import Encounter

result = await session.execute(
    select(Encounter)
    .where(
        (Encounter.care_unit_id == "UNIT-001") &
        (Encounter.is_active == True)
    )
)
encounters = result.scalars().all()
```

### Get Clinician Assignments
```python
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from mcp_server.database import Encounter

result = await session.execute(
    select(Encounter)
    .where(Encounter.id == "ENC-001")
    .options(selectinload(Encounter.clinician_assignments))
)
encounter = result.scalar_one_or_none()
assignments = encounter.clinician_assignments
```

### Find Patient by MRN
```python
from sqlalchemy import select
from mcp_server.database import Patient

result = await session.execute(
    select(Patient).where(Patient.mrn == "MRN-12345")
)
patient = result.scalar_one_or_none()
```

### Get Patient ID Mappings
```python
from sqlalchemy import select
from mcp_server.database import PatientIDMapping

result = await session.execute(
    select(PatientIDMapping)
    .where(PatientIDMapping.patient_id == "PAT-001")
)
mappings = result.scalars().all()
```

## Soft Delete

All models support soft delete via `is_deleted` flag:

```python
# Soft delete
patient.is_deleted = True
patient.deleted_at = datetime.utcnow()
await session.commit()

# Query only active records
result = await session.execute(
    select(Patient).where(Patient.is_deleted == False)
)
active_patients = result.scalars().all()
```

## Audit Fields

All models include audit fields:
- `created_at`: Timestamp when record was created
- `updated_at`: Timestamp when record was last updated
- `deleted_at`: Timestamp when record was soft deleted (if applicable)

```python
patient = Patient(...)
session.add(patient)
await session.commit()

print(f"Created: {patient.created_at}")
print(f"Updated: {patient.updated_at}")
```

## Connection Pool Status

```python
from mcp_server.database import DatabaseConnection

status = await DatabaseConnection.get_pool_status()
print(f"Pool size: {status['pool_size']}")
print(f"Checked out: {status['checked_out']}")
print(f"Overflow: {status['overflow']}")
print(f"Total: {status['total']}")
```

## Health Check

```python
from mcp_server.database import DatabaseConnection

is_healthy = await DatabaseConnection.health_check()
if is_healthy:
    print("Database is healthy")
else:
    print("Database connection failed")
```

## Configuration

Database settings are configured in `config.py`:

```python
database_url: str = "postgresql+asyncpg://user:password@localhost:5432/hospital_clinical_mcp"
database_pool_size: int = 20  # Number of connections to keep in pool
database_max_overflow: int = 10  # Additional connections beyond pool_size
database_pool_timeout: int = 30  # Timeout for getting connection from pool
database_pool_recycle: int = 3600  # Recycle connections after 1 hour
```

## Troubleshooting

### Connection Refused
- Ensure PostgreSQL is running
- Check database URL in config.py
- Verify credentials and database name

### Pool Exhausted
- Increase `database_pool_size` in config.py
- Check for connection leaks (sessions not being closed)
- Monitor pool status with `get_pool_status()`

### Unique Constraint Violations
- Check for duplicate values in unique fields (MRN, email, etc.)
- Use ID mappings to handle duplicate IDs from different sources

### Foreign Key Violations
- Ensure parent records exist before creating child records
- Check cascade delete settings if deleting parent records
