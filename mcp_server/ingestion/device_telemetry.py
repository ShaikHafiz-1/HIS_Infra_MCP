"""
Device Telemetry Ingestion System for Hospital Clinical Intelligence MCP Platform.

This module implements device telemetry ingestion including:
- Device connection management
- Vital signs stream handling (ECG, SpO₂, BP, respiratory rate)
- Waveform data handling for continuous signals
- Alarm event handling
- Device status update handling
- Device data association with patient/encounter
- Server-side timestamp consistency
- Missing/delayed data detection
- Observation storage with device source tracking
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.database.models import (
    Device,
    Encounter,
    Patient,
)
from mcp_server.normalization.id_mapper import IDMapper
from mcp_server.utils.logger import get_logger
from mcp_server.utils.validators import ValidationError

logger = get_logger(__name__)


class DeviceConnectionManager:
    """Manages device connections and lifecycle."""

    def __init__(self):
        """Initialize device connection manager."""
        self.active_connections: Dict[str, "DeviceConnection"] = {}
        self.device_handlers: Dict[str, Any] = {}
        self.patient_device_map: Dict[str, List[str]] = {}

    async def connect_device(
        self,
        device_id: str,
        device_type: str,
        connection_params: Dict[str, Any],
    ) -> None:
        """
        Connect a device and start telemetry streaming.

        Args:
            device_id: Internal device identifier
            device_type: Type of device (e.g., 'ecg_monitor', 'ventilator')
            connection_params: Connection parameters (host, port, protocol, etc.)

        Raises:
            ValidationError: If device_id or device_type is invalid
        """
        if not device_id or not isinstance(device_id, str):
            raise ValidationError("device_id must be a non-empty string")
        if not device_type or not isinstance(device_type, str):
            raise ValidationError("device_type must be a non-empty string")

        try:
            connection = DeviceConnection(
                device_id=device_id,
                device_type=device_type,
                connection_params=connection_params,
            )

            self.active_connections[device_id] = connection
            logger.info(f"Device connected: {device_id} ({device_type})")

        except Exception as e:
            logger.error(f"Failed to connect device {device_id}: {e}")
            raise ValidationError(f"Failed to connect device: {e}")

    async def disconnect_device(self, device_id: str) -> None:
        """
        Disconnect a device and stop telemetry streaming.

        Args:
            device_id: Internal device identifier
        """
        if device_id in self.active_connections:
            connection = self.active_connections[device_id]
            await connection.close()
            del self.active_connections[device_id]
            logger.info(f"Device disconnected: {device_id}")

    def get_device_connection(self, device_id: str) -> Optional["DeviceConnection"]:
        """Get active device connection."""
        return self.active_connections.get(device_id)

    def is_device_online(self, device_id: str) -> bool:
        """Check if device is currently online."""
        return device_id in self.active_connections

    async def map_device_to_patient(
        self, device_id: str, patient_id: str, encounter_id: str
    ) -> None:
        """Map device to patient and encounter."""
        if patient_id not in self.patient_device_map:
            self.patient_device_map[patient_id] = []

        if device_id not in self.patient_device_map[patient_id]:
            self.patient_device_map[patient_id].append(device_id)

        logger.debug(
            f"Mapped device {device_id} to patient {patient_id} "
            f"in encounter {encounter_id}"
        )


class DeviceConnection:
    """Represents a single device connection."""

    def __init__(
        self,
        device_id: str,
        device_type: str,
        connection_params: Dict[str, Any],
    ):
        """Initialize device connection."""
        self.device_id = device_id
        self.device_type = device_type
        self.connection_params = connection_params
        self.is_connected = True
        self.last_heartbeat = datetime.now(timezone.utc)
        self.data_buffer: List[Dict[str, Any]] = []

    async def close(self) -> None:
        """Close device connection."""
        self.is_connected = False
        logger.debug(f"Closed connection for device {self.device_id}")


class VitalSignsStreamHandler:
    """Handles vital signs stream data (ECG, SpO₂, BP, respiratory rate)."""

    # Clinical thresholds for abnormal detection
    VITAL_THRESHOLDS = {
        "heart_rate": {"min": 40, "max": 150, "normal_min": 60, "normal_max": 100},
        "systolic_bp": {"min": 80, "max": 200, "normal_min": 90, "normal_max": 140},
        "diastolic_bp": {"min": 40, "max": 120, "normal_min": 60, "normal_max": 90},
        "spo2": {"min": 85, "max": 100, "normal_min": 95, "normal_max": 100},
        "respiratory_rate": {"min": 8, "max": 40, "normal_min": 12, "normal_max": 20},
    }

    @staticmethod
    async def process_vital_signs(
        session: AsyncSession,
        device_id: str,
        patient_id: str,
        encounter_id: str,
        vitals: Dict[str, float],
        timestamp: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Process vital signs stream data.

        Args:
            session: Database session
            device_id: Internal device identifier
            patient_id: Internal patient identifier
            encounter_id: Internal encounter identifier
            vitals: Dictionary of vital sign values
            timestamp: Optional timestamp (uses server time if not provided)

        Returns:
            Dictionary with processed vital signs and annotations

        Raises:
            ValidationError: If parameters are invalid
        """
        if not device_id or not patient_id or not encounter_id:
            raise ValidationError("device_id, patient_id, and encounter_id required")

        if not vitals or not isinstance(vitals, dict):
            raise ValidationError("vitals must be a non-empty dictionary")

        # Use server-side timestamp for consistency
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        try:
            # Validate vital sign values
            annotations = {}
            for vital_name, vital_value in vitals.items():
                if vital_name in VitalSignsStreamHandler.VITAL_THRESHOLDS:
                    threshold = VitalSignsStreamHandler.VITAL_THRESHOLDS[vital_name]

                    # Check if value is within acceptable range
                    if not (threshold["min"] <= vital_value <= threshold["max"]):
                        annotations[vital_name] = {
                            "abnormal": True,
                            "reason": "out_of_range",
                            "threshold": threshold,
                        }
                    # Check if value is outside normal range
                    elif not (
                        threshold["normal_min"]
                        <= vital_value
                        <= threshold["normal_max"]
                    ):
                        annotations[vital_name] = {
                            "abnormal": True,
                            "reason": "outside_normal_range",
                            "threshold": threshold,
                        }

            logger.debug(
                f"Processed vital signs for patient {patient_id}: {vitals}"
            )

            return {
                "device_id": device_id,
                "patient_id": patient_id,
                "encounter_id": encounter_id,
                "vitals": vitals,
                "timestamp": timestamp,
                "annotations": annotations,
                "confidence_score": VitalSignsStreamHandler._calculate_confidence(
                    vitals, annotations
                ),
            }

        except Exception as e:
            logger.error(f"Error processing vital signs: {e}")
            raise ValidationError(f"Failed to process vital signs: {e}")

    @staticmethod
    def _calculate_confidence(
        vitals: Dict[str, float], annotations: Dict[str, Any]
    ) -> float:
        """Calculate confidence score for vital signs."""
        if not vitals:
            return 0.0

        # Start with high confidence
        confidence = 1.0

        # Reduce confidence for abnormal values
        abnormal_count = len(annotations)
        total_count = len(vitals)

        if total_count > 0:
            confidence -= (abnormal_count / total_count) * 0.2

        return max(0.0, min(1.0, confidence))


