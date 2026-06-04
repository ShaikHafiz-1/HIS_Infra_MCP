"""
HL7 v2 Message Parser.

This module provides parsers for different HL7 v2 message types:
- ADT (Admission/Discharge/Transfer)
- ORU (Observation Result)
- ORM (Order)
- MDM (Medical Document Management)

Handles message validation, field extraction, and error handling.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from mcp_server.utils.logger import get_logger

logger = get_logger(__name__)


class HL7Parser:
    """
    Parser for HL7 v2 messages.
    
    Supports:
    - ADT messages (patient registration, admission, discharge, transfer)
    - ORU messages (observation results)
    - ORM messages (medication and procedure orders)
    - MDM messages (clinical notes and discharge summaries)
    """

    # HL7 field separator and encoding characters
    FIELD_SEPARATOR = "|"
    COMPONENT_SEPARATOR = "^"
    REPETITION_SEPARATOR = "~"
    ESCAPE_CHARACTER = "\\"
    SUBCOMPONENT_SEPARATOR = "&"

    # Message type handlers
    MESSAGE_HANDLERS = {
        "ADT": "parse_adt",
        "ORU": "parse_oru",
        "ORM": "parse_orm",
        "MDM": "parse_mdm",
    }

    def parse(self, message: str) -> Dict[str, Any]:
        """
        Parse an HL7 v2 message.
        
        Args:
            message: Raw HL7 message string
            
        Returns:
            Dictionary containing parsed message data
            
        Raises:
            ValueError: If message format is invalid
        """
        try:
            # Split into segments
            segments = message.strip().split("\r")
            
            if not segments or not segments[0].startswith("MSH"):
                raise ValueError("Invalid HL7 message: missing MSH segment")
            
            # Parse MSH segment to get message type
            msh_segment = self.parse_segment(segments[0])
            message_type = msh_segment.get("message_type", "")
            
            if not message_type:
                raise ValueError("Invalid HL7 message: missing message type")
            
            # Get the base message type (e.g., "ADT" from "ADT^A01")
            base_type = message_type.split(self.COMPONENT_SEPARATOR)[0]
            
            # Route to appropriate handler
            handler_name = self.MESSAGE_HANDLERS.get(base_type)
            if not handler_name:
                raise ValueError(f"Unsupported message type: {base_type}")
            
            handler = getattr(self, handler_name)
            parsed = handler(segments)
            
            # Add common fields
            parsed["raw_message"] = message
            parsed["parsed_at"] = datetime.now(timezone.utc).isoformat()
            
            return parsed
            
        except Exception as e:
            logger.error(f"Failed to parse HL7 message: {e}")
            raise

    def parse_segment(self, segment: str) -> Dict[str, str]:
        """
        Parse a single HL7 segment into fields.
        
        Args:
            segment: HL7 segment string
            
        Returns:
            Dictionary with field names and values
        """
        fields = segment.split(self.FIELD_SEPARATOR)
        
        if not fields:
            return {}
        
        segment_id = fields[0]
        result = {"segment_id": segment_id}
        
        # Parse fields based on segment type
        if segment_id == "MSH":
            # MSH has special handling for encoding characters
            result.update(self.parse_msh_segment(fields))
        elif segment_id == "PID":
            result.update(self.parse_pid_segment(fields))
        elif segment_id == "PV1":
            result.update(self.parse_pv1_segment(fields))
        elif segment_id == "OBR":
            result.update(self.parse_obr_segment(fields))
        elif segment_id == "OBX":
            result.update(self.parse_obx_segment(fields))
        elif segment_id == "ORC":
            result.update(self.parse_orc_segment(fields))
        elif segment_id == "RXO":
            result.update(self.parse_rxo_segment(fields))
        elif segment_id == "TXA":
            result.update(self.parse_txa_segment(fields))
        elif segment_id == "EVN":
            result.update(self.parse_evn_segment(fields))
        else:
            # Generic segment parsing
            for i, field in enumerate(fields[1:], 1):
                result[f"field_{i}"] = field
        
        return result

    def parse_msh_segment(self, fields: List[str]) -> Dict[str, str]:
        """Parse MSH (Message Header) segment."""
        result = {}
        
        if len(fields) > 1:
            result["encoding_characters"] = fields[1]
        if len(fields) > 2:
            result["sending_application"] = fields[2]
        if len(fields) > 3:
            result["sending_facility"] = fields[3]
        if len(fields) > 4:
            result["receiving_application"] = fields[4]
        if len(fields) > 5:
            result["receiving_facility"] = fields[5]
        if len(fields) > 6:
            result["timestamp"] = fields[6]
        if len(fields) > 9:
            result["message_type"] = fields[9]
        if len(fields) > 10:
            result["message_id"] = fields[10]
        if len(fields) > 11:
            result["processing_id"] = fields[11]
        if len(fields) > 12:
            result["version_id"] = fields[12]
        
        return result

    def parse_pid_segment(self, fields: List[str]) -> Dict[str, str]:
        """Parse PID (Patient Identification) segment."""
        result = {}
        
        if len(fields) > 1:
            result["set_id"] = fields[1]
        if len(fields) > 2:
            result["patient_id"] = fields[2]
        if len(fields) > 3:
            result["patient_id_list"] = fields[3]
        if len(fields) > 5:
            # Name field (components: family^given^middle^prefix^suffix)
            name_parts = fields[5].split(self.COMPONENT_SEPARATOR)
            result["patient_name"] = fields[5]
            if len(name_parts) > 0:
                result["family_name"] = name_parts[0]
            if len(name_parts) > 1:
                result["given_name"] = name_parts[1]
        if len(fields) > 7:
            result["date_of_birth"] = fields[7]
        if len(fields) > 8:
            result["gender"] = fields[8]
        if len(fields) > 11:
            result["address"] = fields[11]
        if len(fields) > 13:
            result["phone"] = fields[13]
        
        return result

    def parse_pv1_segment(self, fields: List[str]) -> Dict[str, str]:
        """Parse PV1 (Patient Visit) segment."""
        result = {}
        
        if len(fields) > 1:
            result["set_id"] = fields[1]
        if len(fields) > 2:
            result["patient_class"] = fields[2]
        if len(fields) > 3:
            # Assigned patient location (point of care^room^bed^facility^location status^etc)
            location_parts = fields[3].split(self.COMPONENT_SEPARATOR)
            result["assigned_patient_location"] = fields[3]
            if len(location_parts) > 0:
                result["point_of_care"] = location_parts[0]
            if len(location_parts) > 1:
                result["room"] = location_parts[1]
            if len(location_parts) > 2:
                result["bed"] = location_parts[2]
        if len(fields) > 7:
            result["attending_doctor"] = fields[7]
        if len(fields) > 8:
            result["admission_type"] = fields[8]
        if len(fields) > 44:
            result["admission_time"] = fields[44]
        
        return result

    def parse_obr_segment(self, fields: List[str]) -> Dict[str, str]:
        """Parse OBR (Observation Request) segment."""
        result = {}
        
        if len(fields) > 1:
            result["set_id"] = fields[1]
        if len(fields) > 2:
            result["placer_order_number"] = fields[2]
        if len(fields) > 3:
            result["filler_order_number"] = fields[3]
        if len(fields) > 4:
            # Universal service ID (code^text^coding_system)
            service_parts = fields[4].split(self.COMPONENT_SEPARATOR)
            result["universal_service_id"] = fields[4]
            if len(service_parts) > 0:
                result["test_code"] = service_parts[0]
            if len(service_parts) > 1:
                result["test_name"] = service_parts[1]
        if len(fields) > 6:
            result["observation_datetime"] = fields[6]
        if len(fields) > 7:
            result["observation_end_datetime"] = fields[7]
        
        return result

    def parse_obx_segment(self, fields: List[str]) -> Dict[str, str]:
        """Parse OBX (Observation/Result) segment."""
        result = {}
        
        if len(fields) > 1:
            result["set_id"] = fields[1]
        if len(fields) > 2:
            result["value_type"] = fields[2]
        if len(fields) > 3:
            # Observation identifier (code^text^coding_system)
            obs_parts = fields[3].split(self.COMPONENT_SEPARATOR)
            result["observation_identifier"] = fields[3]
            if len(obs_parts) > 0:
                result["observation_code"] = obs_parts[0]
            if len(obs_parts) > 1:
                result["observation_name"] = obs_parts[1]
        if len(fields) > 5:
            result["observation_value"] = fields[5]
        if len(fields) > 6:
            result["units"] = fields[6]
        if len(fields) > 7:
            result["reference_range"] = fields[7]
        if len(fields) > 8:
            result["abnormal_flags"] = fields[8]
        
        return result

    def parse_orc_segment(self, fields: List[str]) -> Dict[str, str]:
        """Parse ORC (Order Common) segment."""
        result = {}
        
        if len(fields) > 1:
            result["order_control"] = fields[1]
        if len(fields) > 2:
            result["placer_order_number"] = fields[2]
        if len(fields) > 3:
            result["filler_order_number"] = fields[3]
        if len(fields) > 4:
            result["placer_group_number"] = fields[4]
        if len(fields) > 5:
            result["order_status"] = fields[5]
        if len(fields) > 9:
            result["date_time_of_transaction"] = fields[9]
        
        return result

    def parse_rxo_segment(self, fields: List[str]) -> Dict[str, str]:
        """Parse RXO (Pharmacy/Treatment Order) segment."""
        result = {}
        
        if len(fields) > 1:
            # Requested give (code^text^coding_system)
            med_parts = fields[1].split(self.COMPONENT_SEPARATOR)
            result["requested_give"] = fields[1]
            if len(med_parts) > 0:
                result["medication_code"] = med_parts[0]
            if len(med_parts) > 1:
                result["medication_name"] = med_parts[1]
        if len(fields) > 2:
            result["dose"] = fields[2]
        if len(fields) > 3:
            result["dose_units"] = fields[3]
        if len(fields) > 4:
            result["frequency"] = fields[4]
        if len(fields) > 5:
            result["route"] = fields[5]
        
        return result

    def parse_txa_segment(self, fields: List[str]) -> Dict[str, str]:
        """Parse TXA (Transcription Document Header) segment."""
        result = {}
        
        if len(fields) > 1:
            result["set_id"] = fields[1]
        if len(fields) > 2:
            result["document_type"] = fields[2]
        if len(fields) > 3:
            result["document_content_presentation"] = fields[3]
        if len(fields) > 4:
            result["activity_date_time"] = fields[4]
        if len(fields) > 5:
            result["primary_activity_date_time"] = fields[5]
        if len(fields) > 6:
            result["document_completion_date_time"] = fields[6]
        if len(fields) > 7:
            result["document_confidentiality_status"] = fields[7]
        if len(fields) > 8:
            result["document_availability_status"] = fields[8]
        if len(fields) > 9:
            result["document_storage_status"] = fields[9]
        if len(fields) > 10:
            result["document_title"] = fields[10]
        
        return result

    def parse_evn_segment(self, fields: List[str]) -> Dict[str, str]:
        """Parse EVN (Event Type) segment."""
        result = {}
        
        if len(fields) > 1:
            result["event_type_code"] = fields[1]
        if len(fields) > 2:
            result["recorded_date_time"] = fields[2]
        if len(fields) > 3:
            result["date_time_planned_event"] = fields[3]
        if len(fields) > 4:
            result["event_reason_code"] = fields[4]
        
        return result

    def parse_adt(self, segments: List[str]) -> Dict[str, Any]:
        """
        Parse ADT (Admission/Discharge/Transfer) message.
        
        Args:
            segments: List of HL7 segments
            
        Returns:
            Dictionary with parsed ADT data
        """
        result = {
            "message_type": "ADT",
            "segments": {},
        }
        
        for segment in segments:
            if not segment:
                continue
            
            parsed_segment = self.parse_segment(segment)
            segment_id = parsed_segment.get("segment_id")
            
            if segment_id == "MSH":
                result["msh"] = parsed_segment
                result["message_id"] = parsed_segment.get("message_id")
                result["timestamp"] = parsed_segment.get("timestamp")
            elif segment_id == "EVN":
                result["evn"] = parsed_segment
                result["event_type"] = parsed_segment.get("event_type_code")
            elif segment_id == "PID":
                result["pid"] = parsed_segment
                result["patient_id"] = parsed_segment.get("patient_id")
                result["patient_name"] = parsed_segment.get("patient_name")
                result["date_of_birth"] = parsed_segment.get("date_of_birth")
                result["gender"] = parsed_segment.get("gender")
            elif segment_id == "PV1":
                result["pv1"] = parsed_segment
                result["patient_class"] = parsed_segment.get("patient_class")
                result["assigned_patient_location"] = parsed_segment.get("assigned_patient_location")
                result["point_of_care"] = parsed_segment.get("point_of_care")
                result["admission_type"] = parsed_segment.get("admission_type")
        
        return result

    def parse_oru(self, segments: List[str]) -> Dict[str, Any]:
        """
        Parse ORU (Observation Result) message.
        
        Args:
            segments: List of HL7 segments
            
        Returns:
            Dictionary with parsed ORU data
        """
        result = {
            "message_type": "ORU",
            "segments": {},
            "observations": [],
        }
        
        current_obr = None
        
        for segment in segments:
            if not segment:
                continue
            
            parsed_segment = self.parse_segment(segment)
            segment_id = parsed_segment.get("segment_id")
            
            if segment_id == "MSH":
                result["msh"] = parsed_segment
                result["message_id"] = parsed_segment.get("message_id")
                result["timestamp"] = parsed_segment.get("timestamp")
            elif segment_id == "PID":
                result["pid"] = parsed_segment
                result["patient_id"] = parsed_segment.get("patient_id")
                result["patient_name"] = parsed_segment.get("patient_name")
            elif segment_id == "OBR":
                result["obr"] = parsed_segment
                current_obr = parsed_segment
            elif segment_id == "OBX":
                result["obx"] = parsed_segment
                observation = {
                    "code": parsed_segment.get("observation_code"),
                    "name": parsed_segment.get("observation_name"),
                    "value": parsed_segment.get("observation_value"),
                    "units": parsed_segment.get("units"),
                    "reference_range": parsed_segment.get("reference_range"),
                    "abnormal_flags": parsed_segment.get("abnormal_flags"),
                }
                result["observations"].append(observation)
        
        return result

    def parse_orm(self, segments: List[str]) -> Dict[str, Any]:
        """
        Parse ORM (Order) message.
        
        Args:
            segments: List of HL7 segments
            
        Returns:
            Dictionary with parsed ORM data
        """
        result = {
            "message_type": "ORM",
            "segments": {},
            "orders": [],
        }
        
        for segment in segments:
            if not segment:
                continue
            
            parsed_segment = self.parse_segment(segment)
            segment_id = parsed_segment.get("segment_id")
            
            if segment_id == "MSH":
                result["msh"] = parsed_segment
                result["message_id"] = parsed_segment.get("message_id")
                result["timestamp"] = parsed_segment.get("timestamp")
            elif segment_id == "PID":
                result["pid"] = parsed_segment
                result["patient_id"] = parsed_segment.get("patient_id")
                result["patient_name"] = parsed_segment.get("patient_name")
            elif segment_id == "ORC":
                result["orc"] = parsed_segment
                order = {
                    "order_control": parsed_segment.get("order_control"),
                    "placer_order_number": parsed_segment.get("placer_order_number"),
                    "filler_order_number": parsed_segment.get("filler_order_number"),
                    "order_status": parsed_segment.get("order_status"),
                    "date_time": parsed_segment.get("date_time_of_transaction"),
                }
                result["orders"].append(order)
            elif segment_id == "RXO":
                result["rxo"] = parsed_segment
                if result["orders"]:
                    result["orders"][-1]["medication"] = {
                        "code": parsed_segment.get("medication_code"),
                        "name": parsed_segment.get("medication_name"),
                        "dose": parsed_segment.get("dose"),
                        "dose_units": parsed_segment.get("dose_units"),
                        "frequency": parsed_segment.get("frequency"),
                        "route": parsed_segment.get("route"),
                    }
        
        return result

    def parse_mdm(self, segments: List[str]) -> Dict[str, Any]:
        """
        Parse MDM (Medical Document Management) message.
        
        Args:
            segments: List of HL7 segments
            
        Returns:
            Dictionary with parsed MDM data
        """
        result = {
            "message_type": "MDM",
            "segments": {},
        }
        
        for segment in segments:
            if not segment:
                continue
            
            parsed_segment = self.parse_segment(segment)
            segment_id = parsed_segment.get("segment_id")
            
            if segment_id == "MSH":
                result["msh"] = parsed_segment
                result["message_id"] = parsed_segment.get("message_id")
                result["timestamp"] = parsed_segment.get("timestamp")
            elif segment_id == "EVN":
                result["evn"] = parsed_segment
                result["event_type"] = parsed_segment.get("event_type_code")
            elif segment_id == "PID":
                result["pid"] = parsed_segment
                result["patient_id"] = parsed_segment.get("patient_id")
                result["patient_name"] = parsed_segment.get("patient_name")
            elif segment_id == "TXA":
                result["txa"] = parsed_segment
                result["document_type"] = parsed_segment.get("document_type")
                result["document_title"] = parsed_segment.get("document_title")
                result["activity_date_time"] = parsed_segment.get("activity_date_time")
        
        return result
