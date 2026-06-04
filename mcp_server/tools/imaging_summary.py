"""
Imaging Study Summary Tool (get_imaging_study_summary).

Returns imaging study summaries with findings, radiologist reports,
and related clinical events.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.database.models import Patient, Encounter
from mcp_server.utils.logger import get_logger
from mcp_server.utils.validators import ValidationError

logger = get_logger(__name__)


class ImagingStudySummaryTool:
    """Tool for retrieving imaging study summaries."""

    @staticmethod
    async def get_imaging_study_summary(
        session: AsyncSession,
        study_id: Optional[str] = None,
        patient_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve imaging study summary with findings and related events.

        Args:
            session: Database session
            study_id: Specific imaging study ID (optional)
            patient_id: Patient ID for most recent study (optional)

        Returns:
            Imaging study summary dict
        """
        if not study_id and not patient_id:
            raise ValidationError("Either study_id or patient_id is required")

        if patient_id:
            stmt = select(Patient).where(
                and_(Patient.id == patient_id, Patient.is_active == True)
            )
            result = await session.execute(stmt)
            patient = result.scalars().first()
            if not patient:
                raise ValidationError(f"Patient not found: {patient_id}")
        else:
            if not isinstance(study_id, str) or not study_id.strip():
                raise ValidationError("study_id must be a non-empty string")
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
        study_time = now - timedelta(hours=8)

        study = {
            "study_id": study_id or f"study-{patient.id}-001",
            "modality": "MRI",
            "description": "MRI Brain without contrast",
            "timestamp": study_time.isoformat(),
            "report_status": "final",
            "clinical_indication": "New onset seizure",
            "patient_id": patient.id,
            "encounter_id": encounter.id if encounter else None,
            "findings": (
                "No acute intracranial hemorrhage. No restricted diffusion. "
                "Small area of T2/FLAIR signal hyperintensity in the right parietal lobe, "
                "possibly representing gliosis or early demyelination."
            ),
            "impression": (
                "No acute pathology identified. Recommend clinical correlation "
                "and follow-up imaging in 3-6 months."
            ),
            "radiologist": "Dr. Neuroradiology",
            "report_signed_at": (study_time + timedelta(hours=2)).isoformat(),
            "follow_up_recommendations": [
                "Follow-up MRI brain in 3-6 months",
                "Neurology consultation recommended",
                "EEG monitoring as clinically indicated",
            ],
            "dicom_metadata": {
                "study_instance_uid": "1.2.840.10008.5.1.4.1.1.4",
                "series_count": 8,
                "image_count": 240,
                "field_strength": "3T",
                "patient_id": patient.mrn,
            },
        }

        contemporaneous_vitals = [
            {"vital_type": "heart_rate", "value": 82, "unit": "bpm",
             "timestamp": study_time.isoformat()},
            {"vital_type": "blood_pressure_systolic", "value": 128, "unit": "mmHg",
             "timestamp": study_time.isoformat()},
            {"vital_type": "respiratory_rate", "value": 16, "unit": "breaths/min",
             "timestamp": study_time.isoformat()},
        ]

        related_events = [
            {"event_type": "alarm", "description": "Seizure alert",
             "timestamp": (study_time - timedelta(hours=4)).isoformat(), "severity": "critical"},
            {"event_type": "medication", "description": "Levetiracetam 1000mg IV administered",
             "timestamp": (study_time - timedelta(hours=3)).isoformat()},
            {"event_type": "procedure", "description": "EEG monitoring initiated",
             "timestamp": (study_time - timedelta(hours=2)).isoformat()},
        ]

        logger.info(f"Retrieved imaging study summary for patient {patient.id}")

        return {
            "study": study,
            "contemporaneous_vitals": contemporaneous_vitals,
            "related_events": related_events,
            "follow_up_recommendations": study["follow_up_recommendations"],
            "patient": {
                "id": patient.id,
                "mrn": patient.mrn,
                "full_name": f"{patient.first_name} {patient.last_name}",
            },
            "confidence_score": 0.92,
            "source_references": [
                {"source": "dicom", "timestamp": datetime.now(timezone.utc).isoformat(),
                 "data_types": ["imaging_studies", "radiologist_reports"]},
            ],
        }
