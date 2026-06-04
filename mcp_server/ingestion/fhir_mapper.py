"""
FHIR Resource Mapper for normalizing FHIR resources to internal data structures.

This module implements mapping of FHIR resources to internal database models:
- Patient FHIR → Internal Patient
- Encounter FHIR → Internal Encounter
- Observation FHIR → Internal Observation
- DiagnosticReport FHIR → Internal DiagnosticReport
- ImagingStudy FHIR → Internal ImagingStudy
- MedicationRequest FHIR → Internal Medication
- Procedure FHIR → Internal Procedure
- CarePlan FHIR → Internal CarePlan

Maintains FHIR resource ID mappings for data consolidation.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.utils.logger import get_logger
from mcp_server.utils.validators import ValidationError

logger = get_logger(__name__)


class FHIRMapper:
    """Maps FHIR resources to internal data structures."""

    @staticmethod
    async def map_patient(
        session: AsyncSession,
        fhir_patient: Dict[str, Any],
        source_system: str = "fhir",
    ) -> Dict[str, Any]:
        """
        Map FHIR Patient resource to internal patient structure.

        Args:
            session: Database session
            fhir_patient: FHIR Patient resource
            source_system: Source system identifier (default: "fhir")

        Returns:
            Dictionary with internal patient data and FHIR mapping

        Raises:
            ValidationError: If patient data is invalid
        """
        try:
            # Extract FHIR patient ID
            fhir_id = fhir_patient.get("id")
            if not fhir_id:
                raise ValidationError("FHIR Patient missing ID")

            # Extract identifiers (MRN, etc.)
            identifiers = fhir_patient.get("identifier", [])
            mrn = None
            for identifier in identifiers:
                if identifier.get("type", {}).get("coding", [{}])[0].get("code") == "MR":
                    mrn = identifier.get("value")
                    break

            # Extract name
            names = fhir_patient.get("name", [])
            first_name = ""
            last_name = ""
            if names:
                name = names[0]
                given_names = name.get("given", [])
                first_name = given_names[0] if given_names else ""
                last_name = name.get("family", "")

            # Extract date of birth
            dob_str = fhir_patient.get("birthDate")
            dob = None
            if dob_str:
                try:
                    dob = datetime.fromisoformat(dob_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    logger.warning(f"Invalid date of birth format: {dob_str}")

            # Extract gender
            gender = fhir_patient.get("gender")

            # Extract contact information
            telecom = fhir_patient.get("telecom", [])
            phone = None
            email = None
            for contact in telecom:
                if contact.get("system") == "phone":
                    phone = contact.get("value")
                elif contact.get("system") == "email":
                    email = contact.get("value")

            # Extract address
            addresses = fhir_patient.get("address", [])
            address = None
            if addresses:
                addr = addresses[0]
                address_parts = [
                    addr.get("line", [{}])[0] if addr.get("line") else "",
                    addr.get("city", ""),
                    addr.get("state", ""),
                    addr.get("postalCode", ""),
                ]
                address = ", ".join(filter(None, address_parts))

            # Build internal patient structure
            internal_patient = {
                "fhir_id": fhir_id,
                "source_system": source_system,
                "first_name": first_name,
                "last_name": last_name,
                "date_of_birth": dob,
                "gender": gender,
                "mrn": mrn,
                "phone": phone,
                "email": email,
                "address": address,
                "is_active": fhir_patient.get("active", True),
                "fhir_resource": fhir_patient,  # Store original FHIR resource
            }

            logger.info(
                f"Mapped FHIR Patient {fhir_id} to internal structure "
                f"(MRN: {mrn}, Name: {first_name} {last_name})"
            )

            return internal_patient

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error mapping FHIR Patient: {e}")
            raise ValidationError(f"Failed to map FHIR Patient: {e}")

    @staticmethod
    async def map_encounter(
        fhir_encounter: Dict[str, Any],
        internal_patient_id: str,
        source_system: str = "fhir",
    ) -> Dict[str, Any]:
        """
        Map FHIR Encounter resource to internal encounter structure.

        Args:
            fhir_encounter: FHIR Encounter resource
            internal_patient_id: Internal patient ID
            source_system: Source system identifier

        Returns:
            Dictionary with internal encounter data
        """
        try:
            fhir_id = fhir_encounter.get("id")
            if not fhir_id:
                raise ValidationError("FHIR Encounter missing ID")

            # Extract encounter type
            encounter_type = "unknown"
            encounter_class = fhir_encounter.get("class", {})
            if isinstance(encounter_class, dict):
                encounter_type = encounter_class.get("code", "unknown")

            # Extract admission time
            period = fhir_encounter.get("period", {})
            admission_time_str = period.get("start")
            admission_time = None
            if admission_time_str:
                try:
                    admission_time = datetime.fromisoformat(
                        admission_time_str.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    logger.warning(f"Invalid admission time format: {admission_time_str}")

            # Extract discharge time
            discharge_time_str = period.get("end")
            discharge_time = None
            if discharge_time_str:
                try:
                    discharge_time = datetime.fromisoformat(
                        discharge_time_str.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    logger.warning(f"Invalid discharge time format: {discharge_time_str}")

            # Extract chief complaint and diagnoses
            chief_complaint = None
            admission_diagnosis = None
            reason_codes = fhir_encounter.get("reasonCode", [])
            if reason_codes:
                chief_complaint = reason_codes[0].get("text", "")

            # Extract care unit (location)
            care_unit_id = None
            locations = fhir_encounter.get("location", [])
            if locations:
                location_ref = locations[0].get("location", {})
                if isinstance(location_ref, dict):
                    care_unit_id = location_ref.get("reference", "").split("/")[-1]

            # Build internal encounter structure
            internal_encounter = {
                "fhir_id": fhir_id,
                "source_system": source_system,
                "patient_id": internal_patient_id,
                "encounter_type": encounter_type,
                "admission_time": admission_time,
                "discharge_time": discharge_time,
                "is_active": discharge_time is None,
                "chief_complaint": chief_complaint,
                "admission_diagnosis": admission_diagnosis,
                "care_unit_id": care_unit_id,
                "fhir_resource": fhir_encounter,
            }

            logger.info(
                f"Mapped FHIR Encounter {fhir_id} to internal structure "
                f"(Type: {encounter_type}, Patient: {internal_patient_id})"
            )

            return internal_encounter

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error mapping FHIR Encounter: {e}")
            raise ValidationError(f"Failed to map FHIR Encounter: {e}")

    @staticmethod
    async def map_observation(
        fhir_observation: Dict[str, Any],
        internal_patient_id: str,
        internal_encounter_id: Optional[str] = None,
        source_system: str = "fhir",
    ) -> Dict[str, Any]:
        """
        Map FHIR Observation resource to internal observation structure.

        Args:
            fhir_observation: FHIR Observation resource
            internal_patient_id: Internal patient ID
            internal_encounter_id: Internal encounter ID (optional)
            source_system: Source system identifier

        Returns:
            Dictionary with internal observation data
        """
        try:
            fhir_id = fhir_observation.get("id")
            if not fhir_id:
                raise ValidationError("FHIR Observation missing ID")

            # Extract observation code
            code_coding = fhir_observation.get("code", {}).get("coding", [{}])[0]
            observation_code = code_coding.get("code", "unknown")
            observation_display = code_coding.get("display", observation_code)

            # Extract value
            value = None
            value_quantity = fhir_observation.get("valueQuantity")
            if value_quantity:
                value = value_quantity.get("value")

            # Extract unit
            unit = None
            if value_quantity:
                unit = value_quantity.get("unit")

            # Extract effective time
            effective_time_str = fhir_observation.get("effectiveDateTime")
            effective_time = None
            if effective_time_str:
                try:
                    effective_time = datetime.fromisoformat(
                        effective_time_str.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    logger.warning(f"Invalid effective time format: {effective_time_str}")

            # Extract status
            status = fhir_observation.get("status", "unknown")

            # Extract reference range
            reference_range = None
            ranges = fhir_observation.get("referenceRange", [])
            if ranges:
                range_obj = ranges[0]
                low = range_obj.get("low", {}).get("value")
                high = range_obj.get("high", {}).get("value")
                if low is not None and high is not None:
                    reference_range = f"{low}-{high}"

            # Build internal observation structure
            internal_observation = {
                "fhir_id": fhir_id,
                "source_system": source_system,
                "patient_id": internal_patient_id,
                "encounter_id": internal_encounter_id,
                "observation_code": observation_code,
                "observation_display": observation_display,
                "value": value,
                "unit": unit,
                "effective_time": effective_time,
                "status": status,
                "reference_range": reference_range,
                "fhir_resource": fhir_observation,
            }

            logger.info(
                f"Mapped FHIR Observation {fhir_id} to internal structure "
                f"(Code: {observation_code}, Value: {value} {unit})"
            )

            return internal_observation

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error mapping FHIR Observation: {e}")
            raise ValidationError(f"Failed to map FHIR Observation: {e}")

    @staticmethod
    async def map_diagnostic_report(
        fhir_report: Dict[str, Any],
        internal_patient_id: str,
        internal_encounter_id: Optional[str] = None,
        source_system: str = "fhir",
    ) -> Dict[str, Any]:
        """
        Map FHIR DiagnosticReport resource to internal structure.

        Args:
            fhir_report: FHIR DiagnosticReport resource
            internal_patient_id: Internal patient ID
            internal_encounter_id: Internal encounter ID (optional)
            source_system: Source system identifier

        Returns:
            Dictionary with internal diagnostic report data
        """
        try:
            fhir_id = fhir_report.get("id")
            if not fhir_id:
                raise ValidationError("FHIR DiagnosticReport missing ID")

            # Extract report code
            code_coding = fhir_report.get("code", {}).get("coding", [{}])[0]
            report_code = code_coding.get("code", "unknown")
            report_display = code_coding.get("display", report_code)

            # Extract effective time
            effective_time_str = fhir_report.get("effectiveDateTime")
            effective_time = None
            if effective_time_str:
                try:
                    effective_time = datetime.fromisoformat(
                        effective_time_str.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    logger.warning(f"Invalid effective time format: {effective_time_str}")

            # Extract conclusion
            conclusion = fhir_report.get("conclusion")

            # Extract status
            status = fhir_report.get("status", "unknown")

            # Extract result references
            results = fhir_report.get("result", [])
            result_ids = [r.get("reference", "").split("/")[-1] for r in results]

            # Build internal diagnostic report structure
            internal_report = {
                "fhir_id": fhir_id,
                "source_system": source_system,
                "patient_id": internal_patient_id,
                "encounter_id": internal_encounter_id,
                "report_code": report_code,
                "report_display": report_display,
                "effective_time": effective_time,
                "conclusion": conclusion,
                "status": status,
                "result_ids": result_ids,
                "fhir_resource": fhir_report,
            }

            logger.info(
                f"Mapped FHIR DiagnosticReport {fhir_id} to internal structure "
                f"(Code: {report_code}, Status: {status})"
            )

            return internal_report

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error mapping FHIR DiagnosticReport: {e}")
            raise ValidationError(f"Failed to map FHIR DiagnosticReport: {e}")

    @staticmethod
    async def map_imaging_study(
        fhir_study: Dict[str, Any],
        internal_patient_id: str,
        internal_encounter_id: Optional[str] = None,
        source_system: str = "fhir",
    ) -> Dict[str, Any]:
        """
        Map FHIR ImagingStudy resource to internal structure.

        Args:
            fhir_study: FHIR ImagingStudy resource
            internal_patient_id: Internal patient ID
            internal_encounter_id: Internal encounter ID (optional)
            source_system: Source system identifier

        Returns:
            Dictionary with internal imaging study data
        """
        try:
            fhir_id = fhir_study.get("id")
            if not fhir_id:
                raise ValidationError("FHIR ImagingStudy missing ID")

            # Extract study date
            study_date_str = fhir_study.get("started")
            study_date = None
            if study_date_str:
                try:
                    study_date = datetime.fromisoformat(
                        study_date_str.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    logger.warning(f"Invalid study date format: {study_date_str}")

            # Extract modality
            modality = "unknown"
            series = fhir_study.get("series", [])
            if series:
                modality_coding = series[0].get("modality", {}).get("coding", [{}])[0]
                modality = modality_coding.get("code", "unknown")

            # Extract description
            description = fhir_study.get("description")

            # Extract status
            status = fhir_study.get("status", "unknown")

            # Build internal imaging study structure
            internal_study = {
                "fhir_id": fhir_id,
                "source_system": source_system,
                "patient_id": internal_patient_id,
                "encounter_id": internal_encounter_id,
                "study_date": study_date,
                "modality": modality,
                "description": description,
                "status": status,
                "series_count": len(series),
                "fhir_resource": fhir_study,
            }

            logger.info(
                f"Mapped FHIR ImagingStudy {fhir_id} to internal structure "
                f"(Modality: {modality}, Date: {study_date})"
            )

            return internal_study

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error mapping FHIR ImagingStudy: {e}")
            raise ValidationError(f"Failed to map FHIR ImagingStudy: {e}")

    @staticmethod
    async def map_medication_request(
        fhir_request: Dict[str, Any],
        internal_patient_id: str,
        internal_encounter_id: Optional[str] = None,
        source_system: str = "fhir",
    ) -> Dict[str, Any]:
        """
        Map FHIR MedicationRequest resource to internal structure.

        Args:
            fhir_request: FHIR MedicationRequest resource
            internal_patient_id: Internal patient ID
            internal_encounter_id: Internal encounter ID (optional)
            source_system: Source system identifier

        Returns:
            Dictionary with internal medication request data
        """
        try:
            fhir_id = fhir_request.get("id")
            if not fhir_id:
                raise ValidationError("FHIR MedicationRequest missing ID")

            # Extract medication
            medication_ref = fhir_request.get("medicationReference", {})
            medication_id = medication_ref.get("reference", "").split("/")[-1]
            medication_display = medication_ref.get("display")

            # Extract status
            status = fhir_request.get("status", "unknown")

            # Extract intent
            intent = fhir_request.get("intent", "unknown")

            # Extract authored date
            authored_str = fhir_request.get("authoredOn")
            authored_date = None
            if authored_str:
                try:
                    authored_date = datetime.fromisoformat(
                        authored_str.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    logger.warning(f"Invalid authored date format: {authored_str}")

            # Extract dosage
            dosage_text = None
            dosages = fhir_request.get("dosageInstruction", [])
            if dosages:
                dosage_text = dosages[0].get("text")

            # Extract reason
            reason_codes = fhir_request.get("reasonCode", [])
            reason = None
            if reason_codes:
                reason = reason_codes[0].get("text")

            # Build internal medication request structure
            internal_request = {
                "fhir_id": fhir_id,
                "source_system": source_system,
                "patient_id": internal_patient_id,
                "encounter_id": internal_encounter_id,
                "medication_id": medication_id,
                "medication_display": medication_display,
                "status": status,
                "intent": intent,
                "authored_date": authored_date,
                "dosage": dosage_text,
                "reason": reason,
                "fhir_resource": fhir_request,
            }

            logger.info(
                f"Mapped FHIR MedicationRequest {fhir_id} to internal structure "
                f"(Medication: {medication_display}, Status: {status})"
            )

            return internal_request

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error mapping FHIR MedicationRequest: {e}")
            raise ValidationError(f"Failed to map FHIR MedicationRequest: {e}")

    @staticmethod
    async def map_procedure(
        fhir_procedure: Dict[str, Any],
        internal_patient_id: str,
        internal_encounter_id: Optional[str] = None,
        source_system: str = "fhir",
    ) -> Dict[str, Any]:
        """
        Map FHIR Procedure resource to internal structure.

        Args:
            fhir_procedure: FHIR Procedure resource
            internal_patient_id: Internal patient ID
            internal_encounter_id: Internal encounter ID (optional)
            source_system: Source system identifier

        Returns:
            Dictionary with internal procedure data
        """
        try:
            fhir_id = fhir_procedure.get("id")
            if not fhir_id:
                raise ValidationError("FHIR Procedure missing ID")

            # Extract procedure code
            code_coding = fhir_procedure.get("code", {}).get("coding", [{}])[0]
            procedure_code = code_coding.get("code", "unknown")
            procedure_display = code_coding.get("display", procedure_code)

            # Extract performed date
            performed_str = fhir_procedure.get("performedDateTime")
            performed_date = None
            if performed_str:
                try:
                    performed_date = datetime.fromisoformat(
                        performed_str.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    logger.warning(f"Invalid performed date format: {performed_str}")

            # Extract status
            status = fhir_procedure.get("status", "unknown")

            # Extract outcome
            outcome = fhir_procedure.get("outcome", {}).get("text")

            # Build internal procedure structure
            internal_procedure = {
                "fhir_id": fhir_id,
                "source_system": source_system,
                "patient_id": internal_patient_id,
                "encounter_id": internal_encounter_id,
                "procedure_code": procedure_code,
                "procedure_display": procedure_display,
                "performed_date": performed_date,
                "status": status,
                "outcome": outcome,
                "fhir_resource": fhir_procedure,
            }

            logger.info(
                f"Mapped FHIR Procedure {fhir_id} to internal structure "
                f"(Code: {procedure_code}, Status: {status})"
            )

            return internal_procedure

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error mapping FHIR Procedure: {e}")
            raise ValidationError(f"Failed to map FHIR Procedure: {e}")

    @staticmethod
    async def map_care_plan(
        fhir_plan: Dict[str, Any],
        internal_patient_id: str,
        internal_encounter_id: Optional[str] = None,
        source_system: str = "fhir",
    ) -> Dict[str, Any]:
        """
        Map FHIR CarePlan resource to internal structure.

        Args:
            fhir_plan: FHIR CarePlan resource
            internal_patient_id: Internal patient ID
            internal_encounter_id: Internal encounter ID (optional)
            source_system: Source system identifier

        Returns:
            Dictionary with internal care plan data
        """
        try:
            fhir_id = fhir_plan.get("id")
            if not fhir_id:
                raise ValidationError("FHIR CarePlan missing ID")

            # Extract title
            title = fhir_plan.get("title")

            # Extract status
            status = fhir_plan.get("status", "unknown")

            # Extract intent
            intent = fhir_plan.get("intent", "unknown")

            # Extract created date
            created_str = fhir_plan.get("created")
            created_date = None
            if created_str:
                try:
                    created_date = datetime.fromisoformat(
                        created_str.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    logger.warning(f"Invalid created date format: {created_str}")

            # Extract goals
            goals = fhir_plan.get("goal", [])
            goal_count = len(goals)

            # Extract activities
            activities = fhir_plan.get("activity", [])
            activity_count = len(activities)

            # Build internal care plan structure
            internal_plan = {
                "fhir_id": fhir_id,
                "source_system": source_system,
                "patient_id": internal_patient_id,
                "encounter_id": internal_encounter_id,
                "title": title,
                "status": status,
                "intent": intent,
                "created_date": created_date,
                "goal_count": goal_count,
                "activity_count": activity_count,
                "fhir_resource": fhir_plan,
            }

            logger.info(
                f"Mapped FHIR CarePlan {fhir_id} to internal structure "
                f"(Title: {title}, Status: {status})"
            )

            return internal_plan

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error mapping FHIR CarePlan: {e}")
            raise ValidationError(f"Failed to map FHIR CarePlan: {e}")

    @staticmethod
    async def consolidate_patient_data(
        patients: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Consolidate multiple patient records from different sources.

        Args:
            patients: List of patient dictionaries from different sources

        Returns:
            Consolidated patient dictionary
        """
        if not patients:
            raise ValidationError("No patients to consolidate")

        # Use first patient as base
        consolidated = patients[0].copy()
        consolidated["source_mappings"] = [
            {
                "fhir_id": p.get("fhir_id"),
                "source_system": p.get("source_system"),
            }
            for p in patients
        ]

        # Merge additional data from other sources
        for patient in patients[1:]:
            # Prefer non-null values
            if not consolidated.get("mrn") and patient.get("mrn"):
                consolidated["mrn"] = patient.get("mrn")
            if not consolidated.get("date_of_birth") and patient.get("date_of_birth"):
                consolidated["date_of_birth"] = patient.get("date_of_birth")
            if not consolidated.get("phone") and patient.get("phone"):
                consolidated["phone"] = patient.get("phone")
            if not consolidated.get("email") and patient.get("email"):
                consolidated["email"] = patient.get("email")
            if not consolidated.get("address") and patient.get("address"):
                consolidated["address"] = patient.get("address")

        logger.info(
            f"Consolidated {len(patients)} patient records into single record"
        )

        return consolidated
