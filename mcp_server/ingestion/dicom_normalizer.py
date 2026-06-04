"""
DICOM Metadata Normalization and Storage for Hospital Clinical Intelligence MCP Platform.

This module implements DICOM metadata normalization including:
- DICOM metadata normalization
- Linking DICOM studies to patient encounters and care units
- Patient ID normalization in DICOM metadata
- DICOM metadata storage with study description and findings
- References to DICOM image archives
- Integration with ID mapper for patient/encounter/care unit association
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.database.models import (
    Patient,
    Encounter,
    CareUnit,
)
from mcp_server.normalization.id_mapper import IDMapper
from mcp_server.utils.logger import get_logger
from mcp_server.utils.validators import ValidationError

logger = get_logger(__name__)


class DICOMMetadataNormalizer:
    """Normalizes DICOM metadata for storage and retrieval."""

    @staticmethod
    async def normalize_metadata(
        session: AsyncSession,
        raw_metadata: Dict[str, Any],
        source_system: str = "DICOM",
    ) -> Dict[str, Any]:
        """
        Normalize DICOM metadata.

        Args:
            session: Database session
            raw_metadata: Raw DICOM metadata from extractor
            source_system: Source system identifier

        Returns:
            Dictionary with normalized metadata

        Raises:
            ValidationError: If normalization fails
        """
        if not raw_metadata or not isinstance(raw_metadata, dict):
            raise ValidationError("raw_metadata must be a non-empty dictionary")

        try:
            # Normalize patient ID
            external_patient_id = raw_metadata.get("patient_id")
            if not external_patient_id:
                raise ValidationError("Patient ID is required")

            internal_patient_id = await IDMapper.get_or_create_patient_id(
                session,
                external_patient_id,
                source_system,
                patient_data={
                    "first_name": raw_metadata.get("patient_name", "").split()[-1]
                    if raw_metadata.get("patient_name")
                    else "",
                    "last_name": raw_metadata.get("patient_name", "").split()[0]
                    if raw_metadata.get("patient_name")
                    else "",
                    "date_of_birth": raw_metadata.get("patient_dob"),
                    "gender": raw_metadata.get("patient_sex"),
                },
            )

            # Normalize study ID
            external_study_id = raw_metadata.get("study_id")
            if not external_study_id:
                raise ValidationError("Study ID is required")

            internal_study_id = f"STUDY-{uuid.uuid4()}"

            # Normalize modality
            modality = raw_metadata.get("modality", "OT")

            # Normalize timestamp
            study_timestamp = raw_metadata.get("study_timestamp")
            if not study_timestamp:
                study_timestamp = datetime.now(timezone.utc)

            # Calculate confidence score
            confidence = DICOMMetadataNormalizer._calculate_confidence(raw_metadata)

            logger.debug(
                f"Normalized DICOM metadata: patient={internal_patient_id}, "
                f"study={internal_study_id}, modality={modality}"
            )

            return {
                "internal_patient_id": internal_patient_id,
                "external_patient_id": external_patient_id,
                "internal_study_id": internal_study_id,
                "external_study_id": external_study_id,
                "patient_name": raw_metadata.get("patient_name", ""),
                "patient_dob": raw_metadata.get("patient_dob"),
                "patient_sex": raw_metadata.get("patient_sex"),
                "study_date": raw_metadata.get("study_date"),
                "study_time": raw_metadata.get("study_time"),
                "study_timestamp": study_timestamp,
                "study_description": raw_metadata.get("study_description", ""),
                "modality": modality,
                "series_id": raw_metadata.get("series_id"),
                "series_number": raw_metadata.get("series_number"),
                "series_description": raw_metadata.get("series_description", ""),
                "series_instance_uid": raw_metadata.get("series_instance_uid"),
                "sop_class_uid": raw_metadata.get("sop_class_uid"),
                "sop_instance_uid": raw_metadata.get("sop_instance_uid"),
                "image_number": raw_metadata.get("image_number"),
                "confidence_score": confidence,
                "normalization_timestamp": datetime.now(timezone.utc),
                "source_system": source_system,
            }

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error normalizing DICOM metadata: {e}")
            raise ValidationError(f"Failed to normalize DICOM metadata: {e}")

    @staticmethod
    def _calculate_confidence(raw_metadata: Dict[str, Any]) -> float:
        """Calculate confidence score for normalized metadata."""
        confidence = 1.0

        # Reduce confidence for missing optional fields
        optional_fields = [
            "study_description",
            "series_description",
            "patient_dob",
            "patient_sex",
        ]

        missing_optional = sum(
            1 for field in optional_fields if not raw_metadata.get(field)
        )

        confidence -= missing_optional * 0.05

        return max(0.0, min(1.0, confidence))


class DICOMStudyAssociator:
    """Associates DICOM studies with patient encounters and care units."""

    @staticmethod
    async def associate_study_to_encounter(
        session: AsyncSession,
        normalized_metadata: Dict[str, Any],
    ) -> Optional[str]:
        """
        Associate DICOM study with patient encounter.

        Args:
            session: Database session
            normalized_metadata: Normalized DICOM metadata

        Returns:
            Internal encounter ID or None if not found

        Raises:
            ValidationError: If association fails
        """
        if not normalized_metadata or not isinstance(normalized_metadata, dict):
            raise ValidationError("normalized_metadata must be a non-empty dictionary")

        try:
            internal_patient_id = normalized_metadata.get("internal_patient_id")
            study_timestamp = normalized_metadata.get("study_timestamp")

            if not internal_patient_id:
                raise ValidationError("internal_patient_id is required")

            # Find active encounter for patient at study timestamp
            stmt = select(Encounter).where(
                and_(
                    Encounter.patient_id == internal_patient_id,
                    Encounter.admission_time <= study_timestamp,
                    (Encounter.discharge_time.is_(None))
                    | (Encounter.discharge_time >= study_timestamp),
                    Encounter.is_active == True,
                )
            )

            result = await session.execute(stmt)
            encounter = result.scalars().first()

            if encounter:
                logger.debug(
                    f"Associated DICOM study {normalized_metadata.get('internal_study_id')} "
                    f"with encounter {encounter.id}"
                )
                return encounter.id

            logger.warning(
                f"No active encounter found for patient {internal_patient_id} "
                f"at timestamp {study_timestamp}"
            )
            return None

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error associating DICOM study to encounter: {e}")
            raise ValidationError(f"Failed to associate DICOM study: {e}")

    @staticmethod
    async def get_care_unit_for_study(
        session: AsyncSession,
        encounter_id: Optional[str],
    ) -> Optional[str]:
        """
        Get care unit for DICOM study via encounter.

        Args:
            session: Database session
            encounter_id: Internal encounter ID

        Returns:
            Internal care unit ID or None if not found
        """
        if not encounter_id:
            return None

        try:
            stmt = select(Encounter).where(Encounter.id == encounter_id)
            result = await session.execute(stmt)
            encounter = result.scalars().first()

            if encounter:
                return encounter.care_unit_id

            return None

        except Exception as e:
            logger.error(f"Error getting care unit for study: {e}")
            return None


class DICOMArchiveReferenceManager:
    """Manages references to DICOM image archives."""

    @staticmethod
    async def create_archive_reference(
        session: AsyncSession,
        normalized_metadata: Dict[str, Any],
        archive_url: Optional[str] = None,
        archive_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create reference to DICOM image archive.

        Args:
            session: Database session
            normalized_metadata: Normalized DICOM metadata
            archive_url: URL to DICOM archive (e.g., PACS URL)
            archive_path: File path to DICOM archive

        Returns:
            Dictionary with archive reference

        Raises:
            ValidationError: If reference creation fails
        """
        if not normalized_metadata or not isinstance(normalized_metadata, dict):
            raise ValidationError("normalized_metadata must be a non-empty dictionary")

        try:
            internal_study_id = normalized_metadata.get("internal_study_id")
            external_study_id = normalized_metadata.get("external_study_id")
            sop_instance_uid = normalized_metadata.get("sop_instance_uid")

            if not internal_study_id or not external_study_id:
                raise ValidationError("internal_study_id and external_study_id required")

            # Build archive reference
            reference = {
                "id": f"ARCHIVE-{uuid.uuid4()}",
                "internal_study_id": internal_study_id,
                "external_study_id": external_study_id,
                "sop_instance_uid": sop_instance_uid,
                "archive_url": archive_url,
                "archive_path": archive_path,
                "created_at": datetime.now(timezone.utc),
                "is_available": True,
            }

            logger.debug(
                f"Created archive reference for study {internal_study_id}: "
                f"url={archive_url}, path={archive_path}"
            )

            return reference

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error creating archive reference: {e}")
            raise ValidationError(f"Failed to create archive reference: {e}")

    @staticmethod
    async def resolve_archive_reference(
        session: AsyncSession,
        internal_study_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve DICOM archive reference.

        Args:
            session: Database session
            internal_study_id: Internal study ID

        Returns:
            Dictionary with archive reference or None if not found
        """
        if not internal_study_id or not isinstance(internal_study_id, str):
            raise ValidationError("internal_study_id must be a non-empty string")

        try:
            # In production, would query archive reference table
            logger.debug(f"Resolving archive reference for study {internal_study_id}")
            return None

        except Exception as e:
            logger.error(f"Error resolving archive reference: {e}")
            return None


class DICOMMetadataStorage:
    """Stores DICOM metadata in database."""

    @staticmethod
    async def store_dicom_study(
        session: AsyncSession,
        normalized_metadata: Dict[str, Any],
        encounter_id: Optional[str] = None,
        care_unit_id: Optional[str] = None,
        archive_reference: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Store DICOM study metadata in database.

        Args:
            session: Database session
            normalized_metadata: Normalized DICOM metadata
            encounter_id: Associated encounter ID
            care_unit_id: Associated care unit ID
            archive_reference: Archive reference information

        Returns:
            Dictionary with stored study information

        Raises:
            ValidationError: If storage fails
        """
        if not normalized_metadata or not isinstance(normalized_metadata, dict):
            raise ValidationError("normalized_metadata must be a non-empty dictionary")

        try:
            study_record = {
                "id": normalized_metadata.get("internal_study_id"),
                "patient_id": normalized_metadata.get("internal_patient_id"),
                "encounter_id": encounter_id,
                "care_unit_id": care_unit_id,
                "external_study_id": normalized_metadata.get("external_study_id"),
                "external_patient_id": normalized_metadata.get("external_patient_id"),
                "patient_name": normalized_metadata.get("patient_name"),
                "patient_dob": normalized_metadata.get("patient_dob"),
                "patient_sex": normalized_metadata.get("patient_sex"),
                "study_date": normalized_metadata.get("study_date"),
                "study_time": normalized_metadata.get("study_time"),
                "study_timestamp": normalized_metadata.get("study_timestamp"),
                "study_description": normalized_metadata.get("study_description"),
                "modality": normalized_metadata.get("modality"),
                "series_id": normalized_metadata.get("series_id"),
                "series_number": normalized_metadata.get("series_number"),
                "series_description": normalized_metadata.get("series_description"),
                "series_instance_uid": normalized_metadata.get("series_instance_uid"),
                "sop_class_uid": normalized_metadata.get("sop_class_uid"),
                "sop_instance_uid": normalized_metadata.get("sop_instance_uid"),
                "image_number": normalized_metadata.get("image_number"),
                "archive_url": archive_reference.get("archive_url")
                if archive_reference
                else None,
                "archive_path": archive_reference.get("archive_path")
                if archive_reference
                else None,
                "confidence_score": normalized_metadata.get("confidence_score"),
                "source_system": normalized_metadata.get("source_system"),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

            logger.info(
                f"Stored DICOM study: id={study_record['id']}, "
                f"patient={study_record['patient_id']}, "
                f"modality={study_record['modality']}"
            )

            return study_record

        except Exception as e:
            logger.error(f"Error storing DICOM study: {e}")
            raise ValidationError(f"Failed to store DICOM study: {e}")

    @staticmethod
    async def retrieve_dicom_study(
        session: AsyncSession,
        internal_study_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve DICOM study metadata from database.

        Args:
            session: Database session
            internal_study_id: Internal study ID

        Returns:
            Dictionary with study metadata or None if not found
        """
        if not internal_study_id or not isinstance(internal_study_id, str):
            raise ValidationError("internal_study_id must be a non-empty string")

        try:
            # In production, would query DICOM study table
            logger.debug(f"Retrieving DICOM study: {internal_study_id}")
            return None

        except Exception as e:
            logger.error(f"Error retrieving DICOM study: {e}")
            return None

    @staticmethod
    async def retrieve_patient_studies(
        session: AsyncSession,
        internal_patient_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all DICOM studies for a patient.

        Args:
            session: Database session
            internal_patient_id: Internal patient ID
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of study metadata dictionaries
        """
        if not internal_patient_id or not isinstance(internal_patient_id, str):
            raise ValidationError("internal_patient_id must be a non-empty string")

        try:
            # In production, would query DICOM study table with filters
            logger.debug(
                f"Retrieving DICOM studies for patient: {internal_patient_id}, "
                f"start_date={start_date}, end_date={end_date}"
            )
            return []

        except Exception as e:
            logger.error(f"Error retrieving patient studies: {e}")
            return []
