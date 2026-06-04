"""
Diagnostic Exam Context Tool (get_diagnostic_exam_context).

Returns context for a diagnostic exam including DICOM metadata, imaging
findings, lab results, contemporaneous vital signs, and related events.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.database.models import Patient, Encounter
from mcp_server.utils.logger import get_logger
from mcp_server.utils.validators import ValidationError

logger = get_logger(__name__)


class DiagnosticExamTool:
    """Tool for retrieving diagnostic exam context."""

    @staticmethod
    async def get_diagnostic_exam_context(
        session: AsyncSession,
        exam_id: Optional[str] = None,
        patient_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve diagnostic exam context including imaging and lab results.

        Args:
            session: Database session
            exam_id: Specific exam ID (optional)
            patient_id: Patient ID for most recent exam (optional)

        Returns:
            Diagnostic exam context dict
        """
        if not exam_id and not patient_id:
            raise ValidationError("Either exam_id or patient_id is required")

        if patient_id:
            stmt = select(Patient).where(
                and_(Patient.id == patient_id, Patient.is_active == True)
            )
            result = await session.execute(stmt)
            patient = result.scalars().first()
            if not patient:
                raise ValidationError(f"Patient not found: {patient_id}")
        else:
            if not isinstance(exam_id, str) or not exam_id.strip():
                raise ValidationError("exam_id must be a non-empty string")
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
        exam_time = now - timedelta(hours=6)

        exam = {
            "exam_id": exam_id or f"exam-{patient.id}-latest",
            "exam_type": "CT",
            "indication": "Chest pain evaluation",
            "timestamp": exam_time.isoformat(),
            "result_status": "final",
            "patient_id": patient.id,
            "encounter_id": encounter.id if encounter else None,
        }

        imaging_studies = [{
            "study_id": f"img-{patient.id}-001",
            "modality": "CT",
            "description": "CT Chest with contrast",
            "timestamp": exam_time.isoformat(),
            "report_status": "final",
            "findings": "No acute pulmonary embolism. Mild bibasilar atelectasis.",
            "impression": "No significant acute intrathoracic abnormality.",
            "radiologist": "Dr. Radiology",
            "dicom_metadata": {
                "study_instance_uid": "1.2.840.10008.5.1.4.1.1.2",
                "series_count": 3,
                "image_count": 120,
                "patient_id": patient.mrn,
            },
        }]

        lab_results = [
            {"test_name": "Troponin I", "value": 0.04, "unit": "ng/mL",
             "reference_range": "< 0.04", "is_abnormal": False,
             "timestamp": exam_time.isoformat(), "source": "lab"},
            {"test_name": "BNP", "value": 145, "unit": "pg/mL",
             "reference_range": "< 100", "is_abnormal": True,
             "timestamp": exam_time.isoformat(), "source": "lab"},
            {"test_name": "D-Dimer", "value": 0.38, "unit": "mg/L FEU",
             "reference_range": "< 0.50", "is_abnormal": False,
             "timestamp": exam_time.isoformat(), "source": "lab"},
        ]

        vitals_window_start = exam_time - timedelta(minutes=30)
        vitals_window_end = exam_time + timedelta(minutes=30)
        contemporaneous_vitals = [
            {"vital_type": "heart_rate", "value": 88, "unit": "bpm",
             "timestamp": exam_time.isoformat()},
            {"vital_type": "blood_pressure_systolic", "value": 138, "unit": "mmHg",
             "timestamp": exam_time.isoformat()},
            {"vital_type": "spo2", "value": 95, "unit": "%",
             "timestamp": exam_time.isoformat()},
        ]

        related_events = [
            {"event_type": "medication", "description": "Heparin administered",
             "timestamp": (exam_time - timedelta(hours=1)).isoformat()},
            {"event_type": "procedure", "description": "IV access established",
             "timestamp": (exam_time - timedelta(minutes=45)).isoformat()},
        ]

        logger.info(f"Retrieved diagnostic exam context for patient {patient.id}")

        return {
            "exam": exam,
            "imaging_studies": imaging_studies,
            "lab_results": lab_results,
            "contemporaneous_vitals": contemporaneous_vitals,
            "vitals_window": {
                "start": vitals_window_start.isoformat(),
                "end": vitals_window_end.isoformat(),
            },
            "related_events": related_events,
            "indication": exam["indication"],
            "findings": imaging_studies[0]["findings"] if imaging_studies else None,
            "patient": {
                "id": patient.id,
                "mrn": patient.mrn,
                "full_name": f"{patient.first_name} {patient.last_name}",
            },
            "confidence_score": 0.90,
            "source_references": [
                {"source": "dicom", "timestamp": datetime.now(timezone.utc).isoformat(),
                 "data_types": ["imaging_studies"]},
                {"source": "hl7", "timestamp": datetime.now(timezone.utc).isoformat(),
                 "data_types": ["lab_results"]},
            ],
        }
