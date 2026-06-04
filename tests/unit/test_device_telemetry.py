"""
Unit tests for device telemetry ingestion module.

Tests cover:
- Device connection management
- Vital signs stream handling
- Waveform data handling
- Alarm event handling
- Device status updates
- Device data association
- Missing/delayed data detection
- Error handling
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.ingestion.device_telemetry import (
    DeviceConnectionManager,
    DeviceConnection,
    VitalSignsStreamHandler,
    WaveformDataHandler,
    AlarmEventHandler,
    DeviceStatusUpdateHandler,
    DeviceDataAssociator,
)
from mcp_server.database.models import Device, Encounter, Patient
from mcp_server.utils.validators import ValidationError


class TestDeviceConnectionManager:
    """Test device connection manager."""

    def test_init(self):
        """Test initialization."""
        manager = DeviceConnectionManager()
        assert manager.active_connections == {}
        assert manager.device_handlers == {}
        assert manager.patient_device_map == {}

    @pytest.mark.asyncio
    async def test_connect_device_success(self):
        """Test successful device connection."""
        manager = DeviceConnectionManager()
        device_id = "DEV-123"
        device_type = "ecg_monitor"
        connection_params = {"host": "192.168.1.100", "port": 5000}

        await manager.connect_device(device_id, device_type, connection_params)

        assert device_id in manager.active_connections
        assert manager.is_device_online(device_id)

    @pytest.mark.asyncio
    async def test_connect_device_invalid_device_id(self):
        """Test connection with invalid device_id."""
        manager = DeviceConnectionManager()

        with pytest.raises(ValidationError):
            await manager.connect_device("", "ecg_monitor", {})

        with pytest.raises(ValidationError):
            await manager.connect_device(None, "ecg_monitor", {})

    @pytest.mark.asyncio
    async def test_connect_device_invalid_device_type(self):
        """Test connection with invalid device_type."""
        manager = DeviceConnectionManager()

        with pytest.raises(ValidationError):
            await manager.connect_device("DEV-123", "", {})

        with pytest.raises(ValidationError):
            await manager.connect_device("DEV-123", None, {})

    @pytest.mark.asyncio
    async def test_disconnect_device(self):
        """Test device disconnection."""
        manager = DeviceConnectionManager()
        device_id = "DEV-123"

        await manager.connect_device(device_id, "ecg_monitor", {})
        assert manager.is_device_online(device_id)

        await manager.disconnect_device(device_id)
        assert not manager.is_device_online(device_id)

    @pytest.mark.asyncio
    async def test_get_device_connection(self):
        """Test getting device connection."""
        manager = DeviceConnectionManager()
        device_id = "DEV-123"

        await manager.connect_device(device_id, "ecg_monitor", {})
        connection = manager.get_device_connection(device_id)

        assert connection is not None
        assert connection.device_id == device_id

    @pytest.mark.asyncio
    async def test_map_device_to_patient(self):
        """Test mapping device to patient."""
        manager = DeviceConnectionManager()
        device_id = "DEV-123"
        patient_id = "PAT-456"
        encounter_id = "ENC-789"

        await manager.map_device_to_patient(device_id, patient_id, encounter_id)

        assert patient_id in manager.patient_device_map
        assert device_id in manager.patient_device_map[patient_id]


class TestDeviceConnection:
    """Test device connection class."""

    def test_init(self):
        """Test initialization."""
        device_id = "DEV-123"
        device_type = "ecg_monitor"
        connection_params = {"host": "192.168.1.100"}

        connection = DeviceConnection(device_id, device_type, connection_params)

        assert connection.device_id == device_id
        assert connection.device_type == device_type
        assert connection.connection_params == connection_params
        assert connection.is_connected is True
        assert connection.data_buffer == []

    @pytest.mark.asyncio
    async def test_close(self):
        """Test closing connection."""
        connection = DeviceConnection("DEV-123", "ecg_monitor", {})
        assert connection.is_connected is True

        await connection.close()
        assert connection.is_connected is False


class TestVitalSignsStreamHandler:
    """Test vital signs stream handler."""

    @pytest.mark.asyncio
    async def test_process_vital_signs_success(self):
        """Test processing valid vital signs."""
        session = AsyncMock(spec=AsyncSession)
        device_id = "DEV-123"
        patient_id = "PAT-456"
        encounter_id = "ENC-789"
        vitals = {
            "heart_rate": 85,
            "systolic_bp": 120,
            "diastolic_bp": 80,
            "spo2": 98,
            "respiratory_rate": 16,
        }

        result = await VitalSignsStreamHandler.process_vital_signs(
            session, device_id, patient_id, encounter_id, vitals
        )

        assert result["device_id"] == device_id
        assert result["patient_id"] == patient_id
        assert result["encounter_id"] == encounter_id
        assert result["vitals"] == vitals
        assert "timestamp" in result
        assert "annotations" in result
        assert "confidence_score" in result
        assert 0 <= result["confidence_score"] <= 1

    @pytest.mark.asyncio
    async def test_process_vital_signs_abnormal_values(self):
        """Test processing abnormal vital signs."""
        session = AsyncMock(spec=AsyncSession)
        vitals = {
            "heart_rate": 180,  # Abnormal - too high
            "systolic_bp": 60,  # Abnormal - too low
            "spo2": 88,  # Abnormal - low
        }

        result = await VitalSignsStreamHandler.process_vital_signs(
            session, "DEV-123", "PAT-456", "ENC-789", vitals
        )

        assert len(result["annotations"]) > 0
        assert result["confidence_score"] < 1.0

    @pytest.mark.asyncio
    async def test_process_vital_signs_invalid_device_id(self):
        """Test with invalid device_id."""
        session = AsyncMock(spec=AsyncSession)

        with pytest.raises(ValidationError):
            await VitalSignsStreamHandler.process_vital_signs(
                session, "", "PAT-456", "ENC-789", {"heart_rate": 85}
            )

    @pytest.mark.asyncio
    async def test_process_vital_signs_invalid_vitals(self):
        """Test with invalid vitals."""
        session = AsyncMock(spec=AsyncSession)

        with pytest.raises(ValidationError):
            await VitalSignsStreamHandler.process_vital_signs(
                session, "DEV-123", "PAT-456", "ENC-789", {}
            )

        with pytest.raises(ValidationError):
            await VitalSignsStreamHandler.process_vital_signs(
                session, "DEV-123", "PAT-456", "ENC-789", None
            )

    @pytest.mark.asyncio
    async def test_process_vital_signs_custom_timestamp(self):
        """Test with custom timestamp."""
        session = AsyncMock(spec=AsyncSession)
        custom_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        result = await VitalSignsStreamHandler.process_vital_signs(
            session,
            "DEV-123",
            "PAT-456",
            "ENC-789",
            {"heart_rate": 85},
            timestamp=custom_time,
        )

        assert result["timestamp"] == custom_time


class TestWaveformDataHandler:
    """Test waveform data handler."""

    @pytest.mark.asyncio
    async def test_process_waveform_data_success(self):
        """Test processing valid waveform data."""
        session = AsyncMock(spec=AsyncSession)
        device_id = "DEV-123"
        patient_id = "PAT-456"
        encounter_id = "ENC-789"
        samples = [1.0, 2.0, 3.0, 4.0, 5.0]
        sample_rate = 500

        result = await WaveformDataHandler.process_waveform_data(
            session,
            device_id,
            patient_id,
            encounter_id,
            "ecg",
            samples,
            sample_rate,
        )

        assert result["device_id"] == device_id
        assert result["patient_id"] == patient_id
        assert result["encounter_id"] == encounter_id
        assert result["waveform_type"] == "ecg"
        assert result["sample_count"] == 5
        assert result["sample_rate"] == 500
        assert result["min_value"] == 1.0
        assert result["max_value"] == 5.0
        assert result["mean_value"] == 3.0
        assert result["confidence_score"] == 1.0

    @pytest.mark.asyncio
    async def test_process_waveform_data_invalid_device_id(self):
        """Test with invalid device_id."""
        session = AsyncMock(spec=AsyncSession)

        with pytest.raises(ValidationError):
            await WaveformDataHandler.process_waveform_data(
                session, "", "PAT-456", "ENC-789", "ecg", [1.0, 2.0], 500
            )

    @pytest.mark.asyncio
    async def test_process_waveform_data_invalid_samples(self):
        """Test with invalid samples."""
        session = AsyncMock(spec=AsyncSession)

        with pytest.raises(ValidationError):
            await WaveformDataHandler.process_waveform_data(
                session, "DEV-123", "PAT-456", "ENC-789", "ecg", [], 500
            )

        with pytest.raises(ValidationError):
            await WaveformDataHandler.process_waveform_data(
                session, "DEV-123", "PAT-456", "ENC-789", "ecg", None, 500
            )

    @pytest.mark.asyncio
    async def test_process_waveform_data_invalid_sample_rate(self):
        """Test with invalid sample_rate."""
        session = AsyncMock(spec=AsyncSession)

        with pytest.raises(ValidationError):
            await WaveformDataHandler.process_waveform_data(
                session, "DEV-123", "PAT-456", "ENC-789", "ecg", [1.0, 2.0], 0
            )

        with pytest.raises(ValidationError):
            await WaveformDataHandler.process_waveform_data(
                session, "DEV-123", "PAT-456", "ENC-789", "ecg", [1.0, 2.0], -1
            )


class TestAlarmEventHandler:
    """Test alarm event handler."""

    @pytest.mark.asyncio
    async def test_process_alarm_event_success(self):
        """Test processing valid alarm event."""
        session = AsyncMock(spec=AsyncSession)
        device_id = "DEV-123"
        patient_id = "PAT-456"
        encounter_id = "ENC-789"

        result = await AlarmEventHandler.process_alarm_event(
            session,
            device_id,
            patient_id,
            encounter_id,
            "low_spo2",
            "critical",
            threshold=90,
            current_value=88,
        )

        assert result["device_id"] == device_id
        assert result["patient_id"] == patient_id
        assert result["encounter_id"] == encounter_id
        assert result["alarm_type"] == "low_spo2"
        assert result["severity"] == "critical"
        assert result["threshold"] == 90
        assert result["current_value"] == 88
        assert result["acknowledged"] is False
        assert result["confidence_score"] == 1.0
        assert "id" in result

    @pytest.mark.asyncio
    async def test_process_alarm_event_invalid_severity(self):
        """Test with invalid severity."""
        session = AsyncMock(spec=AsyncSession)

        with pytest.raises(ValidationError):
            await AlarmEventHandler.process_alarm_event(
                session,
                "DEV-123",
                "PAT-456",
                "ENC-789",
                "low_spo2",
                "invalid_severity",
            )

    @pytest.mark.asyncio
    async def test_process_alarm_event_all_severity_levels(self):
        """Test all valid severity levels."""
        session = AsyncMock(spec=AsyncSession)

        for severity in ["critical", "high", "medium", "low", "info"]:
            result = await AlarmEventHandler.process_alarm_event(
                session,
                "DEV-123",
                "PAT-456",
                "ENC-789",
                "test_alarm",
                severity,
            )
            assert result["severity"] == severity


class TestDeviceStatusUpdateHandler:
    """Test device status update handler."""

    @pytest.mark.asyncio
    async def test_process_device_status_online(self):
        """Test processing device status - online."""
        session = AsyncMock(spec=AsyncSession)

        result = await DeviceStatusUpdateHandler.process_device_status_update(
            session, "DEV-123", is_online=True, battery_level=85
        )

        assert result["device_id"] == "DEV-123"
        assert result["is_online"] is True
        assert result["battery_level"] == 85
        assert result["confidence_score"] == 1.0

    @pytest.mark.asyncio
    async def test_process_device_status_offline(self):
        """Test processing device status - offline."""
        session = AsyncMock(spec=AsyncSession)

        result = await DeviceStatusUpdateHandler.process_device_status_update(
            session, "DEV-123", is_online=False
        )

        assert result["device_id"] == "DEV-123"
        assert result["is_online"] is False
        assert result["confidence_score"] == 0.0

    @pytest.mark.asyncio
    async def test_process_device_status_low_battery(self):
        """Test processing device status with low battery."""
        session = AsyncMock(spec=AsyncSession)

        result = await DeviceStatusUpdateHandler.process_device_status_update(
            session, "DEV-123", is_online=True, battery_level=15
        )

        assert result["battery_level"] == 15
        assert result["confidence_score"] < 1.0

    @pytest.mark.asyncio
    async def test_process_device_status_needs_calibration(self):
        """Test processing device status - needs calibration."""
        session = AsyncMock(spec=AsyncSession)

        result = await DeviceStatusUpdateHandler.process_device_status_update(
            session,
            "DEV-123",
            is_online=True,
            calibration_status="needs_calibration",
        )

        assert result["calibration_status"] == "needs_calibration"
        assert result["confidence_score"] < 1.0

    @pytest.mark.asyncio
    async def test_process_device_status_invalid_battery_level(self):
        """Test with invalid battery level."""
        session = AsyncMock(spec=AsyncSession)

        with pytest.raises(ValidationError):
            await DeviceStatusUpdateHandler.process_device_status_update(
                session, "DEV-123", is_online=True, battery_level=150
            )

        with pytest.raises(ValidationError):
            await DeviceStatusUpdateHandler.process_device_status_update(
                session, "DEV-123", is_online=True, battery_level=-10
            )


class TestDeviceDataAssociator:
    """Test device data associator."""

    @pytest.mark.asyncio
    async def test_associate_device_data_success(self):
        """Test successful device data association."""
        session = AsyncMock(spec=AsyncSession)

        # Mock device
        device = MagicMock(spec=Device)
        device.id = "DEV-123"
        device.encounter_id = "ENC-789"

        # Mock encounter
        encounter = MagicMock(spec=Encounter)
        encounter.id = "ENC-789"
        encounter.patient_id = "PAT-456"

        # Mock query results - need to properly mock async behavior
        device_scalars = MagicMock()
        device_scalars.first.return_value = device

        encounter_scalars = MagicMock()
        encounter_scalars.first.return_value = encounter

        device_result = MagicMock()
        device_result.scalars.return_value = device_scalars

        encounter_result = MagicMock()
        encounter_result.scalars.return_value = encounter_scalars

        session.execute.side_effect = [device_result, encounter_result]

        patient_id, encounter_id = await DeviceDataAssociator.associate_device_data(
            session, "DEV-123"
        )

        assert patient_id == "PAT-456"
        assert encounter_id == "ENC-789"

    @pytest.mark.asyncio
    async def test_associate_device_data_device_not_found(self):
        """Test when device is not found."""
        session = AsyncMock(spec=AsyncSession)

        # Mock query result - device not found
        scalars = MagicMock()
        scalars.first.return_value = None

        result = MagicMock()
        result.scalars.return_value = scalars

        session.execute.return_value = result

        patient_id, encounter_id = await DeviceDataAssociator.associate_device_data(
            session, "DEV-999"
        )

        assert patient_id is None
        assert encounter_id is None

    @pytest.mark.asyncio
    async def test_associate_device_data_invalid_device_id(self):
        """Test with invalid device_id."""
        session = AsyncMock(spec=AsyncSession)

        with pytest.raises(ValidationError):
            await DeviceDataAssociator.associate_device_data(session, "")

        with pytest.raises(ValidationError):
            await DeviceDataAssociator.associate_device_data(session, None)

    @pytest.mark.asyncio
    async def test_detect_missing_data_no_delay(self):
        """Test detecting missing data - no delay."""
        session = AsyncMock(spec=AsyncSession)
        last_timestamp = datetime.now(timezone.utc)

        is_missing = await DeviceDataAssociator.detect_missing_data(
            session, "DEV-123", last_timestamp, max_delay_seconds=60
        )

        assert is_missing is False

    @pytest.mark.asyncio
    async def test_detect_missing_data_with_delay(self):
        """Test detecting missing data - with delay."""
        session = AsyncMock(spec=AsyncSession)
        last_timestamp = datetime.now(timezone.utc) - timedelta(seconds=120)

        is_missing = await DeviceDataAssociator.detect_missing_data(
            session, "DEV-123", last_timestamp, max_delay_seconds=60
        )

        assert is_missing is True

    @pytest.mark.asyncio
    async def test_detect_missing_data_at_threshold(self):
        """Test detecting missing data - at threshold."""
        session = AsyncMock(spec=AsyncSession)
        last_timestamp = datetime.now(timezone.utc) - timedelta(seconds=59)

        is_missing = await DeviceDataAssociator.detect_missing_data(
            session, "DEV-123", last_timestamp, max_delay_seconds=60
        )

        # Should be False since delay is less than max_delay
        assert is_missing is False


class TestDeviceTelemetryIntegration:
    """Integration tests for device telemetry."""

    @pytest.mark.asyncio
    async def test_complete_device_telemetry_flow(self):
        """Test complete device telemetry flow."""
        session = AsyncMock(spec=AsyncSession)
        manager = DeviceConnectionManager()

        # 1. Connect device
        device_id = "DEV-123"
        await manager.connect_device(device_id, "ecg_monitor", {})
        assert manager.is_device_online(device_id)

        # 2. Process vital signs
        vitals = {"heart_rate": 85, "spo2": 98}
        vital_result = await VitalSignsStreamHandler.process_vital_signs(
            session, device_id, "PAT-456", "ENC-789", vitals
        )
        assert vital_result["confidence_score"] > 0

        # 3. Process waveform
        waveform_result = await WaveformDataHandler.process_waveform_data(
            session, device_id, "PAT-456", "ENC-789", "ecg", [1.0, 2.0, 3.0], 500
        )
        assert waveform_result["sample_count"] == 3

        # 4. Process alarm
        alarm_result = await AlarmEventHandler.process_alarm_event(
            session, device_id, "PAT-456", "ENC-789", "low_spo2", "high"
        )
        assert alarm_result["alarm_type"] == "low_spo2"

        # 5. Update device status
        status_result = await DeviceStatusUpdateHandler.process_device_status_update(
            session, device_id, is_online=True, battery_level=85
        )
        assert status_result["is_online"] is True

        # 6. Disconnect device
        await manager.disconnect_device(device_id)
        assert not manager.is_device_online(device_id)

    @pytest.mark.asyncio
    async def test_multiple_devices_concurrent_processing(self):
        """Test processing from multiple devices concurrently."""
        session = AsyncMock(spec=AsyncSession)
        manager = DeviceConnectionManager()

        # Connect multiple devices
        devices = ["DEV-1", "DEV-2", "DEV-3"]
        for device_id in devices:
            await manager.connect_device(device_id, "monitor", {})

        # Process data from all devices
        for device_id in devices:
            vitals = {"heart_rate": 80 + len(device_id)}
            await VitalSignsStreamHandler.process_vital_signs(
                session, device_id, "PAT-456", "ENC-789", vitals
            )

        # Verify all devices are online
        for device_id in devices:
            assert manager.is_device_online(device_id)
