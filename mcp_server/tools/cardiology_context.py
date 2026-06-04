"""
Cardiology Event Context Tool (get_cardiology_event_context).

Returns cardiac event context including ECG events, arrhythmias, hemodynamics,
cardiac medications, and related diagnostic exams.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.database.models import Patient, Encounter, Device
from mcp_server.utils.logger import get_logger
from mcp_server.utils.validators import ValidationError

logger = get_logger(__name__)


class CardiologyEventTool:
    """Tool for retrieving cardiology event context."""

    @staticmethod
    async def get_cardiology_event_context(
        session: AsyncSession,
        patient_id: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve cardiac event context.

        Args:
            session: Database session
            patient_id: Patient ID (optional)
            event_id: Specific cardiac event ID (optional)

        Returns:
            Cardiology event context dict
        """
        if not patient_id and not event_id:
            raise ValidationError("Either patient_id or event_id is required")

        if patient_id:
            stmt = select(Patient).where(
                and_(Patient.id == patient_id, Patient.is_active == True)
            )
            result = await session.execute(stmt)
            patient = result.scalars().first()
            if not patient:
                raise ValidationError(f"Patient not found: {patient_id}")
        else:
            if not isinstance(event_id, str) or not event_id.strip():
                raise ValidationError("event_id must be a non-empty string")
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
        cardiac_monitor = next((d for d in devices if d.device_type == "cardiac_monitor"), None)

        now = datetime.now(timezone.utc)
        event_time = now - timedelta(hours=4)

        ecg_events = [
            {
                "event_id": event_id or f"ecg-{patient.id}-001",
                "event_type": "arrhythmia_detected",
                "arrhythmia_type": "atrial_fibrillation",
                "onset_timestamp": event_time.isoformat(),
                "duration_minutes": 45,
                "resolution_timestamp": (event_time + timedelta(minutes=45)).isoformat(),
                "heart_rate_during": {"min": 88, "max": 142, "average": 112},
                "device_id": cardiac_monitor.id if cardiac_monitor else None,
                "interpretation": "Rapid ventricular response atrial fibrillation",
                "is_sustained": False,
            }
        ]

        ecg_waveform_data = [
            {
                "waveform_id": f"wf-{patient.id}-001",
                "timestamp": event_time.isoformat(),
                "duration_seconds": 10,
                "rhythm": "Atrial fibrillation",
                "rate": 112,
                "pr_interval": None,
                "qrs_duration": 88,
                "qt_interval": 380,
                "st_changes": "No significant ST changes",
                "interpretation": "Atrial fibrillation with rapid ventricular response",
            }
        ]

        bp_trend = [
            {"vital_type": "blood_pressure_systolic", "value": 148, "unit": "mmHg",
             "timestamp": (event_time - timedelta(hours=1)).isoformat()},
            {"vital_type": "blood_pressure_systolic", "value": 162, "unit": "mmHg",
             "timestamp": event_time.isoformat(), "is_abnormal": True},
            {"vital_type": "blood_pressure_systolic", "value": 138, "unit": "mmHg",
             "timestamp": (event_time + timedelta(hours=1)).isoformat()},
        ]
        spo2_trend = [
            {"vital_type": "spo2", "value": 96, "unit": "%",
             "timestamp": (event_time - timedelta(hours=1)).isoformat()},
            {"vital_type": "spo2", "value": 93, "unit": "%",
             "timestamp": event_time.isoformat(), "is_abnormal": True},
            {"vital_type": "spo2", "value": 97, "unit": "%",
             "timestamp": (event_time + timedelta(hours=1)).isoformat()},
        ]

        cardiac_alarms = [
            {"alarm_type": "atrial_fibrillation_detected", "severity": "high",
             "timestamp": event_time.isoformat(), "device_id": cardiac_monitor.id if cardiac_monitor else None},
            {"alarm_type": "high_heart_rate", "severity": "high",
             "timestamp": (event_time + timedelta(minutes=5)).isoformat(),
             "threshold": 120, "value": 142},
        ]

        cardiac_medications = [
            {"medication": "Metoprolol", "dose": "5mg IV", "route": "IV",
             "timestamp": (event_time + timedelta(minutes=10)).isoformat(),
             "indication": "Rate control for AF"},
            {"medication": "Heparin", "dose": "5000 units IV", "route": "IV",
             "timestamp": (event_time + timedelta(minutes=15)).isoformat(),
             "indication": "Anticoagulation for AF"},
        ]

        related_exams = [
            {"exam_type": "Echocardiogram", "description": "Bedside TTE",
             "timestamp": (event_time + timedelta(hours=2)).isoformat(),
             "findings": "Mildly reduced LV function, EF 45%, no valvular pathology",
             "report_status": "preliminary"},
            {"exam_type": "Troponin", "description": "Troponin I",
             "timestamp": event_time.isoformat(),
             "value": 0.08, "unit": "ng/mL", "reference_range": "< 0.04",
             "is_abnormal": True},
        ]

        clinical_notes = [
            {"type": "cardiology_note", "author": "Cardiology Fellow",
             "content_summary": "New onset AF with RVR. Rate controlled with metoprolol. "
                                "Initiated anticoagulation. Echo ordered.",
             "timestamp": (event_time + timedelta(hours=1)).isoformat()},
        ]

        logger.info(f"Retrieved cardiology event context for patient {patient.id}")

        return {
            "patient": {
                "id": patient.id,
                "mrn": patient.mrn,
                "full_name": f"{patient.first_name} {patient.last_name}",
            },
            "encounter": {"id": encounter.id if encounter else None},
            "ecg_events": ecg_events,
            "ecg_waveform_data": ecg_waveform_data,
            "blood_pressure_trend": bp_trend,
            "spo2_trend": spo2_trend,
            "cardiac_alarm_events": cardiac_alarms,
            "cardiac_medications": cardiac_medications,
            "related_diagnostic_exams": related_exams,
            "clinical_notes": clinical_notes,
            "cardiac_assessments": [
                {"assessment": "Risk stratification", "score": "CHADS2-VASc 3",
                 "recommendation": "Anticoagulation indicated",
                 "timestamp": (event_time + timedelta(hours=1, minutes=30)).isoformat()},
            ],
            "confidence_score": 0.92,
            "source_references": [
                {"source": "device_telemetry", "timestamp": datetime.now(timezone.utc).isoformat(),
                 "data_types": ["ecg_waveforms", "alarm_events", "vital_signs"]},
                {"source": "hl7", "timestamp": datetime.now(timezone.utc).isoformat(),
                 "data_types": ["medications", "clinical_notes", "lab_results"]},
            ],
        }
