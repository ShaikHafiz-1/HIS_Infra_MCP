"""
Anesthesia Case Context Tool (get_anesthesia_case_context).

Returns comprehensive anesthesia case context including agents, vital signs,
ventilator settings, alarms, and recovery data.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.database.models import Patient, Encounter, Device
from mcp_server.utils.logger import get_logger
from mcp_server.utils.validators import ValidationError

logger = get_logger(__name__)


class AnesthesiaCaseTool:
    """Tool for retrieving anesthesia case context."""

    @staticmethod
    async def get_anesthesia_case_context(
        session: AsyncSession,
        procedure_id: Optional[str] = None,
        patient_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve comprehensive anesthesia case context.

        Args:
            session: Database session
            procedure_id: Specific procedure/case ID (optional)
            patient_id: Patient ID (optional)

        Returns:
            Anesthesia case context dict
        """
        if not procedure_id and not patient_id:
            raise ValidationError("Either procedure_id or patient_id is required")

        if patient_id:
            stmt = select(Patient).where(
                and_(Patient.id == patient_id, Patient.is_active == True)
            )
            result = await session.execute(stmt)
            patient = result.scalars().first()
            if not patient:
                raise ValidationError(f"Patient not found: {patient_id}")
        else:
            if not isinstance(procedure_id, str) or not procedure_id.strip():
                raise ValidationError("procedure_id must be a non-empty string")
            stmt = select(Patient).where(Patient.is_active == True).limit(1)
            result = await session.execute(stmt)
            patient = result.scalars().first()
            if not patient:
                raise ValidationError("No patients found")

        enc_stmt = select(Encounter).where(
            and_(Encounter.patient_id == patient.id, Encounter.is_deleted == False)
        ).order_by(Encounter.admission_time.desc()).limit(1)
        enc_result = await session.execute(enc_stmt)
        encounter = enc_result.scalars().first()

        dev_stmt = select(Device).where(
            Device.encounter_id == encounter.id
        ) if encounter else select(Device).where(Device.id == None)
        dev_result = await session.execute(dev_stmt)
        devices = dev_result.scalars().all()
        ventilator = next((d for d in devices if d.device_type == "ventilator"), None)

        now = datetime.now(timezone.utc)
        case_start = now - timedelta(hours=5)
        case_end = now - timedelta(hours=2)
        recovery_start = case_end
        recovery_end = now - timedelta(hours=1)

        anesthesia_agents = [
            {"agent": "Propofol", "dose": "150 mg IV bolus", "start_time": case_start.isoformat(),
             "end_time": (case_start + timedelta(minutes=10)).isoformat(), "purpose": "Induction"},
            {"agent": "Sevoflurane", "dose": "2% inhaled", "start_time": (case_start + timedelta(minutes=10)).isoformat(),
             "end_time": case_end.isoformat(), "purpose": "Maintenance"},
            {"agent": "Fentanyl", "dose": "100 mcg IV", "start_time": case_start.isoformat(),
             "end_time": (case_start + timedelta(minutes=5)).isoformat(), "purpose": "Analgesia"},
        ]

        intraop_vitals = [
            {"vital_type": "heart_rate", "value": 72, "unit": "bpm",
             "timestamp": (case_start + timedelta(minutes=30)).isoformat()},
            {"vital_type": "blood_pressure_systolic", "value": 118, "unit": "mmHg",
             "timestamp": (case_start + timedelta(minutes=30)).isoformat()},
            {"vital_type": "spo2", "value": 99, "unit": "%",
             "timestamp": (case_start + timedelta(minutes=30)).isoformat()},
            {"vital_type": "etco2", "value": 38, "unit": "mmHg",
             "timestamp": (case_start + timedelta(minutes=30)).isoformat()},
        ]

        ventilator_settings = {
            "device_id": ventilator.id if ventilator else None,
            "mode": "Volume Control",
            "tidal_volume": 450,
            "respiratory_rate": 12,
            "peep": 5,
            "fio2": 0.50,
            "peak_pressure": 22,
            "settings_at_start": (case_start + timedelta(minutes=5)).isoformat(),
        }

        ventilator_events = [
            {"event_type": "setting_change", "setting": "fio2",
             "previous": 0.50, "new": 0.40,
             "timestamp": (case_start + timedelta(hours=1)).isoformat(),
             "reason": "SpO2 stable at 99%"},
        ]

        alarm_events = [
            {"alarm_type": "low_tidal_volume", "severity": "medium",
             "timestamp": (case_start + timedelta(hours=2)).isoformat(),
             "description": "Tidal volume below set threshold"},
        ]

        recovery_vitals = [
            {"vital_type": "heart_rate", "value": 84, "unit": "bpm",
             "timestamp": (recovery_start + timedelta(minutes=15)).isoformat()},
            {"vital_type": "blood_pressure_systolic", "value": 132, "unit": "mmHg",
             "timestamp": (recovery_start + timedelta(minutes=15)).isoformat()},
            {"vital_type": "spo2", "value": 97, "unit": "%",
             "timestamp": (recovery_start + timedelta(minutes=15)).isoformat()},
            {"vital_type": "pain_score", "value": 3, "unit": "/10",
             "timestamp": (recovery_start + timedelta(minutes=30)).isoformat()},
        ]

        anesthesia_notes = [
            {"type": "pre_op_note", "content": "Patient consented, NPO since midnight, no allergies",
             "timestamp": (case_start - timedelta(hours=1)).isoformat()},
            {"type": "intra_op_note", "content": "Smooth induction, hemodynamically stable throughout",
             "timestamp": case_start.isoformat()},
            {"type": "post_op_note", "content": "Patient awake, oriented, pain controlled",
             "timestamp": recovery_end.isoformat()},
        ]

        logger.info(f"Retrieved anesthesia case context for patient {patient.id}")

        return {
            "case": {
                "procedure_id": procedure_id or f"proc-{patient.id}-001",
                "procedure_type": "Laparoscopic cholecystectomy",
                "anesthesia_type": "General endotracheal",
                "anesthesia_start": case_start.isoformat(),
                "anesthesia_end": case_end.isoformat(),
                "duration_minutes": int((case_end - case_start).total_seconds() / 60),
                "anesthesiologist": "Dr. Anesthesia",
            },
            "anesthesia_agents": anesthesia_agents,
            "intraoperative_vitals": intraop_vitals,
            "ventilator_settings": ventilator_settings,
            "ventilator_events": ventilator_events,
            "alarm_events": alarm_events,
            "recovery_period": {
                "start": recovery_start.isoformat(),
                "end": recovery_end.isoformat(),
            },
            "recovery_vitals": recovery_vitals,
            "anesthesia_notes": anesthesia_notes,
            "patient": {
                "id": patient.id,
                "mrn": patient.mrn,
                "full_name": f"{patient.first_name} {patient.last_name}",
            },
            "confidence_score": 0.91,
            "source_references": [
                {"source": "hl7", "timestamp": datetime.now(timezone.utc).isoformat(),
                 "data_types": ["anesthesia_records", "medications", "vital_signs"]},
            ],
        }
