"""
Unit tests for device events tool.

Tests cover device event retrieval, time window parsing, device filtering,
event generation, and error handling.
"""

import pytest
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.tools.device_events import DeviceEventsTool
from mcp_server.database.models import (
    Patient,
    Encounter,
    CareUnit,
    Device,
)
from mcp_server.utils.validators import ValidationError


@pytest.fixture
async def patient_with_encounters(db_session: AsyncSession) -> tuple[Patient, list[Encounter]]:
    """Create a patient with multiple encounters."""
    patient = Patient(
        id="pat-001",
        first_name="John",
        last_name="Doe",
        date_of_birth=datetime(1980, 5, 15, tzinfo=timezone.utc),
        gender="M",
        mrn="MRN-001",
        phone="555-1234",
        email="john.doe@example.com",
        is_active=True,
    )
    db_session.add(patient)

    encounters = []
    for i in range(2):
        care_unit = CareUnit(
            id=f"cu-{i:03d}",
            name=f"Unit {i}",
            code=f"UNIT{i}",
            description=f"Unit {i}",
            location=f"Building A, Floor {i}",
            unit_type="specialty",
            is_active=True,
        )
        db_session.add(care_unit)

        encounter = Encounter(
            id=f"enc-{i:03d}",
            patient_id=patient.id,
            care_unit_id=care_unit.id,
            encounter_type="inpatient",
            admission_time=datetime(2024, 1, 15 + i, 10, 0, 0, tzinfo=timezone.utc),
            discharge_time=None,
            is_active=True,
            chief_complaint=f"Chief complaint {i}",
        )
        db_session.add(encounter)
        encounters.append(encounter)

    await db_session.commit()
    return patient, encounters


@pytest.fixture
async def devices_in_encounters(
    db_session: AsyncSession, patient_with_encounters: tuple[Patient, list[Encounter]]
) -> list[Device]:
    """Create devices in encounters."""
    _, encounters = patient_with_encounters
    devices = []

    device_types = ["cardiac_monitor", "ventilator", "infusion_pump"]

    for i, encounter in enumerate(encounters):
        for j, device_type in enumerate(device_types):
            device = Device(
                id=f"dev-{i:03d}-{j:03d}",
                encounter_id=encounter.id,
                device_type=device_type,
                device_name=f"{device_type.replace('_', ' ').title()} {i}-{j}",
                serial_number=f"SN-{i:05d}-{j:05d}",
                manufacturer="Philips" if j % 2 == 0 else "Siemens",
                model="MP70" if device_type == "cardiac_monitor" else "SERVO-i",
                location=f"Bed {i + 1}",
                is_online=True,
                battery_level=95.0 - (j * 5),
                calibration_status="calibrated",
                is_active=True,
            )
            db_session.add(device)
            devices.append(device)

    await db_session.commit()
    return devices


