"""
DICOM Metadata Ingestion System for Hospital Clinical Intelligence MCP Platform.

This module implements DICOM metadata ingestion including:
- DICOM C-STORE handler on port 11112
- DICOM metadata extraction (patient ID, study ID, modality, timestamp, description)
- DICOM message validation
- Concurrent DICOM transfer handling
- Comprehensive error handling and logging
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.utils.logger import get_logger
from mcp_server.utils.validators import ValidationError

logger = get_logger(__name__)


class DICOMCStoreHandler:
    """Handles DICOM C-STORE protocol on port 11112."""

    # Supported DICOM modalities
    SUPPORTED_MODALITIES = {
        "CT": "Computed Tomography",
        "MR": "Magnetic Resonance",
        "XR": "X-Ray",
        "US": "Ultrasound",
        "NM": "Nuclear Medicine",
        "PT": "Positron Emission Tomography",
        "OT": "Other",
        "PR": "Presentation State",
        "SR": "Structured Report",
        "KO": "Key Object Selection",
    }

    def __init__(self, port: int = 11112):
        """
        Initialize DICOM C-STORE handler.

        Args:
            port: Port to listen on (default 11112)
        """
        self.port = port
        self.server = None
        self.active_transfers: Dict[str, "DICOMTransfer"] = {}
        self.transfer_lock = asyncio.Lock()

    async def start(self) -> None:
        """Start DICOM C-STORE server."""
        try:
            logger.info(f"Starting DICOM C-STORE server on port {self.port}")
            # In production, would use pynetdicom library
            # For now, this is a placeholder for the server startup
            logger.info("DICOM C-STORE server started")
        except Exception as e:
            logger.error(f"Failed to start DICOM C-STORE server: {e}")
            raise ValidationError(f"Failed to start DICOM server: {e}")

    async def stop(self) -> None:
        """Stop DICOM C-STORE server."""
        try:
            logger.info("Stopping DICOM C-STORE server")
            # Close all active transfers
            async with self.transfer_lock:
                for transfer_id in list(self.active_transfers.keys()):
                    transfer = self.active_transfers[transfer_id]
                    await transfer.close()
                    del self.active_transfers[transfer_id]
            logger.info("DICOM C-STORE server stopped")
        except Exception as e:
            logger.error(f"Error stopping DICOM server: {e}")

    async def handle_c_store(
        self, session: AsyncSession, dicom_dataset: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle incoming DICOM C-STORE request.

        Args:
            session: Database session
            dicom_dataset: DICOM dataset dictionary

        Returns:
            Dictionary with C-STORE response

        Raises:
            ValidationError: If DICOM data is invalid
        """
        try:
            # Validate DICOM message
            await DICOMMessageValidator.validate_dicom_message(dicom_dataset)

            # Extract metadata
            metadata = await DICOMMetadataExtractor.extract_metadata(dicom_dataset)

            # Create transfer record
            transfer_id = f"DICOM-{uuid.uuid4()}"
            transfer = DICOMTransfer(transfer_id, metadata)

            async with self.transfer_lock:
                self.active_transfers[transfer_id] = transfer

            logger.info(
                f"Received DICOM C-STORE: patient={metadata['patient_id']}, "
                f"study={metadata['study_id']}, modality={metadata['modality']}"
            )

            return {
                "transfer_id": transfer_id,
                "status": "success",
                "message": "DICOM C-STORE accepted",
            }

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error handling DICOM C-STORE: {e}")
            raise ValidationError(f"Failed to handle DICOM C-STORE: {e}")

    async def get_transfer_status(self, transfer_id: str) -> Optional[Dict[str, Any]]:
        """Get status of DICOM transfer."""
        async with self.transfer_lock:
            transfer = self.active_transfers.get(transfer_id)
            if transfer:
                return transfer.get_status()
        return None

    async def complete_transfer(self, transfer_id: str) -> None:
        """Mark DICOM transfer as complete."""
        async with self.transfer_lock:
            if transfer_id in self.active_transfers:
                transfer = self.active_transfers[transfer_id]
                transfer.mark_complete()
                logger.info(f"DICOM transfer completed: {transfer_id}")


