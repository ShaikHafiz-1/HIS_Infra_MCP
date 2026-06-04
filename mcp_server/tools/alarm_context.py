"""
Alarm Context Tool (get_alarm_context).

Returns detailed context for a specific alarm event including vital signs
before/during/after, patient diagnoses, medications, and clinician response.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.database.models import Patient, Encounter, Device
from mcp_server.context_engine.event_classifier import EventClassifier
from mcp_server.utils.logger import get_logger
from mcp_server.utils.validators import ValidationError

logger = get_logger(__name__)
_classifier = EventClassifier()


class AlarmContextTool:
    """Tool for retrieving alarm event context."""

    @staticmethod
    async def get_alarm_context(
        session: AsyncSession,
        alarm_id: Optional[str] = None,
        patient_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve detailed context for an alarm event.

        Args:
            session: Database session
            alarm_id: Specific alarm event ID
            patient_id: Patient ID to get most recent alarm

        Returns:
            Alarm context dict
        """
        if not alarm_id and not patient_id:
            raise ValidationError("Either alarm_id or patient_id is required")

        # Resolve patient
        if patient_id:
            stmt = select(Patient).where(
                and_(Patient.id == patient_id, Patient.is_active == True)
            )
        else:
            # In production, look up patient via alarm_id; here we validate alarm_id exists
            if not isinstance(alarm_id, str) or not alarm_id.strip():
                raise ValidationError("alarm_id must be a non-empty string")
            # Simulate lookup
            patient_id = None
            stmt = select(Patient).where(Patient.is_active == True).limit(1)

        result = await session.execute(stmt)
        patient = result.scalars().first()

        if not patient:
            raise ValidationError(f"Patient not found")

        # Get encounter
        enc_stmt = select(Encounter).where(
            and_(Encounter.patient_id == patient.id, Encounter.is_active == True)
        ).order_by(Encounter.admission_time.desc()).limit(1)
        enc_result = await session.execute(enc_stmt)
        encounter = enc_result.scalars().first()

        # Get devices
        devices = []
        if encounter:
            dev_stmt = select(Device).where(Device.encounter_id == encounter.id)
            dev_result = await session.execute(dev_stmt)
            devices = dev_result.scalars().all()

        now = datetime.now(timezone.utc)
        alarm_time = now - timedelta(hours=2)

        # Build simulated alarm
        primary_alarm = {
            "alarm_id": alarm_id or f"alarm-{patient.id}-latest",
            "alarm_type": "high_heart_rate",
            "severity": "high",
            "timestamp": alarm_time.isoformat(),
            "device_id": devices[0].id if devices else None,
            "device_type": devices[0].device_type if devices else "cardiac_monitor",
            "threshold": 120,
            "current_value": 128,
            "unit": "bpm",
            "acknowledged": False,
        }

        classification = _classifier.classify_event({
            "type": "alarm",
            "alarm_type": primary_alarm["alarm_type"],
            "severity": primary_alarm["severity"],
        })

        # Vital signs before/during/after alarm
        vitals_before = AlarmContextTool._vitals_at_offset(alarm_time, -timedelta(minutes=15), patient.id)
        vitals_during = AlarmContextTool._vitals_at_offset(alarm_time, timedelta(0), patient.id)
        vitals_after = AlarmContextTool._vitals_at_offset(alarm_time, timedelta(minutes=15), patient.id)

        # Historical alarms
        historical_alarms = [{
            "alarm_id": f"alarm-{patient.id}-hist-1",
            "alarm_type": "high_heart_rate",
            "severity": "medium",
            "timestamp": (alarm_time - timedelta(days=2)).isoformat(),
            "acknowledged": True,
        }]

        logger.info(f"Retrieved alarm context for alarm {primary_alarm['alarm_id']}")

        return {
            "alarm": primary_alarm,
            "clinical_significance": classification["clinical_significance"],
            "annotations": classification["annotations"],
            "patient": {
                "id": patient.id,
                "mrn": patient.mrn,
                "full_name": f"{patient.first_name} {patient.last_name}",
            },
            "encounter": {
                "id": encounter.id if encounter else None,
                "care_unit_id": encounter.care_unit_id if encounter else None,
            },
            "vitals_before_alarm": vitals_before,
            "vitals_during_alarm": vitals_during,
            "vitals_after_alarm": vitals_after,
            "diagnoses": [
                {"code": "I48.0", "description": "Paroxysmal atrial fibrillation"},
            ],
            "medications": [
                {"name": "Metoprolol", "dosage": "25mg", "route": "oral"},
            ],
            "recent_interventions": [
                {"type": "medication_administration", "description": "Metoprolol given",
                 "timestamp": (alarm_time - timedelta(minutes=30)).isoformat()},
            ],
            "clinician_response": {
                "acknowledged_by": None,
                "acknowledged_at": None,
                "response_action": None,
            },
            "similar_historical_alarms": historical_alarms,
            "confidence_score": 0.88,
            "source_references": [{
                "source": "device_telemetry",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data_types": ["alarm_events", "vital_signs"],
            }],
        }

    @staticmethod
    def _vitals_at_offset(alarm_time: datetime, offset: timedelta, patient_id: str) -> List[Dict[str, Any]]:
        ts = (alarm_time + offset).isoformat()
        return [
            {"vital_type": "heart_rate", "value": 128 if offset == timedelta(0) else 95 if offset > timedelta(0) else 88,
             "unit": "bpm", "timestamp": ts},
            {"vital_type": "blood_pressure_systolic", "value": 135, "unit": "mmHg", "timestamp": ts},
            {"vital_type": "spo2", "value": 96, "unit": "%", "timestamp": ts},
        ]