class TestDeviceEventsRetrieval:
    """Tests for device events retrieval."""

    @pytest.mark.asyncio
    async def test_get_device_events_success(
        self,
        db_session: AsyncSession,
        patient_with_encounters: tuple[Patient, list[Encounter]],
        devices_in_encounters: list[Device],
    ):
        """Test successful device events retrieval."""
        patient, _ = patient_with_encounters

        events = await DeviceEventsTool.get_device_events_by_patient(
            session=db_session,
            patient_id=patient.id,
        )

        assert events is not None
        assert events["patient_id"] == patient.id
        assert events["mrn"] == "MRN-001"
        assert events["first_name"] == "John"
        assert events["last_name"] == "Doe"
        assert events["full_name"] == "John Doe"
        assert events["device_count"] == 6  # 2 encounters * 3 device types
        assert events["confidence_score"] == 0.88

    @pytest.mark.asyncio
    async def test_get_device_events_includes_alarm_events(
        self,
        db_session: AsyncSession,
        patient_with_encounters: tuple[Patient, list[Encounter]],
        devices_in_encounters: list[Device],
    ):
        """Test device events includes alarm events."""
        patient, _ = patient_with_encounters

        events = await DeviceEventsTool.get_device_events_by_patient(
            session=db_session,
            patient_id=patient.id,
        )

        assert "alarm_events" in events
        assert isinstance(events["alarm_events"], list)

    @pytest.mark.asyncio
    async def test_get_device_events_includes_status_changes(
        self,
        db_session: AsyncSession,
        patient_with_encounters: tuple[Patient, list[Encounter]],
        devices_in_encounters: list[Device],
    ):
        """Test device events includes device status changes."""
        patient, _ = patient_with_encounters

        events = await DeviceEventsTool.get_device_events_by_patient(
            session=db_session,
            patient_id=patient.id,
        )

        assert "device_status_changes" in events
        assert isinstance(events["device_status_changes"], list)

    @pytest.mark.asyncio
    async def test_get_device_events_includes_waveform_events(
        self,
        db_session: AsyncSession,
        patient_with_encounters: tuple[Patient, list[Encounter]],
        devices_in_encounters: list[Device],
    ):
        """Test device events includes waveform events."""
        patient, _ = patient_with_encounters

        events = await DeviceEventsTool.get_device_events_by_patient(
            session=db_session,
            patient_id=patient.id,
        )

        assert "waveform_events" in events
        assert isinstance(events["waveform_events"], list)

    @pytest.mark.asyncio
    async def test_get_device_events_includes_setting_changes(
        self,
        db_session: AsyncSession,
        patient_with_encounters: tuple[Patient, list[Encounter]],
        devices_in_encounters: list[Device],
    ):
        """Test device events includes device setting changes."""
        patient, _ = patient_with_encounters

        events = await DeviceEventsTool.get_device_events_by_patient(
            session=db_session,
            patient_id=patient.id,
        )

        assert "device_setting_changes" in events
        assert isinstance(events["device_setting_changes"], list)

    @pytest.mark.asyncio
    async def test_get_device_events_includes_vital_trends(
        self,
        db_session: AsyncSession,
        patient_with_encounters: tuple[Patient, list[Encounter]],
        devices_in_encounters: list[Device],
    ):
        """Test device events includes vital sign trends."""
        patient, _ = patient_with_encounters

        events = await DeviceEventsTool.get_device_events_by_patient(
            session=db_session,
            patient_id=patient.id,
        )

        assert "vital_sign_trends" in events
        assert isinstance(events["vital_sign_trends"], list)

    @pytest.mark.asyncio
    async def test_get_device_events_patient_not_found(
        self, db_session: AsyncSession
    ):
        """Test device events retrieval with nonexistent patient."""
        with pytest.raises(ValidationError, match="Patient not found"):
            await DeviceEventsTool.get_device_events_by_patient(
                session=db_session,
                patient_id="nonexistent-patient",
            )

    @pytest.mark.asyncio
    async def test_get_device_events_invalid_patient_id(
        self, db_session: AsyncSession
    ):
        """Test device events retrieval with invalid patient ID."""
        with pytest.raises(ValidationError, match="must be a non-empty string"):
            await DeviceEventsTool.get_device_events_by_patient(
                session=db_session,
                patient_id="",
            )

    @pytest.mark.asyncio
    async def test_get_device_events_invalid_patient_id_type(
        self, db_session: AsyncSession
    ):
        """Test device events retrieval with invalid patient ID type."""
        with pytest.raises(ValidationError, match="must be a non-empty string"):
            await DeviceEventsTool.get_device_events_by_patient(
                session=db_session,
                patient_id=123,  # type: ignore
            )


class TestDeviceEventsTimeWindow:
    """Tests for time window parsing and validation."""

    def test_parse_time_window_defaults(self):
        """Test time window parsing with defaults."""
        start_dt, end_dt = DeviceEventsTool._parse_time_window(None, None)

        assert start_dt is not None
        assert end_dt is not None
        assert start_dt < end_dt
        # Default should be 24 hours
        diff = end_dt - start_dt
        assert diff.total_seconds() == 24 * 3600

    def test_parse_time_window_with_times(self):
        """Test time window parsing with specified times."""
        now = datetime.now(timezone.utc)
        start_time = (now - timedelta(hours=12)).isoformat()
        end_time = now.isoformat()

        start_dt, end_dt = DeviceEventsTool._parse_time_window(start_time, end_time)

        assert start_dt is not None
        assert end_dt is not None
        assert start_dt < end_dt

    def test_parse_time_window_invalid_start_time(self):
        """Test time window parsing with invalid start time."""
        with pytest.raises(ValidationError, match="Invalid start_time format"):
            DeviceEventsTool._parse_time_window("invalid-time", None)

    def test_parse_time_window_invalid_end_time(self):
        """Test time window parsing with invalid end time."""
        with pytest.raises(ValidationError, match="Invalid end_time format"):
            DeviceEventsTool._parse_time_window(None, "invalid-time")

    def test_parse_time_window_start_after_end(self):
        """Test time window parsing with start time after end time."""
        now = datetime.now(timezone.utc)
        start_time = now.isoformat()
        end_time = (now - timedelta(hours=1)).isoformat()

        with pytest.raises(ValidationError, match="start_time must be before end_time"):
            DeviceEventsTool._parse_time_window(start_time, end_time)

    def test_parse_time_window_with_z_suffix(self):
        """Test time window parsing with Z suffix (UTC indicator)."""
        now = datetime.now(timezone.utc)
        start_time = (now - timedelta(hours=12)).isoformat().replace("+00:00", "Z")
        end_time = now.isoformat().replace("+00:00", "Z")

        start_dt, end_dt = DeviceEventsTool._parse_time_window(start_time, end_time)

        assert start_dt is not None
        assert end_dt is not None
        assert start_dt < end_dt


