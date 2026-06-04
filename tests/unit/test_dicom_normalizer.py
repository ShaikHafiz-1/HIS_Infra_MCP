"""
Unit tests for DICOM metadata normalization and storage module.

Tests cover:
- DICOM metadata normalization
- DICOM study association with encounters and care units
- DICOM archive reference management
- DICOM metadata storage
- ID mapper integration
- Error handling
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.ingestion.dicom_normalizer import (
    DICOMMetadataNormalizer,
    DICOMStudyAssociator,
    DICOMArchiveReferenceManager,
    DICOMMetadataStorage,
)
from mcp_server.utils.validators import ValidationError


class TestDICOMMetadataNormalizer:
    """Test DICOM metadata normalizer."""

    @pytest.mark.asyncio
    async def test_normalize_metadata_success(self):
        """Test successful metadata normalization."""
        session = AsyncMock(spec=AsyncSession)

        # Mock ID mapper
        with patch(
            "mcp_server.ingestion.dicom_normalizer.IDMapper.get_or_create_patient_id"
        ) as mock_get_patient_id:
            mock_get_patient_id.return_value = "PAT-internal-123"

            raw_metadata = {
                "patient_id": "PAT-123",
                "patient_name": "Doe John",
                "patient_dob": "1980-01-01",
                "patient_sex": "M",
                "study_id": "STUDY-456",
                "study_date": "20240101",
                "study_time": "120000",
                "study_timestamp": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                "study_description": "CT Chest",
                "modality": "CT",
                "series_id": "SERIES-789",
                "series_number": "1",
                "series_description": "Chest",
                "series_instance_uid": "1.2.3.4.5.1",
                "sop_class_uid": "1.2.840.10008.5.1.4.1.1.2",
                "sop_instance_uid": "1.2.3.4.5.6",
                "image_number": "1",
            }

            result = await DICOMMetadataNormalizer.normalize_metadata(
                session, raw_metadata
            )

            assert result["internal_patient_id"] == "PAT-internal-123"
            assert result["external_patient_id"] == "PAT-123"
            assert "internal_study_id" in result
            assert result["study_description"] == "CT Chest"
            assert result["modality"] == "CT"
            assert result["confidence_score"] == 1.0
            assert result["normalization_timestamp"] is not None

    @pytest.mark.asyncio
    async def test_normalize_metadata_missing_patient_id(self):
        """Test normalization with missing patient ID."""
        session = AsyncMock(spec=AsyncSession)

        raw_metadata = {
            # Missing patient_id
            "study_id": "STUDY-456",
            "study_timestamp": datetime.now(timezone.utc),
        }

        with pytest.raises(ValidationError):
            await DICOMMetadataNormalizer.normalize_metadata(session, raw_metadata)

    @pytest.mark.asyncio
    async def test_normalize_metadata_missing_study_id(self):
        """Test normalization with missing study ID."""
        session = AsyncMock(spec=AsyncSession)

        with patch(
            "mcp_server.ingestion.dicom_normalizer.IDMapper.get_or_create_patient_id"
        ) as mock_get_patient_id:
            mock_get_patient_id.return_value = "PAT-internal-123"

            raw_metadata = {
                "patient_id": "PAT-123",
                # Missing study_id
                "study_timestamp": datetime.now(timezone.utc),
            }

            with pytest.raises(ValidationError):
                await DICOMMetadataNormalizer.normalize_metadata(session, raw_metadata)

    @pytest.mark.asyncio
    async def test_normalize_metadata_invalid_input(self):
        """Test normalization with invalid input."""
        session = AsyncMock(spec=AsyncSession)

        with pytest.raises(ValidationError):
            await DICOMMetadataNormalizer.normalize_metadata(session, None)

        with pytest.raises(ValidationError):
            await DICOMMetadataNormalizer.normalize_metadata(session, {})

    @pytest.mark.asyncio
    async def test_normalize_metadata_missing_optional_fields(self):
        """Test normalization with missing optional fields."""
        session = AsyncMock(spec=AsyncSession)

        with patch(
            "mcp_server.ingestion.dicom_normalizer.IDMapper.get_or_create_patient_id"
        ) as mock_get_patient_id:
            mock_get_patient_id.return_value = "PAT-internal-123"

            raw_metadata = {
                "patient_id": "PAT-123",
                "study_id": "STUDY-456",
                "study_timestamp": datetime.now(timezone.utc),
                # Missing optional fields
            }

            result = await DICOMMetadataNormalizer.normalize_metadata(
                session, raw_metadata
            )

            assert result["confidence_score"] < 1.0

    @pytest.mark.asyncio
    async def test_normalize_metadata_default_modality(self):
        """Test normalization with default modality."""
        session = AsyncMock(spec=AsyncSession)

        with patch(
            "mcp_server.ingestion.dicom_normalizer.IDMapper.get_or_create_patient_id"
        ) as mock_get_patient_id:
            mock_get_patient_id.return_value = "PAT-internal-123"

            raw_metadata = {
                "patient_id": "PAT-123",
                "study_id": "STUDY-456",
                "study_timestamp": datetime.now(timezone.utc),
                # Missing modality
            }

            result = await DICOMMetadataNormalizer.normalize_metadata(
                session, raw_metadata
            )

            assert result["modality"] == "OT"  # Default


class TestDICOMStudyAssociator:
    """Test DICOM study associator."""

    @pytest.mark.asyncio
    async def test_associate_study_to_encounter_success(self):
        """Test successful study association."""
        session = AsyncMock(spec=AsyncSession)

        # Mock encounter
        encounter = MagicMock()
        encounter.id = "ENC-123"
        encounter.patient_id = "PAT-456"

        # Mock query result
        scalars = MagicMock()
        scalars.first.return_value = encounter

        result = MagicMock()
        result.scalars.return_value = scalars

        session.execute.return_value = result

        normalized_metadata = {
            "internal_patient_id": "PAT-456",
            "internal_study_id": "STUDY-789",
            "study_timestamp": datetime.now(timezone.utc),
        }

        encounter_id = await DICOMStudyAssociator.associate_study_to_encounter(
            session, normalized_metadata
        )

        assert encounter_id == "ENC-123"

    @pytest.mark.asyncio
    async def test_associate_study_to_encounter_not_found(self):
        """Test association when encounter not found."""
        session = AsyncMock(spec=AsyncSession)

        # Mock query result - no encounter found
        scalars = MagicMock()
        scalars.first.return_value = None

        result = MagicMock()
        result.scalars.return_value = scalars

        session.execute.return_value = result

        normalized_metadata = {
            "internal_patient_id": "PAT-456",
            "internal_study_id": "STUDY-789",
            "study_timestamp": datetime.now(timezone.utc),
        }

        encounter_id = await DICOMStudyAssociator.associate_study_to_encounter(
            session, normalized_metadata
        )

        assert encounter_id is None

    @pytest.mark.asyncio
    async def test_associate_study_to_encounter_invalid_input(self):
        """Test association with invalid input."""
        session = AsyncMock(spec=AsyncSession)

        with pytest.raises(ValidationError):
            await DICOMStudyAssociator.associate_study_to_encounter(session, None)

        with pytest.raises(ValidationError):
            await DICOMStudyAssociator.associate_study_to_encounter(session, {})

    @pytest.mark.asyncio
    async def test_associate_study_to_encounter_missing_patient_id(self):
        """Test association with missing patient ID."""
        session = AsyncMock(spec=AsyncSession)

        normalized_metadata = {
            # Missing internal_patient_id
            "internal_study_id": "STUDY-789",
            "study_timestamp": datetime.now(timezone.utc),
        }

        with pytest.raises(ValidationError):
            await DICOMStudyAssociator.associate_study_to_encounter(
                session, normalized_metadata
            )

    @pytest.mark.asyncio
    async def test_get_care_unit_for_study_success(self):
        """Test getting care unit for study."""
        session = AsyncMock(spec=AsyncSession)

        # Mock encounter
        encounter = MagicMock()
        encounter.id = "ENC-123"
        encounter.care_unit_id = "CU-456"

        # Mock query result
        scalars = MagicMock()
        scalars.first.return_value = encounter

        result = MagicMock()
        result.scalars.return_value = scalars

        session.execute.return_value = result

        care_unit_id = await DICOMStudyAssociator.get_care_unit_for_study(
            session, "ENC-123"
        )

        assert care_unit_id == "CU-456"

    @pytest.mark.asyncio
    async def test_get_care_unit_for_study_not_found(self):
        """Test getting care unit when encounter not found."""
        session = AsyncMock(spec=AsyncSession)

        # Mock query result - no encounter found
        scalars = MagicMock()
        scalars.first.return_value = None

        result = MagicMock()
        result.scalars.return_value = scalars

        session.execute.return_value = result

        care_unit_id = await DICOMStudyAssociator.get_care_unit_for_study(
            session, "ENC-999"
        )

        assert care_unit_id is None

    @pytest.mark.asyncio
    async def test_get_care_unit_for_study_no_encounter_id(self):
        """Test getting care unit with no encounter ID."""
        session = AsyncMock(spec=AsyncSession)

        care_unit_id = await DICOMStudyAssociator.get_care_unit_for_study(
            session, None
        )

        assert care_unit_id is None


class TestDICOMArchiveReferenceManager:
    """Test DICOM archive reference manager."""

    @pytest.mark.asyncio
    async def test_create_archive_reference_success(self):
        """Test successful archive reference creation."""
        session = AsyncMock(spec=AsyncSession)

        normalized_metadata = {
            "internal_study_id": "STUDY-123",
            "external_study_id": "STUDY-456",
            "sop_instance_uid": "1.2.3.4.5.6",
        }

        reference = await DICOMArchiveReferenceManager.create_archive_reference(
            session,
            normalized_metadata,
            archive_url="http://pacs.hospital.local/study/STUDY-456",
            archive_path="/archive/2024/01/STUDY-456",
        )

        assert reference["internal_study_id"] == "STUDY-123"
        assert reference["external_study_id"] == "STUDY-456"
        assert reference["archive_url"] == "http://pacs.hospital.local/study/STUDY-456"
        assert reference["archive_path"] == "/archive/2024/01/STUDY-456"
        assert reference["is_available"] is True
        assert "id" in reference
        assert "created_at" in reference

    @pytest.mark.asyncio
    async def test_create_archive_reference_without_url(self):
        """Test archive reference creation without URL."""
        session = AsyncMock(spec=AsyncSession)

        normalized_metadata = {
            "internal_study_id": "STUDY-123",
            "external_study_id": "STUDY-456",
        }

        reference = await DICOMArchiveReferenceManager.create_archive_reference(
            session, normalized_metadata, archive_path="/archive/2024/01/STUDY-456"
        )

        assert reference["archive_url"] is None
        assert reference["archive_path"] == "/archive/2024/01/STUDY-456"

    @pytest.mark.asyncio
    async def test_create_archive_reference_invalid_input(self):
        """Test archive reference creation with invalid input."""
        session = AsyncMock(spec=AsyncSession)

        with pytest.raises(ValidationError):
            await DICOMArchiveReferenceManager.create_archive_reference(
                session, None
            )

        with pytest.raises(ValidationError):
            await DICOMArchiveReferenceManager.create_archive_reference(session, {})

    @pytest.mark.asyncio
    async def test_create_archive_reference_missing_study_id(self):
        """Test archive reference creation with missing study ID."""
        session = AsyncMock(spec=AsyncSession)

        normalized_metadata = {
            # Missing internal_study_id
            "external_study_id": "STUDY-456",
        }

        with pytest.raises(ValidationError):
            await DICOMArchiveReferenceManager.create_archive_reference(
                session, normalized_metadata
            )

    @pytest.mark.asyncio
    async def test_resolve_archive_reference(self):
        """Test resolving archive reference."""
        session = AsyncMock(spec=AsyncSession)

        reference = await DICOMArchiveReferenceManager.resolve_archive_reference(
            session, "STUDY-123"
        )

        # In production, would return reference from database
        assert reference is None

    @pytest.mark.asyncio
    async def test_resolve_archive_reference_invalid_study_id(self):
        """Test resolving with invalid study ID."""
        session = AsyncMock(spec=AsyncSession)

        with pytest.raises(ValidationError):
            await DICOMArchiveReferenceManager.resolve_archive_reference(session, "")

        with pytest.raises(ValidationError):
            await DICOMArchiveReferenceManager.resolve_archive_reference(session, None)


class TestDICOMMetadataStorage:
    """Test DICOM metadata storage."""

    @pytest.mark.asyncio
    async def test_store_dicom_study_success(self):
        """Test successful DICOM study storage."""
        session = AsyncMock(spec=AsyncSession)

        normalized_metadata = {
            "internal_study_id": "STUDY-123",
            "internal_patient_id": "PAT-456",
            "external_study_id": "STUDY-789",
            "external_patient_id": "PAT-999",
            "patient_name": "Doe^John",
            "patient_dob": "1980-01-01",
            "patient_sex": "M",
            "study_date": "20240101",
            "study_time": "120000",
            "study_timestamp": datetime.now(timezone.utc),
            "study_description": "CT Chest",
            "modality": "CT",
            "series_id": "SERIES-123",
            "series_number": "1",
            "series_description": "Chest",
            "series_instance_uid": "1.2.3.4.5.1",
            "sop_class_uid": "1.2.840.10008.5.1.4.1.1.2",
            "sop_instance_uid": "1.2.3.4.5.6",
            "image_number": "1",
            "confidence_score": 1.0,
            "source_system": "DICOM",
        }

        archive_reference = {
            "archive_url": "http://pacs.hospital.local/study/STUDY-789",
            "archive_path": "/archive/2024/01/STUDY-789",
        }

        result = await DICOMMetadataStorage.store_dicom_study(
            session,
            normalized_metadata,
            encounter_id="ENC-123",
            care_unit_id="CU-456",
            archive_reference=archive_reference,
        )

        assert result["id"] == "STUDY-123"
        assert result["patient_id"] == "PAT-456"
        assert result["encounter_id"] == "ENC-123"
        assert result["care_unit_id"] == "CU-456"
        assert result["modality"] == "CT"
        assert result["archive_url"] == "http://pacs.hospital.local/study/STUDY-789"
        assert result["created_at"] is not None

    @pytest.mark.asyncio
    async def test_store_dicom_study_without_encounter(self):
        """Test storing DICOM study without encounter."""
        session = AsyncMock(spec=AsyncSession)

        normalized_metadata = {
            "internal_study_id": "STUDY-123",
            "internal_patient_id": "PAT-456",
            "external_study_id": "STUDY-789",
            "external_patient_id": "PAT-999",
            "study_timestamp": datetime.now(timezone.utc),
            "modality": "CT",
            "confidence_score": 1.0,
            "source_system": "DICOM",
        }

        result = await DICOMMetadataStorage.store_dicom_study(
            session, normalized_metadata
        )

        assert result["id"] == "STUDY-123"
        assert result["encounter_id"] is None
        assert result["care_unit_id"] is None

    @pytest.mark.asyncio
    async def test_store_dicom_study_invalid_input(self):
        """Test storing with invalid input."""
        session = AsyncMock(spec=AsyncSession)

        with pytest.raises(ValidationError):
            await DICOMMetadataStorage.store_dicom_study(session, None)

        with pytest.raises(ValidationError):
            await DICOMMetadataStorage.store_dicom_study(session, {})

    @pytest.mark.asyncio
    async def test_retrieve_dicom_study(self):
        """Test retrieving DICOM study."""
        session = AsyncMock(spec=AsyncSession)

        result = await DICOMMetadataStorage.retrieve_dicom_study(
            session, "STUDY-123"
        )

        # In production, would return study from database
        assert result is None

    @pytest.mark.asyncio
    async def test_retrieve_dicom_study_invalid_id(self):
        """Test retrieving with invalid study ID."""
        session = AsyncMock(spec=AsyncSession)

        with pytest.raises(ValidationError):
            await DICOMMetadataStorage.retrieve_dicom_study(session, "")

        with pytest.raises(ValidationError):
            await DICOMMetadataStorage.retrieve_dicom_study(session, None)

    @pytest.mark.asyncio
    async def test_retrieve_patient_studies(self):
        """Test retrieving patient studies."""
        session = AsyncMock(spec=AsyncSession)

        result = await DICOMMetadataStorage.retrieve_patient_studies(
            session, "PAT-123"
        )

        # In production, would return studies from database
        assert result == []

    @pytest.mark.asyncio
    async def test_retrieve_patient_studies_with_date_range(self):
        """Test retrieving patient studies with date range."""
        session = AsyncMock(spec=AsyncSession)

        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 31, tzinfo=timezone.utc)

        result = await DICOMMetadataStorage.retrieve_patient_studies(
            session, "PAT-123", start_date=start_date, end_date=end_date
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_retrieve_patient_studies_invalid_patient_id(self):
        """Test retrieving with invalid patient ID."""
        session = AsyncMock(spec=AsyncSession)

        with pytest.raises(ValidationError):
            await DICOMMetadataStorage.retrieve_patient_studies(session, "")

        with pytest.raises(ValidationError):
            await DICOMMetadataStorage.retrieve_patient_studies(session, None)


class TestDICOMNormalizerIntegration:
    """Integration tests for DICOM normalizer."""

    @pytest.mark.asyncio
    async def test_complete_dicom_normalization_flow(self):
        """Test complete DICOM normalization flow."""
        session = AsyncMock(spec=AsyncSession)

        # Mock ID mapper
        with patch(
            "mcp_server.ingestion.dicom_normalizer.IDMapper.get_or_create_patient_id"
        ) as mock_get_patient_id:
            mock_get_patient_id.return_value = "PAT-internal-123"

            # Mock encounter
            encounter = MagicMock()
            encounter.id = "ENC-123"
            encounter.care_unit_id = "CU-456"

            scalars = MagicMock()
            scalars.first.return_value = encounter

            result = MagicMock()
            result.scalars.return_value = scalars

            session.execute.return_value = result

            # 1. Extract raw metadata
            raw_metadata = {
                "patient_id": "PAT-123",
                "patient_name": "Doe^John",
                "study_id": "STUDY-456",
                "study_date": "20240101",
                "study_time": "120000",
                "study_timestamp": datetime.now(timezone.utc),
                "study_description": "CT Chest",
                "modality": "CT",
                "series_id": "SERIES-789",
                "sop_class_uid": "1.2.840.10008.5.1.4.1.1.2",
                "sop_instance_uid": "1.2.3.4.5.6",
            }

            # 2. Normalize metadata
            normalized = await DICOMMetadataNormalizer.normalize_metadata(
                session, raw_metadata
            )
            assert normalized["internal_patient_id"] == "PAT-internal-123"

            # 3. Associate with encounter
            encounter_id = (
                await DICOMStudyAssociator.associate_study_to_encounter(
                    session, normalized
                )
            )
            assert encounter_id == "ENC-123"

            # 4. Get care unit
            care_unit_id = await DICOMStudyAssociator.get_care_unit_for_study(
                session, encounter_id
            )
            assert care_unit_id == "CU-456"

            # 5. Create archive reference
            archive_ref = (
                await DICOMArchiveReferenceManager.create_archive_reference(
                    session,
                    normalized,
                    archive_url="http://pacs.hospital.local/study/STUDY-456",
                )
            )
            assert archive_ref["internal_study_id"] == normalized["internal_study_id"]

            # 6. Store study
            stored = await DICOMMetadataStorage.store_dicom_study(
                session,
                normalized,
                encounter_id=encounter_id,
                care_unit_id=care_unit_id,
                archive_reference=archive_ref,
            )
            assert stored["id"] == normalized["internal_study_id"]
            assert stored["encounter_id"] == "ENC-123"
            assert stored["care_unit_id"] == "CU-456"
