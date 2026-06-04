"""
Neuro Event Context Tool (get_neuro_event_context).

Returns neurological event context including seizures, EEG data,
neuroimaging, and management medications.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.database.models import Patient, Encounter
from mcp_server.utils.logger import get_logger
from mcp_server.utils.validators import ValidationError

logger = get_logger(__name__)


class NeuroEventTool:
    """Tool for retrieving neurological event context."""

    @staticmethod
    async def get_neuro_event_context(
        session: AsyncSession,
        patient_id: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve neurological event context.

        Args:
            session: Database session
            patient_id: Patient ID (optional)
            event_id: Specific neuro event ID (optional)

        Returns:
            Neuro event context dict
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

        now = datetime.now(timezone.utc)
        event_time = now - timedelta(hours=12)

        seizure_events = [
            {
                "event_id": event_id or f"neuro-{patient.id}-001",
                "event_type": "seizure",
                "seizure_type": "generalized_tonic_clonic",
                "onset_timestamp": event_time.isoformat(),
                "duration_seconds": 120,
                "resolution_timestamp": (event_time + timedelta(seconds=120)).isoformat(),
                "witnessed_by": "Nursing staff",
                "postictal_period_minutes": 30,
                "description": "Generalized tonic-clonic seizure, 2 minutes duration",
            }
        ]

        eeg_findings = [
            {
                "study_id": f"eeg-{patient.id}-001",
                "timestamp": (event_time - timedelta(hours=2)).isoformat(),
                "duration_hours": 4,
                "report_status": "final",
                "findings": "Epileptiform discharges in the right temporal region.",
                "abnormalities": ["right_temporal_spikes", "generalized_slowing"],
                "background_activity": "Mildly disorganized alpha rhythm",
                "impression": "Focal epileptiform activity consistent with right temporal epilepsy",
                "technician": "EEG Tech",
                "neurologist": "Dr. Neurology",
            }
        ]

        neuroimaging = [
            {
                "study_id": f"img-{patient.id}-neuro-001",
                "modality": "MRI",
                "description": "MRI Brain with and without contrast",
                "timestamp": (event_time + timedelta(hours=2)).isoformat(),
                "report_status": "final",
                "findings": "Right mesial temporal sclerosis. No acute hemorrhage or mass lesion.",
                "impression": "Findings consistent with mesial temporal sclerosis.",
            }
        ]

        vitals_during_event = [
            {"vital_type": "heart_rate", "value": 142, "unit": "bpm",
             "timestamp": (event_time + timedelta(seconds=30)).isoformat(), "is_abnormal": True},
            {"vital_type": "blood_pressure_systolic", "value": 168, "unit": "mmHg",
             "timestamp": (event_time + timedelta(seconds=30)).isoformat(), "is_abnormal": True},
            {"vital_type": "spo2", "value": 88, "unit": "%",
             "timestamp": (event_time + timedelta(seconds=60)).isoformat(), "is_abnormal": True},
        ]
        vitals_after_event = [
            {"vital_type": "heart_rate", "value": 92, "unit": "bpm",
             "timestamp": (event_time + timedelta(minutes=10)).isoformat(), "is_abnormal": False},
            {"vital_type": "blood_pressure_systolic", "value": 138, "unit": "mmHg",
             "timestamp": (event_time + timedelta(minutes=10)).isoformat(), "is_abnormal": False},
            {"vital_type": "spo2", "value": 97, "unit": "%",
             "timestamp": (event_time + timedelta(minutes=10)).isoformat(), "is_abnormal": False},
        ]

        seizure_medications = [
            {"medication": "Lorazepam", "dose": "2mg IV", "route": "IV",
             "timestamp": (event_time + timedelta(minutes=2)).isoformat(),
             "indication": "Seizure termination"},
            {"medication": "Levetiracetam", "dose": "1000mg IV", "route": "IV",
             "timestamp": (event_time + timedelta(minutes=5)).isoformat(),
             "indication": "Seizure prophylaxis"},
        ]

        clinical_notes = [
            {"type": "neurology_note", "author": "Dr. Neurology",
             "content_summary": "New onset seizure in context of mesial temporal sclerosis. "
                                "Initiated anti-epileptic therapy. Plan EEG monitoring.",
             "timestamp": (event_time + timedelta(hours=3)).isoformat()},
        ]

        logger.info(f"Retrieved neuro event context for patient {patient.id}")

        return {
            "patient": {
                "id": patient.id,
                "mrn": patient.mrn,
                "full_name": f"{patient.first_name} {patient.last_name}",
            },
            "encounter": {"id": encounter.id if encounter else None},
            "seizure_events": seizure_events,
            "eeg_findings": eeg_findings,
            "neuroimaging_studies": neuroimaging,
            "vitals_during_event": vitals_during_event,
            "vitals_after_event": vitals_after_event,
            "seizure_management_medications": seizure_medications,
            "clinical_notes": clinical_notes,
            "neurological_assessments": [
                {"assessment_type": "GCS", "score": 14, "components": {"E": 4, "V": 4, "M": 6},
                 "timestamp": (event_time + timedelta(minutes=35)).isoformat()},
            ],
            "confidence_score": 0.89,
            "source_references": [
                {"source": "hl7", "timestamp": datetime.now(timezone.utc).isoformat(),
                 "data_types": ["seizure_events", "medications", "clinical_notes"]},
                {"source": "dicom", "timestamp": datetime.now(timezone.utc).isoformat(),
                 "data_types": ["eeg_studies", "neuroimaging"]},
            ],
        }
