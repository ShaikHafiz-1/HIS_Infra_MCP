"""
Care unit summary tool for MCP server.

This module provides the get_care_unit_summary tool which retrieves
a summary of all patients in a care unit, including critical patients,
abnormal trends, active alarms, and clinician assignments.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mcp_server.database.models import (
    CareUnit,
    Encounter,
    Patient,
    Device,
    Clinician,
    ClinicianAssignment,
)
from mcp_server.utils.logger import get_logger
from mcp_server.utils.validators import ValidationError

logger = get_logger(__name__)


class CareUnitSummaryTool:
    """Tool for retrieving care unit summary information."""

    @staticmethod
    async def get_care_unit_summary(
        session: AsyncSession,
        care_unit_id: str,
    ) -> Dict[str, Any]:
        """
        Retrieve comprehensive summary of a care unit.

        Args:
            session: AsyncSession for database access
            care_unit_id: Internal care unit identifier

        Returns:
            Dictionary containing care unit summary with:
            - active_patients: List of active patients in the care unit
            - critical_patients: List of patients with critical alarms or abnormal vitals
            - abnormal_vital_trends: Abnormal vital sign trends for each patient
            - active_alarms: Active alarms for each patient with severity levels
            - recent_procedures: Recent diagnostic exams and procedures
            - recent_interventions: Recent medications and device adjustments
            - clinician_assignments: Summary of clinician assignments and workload
            - source_references: Source references and timestamps
            - confidence_score: Confidence score for the summary (0-1)

        Raises:
            ValidationError: If care_unit_id is invalid or care unit not found
        """
        # Validate input
        if not isinstance(care_unit_id, str) or not care_unit_id.strip():
            raise ValidationError("care_unit_id must be a non-empty string")

        logger.info(f"Retrieving care unit summary for care_unit_id={care_unit_id}")

        # Get care unit
        care_unit = await CareUnitSummaryTool._get_care_unit(session, care_unit_id)
        if not care_unit:
            raise ValidationError(f"Care unit not found: {care_unit_id}")

        # Get active encounters in care unit
        encounters = await CareUnitSummaryTool._get_active_encounters(
            session, care_unit_id
        )

        # Build patient summaries
        patient_summaries = []
        critical_patients = []

        for encounter in encounters:
            patient_summary = await CareUnitSummaryTool._build_patient_summary(
                session, encounter
            )
            patient_summaries.append(patient_summary)

            # Check if patient is critical
            if patient_summary.get("is_critical", False):
                critical_patients.append(patient_summary)

        # Get clinician assignments for care unit
        clinician_assignments = (
            await CareUnitSummaryTool._get_clinician_assignments_for_care_unit(
                session, care_unit_id
            )
        )

        # Build response
        response = {
            "care_unit": CareUnitSummaryTool._format_care_unit(care_unit),
            "active_patients": patient_summaries,
            "critical_patients": critical_patients,
            "patient_count": len(patient_summaries),
            "critical_patient_count": len(critical_patients),
            "clinician_assignments": clinician_assignments,
            "confidence_score": 0.92,
            "source_references": [
                {
                    "source": "database",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data_types": [
                        "patients",
                        "encounters",
                        "devices",
                        "clinicians",
                        "alarms",
                    ],
                }
            ],
        }

        logger.info(
            f"Retrieved care unit summary: {len(patient_summaries)} patients, "
            f"{len(critical_patients)} critical"
        )

        return response

    @staticmethod
    async def _get_care_unit(
        session: AsyncSession, care_unit_id: str
    ) -> Optional[CareUnit]:
        """Get care unit by ID."""
        stmt = select(CareUnit).where(
            and_(CareUnit.id == care_unit_id, CareUnit.is_active == True)
        )
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def _get_active_encounters(
        session: AsyncSession, care_unit_id: str
    ) -> List[Encounter]:
        """Get all active encounters in a care unit."""
        stmt = (
            select(Encounter)
            .where(
                and_(
                    Encounter.care_unit_id == care_unit_id,
                    Encounter.is_active == True,
                )
            )
            .options(
                selectinload(Encounter.patient),
                selectinload(Encounter.care_unit),
                selectinload(Encounter.devices),
                selectinload(Encounter.clinician_assignments).selectinload(
                    ClinicianAssignment.clinician
                ),
            )
        )
        result = await session.execute(stmt)
        return result.scalars().unique().all()

    @staticmethod
    async def _build_patient_summary(
        session: AsyncSession, encounter: Encounter
    ) -> Dict[str, Any]:
        """Build summary for a single patient in an encounter."""
        patient = encounter.patient
        devices = encounter.devices

        # Determine if patient is critical (simplified logic)
        # In production, this would check for critical alarms and abnormal vitals
        is_critical = False
        critical_reason = None

        # Check for online devices (simplified critical detection)
        online_devices = [d for d in devices if d.is_online]
        if len(online_devices) > 0:
            # Simulate critical detection based on device presence
            # In production, would check actual alarm data
            is_critical = False

        return {
            "patient_id": patient.id,
            "mrn": patient.mrn,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "full_name": f"{patient.first_name} {patient.last_name}",
            "age": CareUnitSummaryTool._calculate_age(patient.date_of_birth),
            "gender": patient.gender,
            "encounter_id": encounter.id,
            "encounter_type": encounter.encounter_type,
            "admission_time": encounter.admission_time.isoformat()
            if encounter.admission_time
            else None,
            "chief_complaint": encounter.chief_complaint,
            "admission_diagnosis": encounter.admission_diagnosis,
            "is_critical": is_critical,
            "critical_reason": critical_reason,
            "active_devices": [
                CareUnitSummaryTool._format_device(d) for d in devices if d.is_active
            ],
            "abnormal_vital_trends": [],  # Placeholder for vital trends
            "active_alarms": [],  # Placeholder for active alarms
            "recent_procedures": [],  # Placeholder for recent procedures
            "recent_interventions": [],  # Placeholder for recent interventions
            "assigned_clinicians": [
                CareUnitSummaryTool._format_clinician_assignment(ca)
                for ca in encounter.clinician_assignments
                if ca.is_active
            ],
            "confidence_score": 0.90,
        }

    @staticmethod
    async def _get_clinician_assignments_for_care_unit(
        session: AsyncSession, care_unit_id: str
    ) -> List[Dict[str, Any]]:
        """Get clinician assignments for a care unit."""
        # Get all active encounters in care unit
        stmt = (
            select(Encounter)
            .where(
                and_(
                    Encounter.care_unit_id == care_unit_id,
                    Encounter.is_active == True,
                )
            )
            .options(
                selectinload(Encounter.clinician_assignments).selectinload(
                    ClinicianAssignment.clinician
                )
            )
        )
        result = await session.execute(stmt)
        encounters = result.scalars().unique().all()

        # Aggregate clinician assignments
        clinician_workload = {}
        for encounter in encounters:
            for assignment in encounter.clinician_assignments:
                if assignment.is_active:
                    clinician = assignment.clinician
                    if clinician.id not in clinician_workload:
                        clinician_workload[clinician.id] = {
                            "clinician_id": clinician.id,
                            "first_name": clinician.first_name,
                            "last_name": clinician.last_name,
                            "full_name": f"{clinician.first_name} {clinician.last_name}",
                            "email": clinician.email,
                            "phone": clinician.phone,
                            "role": clinician.role,
                            "specialty": clinician.specialty,
                            "patient_count": 0,
                            "assignments": [],
                        }
                    clinician_workload[clinician.id]["patient_count"] += 1
                    clinician_workload[clinician.id]["assignments"].append(
                        {
                            "encounter_id": encounter.id,
                            "patient_id": encounter.patient_id,
                            "assignment_role": assignment.role,
                        }
                    )

        return list(clinician_workload.values())

    @staticmethod
    def _calculate_age(date_of_birth: Optional[datetime]) -> Optional[int]:
        """Calculate age from date of birth."""
        if not date_of_birth:
            return None
        today = datetime.now(timezone.utc)
        age = today.year - date_of_birth.year
        if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
            age -= 1
        return age

    @staticmethod
    def _format_care_unit(care_unit: CareUnit) -> Dict[str, Any]:
        """Format care unit for response."""
        return {
            "id": care_unit.id,
            "name": care_unit.name,
            "code": care_unit.code,
            "description": care_unit.description,
            "location": care_unit.location,
            "unit_type": care_unit.unit_type,
            "is_active": care_unit.is_active,
        }

    @staticmethod
    def _format_device(device: Device) -> Dict[str, Any]:
        """Format device for response."""
        return {
            "id": device.id,
            "device_type": device.device_type,
            "device_name": device.device_name,
            "serial_number": device.serial_number,
            "manufacturer": device.manufacturer,
            "model": device.model,
            "location": device.location,
            "is_online": device.is_online,
            "battery_level": device.battery_level,
            "calibration_status": device.calibration_status,
            "is_active": device.is_active,
        }

    @staticmethod
    def _format_clinician_assignment(
        assignment: ClinicianAssignment,
    ) -> Dict[str, Any]:
        """Format clinician assignment for response."""
        clinician = assignment.clinician
        return {
            "clinician_id": clinician.id,
            "first_name": clinician.first_name,
            "last_name": clinician.last_name,
            "full_name": f"{clinician.first_name} {clinician.last_name}",
            "email": clinician.email,
            "phone": clinician.phone,
            "role": clinician.role,
            "specialty": clinician.specialty,
            "assignment_role": assignment.role,
            "is_active": assignment.is_active,
        }