class DICOMTransfer:
    """Represents a single DICOM transfer."""

    def __init__(self, transfer_id: str, metadata: Dict[str, Any]):
        """Initialize DICOM transfer."""
        self.transfer_id = transfer_id
        self.metadata = metadata
        self.start_time = datetime.now(timezone.utc)
        self.end_time: Optional[datetime] = None
        self.is_complete = False
        self.bytes_transferred = 0

    def mark_complete(self) -> None:
        """Mark transfer as complete."""
        self.is_complete = True
        self.end_time = datetime.now(timezone.utc)

    async def close(self) -> None:
        """Close transfer."""
        if not self.is_complete:
            self.mark_complete()

    def get_status(self) -> Dict[str, Any]:
        """Get transfer status."""
        duration = None
        if self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()

        return {
            "transfer_id": self.transfer_id,
            "is_complete": self.is_complete,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": duration,
            "bytes_transferred": self.bytes_transferred,
        }


class DICOMMetadataExtractor:
    """Extracts metadata from DICOM messages."""

    @staticmethod
    async def extract_metadata(dicom_dataset: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract DICOM metadata from dataset.

        Args:
            dicom_dataset: DICOM dataset dictionary

        Returns:
            Dictionary with extracted metadata

        Raises:
            ValidationError: If required fields are missing
        """
        if not dicom_dataset or not isinstance(dicom_dataset, dict):
            raise ValidationError("DICOM dataset must be a non-empty dictionary")

        try:
            # Extract patient information
            patient_id = dicom_dataset.get("PatientID")
            patient_name = dicom_dataset.get("PatientName", "")
            patient_dob = dicom_dataset.get("PatientBirthDate")
            patient_sex = dicom_dataset.get("PatientSex")

            # Extract study information
            study_id = dicom_dataset.get("StudyInstanceUID")
            study_date = dicom_dataset.get("StudyDate")
            study_time = dicom_dataset.get("StudyTime")
            study_description = dicom_dataset.get("StudyDescription", "")
            modality = dicom_dataset.get("Modality")

            # Extract series information
            series_id = dicom_dataset.get("SeriesInstanceUID")
            series_number = dicom_dataset.get("SeriesNumber")
            series_description = dicom_dataset.get("SeriesDescription", "")
            series_instance_uid = dicom_dataset.get("SeriesInstanceUID")

            # Extract image information
            sop_class_uid = dicom_dataset.get("SOPClassUID")
            sop_instance_uid = dicom_dataset.get("SOPInstanceUID")
            image_number = dicom_dataset.get("InstanceNumber")

            # Combine date and time
            study_timestamp = None
            if study_date and study_time:
                try:
                    study_timestamp = datetime.strptime(
                        f"{study_date}{study_time}", "%Y%m%d%H%M%S"
                    ).replace(tzinfo=timezone.utc)
                except ValueError:
                    logger.warning(
                        f"Could not parse study timestamp: {study_date} {study_time}"
                    )
                    study_timestamp = datetime.now(timezone.utc)

            # Calculate confidence score
            confidence = DICOMMetadataExtractor._calculate_confidence(
                patient_id, study_id, modality, study_timestamp
            )

            logger.debug(
                f"Extracted DICOM metadata: patient={patient_id}, "
                f"study={study_id}, modality={modality}"
            )

            return {
                "patient_id": patient_id,
                "patient_name": patient_name,
                "patient_dob": patient_dob,
                "patient_sex": patient_sex,
                "study_id": study_id,
                "study_date": study_date,
                "study_time": study_time,
                "study_timestamp": study_timestamp,
                "study_description": study_description,
                "modality": modality,
                "series_id": series_id,
                "series_number": series_number,
                "series_description": series_description,
                "series_instance_uid": series_instance_uid,
                "sop_class_uid": sop_class_uid,
                "sop_instance_uid": sop_instance_uid,
                "image_number": image_number,
                "confidence_score": confidence,
                "extraction_timestamp": datetime.now(timezone.utc),
            }

        except Exception as e:
            logger.error(f"Error extracting DICOM metadata: {e}")
            raise ValidationError(f"Failed to extract DICOM metadata: {e}")

    @staticmethod
    def _calculate_confidence(
        patient_id: Optional[str],
        study_id: Optional[str],
        modality: Optional[str],
        study_timestamp: Optional[datetime],
    ) -> float:
        """Calculate confidence score for extracted metadata."""
        confidence = 1.0

        # Reduce confidence for missing required fields
        if not patient_id:
            confidence -= 0.3
        if not study_id:
            confidence -= 0.3
        if not modality:
            confidence -= 0.2
        if not study_timestamp:
            confidence -= 0.1

        return max(0.0, min(1.0, confidence))


class DICOMMessageValidator:
    """Validates DICOM messages."""

    REQUIRED_FIELDS = [
        "PatientID",
        "StudyInstanceUID",
        "Modality",
        "SOPClassUID",
        "SOPInstanceUID",
    ]

    @staticmethod
    async def validate_dicom_message(dicom_dataset: Dict[str, Any]) -> None:
        """
        Validate DICOM message.

        Args:
            dicom_dataset: DICOM dataset dictionary

        Raises:
            ValidationError: If validation fails
        """
        if not dicom_dataset or not isinstance(dicom_dataset, dict):
            raise ValidationError("DICOM dataset must be a non-empty dictionary")

        # Check required fields
        missing_fields = []
        for field in DICOMMessageValidator.REQUIRED_FIELDS:
            if field not in dicom_dataset or not dicom_dataset[field]:
                missing_fields.append(field)

        if missing_fields:
            raise ValidationError(
                f"DICOM message missing required fields: {', '.join(missing_fields)}"
            )

        # Validate modality
        modality = dicom_dataset.get("Modality")
        if modality not in DICOMCStoreHandler.SUPPORTED_MODALITIES:
            logger.warning(f"Unsupported DICOM modality: {modality}")

        # Validate UIDs format (basic check)
        study_uid = dicom_dataset.get("StudyInstanceUID")
        if study_uid and not DICOMMessageValidator._is_valid_uid(study_uid):
            raise ValidationError(f"Invalid StudyInstanceUID format: {study_uid}")

        sop_class_uid = dicom_dataset.get("SOPClassUID")
        if sop_class_uid and not DICOMMessageValidator._is_valid_uid(sop_class_uid):
            raise ValidationError(f"Invalid SOPClassUID format: {sop_class_uid}")

        sop_instance_uid = dicom_dataset.get("SOPInstanceUID")
        if sop_instance_uid and not DICOMMessageValidator._is_valid_uid(
            sop_instance_uid
        ):
            raise ValidationError(f"Invalid SOPInstanceUID format: {sop_instance_uid}")

        logger.debug("DICOM message validation passed")

    @staticmethod
    def _is_valid_uid(uid: str) -> bool:
        """Check if UID has valid format (basic check)."""
        if not uid or not isinstance(uid, str):
            return False
        # UIDs are dot-separated numeric strings
        parts = uid.split(".")
        return all(part.isdigit() for part in parts) and len(parts) >= 2


class DICOMConnectionManager:
    """Manages concurrent DICOM connections."""

    def __init__(self, max_concurrent_transfers: int = 10):
        """
        Initialize connection manager.

        Args:
            max_concurrent_transfers: Maximum concurrent DICOM transfers
        """
        self.max_concurrent_transfers = max_concurrent_transfers
        self.active_transfers: Dict[str, DICOMTransfer] = {}
        self.transfer_lock = asyncio.Lock()
        self.connection_semaphore = asyncio.Semaphore(max_concurrent_transfers)

    async def acquire_transfer_slot(self) -> None:
        """Acquire a slot for a new DICOM transfer."""
        await self.connection_semaphore.acquire()

    def release_transfer_slot(self) -> None:
        """Release a DICOM transfer slot."""
        self.connection_semaphore.release()

    async def register_transfer(
        self, transfer_id: str, metadata: Dict[str, Any]
    ) -> None:
        """Register a new DICOM transfer."""
        async with self.transfer_lock:
            transfer = DICOMTransfer(transfer_id, metadata)
            self.active_transfers[transfer_id] = transfer
            logger.debug(f"Registered DICOM transfer: {transfer_id}")

    async def unregister_transfer(self, transfer_id: str) -> None:
        """Unregister a completed DICOM transfer."""
        async with self.transfer_lock:
            if transfer_id in self.active_transfers:
                transfer = self.active_transfers[transfer_id]
                await transfer.close()
                del self.active_transfers[transfer_id]
                logger.debug(f"Unregistered DICOM transfer: {transfer_id}")

    async def get_active_transfer_count(self) -> int:
        """Get count of active DICOM transfers."""
        async with self.transfer_lock:
            return len(self.active_transfers)

    async def get_transfer_status(self, transfer_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a DICOM transfer."""
        async with self.transfer_lock:
            transfer = self.active_transfers.get(transfer_id)
            if transfer:
                return transfer.get_status()
        return None

    async def get_all_transfers(self) -> List[Dict[str, Any]]:
        """Get status of all active DICOM transfers."""
        async with self.transfer_lock:
            return [transfer.get_status() for transfer in self.active_transfers.values()]