class WaveformDataHandler:
    """Handles continuous waveform data (ECG, arterial pressure, respiratory)."""

    @staticmethod
    async def process_waveform_data(
        session: AsyncSession,
        device_id: str,
        patient_id: str,
        encounter_id: str,
        waveform_type: str,
        samples: List[float],
        sample_rate: int,
        timestamp: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Process continuous waveform data.

        Args:
            session: Database session
            device_id: Internal device identifier
            patient_id: Internal patient identifier
            encounter_id: Internal encounter identifier
            waveform_type: Type of waveform (ecg, arterial_pressure, respiratory)
            samples: List of waveform samples
            sample_rate: Sampling rate in Hz
            timestamp: Optional timestamp (uses server time if not provided)

        Returns:
            Dictionary with processed waveform data

        Raises:
            ValidationError: If parameters are invalid
        """
        if not device_id or not patient_id or not encounter_id:
            raise ValidationError("device_id, patient_id, and encounter_id required")

        if not waveform_type or not isinstance(waveform_type, str):
            raise ValidationError("waveform_type must be a non-empty string")

        if not samples or not isinstance(samples, list):
            raise ValidationError("samples must be a non-empty list")

        if sample_rate <= 0:
            raise ValidationError("sample_rate must be positive")

        # Use server-side timestamp for consistency
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        try:
            # Calculate waveform statistics
            min_value = min(samples)
            max_value = max(samples)
            mean_value = sum(samples) / len(samples)
            duration_seconds = len(samples) / sample_rate

            logger.debug(
                f"Processed {waveform_type} waveform for patient {patient_id}: "
                f"{len(samples)} samples at {sample_rate}Hz"
            )

            return {
                "device_id": device_id,
                "patient_id": patient_id,
                "encounter_id": encounter_id,
                "waveform_type": waveform_type,
                "sample_count": len(samples),
                "sample_rate": sample_rate,
                "duration_seconds": duration_seconds,
                "min_value": min_value,
                "max_value": max_value,
                "mean_value": mean_value,
                "timestamp": timestamp,
                "confidence_score": 1.0,
            }

        except Exception as e:
            logger.error(f"Error processing waveform data: {e}")
            raise ValidationError(f"Failed to process waveform data: {e}")


class AlarmEventHandler:
    """Handles device alarm events."""

    SEVERITY_LEVELS = ["critical", "high", "medium", "low", "info"]

    @staticmethod
    async def process_alarm_event(
        session: AsyncSession,
        device_id: str,
        patient_id: str,
        encounter_id: str,
        alarm_type: str,
        severity: str,
        threshold: Optional[float] = None,
        current_value: Optional[float] = None,
        timestamp: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Process device alarm event.

        Args:
            session: Database session
            device_id: Internal device identifier
            patient_id: Internal patient identifier
            encounter_id: Internal encounter identifier
            alarm_type: Type of alarm (e.g., 'low_spo2', 'high_heart_rate')
            severity: Severity level (critical, high, medium, low, info)
            threshold: Alarm threshold value
            current_value: Current vital sign value
            timestamp: Optional timestamp (uses server time if not provided)

        Returns:
            Dictionary with processed alarm event

        Raises:
            ValidationError: If parameters are invalid
        """
        if not device_id or not patient_id or not encounter_id:
            raise ValidationError("device_id, patient_id, and encounter_id required")

        if not alarm_type or not isinstance(alarm_type, str):
            raise ValidationError("alarm_type must be a non-empty string")

        if severity not in AlarmEventHandler.SEVERITY_LEVELS:
            raise ValidationError(
                f"severity must be one of {AlarmEventHandler.SEVERITY_LEVELS}"
            )

        # Use server-side timestamp for consistency
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        try:
            logger.warning(
                f"Alarm event: {alarm_type} (severity={severity}) "
                f"for patient {patient_id} on device {device_id}"
            )

            return {
                "id": f"ALARM-{uuid.uuid4()}",
                "device_id": device_id,
                "patient_id": patient_id,
                "encounter_id": encounter_id,
                "alarm_type": alarm_type,
                "severity": severity,
                "threshold": threshold,
                "current_value": current_value,
                "timestamp": timestamp,
                "acknowledged": False,
                "confidence_score": 1.0,
            }

        except Exception as e:
            logger.error(f"Error processing alarm event: {e}")
            raise ValidationError(f"Failed to process alarm event: {e}")


class DeviceStatusUpdateHandler:
    """Handles device status updates (online/offline, battery, calibration)."""

    @staticmethod
    async def process_device_status_update(
        session: AsyncSession,
        device_id: str,
        is_online: bool,
        battery_level: Optional[float] = None,
        calibration_status: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Process device status update.

        Args:
            session: Database session
            device_id: Internal device identifier
            is_online: Whether device is online
            battery_level: Battery level (0-100) if applicable
            calibration_status: Calibration status (calibrated, needs_calibration, etc.)
            timestamp: Optional timestamp (uses server time if not provided)

        Returns:
            Dictionary with processed device status

        Raises:
            ValidationError: If parameters are invalid
        """
        if not device_id or not isinstance(device_id, str):
            raise ValidationError("device_id must be a non-empty string")

        if not isinstance(is_online, bool):
            raise ValidationError("is_online must be a boolean")

        if battery_level is not None and not (0 <= battery_level <= 100):
            raise ValidationError("battery_level must be between 0 and 100")

        # Use server-side timestamp for consistency
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        try:
            # Calculate confidence score based on device status
            confidence = 1.0 if is_online else 0.0

            if battery_level is not None and battery_level < 20:
                confidence *= 0.8  # Reduce confidence for low battery

            if calibration_status == "needs_calibration":
                confidence *= 0.5  # Reduce confidence for uncalibrated device

            logger.info(
                f"Device status update: {device_id} - "
                f"online={is_online}, battery={battery_level}, "
                f"calibration={calibration_status}"
            )

            return {
                "device_id": device_id,
                "is_online": is_online,
                "battery_level": battery_level,
                "calibration_status": calibration_status,
                "timestamp": timestamp,
                "confidence_score": confidence,
            }

        except Exception as e:
            logger.error(f"Error processing device status update: {e}")
            raise ValidationError(f"Failed to process device status update: {e}")


class DeviceDataAssociator:
    """Associates device telemetry with correct patient and encounter."""

    @staticmethod
    async def associate_device_data(
        session: AsyncSession,
        device_id: str,
        external_device_id: Optional[str] = None,
        source_system: Optional[str] = None,
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Associate device with patient and encounter.

        Args:
            session: Database session
            device_id: Internal device identifier
            external_device_id: External device identifier
            source_system: Source system identifier

        Returns:
            Tuple of (patient_id, encounter_id) or (None, None) if not found

        Raises:
            ValidationError: If device_id is invalid
        """
        if not device_id or not isinstance(device_id, str):
            raise ValidationError("device_id must be a non-empty string")

        try:
            # Query device from database
            stmt = select(Device).where(Device.id == device_id)
            result = await session.execute(stmt)
            device = result.scalars().first()

            if not device:
                logger.warning(f"Device not found: {device_id}")
                return None, None

            # Get encounter for device
            if device.encounter_id:
                encounter_id = device.encounter_id

                # Get patient from encounter
                stmt = select(Encounter).where(Encounter.id == encounter_id)
                result = await session.execute(stmt)
                encounter = result.scalars().first()

                if encounter:
                    logger.debug(
                        f"Associated device {device_id} with patient "
                        f"{encounter.patient_id} in encounter {encounter_id}"
                    )
                    return encounter.patient_id, encounter_id

            logger.warning(
                f"Could not associate device {device_id} with patient/encounter"
            )
            return None, None

        except Exception as e:
            logger.error(f"Error associating device data: {e}")
            raise ValidationError(f"Failed to associate device data: {e}")

    @staticmethod
    async def detect_missing_data(
        session: AsyncSession,
        device_id: str,
        last_data_timestamp: datetime,
        max_delay_seconds: int = 60,
    ) -> bool:
        """
        Detect missing or delayed device data.

        Args:
            session: Database session
            device_id: Internal device identifier
            last_data_timestamp: Timestamp of last received data
            max_delay_seconds: Maximum acceptable delay in seconds

        Returns:
            True if data is missing/delayed, False otherwise
        """
        try:
            current_time = datetime.now(timezone.utc)
            delay_seconds = (current_time - last_data_timestamp).total_seconds()

            if delay_seconds > max_delay_seconds:
                logger.warning(
                    f"Missing/delayed data from device {device_id}: "
                    f"{delay_seconds}s delay (max: {max_delay_seconds}s)"
                )
                return True

            return False

        except Exception as e:
            logger.error(f"Error detecting missing data: {e}")
            return False
