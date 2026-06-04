"""
Unit tests for DICOM metadata listener module.

Tests cover:
- DICOM C-STORE handler
- DICOM metadata extraction
- DICOM message validation
- Concurrent DICOM transfer handling
- Error handling
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.ingestion.dicom_listener import (
    DICOMCStoreHandler,
    DICOMMetadataExtractor,
    DICOMMessageValidator,
    DICOMConnectionManager,
    DICOMTransfer,
)
from mcp_server.utils.validators import ValidationError


class TestDICOMCStoreHandler:
    """Test DICOM C-STORE handler."""

    def test_init(self):
        """Test initialization."""
        handler = DICOMCStoreHandler(port=11112)
        assert handler.port == 11112
        assert handler.active_transfers == {}
        assert handler.transfer_lock is not None

    def test_init_custom_port(self):
        """Test initialization with custom port."""
        handler = DICOMCStoreHandler(port=12345)
        assert handler.port == 12345

    @pytest.mark.asyncio
    async def test_start(self):
        """Test starting DICOM server."""
        handler = DICOMCStoreHandler()
        await handler.start()
        # Server should be started
        assert handler.port == 11112

    @pytest.mark.asyncio
    async def test_stop(self):
        """Test stopping DICOM server."""
        handler = DICOMCStoreHandler()
        await handler.start()
        await handler.stop()
        # Server should be stopped
        assert handler.active_transfers == {}

    @pytest.mark.asyncio
    async def test_handle_c_store_success(self):
        """Test successful C-STORE handling."""
        session = AsyncMock(spec=AsyncSession)
        handler = DICOMCStoreHandler()

        dicom_dataset = {
            "PatientID": "PAT-123",
            "StudyInstanceUID": "1.2.3.4.5",
            "Modality": "CT",
            "SOPClassUID": "1.2.840.10008.5.1.4.1.1.2",
            "SOPInstanceUID": "1.2.3.4.5.6",
            "StudyDate": "20240101",
            "StudyTime": "120000",
            "StudyDescription": "CT Chest",
        }

        result = await handler.handle_c_store(session, dicom_dataset)

        assert result["status"] == "success"
        assert "transfer_id" in result
        assert result["transfer_id"] in handler.active_transfers

    @pytest.mark.asyncio
    async def test_handle_c_store_missing_required_field(self):
        """Test C-STORE with missing required field."""
        session = AsyncMock(spec=AsyncSession)
        handler = DICOMCStoreHandler()

        dicom_dataset = {
            "PatientID": "PAT-123",
            # Missing StudyInstanceUID
            "Modality": "CT",
            "SOPClassUID": "1.2.840.10008.5.1.4.1.1.2",
            "SOPInstanceUID": "1.2.3.4.5.6",
        }

        with pytest.raises(ValidationError):
            await handler.handle_c_store(session, dicom_dataset)

    @pytest.mark.asyncio
    async def test_handle_c_store_invalid_dataset(self):
        """Test C-STORE with invalid dataset."""
        session = AsyncMock(spec=AsyncSession)
        handler = DICOMCStoreHandler()

        with pytest.raises(ValidationError):
            await handler.handle_c_store(session, None)

        with pytest.raises(ValidationError):
            await handler.handle_c_store(session, {})

    @pytest.mark.asyncio
    async def test_get_transfer_status(self):
        """Test getting transfer status."""
        session = AsyncMock(spec=AsyncSession)
        handler = DICOMCStoreHandler()

        dicom_dataset = {
            "PatientID": "PAT-123",
            "StudyInstanceUID": "1.2.3.4.5",
            "Modality": "CT",
            "SOPClassUID": "1.2.840.10008.5.1.4.1.1.2",
            "SOPInstanceUID": "1.2.3.4.5.6",
            "StudyDate": "20240101",
            "StudyTime": "120000",
        }

        result = await handler.handle_c_store(session, dicom_dataset)
        transfer_id = result["transfer_id"]

        status = await handler.get_transfer_status(transfer_id)
        assert status is not None
        assert status["transfer_id"] == transfer_id
        assert status["is_complete"] is False

    @pytest.mark.asyncio
    async def test_complete_transfer(self):
        """Test completing a transfer."""
        session = AsyncMock(spec=AsyncSession)
        handler = DICOMCStoreHandler()

        dicom_dataset = {
            "PatientID": "PAT-123",
            "StudyInstanceUID": "1.2.3.4.5",
            "Modality": "CT",
            "SOPClassUID": "1.2.840.10008.5.1.4.1.1.2",
            "SOPInstanceUID": "1.2.3.4.5.6",
            "StudyDate": "20240101",
            "StudyTime": "120000",
        }

        result = await handler.handle_c_store(session, dicom_dataset)
        transfer_id = result["transfer_id"]

        await handler.complete_transfer(transfer_id)

        status = await handler.get_transfer_status(transfer_id)
        assert status["is_complete"] is True
        assert status["end_time"] is not None


class TestDICOMTransfer:
    """Test DICOM transfer class."""

    def test_init(self):
        """Test initialization."""
        metadata = {"patient_id": "PAT-123", "study_id": "STUDY-456"}
        transfer = DICOMTransfer("DICOM-123", metadata)

        assert transfer.transfer_id == "DICOM-123"
        assert transfer.metadata == metadata
        assert transfer.is_complete is False
        assert transfer.start_time is not None

    def test_mark_complete(self):
        """Test marking transfer as complete."""
        metadata = {"patient_id": "PAT-123"}
        transfer = DICOMTransfer("DICOM-123", metadata)

        assert transfer.is_complete is False
        transfer.mark_complete()
        assert transfer.is_complete is True
        assert transfer.end_time is not None

    @pytest.mark.asyncio
    async def test_close(self):
        """Test closing transfer."""
        metadata = {"patient_id": "PAT-123"}
        transfer = DICOMTransfer("DICOM-123", metadata)

        await transfer.close()
        assert transfer.is_complete is True

    def test_get_status(self):
        """Test getting transfer status."""
        metadata = {"patient_id": "PAT-123"}
        transfer = DICOMTransfer("DICOM-123", metadata)

        status = transfer.get_status()
        assert status["transfer_id"] == "DICOM-123"
        assert status["is_complete"] is False
        assert status["start_time"] is not None
        assert status["end_time"] is None

    def test_get_status_after_complete(self):
        """Test getting status after completion."""
        metadata = {"patient_id": "PAT-123"}
        transfer = DICOMTransfer("DICOM-123", metadata)

        transfer.mark_complete()
        status = transfer.get_status()

        assert status["is_complete"] is True
        assert status["end_time"] is not None
        assert status["duration_seconds"] is not None


class TestDICOMMetadataExtractor:
    """Test DICOM metadata extractor."""

    @pytest.mark.asyncio
    async def test_extract_metadata_success(self):
        """Test successful metadata extraction."""
        dicom_dataset = {
            "PatientID": "PAT-123",
            "PatientName": "Doe^John",
            "PatientBirthDate": "19800101",
            "PatientSex": "M",
            "StudyInstanceUID": "1.2.3.4.5",
            "StudyDate": "20240101",
            "StudyTime": "120000",
            "StudyDescription": "CT Chest",
            "Modality": "CT",
            "SeriesInstanceUID": "1.2.3.4.5.1",
            "SeriesNumber": "1",
            "SeriesDescription": "Chest",
            "SOPClassUID": "1.2.840.10008.5.1.4.1.1.2",
            "SOPInstanceUID": "1.2.3.4.5.6",
            "InstanceNumber": "1",
        }

        result = await DICOMMetadataExtractor.extract_metadata(dicom_dataset)

        assert result["patient_id"] == "PAT-123"
        assert result["patient_name"] == "Doe^John"
        assert result["study_id"] == "1.2.3.4.5"
        assert result["modality"] == "CT"
        assert result["study_description"] == "CT Chest"
        assert result["confidence_score"] == 1.0
        assert result["extraction_timestamp"] is not None

    @pytest.mark.asyncio
    async def test_extract_metadata_missing_optional_fields(self):
        """Test extraction with missing optional fields."""
        dicom_dataset = {
            "PatientID": "PAT-123",
            "StudyInstanceUID": "1.2.3.4.5",
            "Modality": "CT",
            "SOPClassUID": "1.2.840.10008.5.1.4.1.1.2",
            "SOPInstanceUID": "1.2.3.4.5.6",
            # Missing optional fields
        }

        result = await DICOMMetadataExtractor.extract_metadata(dicom_dataset)

        assert result["patient_id"] == "PAT-123"
        assert result["study_id"] == "1.2.3.4.5"
        assert result["confidence_score"] < 1.0

    @pytest.mark.asyncio
    async def test_extract_metadata_invalid_dataset(self):
        """Test extraction with invalid dataset."""
        with pytest.raises(ValidationError):
            await DICOMMetadataExtractor.extract_metadata(None)

        with pytest.raises(ValidationError):
            await DICOMMetadataExtractor.extract_metadata({})

    @pytest.mark.asyncio
    async def test_extract_metadata_invalid_timestamp(self):
        """Test extraction with invalid timestamp."""
        dicom_dataset = {
            "PatientID": "PAT-123",
            "StudyInstanceUID": "1.2.3.4.5",
            "Modality": "CT",
            "SOPClassUID": "1.2.840.10008.5.1.4.1.1.2",
            "SOPInstanceUID": "1.2.3.4.5.6",
            "StudyDate": "invalid",
            "StudyTime": "invalid",
        }

        result = await DICOMMetadataExtractor.extract_metadata(dicom_dataset)

        # Should handle invalid timestamp gracefully
        assert result["study_timestamp"] is not None


class TestDICOMMessageValidator:
    """Test DICOM message validator."""

    @pytest.mark.asyncio
    async def test_validate_valid_message(self):
        """Test validation of valid DICOM message."""
        dicom_dataset = {
            "PatientID": "PAT-123",
            "StudyInstanceUID": "1.2.3.4.5",
            "Modality": "CT",
            "SOPClassUID": "1.2.840.10008.5.1.4.1.1.2",
            "SOPInstanceUID": "1.2.3.4.5.6",
        }

        # Should not raise
        await DICOMMessageValidator.validate_dicom_message(dicom_dataset)

    @pytest.mark.asyncio
    async def test_validate_missing_required_field(self):
        """Test validation with missing required field."""
        dicom_dataset = {
            "PatientID": "PAT-123",
            # Missing StudyInstanceUID
            "Modality": "CT",
            "SOPClassUID": "1.2.840.10008.5.1.4.1.1.2",
            "SOPInstanceUID": "1.2.3.4.5.6",
        }

        with pytest.raises(ValidationError):
            await DICOMMessageValidator.validate_dicom_message(dicom_dataset)

    @pytest.mark.asyncio
    async def test_validate_invalid_dataset(self):
        """Test validation with invalid dataset."""
        with pytest.raises(ValidationError):
            await DICOMMessageValidator.validate_dicom_message(None)

        with pytest.raises(ValidationError):
            await DICOMMessageValidator.validate_dicom_message({})

    @pytest.mark.asyncio
    async def test_validate_invalid_uid_format(self):
        """Test validation with invalid UID format."""
        dicom_dataset = {
            "PatientID": "PAT-123",
            "StudyInstanceUID": "invalid-uid",  # Invalid format
            "Modality": "CT",
            "SOPClassUID": "1.2.840.10008.5.1.4.1.1.2",
            "SOPInstanceUID": "1.2.3.4.5.6",
        }

        with pytest.raises(ValidationError):
            await DICOMMessageValidator.validate_dicom_message(dicom_dataset)

    @pytest.mark.asyncio
    async def test_validate_unsupported_modality(self):
        """Test validation with unsupported modality."""
        dicom_dataset = {
            "PatientID": "PAT-123",
            "StudyInstanceUID": "1.2.3.4.5",
            "Modality": "UNKNOWN",  # Unsupported
            "SOPClassUID": "1.2.840.10008.5.1.4.1.1.2",
            "SOPInstanceUID": "1.2.3.4.5.6",
        }

        # Should not raise, just log warning
        await DICOMMessageValidator.validate_dicom_message(dicom_dataset)

    @pytest.mark.asyncio
    async def test_validate_all_supported_modalities(self):
        """Test validation with all supported modalities."""
        modalities = ["CT", "MR", "XR", "US", "NM", "PT", "OT", "PR", "SR", "KO"]

        for modality in modalities:
            dicom_dataset = {
                "PatientID": "PAT-123",
                "StudyInstanceUID": "1.2.3.4.5",
                "Modality": modality,
                "SOPClassUID": "1.2.840.10008.5.1.4.1.1.2",
                "SOPInstanceUID": "1.2.3.4.5.6",
            }

            # Should not raise
            await DICOMMessageValidator.validate_dicom_message(dicom_dataset)


class TestDICOMConnectionManager:
    """Test DICOM connection manager."""

    def test_init(self):
        """Test initialization."""
        manager = DICOMConnectionManager(max_concurrent_transfers=10)
        assert manager.max_concurrent_transfers == 10
        assert manager.active_transfers == {}

    def test_init_custom_max_transfers(self):
        """Test initialization with custom max transfers."""
        manager = DICOMConnectionManager(max_concurrent_transfers=20)
        assert manager.max_concurrent_transfers == 20

    @pytest.mark.asyncio
    async def test_acquire_release_transfer_slot(self):
        """Test acquiring and releasing transfer slots."""
        manager = DICOMConnectionManager(max_concurrent_transfers=2)

        # Acquire first slot
        await manager.acquire_transfer_slot()
        # Acquire second slot
        await manager.acquire_transfer_slot()

        # Release slots
        manager.release_transfer_slot()
        manager.release_transfer_slot()

    @pytest.mark.asyncio
    async def test_register_unregister_transfer(self):
        """Test registering and unregistering transfers."""
        manager = DICOMConnectionManager()
        metadata = {"patient_id": "PAT-123"}

        await manager.register_transfer("DICOM-123", metadata)
        assert "DICOM-123" in manager.active_transfers

        await manager.unregister_transfer("DICOM-123")
        assert "DICOM-123" not in manager.active_transfers

    @pytest.mark.asyncio
    async def test_get_active_transfer_count(self):
        """Test getting active transfer count."""
        manager = DICOMConnectionManager()
        metadata = {"patient_id": "PAT-123"}

        assert await manager.get_active_transfer_count() == 0

        await manager.register_transfer("DICOM-1", metadata)
        assert await manager.get_active_transfer_count() == 1

        await manager.register_transfer("DICOM-2", metadata)
        assert await manager.get_active_transfer_count() == 2

        await manager.unregister_transfer("DICOM-1")
        assert await manager.get_active_transfer_count() == 1

    @pytest.mark.asyncio
    async def test_get_transfer_status(self):
        """Test getting transfer status."""
        manager = DICOMConnectionManager()
        metadata = {"patient_id": "PAT-123"}

        await manager.register_transfer("DICOM-123", metadata)
        status = await manager.get_transfer_status("DICOM-123")

        assert status is not None
        assert status["transfer_id"] == "DICOM-123"
        assert status["is_complete"] is False

    @pytest.mark.asyncio
    async def test_get_all_transfers(self):
        """Test getting all transfers."""
        manager = DICOMConnectionManager()
        metadata = {"patient_id": "PAT-123"}

        await manager.register_transfer("DICOM-1", metadata)
        await manager.register_transfer("DICOM-2", metadata)

        transfers = await manager.get_all_transfers()
        assert len(transfers) == 2
        assert any(t["transfer_id"] == "DICOM-1" for t in transfers)
        assert any(t["transfer_id"] == "DICOM-2" for t in transfers)


class TestDICOMListenerIntegration:
    """Integration tests for DICOM listener."""

    @pytest.mark.asyncio
    async def test_complete_dicom_ingestion_flow(self):
        """Test complete DICOM ingestion flow."""
        session = AsyncMock(spec=AsyncSession)
        handler = DICOMCStoreHandler()

        # 1. Start server
        await handler.start()

        # 2. Receive DICOM C-STORE
        dicom_dataset = {
            "PatientID": "PAT-123",
            "PatientName": "Doe^John",
            "StudyInstanceUID": "1.2.3.4.5",
            "StudyDate": "20240101",
            "StudyTime": "120000",
            "StudyDescription": "CT Chest",
            "Modality": "CT",
            "SeriesInstanceUID": "1.2.3.4.5.1",
            "SOPClassUID": "1.2.840.10008.5.1.4.1.1.2",
            "SOPInstanceUID": "1.2.3.4.5.6",
        }

        result = await handler.handle_c_store(session, dicom_dataset)
        assert result["status"] == "success"
        transfer_id = result["transfer_id"]

        # 3. Check transfer status
        status = await handler.get_transfer_status(transfer_id)
        assert status is not None
        assert status["is_complete"] is False

        # 4. Complete transfer
        await handler.complete_transfer(transfer_id)
        status = await handler.get_transfer_status(transfer_id)
        assert status["is_complete"] is True

        # 5. Stop server
        await handler.stop()

    @pytest.mark.asyncio
    async def test_concurrent_dicom_transfers(self):
        """Test handling concurrent DICOM transfers."""
        session = AsyncMock(spec=AsyncSession)
        handler = DICOMCStoreHandler()
        await handler.start()

        # Simulate multiple concurrent transfers
        transfer_ids = []
        for i in range(5):
            dicom_dataset = {
                "PatientID": f"PAT-{i}",
                "StudyInstanceUID": f"1.2.3.4.{i}",
                "Modality": "CT",
                "SOPClassUID": "1.2.840.10008.5.1.4.1.1.2",
                "SOPInstanceUID": f"1.2.3.4.{i}.6",
                "StudyDate": "20240101",
                "StudyTime": "120000",
            }

            result = await handler.handle_c_store(session, dicom_dataset)
            transfer_ids.append(result["transfer_id"])

        # Verify all transfers are active
        assert len(handler.active_transfers) == 5

        # Complete all transfers
        for transfer_id in transfer_ids:
            await handler.complete_transfer(transfer_id)

        await handler.stop()
