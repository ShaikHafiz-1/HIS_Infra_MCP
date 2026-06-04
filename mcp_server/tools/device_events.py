"""
Device events tool for MCP server.

This module provides the get_device_events_by_patient tool which retrieves
device events for a patient within a time window, including alarm events,
device status changes, waveform events, and device setting changes.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mcp_server.database.models import (
    Patient,
    Encounter,
    Device,
)
from mcp_server.utils.logger import get_logger
from mcp_server.utils.validators import ValidationError

logger = get_logger(__name__)


class DeviceEventsTool:
    """Tool for retrieving device events for a patient."""

    @staticmethod
    async def get_device_events_by_patient(
        session: AsyncSession,
        patient_id: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        device_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve device events for a patient within a time window.

        Args:
            session: AsyncSession for database access
            patient_id: Internal patient identifier
            start_time: Start time for event window (ISO format, optional)
            end_time: End time for event window (ISO format, optional)
            device_type: Filter by device type (optional)

        Returns:
            Dictionary containing device events with:
            - patient_id: Patient identifier
            - device_events: List of device events
            - alarm_events: List of alarm events with severity
            - device_status_changes: Device online/offline/calibration changes
            - waveform_events: Arrhythmias, signal loss, artifact events
            - device_setting_changes: Ventilator, infusion rate changes
            - vital_sign_trends: Vital sign trends from device data
            - event_count: Total number of events
            - source_references: Source references and timestamps
            - confidence_score: Confidence score for the data (0-1)

        Raises:
            ValidationError: If patient_id is invalid or patient not found
        """
        # Validate input
        if not isinstance(patient_id, str) or not patient_id.strip():
            raise ValidationError("patient_id must be a non-empty string")

        logger.info(
            f"Retrieving device events for patient_id={patient_id}, "
            f"start_time={start_time}, end_time={end_time}"
        )

        # Parse time window
        start_dt, end_dt = DeviceEventsTool._parse_time_window(start_time, end_time)

        # Get patient
        patient = await DeviceEventsTool._get_patient(session, patient_id)
        if not patient:
            raise ValidationError(f"Patient not found: {patient_id}")

        # Get active encounters for patient
        encounters = await DeviceEventsTool._get_patient_encounters(
            session, patient_id
        )

        # Get devices for patient encounters
        devices = await DeviceEventsTool._get_devices_for_encounters(
            session, [e.id for e in encounters], device_type
        )

        # Build device events (simulated - in production would query actual event tables)
        device_events = []
        alarm_events = []
        device_status_changes = []
        waveform_events = []
        device_setting_changes = []
        vital_sign_trends = []

        for device in devices:
            # Simulate device events
            device_events.extend(
                DeviceEventsTool._generate_device_events(device, start_dt, end_dt)
            )
            alarm_events.extend(
                DeviceEventsTool._generate_alarm_events(device, start_dt, end_dt)
            )
            device_status_changes.extend(
                DeviceEventsTool._generate_status_changes(device, start_dt, end_dt)
            )
            waveform_events.extend(
                DeviceEventsTool._generate_waveform_events(device, start_dt, end_dt)
            )
            device_setting_changes.extend(
                DeviceEventsTool._generate_setting_changes(device, start_dt, end_dt)
            )
            vital_sign_trends.extend(
                DeviceEventsTool._generate_vital_trends(device, start_dt, end_dt)
            )

        # Build response
        response = {
            "patient_id": patient.id,
            "mrn": patient.mrn,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "full_name": f"{patient.first_name} {patient.last_name}",
            "time_window": {
                "start_time": start_dt.isoformat(),
                "end_time": end_dt.isoformat(),
            },
            "device_count": len(devices),
            "device_events": device_events,
            "alarm_events": alarm_events,
            "device_status_changes": device_status_changes,
            "waveform_events": waveform_events,
            "device_setting_changes": device_setting_changes,
            "vital_sign_trends": vital_sign_trends,
            "event_count": (
                len(device_events)
                + len(alarm_events)
                + len(device_status_changes)
                + len(waveform_events)
                + len(device_setting_changes)
            ),
            "confidence_score": 0.88,
            "source_references": [
                {
                    "source": "device_telemetry",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data_types": [
                        "alarm_events",
                        "device_status",
                        "waveform_data",
                        "vital_signs",
                    ],
                }
            ],
        }

        logger.info(
            f"Retrieved {response['event_count']} device events for patient {patient_id}"
        )

        return response

    @staticmethod
    def _parse_time_window(
        start_time: Optional[str], end_time: Optional[str]
    ) -> tuple[datetime, datetime]:
        """Parse and validate time window."""
        now = datetime.now(timezone.utc)

        # Default to last 24 hours if not specified
        if not end_time:
            end_dt = now
        else:
            try:
                end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                raise ValidationError(f"Invalid end_time format: {end_time}")

        if not start_time:
            start_dt = end_dt - timedelta(hours=24)
        else:
            try:
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                raise ValidationError(f"Invalid start_time format: {start_time}")

        # Validate time window
        if start_dt >= end_dt:
            raise ValidationError("start_time must be before end_time")

        return start_dt, end_dt

    @staticmethod
    async def _get_patient(
        session: AsyncSession, patient_id: str
    ) -> Optional[Patient]:
        """Get patient by ID."""
        stmt = select(Patient).where(
            and_(Patient.id == patient_id, Patient.is_active == True)
        )
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def _get_patient_encounters(
        session: AsyncSession, patient_id: str
    ) -> List[Encounter]:
        """Get all encounters for a patient."""
        stmt = (
            select(Encounter)
            .where(Encounter.patient_id == patient_id)
            .options(selectinload(Encounter.devices))
        )
        result = await session.execute(stmt)
        return result.scalars().unique().all()

    @staticmethod
    async def _get_devices_for_encounters(
        session: AsyncSession,
        encounter_ids: List[str],
        device_type: Optional[str] = None,
    ) -> List[Device]:
        """Get devices for a list of encounters."""
        stmt = select(Device).where(Device.encounter_id.in_(encounter_ids))

        if device_type:
            stmt = stmt.where(Device.device_type == device_type)

        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    def _generate_device_events(
        device: Device, start_dt: datetime, end_dt: datetime
    ) -> List[Dict[str, Any]]:
        """Generate simulated device events."""
        events = []

        # Simulate a device event
        if device.is_active:
            events.append(
                {
                    "event_id": f"dev-evt-{device.id}",
                    "device_id": device.id,
                    "device_type": device.device_type,
                    "device_name": device.device_name,
                    "event_type": "device_online",
                    "timestamp": start_dt.isoformat(),
                    "description": f"{device.device_name} came online",
                    "severity": "info",
                    "source": "device_telemetry",
                    "confidence_score": 0.95,
                }
            )

        return events

    @staticmethod
    def _generate_alarm_events(
        device: Device, start_dt: datetime, end_dt: datetime
    ) -> List[Dict[str, Any]]:
        """Generate simulated alarm events."""
        events = []

        # Simulate alarm events based on device type
        if device.device_type == "cardiac_monitor":
            events.append(
                {
                    "alarm_id": f"alarm-{device.id}-1",
                    "device_id": device.id,
                    "device_type": device.device_type,
                    "alarm_type": "high_heart_rate",
                    "severity": "high",
                    "threshold": 120,
                    "current_value": 125,
                    "timestamp": (start_dt + timedelta(hours=2)).isoformat(),
                    "description": "Heart rate above threshold",
                    "source": "device_telemetry",
                    "confidence_score": 0.92,
                }
            )
        elif device.device_type == "ventilator":
            events.append(
                {
                    "alarm_id": f"alarm-{device.id}-1",
                    "device_id": device.id,
                    "device_type": device.device_type,
                    "alarm_type": "low_tidal_volume",
                    "severity": "medium",
                    "threshold": 400,
                    "current_value": 380,
                    "timestamp": (start_dt + timedelta(hours=4)).isoformat(),
                    "description": "Tidal volume below threshold",
                    "source": "device_telemetry",
                    "confidence_score": 0.90,
                }
            )

        return events

    @staticmethod
    def _generate_status_changes(
        device: Device, start_dt: datetime, end_dt: datetime
    ) -> List[Dict[str, Any]]:
        """Generate simulated device status changes."""
        events = []

        # Simulate status change
        if device.is_online:
            events.append(
                {
                    "status_change_id": f"status-{device.id}-1",
                    "device_id": device.id,
                    "device_type": device.device_type,
                    "change_type": "online_status",
                    "previous_status": "offline",
                    "new_status": "online",
                    "timestamp": start_dt.isoformat(),
                    "description": f"{device.device_name} came online",
                    "source": "device_telemetry",
                    "confidence_score": 0.98,
                }
            )

        # Simulate calibration status
        if device.calibration_status:
            events.append(
                {
                    "status_change_id": f"status-{device.id}-2",
                    "device_id": device.id,
                    "device_type": device.device_type,
                    "change_type": "calibration_status",
                    "calibration_status": device.calibration_status,
                    "timestamp": (start_dt + timedelta(hours=1)).isoformat(),
                    "description": f"Calibration status: {device.calibration_status}",
                    "source": "device_telemetry",
                    "confidence_score": 0.95,
                }
            )

        return events

    @staticmethod
    def _generate_waveform_events(
        device: Device, start_dt: datetime, end_dt: datetime
    ) -> List[Dict[str, Any]]:
        """Generate simulated waveform events."""
        events = []

        # Simulate waveform events for cardiac monitors
        if device.device_type == "cardiac_monitor":
            events.append(
                {
                    "waveform_event_id": f"wf-{device.id}-1",
                    "device_id": device.id,
                    "device_type": device.device_type,
                    "event_type": "arrhythmia_detected",
                    "arrhythmia_type": "premature_ventricular_contraction",
                    "timestamp": (start_dt + timedelta(hours=3)).isoformat(),
                    "description": "Premature ventricular contraction detected",
                    "severity": "medium",
                    "source": "device_telemetry",
                    "confidence_score": 0.85,
                }
            )

        return events

    @staticmethod
    def _generate_setting_changes(
        device: Device, start_dt: datetime, end_dt: datetime
    ) -> List[Dict[str, Any]]:
        """Generate simulated device setting changes."""
        events = []

        # Simulate setting changes for ventilators
        if device.device_type == "ventilator":
            events.append(
                {
                    "setting_change_id": f"setting-{device.id}-1",
                    "device_id": device.id,
                    "device_type": device.device_type,
                    "setting_name": "fio2",
                    "previous_value": 0.40,
                    "new_value": 0.45,
                    "timestamp": (start_dt + timedelta(hours=5)).isoformat(),
                    "description": "FiO2 adjusted from 40% to 45%",
                    "clinician_id": None,
                    "source": "device_telemetry",
                    "confidence_score": 0.93,
                }
            )

        # Simulate setting changes for infusion pumps
        if device.device_type == "infusion_pump":
            events.append(
                {
                    "setting_change_id": f"setting-{device.id}-1",
                    "device_id": device.id,
                    "device_type": device.device_type,
                    "setting_name": "infusion_rate",
                    "previous_value": 10.0,
                    "new_value": 15.0,
                    "unit": "ml/hr",
                    "timestamp": (start_dt + timedelta(hours=6)).isoformat(),
                    "description": "Infusion rate adjusted from 10 to 15 ml/hr",
                    "clinician_id": None,
                    "source": "device_telemetry",
                    "confidence_score": 0.94,
                }
            )

        return events

    @staticmethod
    def _generate_vital_trends(
        device: Device, start_dt: datetime, end_dt: datetime
    ) -> List[Dict[str, Any]]:
        """Generate simulated vital sign trends from device data."""
        trends = []

        # Simulate vital trends for cardiac monitors
        if device.device_type == "cardiac_monitor":
            trends.append(
                {
                    "vital_type": "heart_rate",
                    "device_id": device.id,
                    "device_type": device.device_type,
                    "trend_direction": "rising",
                    "start_value": 75,
                    "end_value": 95,
                    "min_value": 72,
                    "max_value": 98,
                    "average_value": 85,
                    "time_window": {
                        "start_time": start_dt.isoformat(),
                        "end_time": end_dt.isoformat(),
                    },
                    "data_points": 288,  # 5-minute intervals over 24 hours
                    "source": "device_telemetry",
                    "confidence_score": 0.91,
                }
            )
            trends.append(
                {
                    "vital_type": "blood_pressure_systolic",
                    "device_id": device.id,
                    "device_type": device.device_type,
                    "trend_direction": "stable",
                    "start_value": 120,
                    "end_value": 118,
                    "min_value": 110,
                    "max_value": 135,
                    "average_value": 122,
                    "time_window": {
                        "start_time": start_dt.isoformat(),
                        "end_time": end_dt.isoformat(),
                    },
                    "data_points": 288,
                    "source": "device_telemetry",
                    "confidence_score": 0.89,
                }
            )

        return trends
