"""
ID Mapping System for normalizing identifiers across multiple data sources.

This module implements mapping of external identifiers to internal identifiers:
- Patient ID mapping (with fuzzy matching for duplicate detection)
- Encounter ID mapping
- Device ID mapping
- Care unit mapping
- Clinician ID mapping

Maintains mappings for data consolidation and duplicate detection.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.database.models import (
    Patient,
    PatientIDMapping,
    Encounter,
    EncounterIDMapping,
    Device,
    DeviceIDMapping,
    CareUnit,
    CareUnitIDMapping,
    Clinician,
    ClinicianIDMapping,
)
from mcp_server.utils.logger import get_logger
from mcp_server.utils.validators import ValidationError

logger = get_logger(__name__)


class IDMapper:
    """Maps external identifiers to internal identifiers."""

    @staticmethod
    async def get_or_create_patient_id(
        session: AsyncSession,
        external_id: str,
        source_system: str,
        patient_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Get or create internal patient ID from external identifier.

        Args:
            session: Database session
            external_id: External patient identifier
            source_system: Source system identifier
            patient_data: Optional patient data for creating new patient

        Returns:
            Internal patient ID

        Raises:
            ValidationError: If external_id or source_system is invalid
        """
        if not external_id or not isinstance(external_id, str):
            raise ValidationError("external_id must be a non-empty string")
        if not source_system or not isinstance(source_system, str):
            raise ValidationError("source_system must be a non-empty string")

        try:
            # Check if mapping already exists
            mapping = await IDMapper._get_patient_mapping(
                session, external_id, source_system
            )
            if mapping:
                logger.debug(
                    f"Found existing patient mapping: {external_id} "
                    f"({source_system}) -> {mapping.patient_id}"
                )
                return mapping.patient_id

            # Check for potential duplicates using fuzzy matching
            potential_duplicates = await IDMapper._find_potential_patient_duplicates(
                session, external_id, source_system, patient_data
            )

            if potential_duplicates:
                logger.warning(
                    f"Found {len(potential_duplicates)} potential duplicate patients "
                    f"for {external_id} ({source_system})"
                )
                # Log for manual reconciliation
                await IDMapper._log_duplicate_detection(
                    session, external_id, source_system, potential_duplicates
                )
                # Use the first duplicate as the internal ID
                internal_patient_id = potential_duplicates[0].id
                # Create mapping to the existing patient
                await IDMapper._create_patient_mapping(
                    session, internal_patient_id, external_id, source_system
                )
                logger.info(
                    f"Mapped duplicate patient: {external_id} "
                    f"({source_system}) -> {internal_patient_id}"
                )
                return internal_patient_id

            # Create new patient if data provided
            if patient_data:
                internal_patient_id = await IDMapper._create_patient(
                    session, external_id, source_system, patient_data
                )
            else:
                # Generate new internal ID
                internal_patient_id = f"PAT-{uuid.uuid4()}"

            # Create mapping
            await IDMapper._create_patient_mapping(
                session, internal_patient_id, external_id, source_system
            )

            logger.info(
                f"Created patient mapping: {external_id} "
                f"({source_system}) -> {internal_patient_id}"
            )

            return internal_patient_id

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting or creating patient ID: {e}")
            raise ValidationError(f"Failed to get or create patient ID: {e}")

    @staticmethod
    async def get_or_create_encounter_id(
        session: AsyncSession,
        external_id: str,
        source_system: str,
        patient_id: str,
        encounter_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Get or create internal encounter ID from external identifier.

        Args:
            session: Database session
            external_id: External encounter identifier
            source_system: Source system identifier
            patient_id: Internal patient ID
            encounter_data: Optional encounter data for creating new encounter

        Returns:
            Internal encounter ID
        """
        if not external_id or not isinstance(external_id, str):
            raise ValidationError("external_id must be a non-empty string")
        if not source_system or not isinstance(source_system, str):
            raise ValidationError("source_system must be a non-empty string")
        if not patient_id or not isinstance(patient_id, str):
            raise ValidationError("patient_id must be a non-empty string")

        try:
            # Check if mapping already exists
            mapping = await IDMapper._get_encounter_mapping(
                session, external_id, source_system, patient_id
            )
            if mapping:
                logger.debug(
                    f"Found existing encounter mapping: {external_id} "
                    f"({source_system}) -> {mapping.encounter_id}"
                )
                return mapping.encounter_id

            # Create new encounter if data provided
            if encounter_data:
                internal_encounter_id = await IDMapper._create_encounter(
                    session, external_id, source_system, patient_id, encounter_data
                )
            else:
                # Generate new internal ID
                internal_encounter_id = f"ENC-{uuid.uuid4()}"

            # Create mapping
            await IDMapper._create_encounter_mapping(
                session, internal_encounter_id, external_id, source_system, patient_id
            )

            logger.info(
                f"Created encounter mapping: {external_id} "
                f"({source_system}) -> {internal_encounter_id}"
            )

            return internal_encounter_id

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting or creating encounter ID: {e}")
            raise ValidationError(f"Failed to get or create encounter ID: {e}")

    @staticmethod
    async def get_or_create_device_id(
        session: AsyncSession,
        external_id: str,
        source_system: str,
        device_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Get or create internal device ID from external identifier.

        Args:
            session: Database session
            external_id: External device identifier
            source_system: Source system identifier
            device_data: Optional device data for creating new device

        Returns:
            Internal device ID
        """
        if not external_id or not isinstance(external_id, str):
            raise ValidationError("external_id must be a non-empty string")
        if not source_system or not isinstance(source_system, str):
            raise ValidationError("source_system must be a non-empty string")

        try:
            # Check if mapping already exists
            mapping = await IDMapper._get_device_mapping(
                session, external_id, source_system
            )
            if mapping:
                logger.debug(
                    f"Found existing device mapping: {external_id} "
                    f"({source_system}) -> {mapping.device_id}"
                )
                return mapping.device_id

            # Create new device if data provided
            if device_data:
                internal_device_id = await IDMapper._create_device(
                    session, external_id, source_system, device_data
                )
            else:
                # Generate new internal ID
                internal_device_id = f"DEV-{uuid.uuid4()}"

            # Create mapping
            await IDMapper._create_device_mapping(
                session, internal_device_id, external_id, source_system
            )

            logger.info(
                f"Created device mapping: {external_id} "
                f"({source_system}) -> {internal_device_id}"
            )

            return internal_device_id

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting or creating device ID: {e}")
            raise ValidationError(f"Failed to get or create device ID: {e}")

    @staticmethod
    async def get_or_create_care_unit_id(
        session: AsyncSession,
        external_code: str,
        source_system: str,
        care_unit_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Get or create internal care unit ID from external code.

        Args:
            session: Database session
            external_code: External care unit code
            source_system: Source system identifier
            care_unit_data: Optional care unit data for creating new care unit

        Returns:
            Internal care unit ID or None if not found
        """
        if not external_code or not isinstance(external_code, str):
            raise ValidationError("external_code must be a non-empty string")
        if not source_system or not isinstance(source_system, str):
            raise ValidationError("source_system must be a non-empty string")

        try:
            # Check if mapping already exists
            mapping = await IDMapper._get_care_unit_mapping(
                session, external_code, source_system
            )
            if mapping:
                logger.debug(
                    f"Found existing care unit mapping: {external_code} "
                    f"({source_system}) -> {mapping.care_unit_id}"
                )
                return mapping.care_unit_id

            # Create new care unit if data provided
            if care_unit_data:
                internal_care_unit_id = await IDMapper._create_care_unit(
                    session, external_code, source_system, care_unit_data
                )
            else:
                logger.warning(
                    f"No mapping found for care unit code: {external_code} "
                    f"({source_system})"
                )
                return None

            # Create mapping
            await IDMapper._create_care_unit_mapping(
                session, internal_care_unit_id, external_code, source_system
            )

            logger.info(
                f"Created care unit mapping: {external_code} "
                f"({source_system}) -> {internal_care_unit_id}"
            )

            return internal_care_unit_id

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting or creating care unit ID: {e}")
            raise ValidationError(f"Failed to get or create care unit ID: {e}")

    @staticmethod
    async def get_or_create_clinician_id(
        session: AsyncSession,
        external_id: str,
        source_system: str,
        clinician_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Get or create internal clinician ID from external identifier.

        Args:
            session: Database session
            external_id: External clinician identifier
            source_system: Source system identifier
            clinician_data: Optional clinician data for creating new clinician

        Returns:
            Internal clinician ID
        """
        if not external_id or not isinstance(external_id, str):
            raise ValidationError("external_id must be a non-empty string")
        if not source_system or not isinstance(source_system, str):
            raise ValidationError("source_system must be a non-empty string")

        try:
            # Check if mapping already exists
            mapping = await IDMapper._get_clinician_mapping(
                session, external_id, source_system
            )
            if mapping:
                logger.debug(
                    f"Found existing clinician mapping: {external_id} "
                    f"({source_system}) -> {mapping.clinician_id}"
                )
                return mapping.clinician_id

            # Create new clinician if data provided
            if clinician_data:
                internal_clinician_id = await IDMapper._create_clinician(
                    session, external_id, source_system, clinician_data
                )
            else:
                # Generate new internal ID
                internal_clinician_id = f"CLIN-{uuid.uuid4()}"

            # Create mapping
            await IDMapper._create_clinician_mapping(
                session, internal_clinician_id, external_id, source_system
            )

            logger.info(
                f"Created clinician mapping: {external_id} "
                f"({source_system}) -> {internal_clinician_id}"
            )

            return internal_clinician_id

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting or creating clinician ID: {e}")
            raise ValidationError(f"Failed to get or create clinician ID: {e}")

    # Private helper methods

    @staticmethod
    async def _get_patient_mapping(
        session: AsyncSession, external_id: str, source_system: str
    ) -> Optional[PatientIDMapping]:
        """Get existing patient ID mapping."""
        stmt = select(PatientIDMapping).where(
            and_(
                PatientIDMapping.external_id == external_id,
                PatientIDMapping.source_system == source_system,
            )
        )
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def _get_encounter_mapping(
        session: AsyncSession,
        external_id: str,
        source_system: str,
        patient_id: str,
    ) -> Optional[EncounterIDMapping]:
        """Get existing encounter ID mapping."""
        stmt = select(EncounterIDMapping).where(
            and_(
                EncounterIDMapping.external_id == external_id,
                EncounterIDMapping.source_system == source_system,
            )
        )
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def _get_device_mapping(
        session: AsyncSession, external_id: str, source_system: str
    ) -> Optional[DeviceIDMapping]:
        """Get existing device ID mapping."""
        stmt = select(DeviceIDMapping).where(
            and_(
                DeviceIDMapping.external_id == external_id,
                DeviceIDMapping.source_system == source_system,
            )
        )
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def _get_care_unit_mapping(
        session: AsyncSession, external_code: str, source_system: str
    ) -> Optional[CareUnitIDMapping]:
        """Get existing care unit ID mapping."""
        stmt = select(CareUnitIDMapping).where(
            and_(
                CareUnitIDMapping.external_code == external_code,
                CareUnitIDMapping.source_system == source_system,
            )
        )
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def _get_clinician_mapping(
        session: AsyncSession, external_id: str, source_system: str
    ) -> Optional[ClinicianIDMapping]:
        """Get existing clinician ID mapping."""
        stmt = select(ClinicianIDMapping).where(
            and_(
                ClinicianIDMapping.external_id == external_id,
                ClinicianIDMapping.source_system == source_system,
            )
        )
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def _find_potential_patient_duplicates(
        session: AsyncSession,
        external_id: str,
        source_system: str,
        patient_data: Optional[Dict[str, Any]] = None,
    ) -> List[Patient]:
        """
        Find potential duplicate patients using fuzzy matching.

        Uses simple string matching on name and MRN.
        In production, would use Levenshtein distance or similar.
        """
        if not patient_data:
            return []

        duplicates = []

        # Check for MRN matches
        if patient_data.get("mrn"):
            stmt = select(Patient).where(
                and_(
                    Patient.mrn == patient_data.get("mrn"),
                    Patient.is_deleted == False,
                )
            )
            result = await session.execute(stmt)
            duplicates.extend(result.scalars().all())

        # Check for name matches
        if patient_data.get("first_name") and patient_data.get("last_name"):
            stmt = select(Patient).where(
                and_(
                    Patient.first_name == patient_data.get("first_name"),
                    Patient.last_name == patient_data.get("last_name"),
                    Patient.is_deleted == False,
                )
            )
            result = await session.execute(stmt)
            duplicates.extend(result.scalars().all())

        # Remove duplicates from list
        seen = set()
        unique_duplicates = []
        for dup in duplicates:
            if dup.id not in seen:
                seen.add(dup.id)
                unique_duplicates.append(dup)

        return unique_duplicates

    @staticmethod
    async def _log_duplicate_detection(
        session: AsyncSession,
        external_id: str,
        source_system: str,
        potential_duplicates: List[Patient],
    ) -> None:
        """Log potential duplicate detection for manual reconciliation."""
        logger.warning(
            f"Potential duplicate patients detected: "
            f"external_id={external_id}, source_system={source_system}, "
            f"duplicates={[p.id for p in potential_duplicates]}"
        )

    @staticmethod
    async def _create_patient(
        session: AsyncSession,
        external_id: str,
        source_system: str,
        patient_data: Dict[str, Any],
    ) -> str:
        """Create new patient from data."""
        internal_patient_id = f"PAT-{uuid.uuid4()}"

        patient = Patient(
            id=internal_patient_id,
            first_name=patient_data.get("first_name", ""),
            last_name=patient_data.get("last_name", ""),
            date_of_birth=patient_data.get("date_of_birth"),
            gender=patient_data.get("gender"),
            mrn=patient_data.get("mrn"),
            phone=patient_data.get("phone"),
            email=patient_data.get("email"),
            address=patient_data.get("address"),
            is_active=patient_data.get("is_active", True),
        )

        session.add(patient)
        await session.flush()

        logger.info(f"Created new patient: {internal_patient_id}")

        return internal_patient_id

    @staticmethod
    async def _create_encounter(
        session: AsyncSession,
        external_id: str,
        source_system: str,
        patient_id: str,
        encounter_data: Dict[str, Any],
    ) -> str:
        """Create new encounter from data."""
        internal_encounter_id = f"ENC-{uuid.uuid4()}"

        encounter = Encounter(
            id=internal_encounter_id,
            patient_id=patient_id,
            care_unit_id=encounter_data.get("care_unit_id", ""),
            encounter_type=encounter_data.get("encounter_type", "unknown"),
            admission_time=encounter_data.get("admission_time", datetime.now(timezone.utc)),
            discharge_time=encounter_data.get("discharge_time"),
            is_active=encounter_data.get("is_active", True),
            chief_complaint=encounter_data.get("chief_complaint"),
            admission_diagnosis=encounter_data.get("admission_diagnosis"),
        )

        session.add(encounter)
        await session.flush()

        logger.info(f"Created new encounter: {internal_encounter_id}")

        return internal_encounter_id

    @staticmethod
    async def _create_device(
        session: AsyncSession,
        external_id: str,
        source_system: str,
        device_data: Dict[str, Any],
    ) -> str:
        """Create new device from data."""
        internal_device_id = f"DEV-{uuid.uuid4()}"

        device = Device(
            id=internal_device_id,
            encounter_id=device_data.get("encounter_id"),
            device_type=device_data.get("device_type", "unknown"),
            device_name=device_data.get("device_name", ""),
            serial_number=device_data.get("serial_number"),
            manufacturer=device_data.get("manufacturer"),
            model=device_data.get("model"),
            location=device_data.get("location"),
            is_online=device_data.get("is_online", False),
            battery_level=device_data.get("battery_level"),
            calibration_status=device_data.get("calibration_status"),
            is_active=device_data.get("is_active", True),
        )

        session.add(device)
        await session.flush()

        logger.info(f"Created new device: {internal_device_id}")

        return internal_device_id

    @staticmethod
    async def _create_care_unit(
        session: AsyncSession,
        external_code: str,
        source_system: str,
        care_unit_data: Dict[str, Any],
    ) -> str:
        """Create new care unit from data."""
        internal_care_unit_id = f"CU-{uuid.uuid4()}"

        care_unit = CareUnit(
            id=internal_care_unit_id,
            name=care_unit_data.get("name", external_code),
            code=care_unit_data.get("code", external_code),
            description=care_unit_data.get("description"),
            location=care_unit_data.get("location"),
            unit_type=care_unit_data.get("unit_type", "unknown"),
            is_active=care_unit_data.get("is_active", True),
        )

        session.add(care_unit)
        await session.flush()

        logger.info(f"Created new care unit: {internal_care_unit_id}")

        return internal_care_unit_id

    @staticmethod
    async def _create_clinician(
        session: AsyncSession,
        external_id: str,
        source_system: str,
        clinician_data: Dict[str, Any],
    ) -> str:
        """Create new clinician from data."""
        internal_clinician_id = f"CLIN-{uuid.uuid4()}"

        clinician = Clinician(
            id=internal_clinician_id,
            first_name=clinician_data.get("first_name", ""),
            last_name=clinician_data.get("last_name", ""),
            email=clinician_data.get("email", f"{external_id}@hospital.local"),
            phone=clinician_data.get("phone"),
            role=clinician_data.get("role", "unknown"),
            specialty=clinician_data.get("specialty"),
            license_number=clinician_data.get("license_number"),
            is_active=clinician_data.get("is_active", True),
        )

        session.add(clinician)
        await session.flush()

        logger.info(f"Created new clinician: {internal_clinician_id}")

        return internal_clinician_id

    @staticmethod
    async def _create_patient_mapping(
        session: AsyncSession,
        internal_id: str,
        external_id: str,
        source_system: str,
    ) -> None:
        """Create patient ID mapping."""
        mapping = PatientIDMapping(
            id=f"MAP-{uuid.uuid4()}",
            patient_id=internal_id,
            external_id=external_id,
            source_system=source_system,
            id_type="external",
        )
        session.add(mapping)
        await session.flush()

    @staticmethod
    async def _create_encounter_mapping(
        session: AsyncSession,
        internal_id: str,
        external_id: str,
        source_system: str,
        patient_id: str,
    ) -> None:
        """Create encounter ID mapping."""
        mapping = EncounterIDMapping(
            id=f"MAP-{uuid.uuid4()}",
            encounter_id=internal_id,
            external_id=external_id,
            source_system=source_system,
            id_type="external",
        )
        session.add(mapping)
        await session.flush()

    @staticmethod
    async def _create_device_mapping(
        session: AsyncSession,
        internal_id: str,
        external_id: str,
        source_system: str,
    ) -> None:
        """Create device ID mapping."""
        mapping = DeviceIDMapping(
            id=f"MAP-{uuid.uuid4()}",
            device_id=internal_id,
            external_id=external_id,
            source_system=source_system,
            id_type="external",
        )
        session.add(mapping)
        await session.flush()

    @staticmethod
    async def _create_care_unit_mapping(
        session: AsyncSession,
        internal_id: str,
        external_code: str,
        source_system: str,
    ) -> None:
        """Create care unit ID mapping."""
        mapping = CareUnitIDMapping(
            id=f"MAP-{uuid.uuid4()}",
            care_unit_id=internal_id,
            external_code=external_code,
            source_system=source_system,
            code_type="external",
        )
        session.add(mapping)
        await session.flush()

    @staticmethod
    async def _create_clinician_mapping(
        session: AsyncSession,
        internal_id: str,
        external_id: str,
        source_system: str,
    ) -> None:
        """Create clinician ID mapping."""
        mapping = ClinicianIDMapping(
            id=f"MAP-{uuid.uuid4()}",
            clinician_id=internal_id,
            external_id=external_id,
            source_system=source_system,
            id_type="external",
        )
        session.add(mapping)
        await session.flush()