class TestDeviceEventsFiltering:
    """Tests for device event filtering."""

    @pytest.mark.asyncio
    async def test_get_device_events_filter_by_device_type(
        self,
        db_session: AsyncSession,
        patient_with_encounters: tuple[Patient, list[Encounter]],
        devices_in_encounters: list[Device],
    ):
        """Test device events retrieval filtered by device type."""
        patient, _ = patient_with_encounters

        events = await DeviceEventsTool.get_device_events_by_patient(
            session=db_session,
            patient_id=patient.id,
            device_type="cardiac_monitor",
        )

        assert events is not None
        assert events["device_count"] == 2  # 2 encounters * 1 cardiac monitor


class TestDeviceEventsEventGeneration:
    """Tests for device event generation."""

    def test_generate_device_events(self):
        """Test device event generation."""
        device = Device(
            id="dev-001",
            encounter_id="enc-001",
            device_type="cardiac_monitor",
            device_name="Philips Monitor",
            serial_number="SN-12345",
            manufacturer="Philips",
            model="MP70",
            location="Bed 1",
            is_online=True,
            battery_level=95.0,
            calibration_status="calibrated",
            is_active=True,
        )

        now = datetime.now(timezone.utc)
        start_dt = now - timedelta(hours=24)
        end_dt = now

        events = DeviceEventsTool._generate_device_events(device, start_dt, end_dt)

        assert isinstance(events, list)
        assert len(events) > 0
        assert "event_id" in events[0]
        assert "device_id" in events[0]
        assert "event_type" in events[0]

    def test_generate_alarm_events_cardiac_monitor(self):
        """Test alarm event generation for cardiac monitor."""
        device = Device(
            id="dev-001",
            encounter_id="enc-001",
            device_type="cardiac_monitor",
            device_name="Philips Monitor",
            serial_number="SN-12345",
            manufacturer="Philips",
            model="MP70",
            location="Bed 1",
            is_online=True,
            battery_level=95.0,
            calibration_status="calibrated",
            is_active=True,
        )

        now = datetime.now(timezone.utc)
        start_dt = now - timedelta(hours=24)
        end_dt = now

        events = DeviceEventsTool._generate_alarm_events(device, start_dt, end_dt)

        assert isinstance(events, list)
        assert len(events) > 0
        assert events[0]["alarm_type"] == "high_heart_rate"
        assert events[0]["severity"] == "high"

    def test_generate_alarm_events_ventilator(self):
        """Test alarm event generation for ventilator."""
        device = Device(
            id="dev-001",
            encounter_id="enc-001",
            device_type="ventilator",
            device_name="Siemens Ventilator",
            serial_number="SN-12345",
            manufacturer="Siemens",
            model="SERVO-i",
            location="Bed 1",
            is_online=True,
            battery_level=None,
            calibration_status="calibrated",
            is_active=True,
        )

        now = datetime.now(timezone.utc)
        start_dt = now - timedelta(hours=24)
        end_dt = now

        events = DeviceEventsTool._generate_alarm_events(device, start_dt, end_dt)

        assert isinstance(events, list)
        assert len(events) > 0
        assert events[0]["alarm_type"] == "low_tidal_volume"
        assert events[0]["severity"] == "medium"

    def test_generate_status_changes(self):
        """Test device status change generation."""
        device = Device(
            id="dev-001",
            encounter_id="enc-001",
            device_type="cardiac_monitor",
            device_name="Philips Monitor",
            serial_number="SN-12345",
            manufacturer="Philips",
            model="MP70",
            location="Bed 1",
            is_online=True,
            battery_level=95.0,
            calibration_status="calibrated",
            is_active=True,
        )

        now = datetime.now(timezone.utc)
        start_dt = now - timedelta(hours=24)
        end_dt = now

        events = DeviceEventsTool._generate_status_changes(device, start_dt, end_dt)

        assert isinstance(events, list)
        assert len(events) > 0
        assert any(e["change_type"] == "online_status" for e in events)

    def test_generate_waveform_events(self):
        """Test waveform event generation."""
        device = Device(
            id="dev-001",
            encounter_id="enc-001",
            device_type="cardiac_monitor",
            device_name="Philips Monitor",
            serial_number="SN-12345",
            manufacturer="Philips",
            model="MP70",
            location="Bed 1",
            is_online=True,
            battery_level=95.0,
            calibration_status="calibrated",
            is_active=True,
        )

        now = datetime.now(timezone.utc)
        start_dt = now - timedelta(hours=24)
        end_dt = now

        events = DeviceEventsTool._generate_waveform_events(device, start_dt, end_dt)

        assert isinstance(events, list)
        assert len(events) > 0
        assert events[0]["event_type"] == "arrhythmia_detected"

    def test_generate_setting_changes_ventilator(self):
        """Test device setting change generation for ventilator."""
        device = Device(
            id="dev-001",
            encounter_id="enc-001",
            device_type="ventilator",
            device_name="Siemens Ventilator",
            serial_number="SN-12345",
            manufacturer="Siemens",
            model="SERVO-i",
            location="Bed 1",
            is_online=True,
            battery_level=None,
            calibration_status="calibrated",
            is_active=True,
        )

        now = datetime.now(timezone.utc)
        start_dt = now - timedelta(hours=24)
        end_dt = now

        events = DeviceEventsTool._generate_setting_changes(device, start_dt, end_dt)

        assert isinstance(events, list)
        assert len(events) > 0
        assert events[0]["setting_name"] == "fio2"

    def test_generate_vital_trends(self):
        """Test vital sign trend generation."""
        device = Device(
            id="dev-001",
            encounter_id="enc-001",
            device_type="cardiac_monitor",
            device_name="Philips Monitor",
            serial_number="SN-12345",
            manufacturer="Philips",
            model="MP70",
            location="Bed 1",
            is_online=True,
            battery_level=95.0,
            calibration_status="calibrated",
            is_active=True,
        )

        now = datetime.now(timezone.utc)
        start_dt = now - timedelta(hours=24)
        end_dt = now

        trends = DeviceEventsTool._generate_vital_trends(device, start_dt, end_dt)

        assert isinstance(trends, list)
        assert len(trends) > 0
        assert "vital_type" in trends[0]
        assert "trend_direction" in trends[0]


