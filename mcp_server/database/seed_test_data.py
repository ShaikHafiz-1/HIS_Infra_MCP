"""
Database seeding script for Hospital Clinical Intelligence MCP Platform.

This script populates the test database with realistic clinical data including:
- 50-100 patients
- 100-200 encounters
- 200-300 devices
- Sample HL7 messages
- Device telemetry data
"""

import asyncio
import logging
import sys
import uuid
from datetime import datetime
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from mcp_server.database.connection import DatabaseConnection
from mcp_server.database.models import (
    CareUnit,
    Clinician,
    Device,
    Encounter,
    Patient,
    PatientIDMapping,
    EncounterIDMapping,
    DeviceIDMapping,
    ClinicianIDMapping,
    CareUnitIDMapping,
)
from mcp_server.ingestion.test_data_generator import (
    PatientDataGenerator,
    EncounterDataGenerator,
    DeviceDataGenerator,
    HL7MessageGenerator,
    DeviceTelemetrySimulator,
)

logger = logging.getLogger(__name__)


class DatabaseSeeder:
    """Seed test database with realistic clinical data."""

    CARE_UNITS = [
        {
            "name": "Cardiology",
            "code": "CARDIO",
            "unit_type": "specialty",
            "location": "Building A, Floor 3",
        },
        {
            "name": "Emergency Department",
            "code": "ED",
            "unit_type": "emergency",
            "location": "Building A, Ground Floor",
        },
        {
            "name": "Neurology",
            "code": "NEURO",
            "unit_type": "specialty",
            "location": "Building B, Floor 2",
        },
        {
            "name": "Surgical Ward",
            "code": "SURG",
            "unit_type": "surgical",
            "location": "Building A, Floor 4",
        },
        {
            "name": "Operating Room",
            "code": "OR",
            "unit_type": "surgical",
            "location": "Building A, Floor 5",
        },
        {
            "name": "Intensive Care Unit",
            "code": "ICU",
            "unit_type": "critical_care",
            "location": "Building B, Floor 3",
        },
        {
            "name": "Radiology",
            "code": "RAD",
            "unit_type": "diagnostic",
            "location": "Building C, Ground Floor",
        },
        {
            "name": "General Ward",
            "code": "GEN",
            "unit_type": "general",
            "location": "Building B, Floor 1",
        },
    ]

    CLINICIANS = [
        {
            "first_name": "John",
            "last_name": "Smith",
            "email": "john.smith@hospital.com",
            "role": "physician",
            "specialty": "Cardiology",
        },
        {
            "first_name": "Sarah",
            "last_name": "Johnson",
            "email": "sarah.johnson@hospital.com",
            "role": "nurse",
            "specialty": "Critical Care",
        },
        {
            "first_name": "Michael",
            "last_name": "Brown",
            "email": "michael.brown@hospital.com",
            "role": "physician",
            "specialty": "Neurology",
        },
        {
            "first_name": "Emily",
            "last_name": "Davis",
            "email": "emily.davis@hospital.com",
            "role": "nurse",
            "specialty": "Emergency",
        },
        {
            "first_name": "Robert",
            "last_name": "Wilson",
            "email": "robert.wilson@hospital.com",
            "role": "technician",
            "specialty": "Radiology",
        },
        {
            "first_name": "Jennifer",
            "last_name": "Martinez",
            "email": "jennifer.martinez@hospital.com",
            "role": "physician",
            "specialty": "Surgery",
        },
        {
            "first_name": "David",
            "last_name": "Anderson",
            "email": "david.anderson@hospital.com",
            "role": "administrator",
            "specialty": None,
        },
        {
            "first_name": "Lisa",
            "last_name": "Taylor",
            "email": "lisa.taylor@hospital.com",
            "role": "nurse",
            "specialty": "General Ward",
        },
    ]

    @staticmethod
    async def seed_care_units(session: AsyncSession) -> List[str]:
        """Seed care units into database."""
        logger.info("Seeding care units...")
        care_unit_ids = []
        
        for unit_data in DatabaseSeeder.CARE_UNITS:
            care_unit_id = str(uuid.uuid4())
            care_unit = CareUnit(
                id=care_unit_id,
                name=unit_data["name"],
                code=unit_data["code"],
                description=f"{unit_data['name']} department",
                location=unit_data["location"],
                unit_type=unit_data["unit_type"],
                is_active=True,
                is_deleted=False,
            )
            session.add(care_unit)
            care_unit_ids.append(care_unit_id)
            
            # Add ID mapping
            mapping = CareUnitIDMapping(
                id=str(uuid.uuid4()),
                care_unit_id=care_unit_id,
                external_code=unit_data["code"],
                source_system="hospital_ehr",
                code_type="department_code",
            )
            session.add(mapping)
        
        await session.commit()
        logger.info(f"Seeded {len(care_unit_ids)} care units")
        return care_unit_ids

    @staticmethod
    async def seed_clinicians(session: AsyncSession) -> List[str]:
        """Seed clinicians into database."""
        logger.info("Seeding clinicians...")
        clinician_ids = []
        
        for clinician_data in DatabaseSeeder.CLINICIANS:
            clinician_id = str(uuid.uuid4())
            clinician = Clinician(
                id=clinician_id,
                first_name=clinician_data["first_name"],
                last_name=clinician_data["last_name"],
                email=clinician_data["email"],
                phone=f"+1-555-{str(uuid.uuid4())[:4]}",
                role=clinician_data["role"],
                specialty=clinician_data["specialty"],
                license_number=f"LIC{str(uuid.uuid4())[:8].upper()}",
                is_active=True,
                is_deleted=False,
            )
            session.add(clinician)
            clinician_ids.append(clinician_id)
            
            # Add ID mapping
            mapping = ClinicianIDMapping(
                id=str(uuid.uuid4()),
                clinician_id=clinician_id,
                external_id=f"CLIN{str(uuid.uuid4())[:8].upper()}",
                source_system="hospital_ehr",
                id_type="clinician_id",
            )
            session.add(mapping)
        
        await session.commit()
        logger.info(f"Seeded {len(clinician_ids)} clinicians")
        return clinician_ids

    @staticmethod
    async def seed_patients(session: AsyncSession, count: int = 50) -> List[str]:
        """Seed patients into database."""
        logger.info(f"Seeding {count} patients...")
        patient_ids = []
        
        patients_data = PatientDataGenerator.generate_patients(count)
        
        for patient_data in patients_data:
            patient = Patient(
                id=patient_data["id"],
                first_name=patient_data["first_name"],
                last_name=patient_data["last_name"],
                mrn=patient_data["mrn"],
                date_of_birth=patient_data["date_of_birth"],
                gender=patient_data["gender"],
                phone=patient_data["phone"],
                email=patient_data["email"],
                address=patient_data["address"],
                is_active=patient_data["is_active"],
                is_deleted=patient_data["is_deleted"],
            )
            session.add(patient)
            patient_ids.append(patient_data["id"])
            
            # Add ID mapping
            mapping = PatientIDMapping(
                id=str(uuid.uuid4()),
                patient_id=patient_data["id"],
                external_id=patient_data["mrn"],
                source_system="hospital_ehr",
                id_type="mrn",
            )
            session.add(mapping)
        
        await session.commit()
        logger.info(f"Seeded {len(patient_ids)} patients")
        return patient_ids

    @staticmethod
    async def seed_encounters(
        session: AsyncSession,
        patient_ids: List[str],
        care_unit_ids: List[str],
        count: int = 150,
    ) -> List[str]:
        """Seed encounters into database."""
        logger.info(f"Seeding {count} encounters...")
        encounter_ids = []
        
        encounters_data = EncounterDataGenerator.generate_encounters(
            patient_ids, care_unit_ids, count
        )
        
        for encounter_data in encounters_data:
            encounter = Encounter(
                id=encounter_data["id"],
                patient_id=encounter_data["patient_id"],
                care_unit_id=encounter_data["care_unit_id"],
                encounter_type=encounter_data["encounter_type"],
                admission_time=encounter_data["admission_time"],
                discharge_time=encounter_data["discharge_time"],
                is_active=encounter_data["is_active"],
                chief_complaint=encounter_data["chief_complaint"],
                admission_diagnosis=encounter_data["admission_diagnosis"],
                discharge_diagnosis=encounter_data["discharge_diagnosis"],
                is_deleted=encounter_data["is_deleted"],
            )
            session.add(encounter)
            encounter_ids.append(encounter_data["id"])
            
            # Add ID mapping
            mapping = EncounterIDMapping(
                id=str(uuid.uuid4()),
                encounter_id=encounter_data["id"],
                external_id=f"ENC{str(uuid.uuid4())[:8].upper()}",
                source_system="hospital_ehr",
                id_type="encounter_id",
            )
            session.add(mapping)
        
        await session.commit()
        logger.info(f"Seeded {len(encounter_ids)} encounters")
        return encounter_ids

    @staticmethod
    async def seed_devices(
        session: AsyncSession, encounter_ids: List[str], count: int = 250
    ) -> List[str]:
        """Seed devices into database."""
        logger.info(f"Seeding {count} devices...")
        device_ids = []
        
        devices_data = DeviceDataGenerator.generate_devices(encounter_ids, count)
        
        for device_data in devices_data:
            device = Device(
                id=device_data["id"],
                encounter_id=device_data["encounter_id"],
                device_type=device_data["device_type"],
                device_name=device_data["device_name"],
                serial_number=device_data["serial_number"],
                manufacturer=device_data["manufacturer"],
                model=device_data["model"],
                location=device_data["location"],
                is_online=device_data["is_online"],
                battery_level=device_data["battery_level"],
                calibration_status=device_data["calibration_status"],
                is_active=device_data["is_active"],
                is_deleted=device_data["is_deleted"],
            )
            session.add(device)
            device_ids.append(device_data["id"])
            
            # Add ID mapping
            mapping = DeviceIDMapping(
                id=str(uuid.uuid4()),
                device_id=device_data["id"],
                external_id=device_data["serial_number"],
                source_system="device_registry",
                id_type="serial_number",
            )
            session.add(mapping)
        
        await session.commit()
        logger.info(f"Seeded {len(device_ids)} devices")
        return device_ids

    @staticmethod
    async def seed_all(
        patient_count: int = 50,
        encounter_count: int = 150,
        device_count: int = 250,
    ) -> bool:
        """Seed all test data into database."""
        try:
            logger.info("Starting database seeding...")
            
            # Initialize database connection
            await DatabaseConnection.initialize()
            
            # Get session
            async for session in DatabaseConnection.get_session():
                # Seed care units
                care_unit_ids = await DatabaseSeeder.seed_care_units(session)
                
                # Seed clinicians
                clinician_ids = await DatabaseSeeder.seed_clinicians(session)
                
                # Seed patients
                patient_ids = await DatabaseSeeder.seed_patients(session, patient_count)
                
                # Seed encounters
                encounter_ids = await DatabaseSeeder.seed_encounters(
                    session, patient_ids, care_unit_ids, encounter_count
                )
                
                # Seed devices
                device_ids = await DatabaseSeeder.seed_devices(
                    session, encounter_ids, device_count
                )
                
                logger.info(
                    f"Database seeding completed successfully:\n"
                    f"  - Care Units: {len(care_unit_ids)}\n"
                    f"  - Clinicians: {len(clinician_ids)}\n"
                    f"  - Patients: {len(patient_ids)}\n"
                    f"  - Encounters: {len(encounter_ids)}\n"
                    f"  - Devices: {len(device_ids)}"
                )
                
                return True
            
        except Exception as e:
            logger.error(f"Database seeding failed: {e}")
            return False
        finally:
            await DatabaseConnection.close()


async def main(
    patient_count: int = 50,
    encounter_count: int = 150,
    device_count: int = 250,
) -> int:
    """Main entry point for database seeding.
    
    Args:
        patient_count: Number of patients to seed
        encounter_count: Number of encounters to seed
        device_count: Number of devices to seed
        
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Configure logging
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    success = await DatabaseSeeder.seed_all(
        patient_count, encounter_count, device_count
    )
    return 0 if success else 1


if __name__ == "__main__":
    patient_count = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    encounter_count = int(sys.argv[2]) if len(sys.argv) > 2 else 150
    device_count = int(sys.argv[3]) if len(sys.argv) > 3 else 250
    
    exit_code = asyncio.run(main(patient_count, encounter_count, device_count))
    sys.exit(exit_code)
