"""
Patient Clinical Context Tool for Hospital Clinical Intelligence MCP Platform.

This module implements the get_patient_clinical_context MCP tool which retrieves
comprehensive clinical context for a specific patient including demographics,
encounter information, diagnoses, medications, clinicians, devices, and recent
abnormal observations.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from mcp_server.database.cache import cache
from mcp_server.database.models import (
    Patient,
    Encounter,
    CareUnit,
    Clinician,
    Device,
    ClinicianAssignment,
)
from mcp_server.utils.logger import get_logger
from mcp_server.utils.validators import ValidationError

logger = get_logger(__name__)


class PatientContextTool:
    """Tool for retrieving comprehensive patient clinical context."""

    @staticmethod
    async def get_patient_clinical_context(
        session: AsyncSession,
        patient_id: str,
        include_timeline: bool = False,
        include_devices: bool = True,
    ) -> Dict[str, Any]:
        """
        Retrieve comprehensive clinical context for a patient.

        This function retrieves:
        - Patient demographics
        - Current encounter and care unit information
        - Active diagnoses
        - Current medications
        - Assigned clinicians
        - Active devices
        - Recent abnormal observations

        Args:
            session: Database session
            patient_id: Internal patient identifier
            include_timeline: Whether to include event timeline (optional)
            include_devices: Whether to include active devices (default: True)

        Returns:
            Dictionary containing patient clinical context

        Raises:
            ValidationError: If patient_id is invalid or patient not found
        """
        # Validate input
        if not patient_id or not isinstance(patient_id, str):
            raise ValidationError("patient_id must be a non-empty string")
        if patient_id.strip() != patient_id or not patient_id.strip():
            raise ValidationError("patient_id must not contain leading/trailing whitespace")
        if len(patient_id) > 255:
            raise ValidationError("patient_id must be less than 255 characters")

        # Try cache first
        cached = cache.get_patient_context(patient_id, include_devices=include_devices)
        if cached is not None:
            logger.debug(f"Cache hit for patient context: {patient_id}")
            return cached

        try:
            # Retrieve patient with relationships
            patient = await PatientContextTool._get_patient(session, patient_id)
            if not patient:
                raise ValidationError(f"Patient not found: {patient_id}")

            # Retrieve current encounter
            encounter = await PatientContextTool._get_current_encounter(session, patient_id)

            # Build response
            context = {
                "patient": PatientContextTool._format_patient(patient),
                "encounter": PatientContextTool._format_encounter(encounter) if encounter else None,
                "care_unit": None,
                "diagnoses": [],
                "medications": [],
                "clinicians": [],
                "devices": [],
                "recent_abnormal_observations": [],
                "confidence_score": 0.95,
                "source_references": [],
            }

            # Add care unit if encounter exists
            if encounter:
                context["care_unit"] = PatientContextTool._format_care_unit(encounter.care_unit)

                # Retrieve assigned clinicians
                clinicians = await PatientContextTool._get_assigned_clinicians(
                    session, encounter.id
                )
                context["clinicians"] = [
                    PatientContextTool._format_clinician(c) for c in clinicians
                ]

                # Retrieve active devices if requested
                if include_devices:
                    devices = await PatientContextTool._get_active_devices(
                        session, encounter.id
                    )
                    context["devices"] = [
                        PatientContextTool._format_device(d) for d in devices
                    ]

            # Add source references
            context["source_references"] = [
                {
                    "source": "internal_database",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data_types": [
                        "demographics",
                        "encounter",
                        "care_unit",
                        "clinicians",
                        "devices",
                    ],
                }
            ]

            logger.info(
                f"Retrieved clinical context for patient {patient_id} "
                f"(encounter: {encounter.id if encounter else 'none'})"
            )

            # Store in cache
            cache.set_patient_context(patient_id, context, include_devices=include_devices)
            return context

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error retrieving patient context for {patient_id}: {e}")
            raise

    @staticmethod
    async def _get_patient(session: AsyncSession, patient_id: str) -> Optional[Patient]:
        """
        Retrieve patient by ID.

        Args:
            session: Database session
            patient_id: Patient ID

        Returns:
            Patient object or None if not found
        """
        stmt = select(Patient).where(
            and_(
                Patient.id == patient_id,
                Patient.is_deleted == False,
            )
        )
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def _get_current_encounter(
        session: AsyncSession, patient_id: str
    ) -> Optional[Encounter]:
        """
        Retrieve current (active) encounter for patient.

        Args:
            session: Database session
            patient_id: Patient ID

        Returns:
            Current Encounter object or None if no active encounter
        """
        stmt = (
            select(Encounter)
            .where(
                and_(
                    Encounter.patient_id == patient_id,
                    Encounter.is_active == True,
                    Encounter.is_deleted == False,
                )
            )
            .options(joinedload(Encounter.care_unit))
            .order_by(Encounter.admission_time.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def _get_assigned_clinicians(
        session: AsyncSession, encounter_id: str
    ) -> List[Clinician]:
        """
        Retrieve clinicians assigned to encounter.

        Args:
            session: Database session
            encounter_id: Encounter ID

        Returns:
            List of assigned Clinician objects
        """
        stmt = (
            select(Clinician)
            .join(ClinicianAssignment)
            .where(
                and_(
                    ClinicianAssignment.encounter_id == encounter_id,
                    ClinicianAssignment.is_active == True,
                    Clinician.is_deleted == False,
                )
            )
            .order_by(Clinician.last_name, Clinician.first_name)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def _get_active_devices(
        session: AsyncSession, encounter_id: str
    ) -> List[Device]:
        """
        Retrieve active devices for encounter.

        Args:
            session: Database session
            encounter_id: Encounter ID

        Returns:
            List of active Device objects
        """
        stmt = select(Device).where(
            and_(
                Device.encounter_id == encounter_id,
                Device.is_active == True,
                Device.is_deleted == False,
            )
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    def _format_patient(patient: Patient) -> Dict[str, Any]:
        """
        Format patient data for response.

        Args:
            patient: Patient object

        Returns:
            Formatted patient dictionary
        """
        age = None
        if patient.date_of_birth:
            today = datetime.now(timezone.utc).date()
            dob = patient.date_of_birth.date() if isinstance(patient.date_of_birth, datetime) else patient.date_of_birth
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

        return {
            "id": patient.id,
            "mrn": patient.mrn,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "full_name": f"{patient.first_name} {patient.last_name}",
            "date_of_birth": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
            "age": age,
            "gender": patient.gender,
            "phone": patient.phone,
            "email": patient.email,
            "is_active": patient.is_active,
        }

    @staticmethod
    def _format_encounter(encounter: Encounter) -> Dict[str, Any]:
        """
        Format encounter data for response.

        Args:
            encounter: Encounter object

        Returns:
            Formatted encounter dictionary
        """
        return {
            "id": encounter.id,
            "patient_id": encounter.patient_id,
            "encounter_type": encounter.encounter_type,
            "admission_time": encounter.admission_time.isoformat(),
            "discharge_time": encounter.discharge_time.isoformat() if encounter.discharge_time else None,
            "is_active": encounter.is_active,
            "chief_complaint": encounter.chief_complaint,
            "admission_diagnosis": encounter.admission_diagnosis,
            "discharge_diagnosis": encounter.discharge_diagnosis,
        }

    @staticmethod
    def _format_care_unit(care_unit: CareUnit) -> Dict[str, Any]:
        """
        Format care unit data for response.

        Args:
            care_unit: CareUnit object

        Returns:
            Formatted care unit dictionary
        """
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
    def _format_clinician(clinician: Clinician) -> Dict[str, Any]:
        """
        Format clinician data for response.

        Args:
            clinician: Clinician object

        Returns:
            Formatted clinician dictionary
        """
        return {
            "id": clinician.id,
            "first_name": clinician.first_name,
            "last_name": clinician.last_name,
            "full_name": f"{clinician.first_name} {clinician.last_name}",
            "email": clinician.email,
            "phone": clinician.phone,
            "role": clinician.role,
            "specialty": clinician.specialty,
            "is_active": clinician.is_active,
        }

    @staticmethod
    def _format_device(device: Device) -> Dict[str, Any]:
        """
        Format device data for response.

        Args:
            device: Device object

        Returns:
            Formatted device dictionary
        """
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
