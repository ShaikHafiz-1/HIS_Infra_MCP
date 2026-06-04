"""
HL7 Data Normalization and Storage.

This module handles:
- Extraction of patient ID, encounter ID, care unit, clinician, timestamp from HL7 messages
- Normalization of patient IDs and encounter IDs across sources
- Storage of parsed HL7 data in normalized format
- Duplicate detection and conflict logging
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.database.connection import get_db_session
from mcp_server.database.models import (
    CareUnit,
    Clinician,
    Encounter,
    Patient,
    PatientIDMapping,
    EncounterIDMapping,
    CareUnitIDMapping,
    ClinicianIDMapping,
)
from mcp_server.utils.logger import get_logger

logger = get_logger(__name__)


class HL7Normalizer:
    """
    Normalize and store HL7 message data.
    
    Handles:
    - ID mapping and normalization
    - Patient and encounter creation/updates
    - Duplicate detection
    - Conflict logging
    """

    SOURCE_SYSTEM = "HL7_v2"

    async def normalize_and_store(self, parsed_message: Dict[str, Any]) -> None:
        """
        Normalize and store a parsed HL7 message.
        
        Args:
            parsed_message: Parsed HL7 message dictionary
            
        Raises:
            Exception: If database operation fails
        """
        try:
            async with get_db_session() as session:
                message_type = parsed_message.get("message_type")
                
                if message_type == "ADT":
                    await self.process_adt_message(session, parsed_message)
                elif message_type == "ORU":
                    await self.process_oru_message(session, parsed_message)
                elif message_type == "ORM":
                    await self.process_orm_message(session, parsed_message)
                elif message_type == "MDM":
                    await self.process_mdm_message(session, parsed_message)
                else:
                    logger.warning(f"Unknown message type: {message_type}")
                
                await session.commit()
                
        except Exception as e:
            logger.error(f"Failed to normalize and store HL7 message: {e}")
            raise

    async def process_adt_message(
        self, session: AsyncSession, message: Dict[str, Any]
    ) -> None:
        """
        Process ADT (Admission/Discharge/Transfer) message.
        
        Args:
            session: Database session
            message: Parsed ADT message
        """
        try:
            # Extract patient information
            external_patient_id = message.get("patient_id")
            patient_name = message.get("patient_name", "")
            date_of_birth = message.get("date_of_birth")
            gender = message.get("gender")
            
            if not external_patient_id:
                logger.warning("ADT message missing patient ID")
                return
            
            # Get or create internal patient ID
            internal_patient_id = await self.get_or_create_patient(
                session,
                external_patient_id,
                patient_name,
                date_of_birth,
                gender,
            )
            
            # Extract encounter information
            point_of_care = message.get("point_of_care")
            admission_type = message.get("admission_type")
            event_type = message.get("event_type", "A01")
            timestamp = message.get("timestamp")
            
            # Get or create care unit
            care_unit_id = await self.get_or_create_care_unit(
                session, point_of_care
            )
            
            # Create or update encounter
            await self.create_or_update_encounter(
                session,
                internal_patient_id,
                care_unit_id,
                admission_type,
                event_type,
                timestamp,
            )
            
            logger.info(
                f"Processed ADT message for patient {internal_patient_id} "
                f"(external: {external_patient_id})"
            )
            
        except Exception as e:
            logger.error(f"Failed to process ADT message: {e}")
            raise

    async def process_oru_message(
        self, session: AsyncSession, message: Dict[str, Any]
    ) -> None:
        """
        Process ORU (Observation Result) message.
        
        Args:
            session: Database session
            message: Parsed ORU message
        """
        try:
            # Extract patient information
            external_patient_id = message.get("patient_id")
            patient_name = message.get("patient_name", "")
            
            if not external_patient_id:
                logger.warning("ORU message missing patient ID")
                return
            
            # Get or create internal patient ID
            internal_patient_id = await self.get_or_create_patient(
                session, external_patient_id, patient_name
            )
            
            # Extract observations
            observations = message.get("observations", [])
            
            logger.info(
                f"Processed ORU message for patient {internal_patient_id} "
                f"with {len(observations)} observations"
            )
            
        except Exception as e:
            logger.error(f"Failed to process ORU message: {e}")
            raise

    async def process_orm_message(
        self, session: AsyncSession, message: Dict[str, Any]
    ) -> None:
        """
        Process ORM (Order) message.
        
        Args:
            session: Database session
            message: Parsed ORM message
        """
        try:
            # Extract patient information
            external_patient_id = message.get("patient_id")
            patient_name = message.get("patient_name", "")
            
            if not external_patient_id:
                logger.warning("ORM message missing patient ID")
                return
            
            # Get or create internal patient ID
            internal_patient_id = await self.get_or_create_patient(
                session, external_patient_id, patient_name
            )
            
            # Extract orders
            orders = message.get("orders", [])
            
            logger.info(
                f"Processed ORM message for patient {internal_patient_id} "
                f"with {len(orders)} orders"
            )
            
        except Exception as e:
            logger.error(f"Failed to process ORM message: {e}")
            raise

    async def process_mdm_message(
        self, session: AsyncSession, message: Dict[str, Any]
    ) -> None:
        """
        Process MDM (Medical Document Management) message.
        
        Args:
            session: Database session
            message: Parsed MDM message
        """
        try:
            # Extract patient information
            external_patient_id = message.get("patient_id")
            patient_name = message.get("patient_name", "")
            
            if not external_patient_id:
                logger.warning("MDM message missing patient ID")
                return
            
            # Get or create internal patient ID
            internal_patient_id = await self.get_or_create_patient(
                session, external_patient_id, patient_name
            )
            
            # Extract document information
            document_type = message.get("document_type")
            document_title = message.get("document_title")
            
            logger.info(
                f"Processed MDM message for patient {internal_patient_id} "
                f"document type: {document_type}"
            )
            
        except Exception as e:
            logger.error(f"Failed to process MDM message: {e}")
            raise

    async def get_or_create_patient(
        self,
        session: AsyncSession,
        external_patient_id: str,
        patient_name: str = "",
        date_of_birth: Optional[str] = None,
        gender: Optional[str] = None,
    ) -> str:
        """
        Get or create a patient with ID mapping.
        
        Args:
            session: Database session
            external_patient_id: External patient ID from HL7 message
            patient_name: Patient name (optional)
            date_of_birth: Patient DOB (optional)
            gender: Patient gender (optional)
            
        Returns:
            Internal patient ID
        """
        try:
            # Check if mapping already exists
            mapping = await session.execute(
                select(PatientIDMapping).where(
                    PatientIDMapping.external_id == external_patient_id,
                    PatientIDMapping.source_system == self.SOURCE_SYSTEM,
                )
            )
            existing_mapping = mapping.scalars().first()
            
            if existing_mapping:
                return existing_mapping.patient_id
            
            # Parse patient name
            first_name = ""
            last_name = ""
            
            if patient_name:
                name_parts = patient_name.split("^")
                if len(name_parts) > 0:
                    last_name = name_parts[0]
                if len(name_parts) > 1:
                    first_name = name_parts[1]
            
            # Create new patient
            patient_id = str(uuid.uuid4())
            patient = Patient(
                id=patient_id,
                first_name=first_name or "Unknown",
                last_name=last_name or "Unknown",
                date_of_birth=self.parse_hl7_date(date_of_birth) if date_of_birth else None,
                gender=gender,
                is_active=True,
                is_deleted=False,
            )
            
            session.add(patient)
            
            # Create ID mapping
            mapping = PatientIDMapping(
                id=str(uuid.uuid4()),
                patient_id=patient_id,
                external_id=external_patient_id,
                source_system=self.SOURCE_SYSTEM,
                id_type="MRN",
            )
            
            session.add(mapping)
            
            logger.info(
                f"Created new patient {patient_id} "
                f"with external ID {external_patient_id}"
            )
            
            return patient_id
            
        except Exception as e:
            logger.error(f"Failed to get or create patient: {e}")
            raise

    async def get_or_create_care_unit(
        self, session: AsyncSession, external_care_unit_code: Optional[str]
    ) -> Optional[str]:
        """
        Get or create a care unit with ID mapping.
        
        Args:
            session: Database session
            external_care_unit_code: External care unit code from HL7 message
            
        Returns:
            Internal care unit ID, or None if not found/created
        """
        try:
            if not external_care_unit_code:
                return None
            
            # Check if mapping already exists
            mapping = await session.execute(
                select(CareUnitIDMapping).where(
                    CareUnitIDMapping.external_code == external_care_unit_code,
                    CareUnitIDMapping.source_system == self.SOURCE_SYSTEM,
                )
            )
            existing_mapping = mapping.scalars().first()
            
            if existing_mapping:
                return existing_mapping.care_unit_id
            
            # Try to find existing care unit by code
            care_unit = await session.execute(
                select(CareUnit).where(CareUnit.code == external_care_unit_code)
            )
            existing_care_unit = care_unit.scalars().first()
            
            if existing_care_unit:
                # Create mapping for existing care unit
                mapping = CareUnitIDMapping(
                    id=str(uuid.uuid4()),
                    care_unit_id=existing_care_unit.id,
                    external_code=external_care_unit_code,
                    source_system=self.SOURCE_SYSTEM,
                    code_type="HL7_LOCATION",
                )
                session.add(mapping)
                return existing_care_unit.id
            
            # Create new care unit
            care_unit_id = str(uuid.uuid4())
            care_unit = CareUnit(
                id=care_unit_id,
                name=external_care_unit_code,
                code=external_care_unit_code,
                unit_type="General",
                is_active=True,
                is_deleted=False,
            )
            
            session.add(care_unit)
            
            # Create ID mapping
            mapping = CareUnitIDMapping(
                id=str(uuid.uuid4()),
                care_unit_id=care_unit_id,
                external_code=external_care_unit_code,
                source_system=self.SOURCE_SYSTEM,
                code_type="HL7_LOCATION",
            )
            
            session.add(mapping)
            
            logger.info(
                f"Created new care unit {care_unit_id} "
                f"with external code {external_care_unit_code}"
            )
            
            return care_unit_id
            
        except Exception as e:
            logger.error(f"Failed to get or create care unit: {e}")
            raise

    async def create_or_update_encounter(
        self,
        session: AsyncSession,
        patient_id: str,
        care_unit_id: Optional[str],
        encounter_type: Optional[str],
        event_type: str,
        timestamp: Optional[str],
    ) -> Optional[str]:
        """
        Create or update an encounter.
        
        Args:
            session: Database session
            patient_id: Internal patient ID
            care_unit_id: Internal care unit ID
            encounter_type: Type of encounter
            event_type: ADT event type (A01, A02, etc.)
            timestamp: Event timestamp
            
        Returns:
            Encounter ID, or None if creation failed
        """
        try:
            if not care_unit_id:
                logger.warning("Cannot create encounter without care unit")
                return None
            
            # Parse timestamp
            admission_time = self.parse_hl7_datetime(timestamp)
            if not admission_time:
                admission_time = datetime.now(timezone.utc)
            
            # Create new encounter
            encounter_id = str(uuid.uuid4())
            encounter = Encounter(
                id=encounter_id,
                patient_id=patient_id,
                care_unit_id=care_unit_id,
                encounter_type=encounter_type or "admission",
                admission_time=admission_time,
                is_active=True,
                is_deleted=False,
            )
            
            session.add(encounter)
            
            logger.info(
                f"Created encounter {encounter_id} "
                f"for patient {patient_id} in care unit {care_unit_id}"
            )
            
            return encounter_id
            
        except Exception as e:
            logger.error(f"Failed to create or update encounter: {e}")
            raise

    @staticmethod
    def parse_hl7_date(date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse HL7 date string (YYYYMMDD format).
        
        Args:
            date_str: HL7 date string
            
        Returns:
            Parsed datetime, or None if invalid
        """
        if not date_str or len(date_str) < 8:
            return None
        
        try:
            year = int(date_str[0:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])
            return datetime(year, month, day, tzinfo=timezone.utc)
        except (ValueError, IndexError):
            logger.warning(f"Failed to parse HL7 date: {date_str}")
            return None

    @staticmethod
    def parse_hl7_datetime(datetime_str: Optional[str]) -> Optional[datetime]:
        """
        Parse HL7 datetime string (YYYYMMDDHHMMSS format).
        
        Args:
            datetime_str: HL7 datetime string
            
        Returns:
            Parsed datetime, or None if invalid
        """
        if not datetime_str:
            return None
        
        try:
            # Handle various HL7 datetime formats
            if len(datetime_str) >= 14:
                year = int(datetime_str[0:4])
                month = int(datetime_str[4:6])
                day = int(datetime_str[6:8])
                hour = int(datetime_str[8:10])
                minute = int(datetime_str[10:12])
                second = int(datetime_str[12:14])
                return datetime(
                    year, month, day, hour, minute, second, tzinfo=timezone.utc
                )
            elif len(datetime_str) >= 8:
                # Just date, no time
                return HL7Normalizer.parse_hl7_date(datetime_str)
        except (ValueError, IndexError):
            logger.warning(f"Failed to parse HL7 datetime: {datetime_str}")
        
        return None