class TestDeviceEventsResponseStructure:
    """Tests for device events response structure."""

    @pytest.mark.asyncio
    async def test_response_has_required_fields(
        self,
        db_session: AsyncSession,
        patient_with_encounters: tuple[Patient, list[Encounter]],
        devices_in_encounters: list[Device],
    ):
        """Test that response has all required fields."""
        patient, _ = patient_with_encounters

        events = await DeviceEventsTool.get_device_events_by_patient(
            session=db_session,
            patient_id=patient.id,
        )

        # Check required top-level fields
        assert "patient_id" in events
        assert "mrn" in events
        assert "first_name" in events
        assert "last_name" in events
        assert "full_name" in events
        assert "time_window" in events
        assert "device_count" in events
        assert "device_events" in events
        assert "alarm_events" in events
        assert "device_status_changes" in events
        assert "waveform_events" in events
        assert "device_setting_changes" in events
        assert "vital_sign_trends" in events
        assert "event_count" in events
        assert "confidence_score" in events
        assert "source_references" in events

        # Check source references
        assert len(events["source_references"]) > 0
        assert "source" in events["source_references"][0]
        assert "timestamp" in events["source_references"][0]
        assert "data_types" in events["source_references"][0]


class TestDeviceEventsNoDevices:
    """Tests for device events with no devices."""

    @pytest.mark.asyncio
    async def test_get_device_events_no_devices(
        self, db_session: AsyncSession
    ):
        """Test device events retrieval for patient with no devices."""
        # Create patient without devices
        patient = Patient(
            id="pat-002",
            first_name="Jane",
            last_name="Smith",
            date_of_birth=datetime(1990, 3, 20, tzinfo=timezone.utc),
            gender="F",
            mrn="MRN-002",
            is_active=True,
        )
        db_session.add(patient)

        care_unit = CareUnit(
            id="cu-002",
            name="General Ward",
            code="GEN",
            description="General Ward",
            location="Building B",
            unit_type="general",
            is_active=True,
        )
        db_session.add(care_unit)

        encounter = Encounter(
            id="enc-002",
            patient_id=patient.id,
            care_unit_id=care_unit.id,
            encounter_type="inpatient",
            admission_time=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            discharge_time=None,
            is_active=True,
        )
        db_session.add(encounter)
        await db_session.commit()

        events = await DeviceEventsTool.get_device_events_by_patient(
            session=db_session,
            patient_id=patient.id,
        )

        assert events["device_count"] == 0
        assert len(events["device_events"]) == 0
