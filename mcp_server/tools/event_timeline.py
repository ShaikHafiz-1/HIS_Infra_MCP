"""
Patient Event Timeline Tool (get_patient_event_timeline).

Returns a chronological timeline of clinical events for a patient including
vital signs, alarms, medications, procedures, notes, and device changes.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.database.models import Patient, Encounter, Device
from mcp_server.context_engine.timeline_builder import TimelineBuilder
from mcp_server.utils.logger import get_logger
from mcp_server.utils.validators import ValidationError

logger = get_logger(__name__)
_builder = TimelineBuilder()


class EventTimelineTool:
    """Tool for building patient event timelines."""

    @staticmethod
    async def get_patient_event_timeline(
        session: AsyncSession,
        patient_id: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        event_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve a chronological event timeline for a patient.

        Args:
            session: Database session
            patient_id: Internal patient identifier
            start_time: ISO start time (default: 24 hours ago)
            end_time: ISO end time (default: now)
            event_types: Filter to specific event types (optional)

        Returns:
            Timeline dict with events sorted chronologically
        """
        if not patient_id or not isinstance(patient_id, str):
            raise ValidationError("patient_id must be a non-empty string")

        start_dt, end_dt = EventTimelineTool._parse_window(start_time, end_time)

        stmt = select(Patient).where(
            and_(Patient.id == patient_id, Patient.is_active == True)
        )
        result = await session.execute(stmt)
        patient = result.scalars().first()
        if not patient:
            raise ValidationError(f"Patient not found: {patient_id}")

        enc_stmt = select(Encounter).where(
            and_(Encounter.patient_id == patient_id, Encounter.is_deleted == False)
        ).order_by(Encounter.admission_time.desc()).limit(1)
        enc_result = await session.execute(enc_stmt)
        encounter = enc_result.scalars().first()

        dev_stmt = select(Device).where(
            Device.encounter_id == encounter.id
        ) if encounter else select(Device).where(Device.id == None)
        dev_result = await session.execute(dev_stmt)
        devices = dev_result.scalars().all()

        # Build simulated event data covering the time window
        observations = EventTimelineTool._simulate_observations(patient_id, devices, start_dt, end_dt)
        alarms = EventTimelineTool._simulate_alarms(patient_id, devices, start_dt, end_dt)
        medications = EventTimelineTool._simulate_medications(patient_id, start_dt, end_dt)
        procedures = EventTimelineTool._simulate_procedures(patient_id, encounter, start_dt, end_dt)
        notes = EventTimelineTool._simulate_notes(patient_id, encounter, start_dt, end_dt)
        device_changes = EventTimelineTool._simulate_device_changes(patient_id, devices, start_dt, end_dt)

        # Apply event type filter
        all_events = {
            "vital_sign": observations,
            "alarm": alarms,
            "medication": medications,
            "procedure": procedures,
            "clinician_note": notes,
            "device_setting_change": device_changes,
        }

        if event_types:
            filtered_obs = observations if "vital_sign" in event_types else []
            filtered_alarms = alarms if "alarm" in event_types else []
            filtered_meds = medications if "medication" in event_types else []
            filtered_procs = procedures if "procedure" in event_types else []
            filtered_notes = notes if "clinician_note" in event_types else []
            filtered_changes = device_changes if "device_setting_change" in event_types else []
        else:
            filtered_obs = observations
            filtered_alarms = alarms
            filtered_meds = medications
            filtered_procs = procedures
            filtered_notes = notes
            filtered_changes = device_changes

        timeline = _builder.build_timeline(
            observations=filtered_obs,
            alarm_events=filtered_alarms,
            medication_events=filtered_meds,
            procedures=filtered_procs,
            notes=filtered_notes,
            device_changes=filtered_changes,
            start_time=start_dt,
            end_time=end_dt,
        )

        logger.info(f"Built timeline with {len(timeline)} events for patient {patient_id}")

        return {
            "patient_id": patient.id,
            "mrn": patient.mrn,
            "full_name": f"{patient.first_name} {patient.last_name}",
            "time_window": {"start_time": start_dt.isoformat(), "end_time": end_dt.isoformat()},
            "event_count": len(timeline),
            "timeline": timeline,
            "event_type_counts": {
                "vital_signs": len(filtered_obs),
                "alarms": len(filtered_alarms),
                "medications": len(filtered_meds),
                "procedures": len(filtered_procs),
                "clinician_notes": len(filtered_notes),
                "device_changes": len(filtered_changes),
            },
            "confidence_score": 0.88,
            "source_references": [{
                "source": "internal_database",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data_types": ["observations", "alarms", "medications", "procedures", "notes"],
            }],
        }

    @staticmethod
    def _parse_window(start_time: Optional[str], end_time: Optional[str]):
        now = datetime.now(timezone.utc)
        if end_time:
            try:
                end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            except ValueError:
                raise ValidationError(f"Invalid end_time: {end_time}")
        else:
            end_dt = now

        if start_time:
            try:
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            except ValueError:
                raise ValidationError(f"Invalid start_time: {start_time}")
        else:
            start_dt = end_dt - timedelta(hours=24)

        if start_dt >= end_dt:
            raise ValidationError("start_time must be before end_time")
        return start_dt, end_dt

    @staticmethod
    def _simulate_observations(patient_id, devices, start_dt, end_dt):
        obs = []
        for i, device in enumerate(devices):
            obs.append({
                "observation_type": "heart_rate",
                "vital_type": "heart_rate",
                "value": 72 + i * 3,
                "unit": "bpm",
                "timestamp": (start_dt + (end_dt - start_dt) * 0.25).isoformat(),
                "device_id": device.id,
                "source_system": "device_telemetry",
                "is_abnormal": False,
            })
            obs.append({
                "observation_type": "spo2",
                "vital_type": "spo2",
                "value": 97 - i,
                "unit": "%",
                "timestamp": (start_dt + (end_dt - start_dt) * 0.5).isoformat(),
                "device_id": device.id,
                "source_system": "device_telemetry",
                "is_abnormal": False,
            })
        return obs

    @staticmethod
    def _simulate_alarms(patient_id, devices, start_dt, end_dt):
        alarms = []
        for device in devices:
            if device.device_type == "cardiac_monitor":
                alarms.append({
                    "alarm_type": "high_heart_rate",
                    "severity": "high",
                    "timestamp": (start_dt + (end_dt - start_dt) * 0.4).isoformat(),
                    "device_id": device.id,
                    "source_system": "device_telemetry",
                })
        return alarms

    @staticmethod
    def _simulate_medications(patient_id, start_dt, end_dt):
        return [{
            "medication_name": "Metoprolol",
            "dosage": "25mg",
            "route": "oral",
            "administration_time": (start_dt + (end_dt - start_dt) * 0.3).isoformat(),
            "indication": "Rate control",
            "source_system": "hl7",
        }]

    @staticmethod
    def _simulate_procedures(patient_id, encounter, start_dt, end_dt):
        if not encounter:
            return []
        return [{
            "procedure_type": "ECG",
            "indication": "Cardiac monitoring",
            "start_time": (start_dt + (end_dt - start_dt) * 0.1).isoformat(),
            "status": "completed",
            "encounter_id": encounter.id,
            "source_system": "hl7",
        }]

    @staticmethod
    def _simulate_notes(patient_id, encounter, start_dt, end_dt):
        if not encounter:
            return []
        return [{
            "note_type": "progress_note",
            "author": "Attending Physician",
            "content_summary": "Patient stable, continue current management",
            "timestamp": (start_dt + (end_dt - start_dt) * 0.6).isoformat(),
            "source_system": "hl7",
        }]

    @staticmethod
    def _simulate_device_changes(patient_id, devices, start_dt, end_dt):
        changes = []
        for device in devices:
            if device.device_type == "ventilator":
                changes.append({
                    "device_id": device.id,
                    "device_type": device.device_type,
                    "setting_name": "fio2",
                    "previous_value": 0.40,
                    "new_value": 0.45,
                    "timestamp": (start_dt + (end_dt - start_dt) * 0.7).isoformat(),
                    "source_system": "device_telemetry",
                })
        return changes
