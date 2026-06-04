"""Input validation utilities for the MCP server."""

import re
from datetime import datetime
from typing import Any, Optional
from uuid import UUID


class ValidationError(Exception):
    """Custom validation error exception."""

    pass


def validate_patient_id(patient_id: str) -> bool:
    """
    Validate patient ID format.

    Args:
        patient_id: Patient ID to validate

    Returns:
        bool: True if valid, False otherwise

    Raises:
        ValidationError: If patient ID is invalid
    """
    if not patient_id or not isinstance(patient_id, str):
        raise ValidationError("Patient ID must be a non-empty string")

    if len(patient_id) > 255:
        raise ValidationError("Patient ID must be less than 255 characters")

    # Allow alphanumeric, hyphens, and underscores
    if not re.match(r"^[a-zA-Z0-9\-_]+$", patient_id):
        raise ValidationError("Patient ID contains invalid characters")

    return True


def validate_encounter_id(encounter_id: str) -> bool:
    """
    Validate encounter ID format.

    Args:
        encounter_id: Encounter ID to validate

    Returns:
        bool: True if valid, False otherwise

    Raises:
        ValidationError: If encounter ID is invalid
    """
    if not encounter_id or not isinstance(encounter_id, str):
        raise ValidationError("Encounter ID must be a non-empty string")

    if len(encounter_id) > 255:
        raise ValidationError("Encounter ID must be less than 255 characters")

    if not re.match(r"^[a-zA-Z0-9\-_]+$", encounter_id):
        raise ValidationError("Encounter ID contains invalid characters")

    return True


def validate_device_id(device_id: str) -> bool:
    """
    Validate device ID format.

    Args:
        device_id: Device ID to validate

    Returns:
        bool: True if valid, False otherwise

    Raises:
        ValidationError: If device ID is invalid
    """
    if not device_id or not isinstance(device_id, str):
        raise ValidationError("Device ID must be a non-empty string")

    if len(device_id) > 255:
        raise ValidationError("Device ID must be less than 255 characters")

    if not re.match(r"^[a-zA-Z0-9\-_]+$", device_id):
        raise ValidationError("Device ID contains invalid characters")

    return True


def validate_time_window(start_time: datetime, end_time: datetime) -> bool:
    """
    Validate time window.

    Args:
        start_time: Start time
        end_time: End time

    Returns:
        bool: True if valid, False otherwise

    Raises:
        ValidationError: If time window is invalid
    """
    if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
        raise ValidationError("Start and end times must be datetime objects")

    if start_time >= end_time:
        raise ValidationError("Start time must be before end time")

    # Check if time window is reasonable (not more than 1 year)
    max_window = 365 * 24 * 60 * 60  # 1 year in seconds
    if (end_time - start_time).total_seconds() > max_window:
        raise ValidationError("Time window cannot exceed 1 year")

    return True


def validate_uuid(value: str) -> bool:
    """
    Validate UUID format.

    Args:
        value: UUID string to validate

    Returns:
        bool: True if valid, False otherwise

    Raises:
        ValidationError: If UUID is invalid
    """
    try:
        UUID(value)
        return True
    except (ValueError, AttributeError):
        raise ValidationError(f"Invalid UUID format: {value}")


def validate_email(email: str) -> bool:
    """
    Validate email format.

    Args:
        email: Email address to validate

    Returns:
        bool: True if valid, False otherwise

    Raises:
        ValidationError: If email is invalid
    """
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    if not re.match(email_pattern, email):
        raise ValidationError(f"Invalid email format: {email}")

    return True


def validate_role(role: str) -> bool:
    """
    Validate clinician role.

    Args:
        role: Role to validate

    Returns:
        bool: True if valid, False otherwise

    Raises:
        ValidationError: If role is invalid
    """
    valid_roles = {"physician", "nurse", "technician", "administrator"}

    if role not in valid_roles:
        raise ValidationError(f"Invalid role: {role}. Must be one of {valid_roles}")

    return True


def validate_care_unit(care_unit: str) -> bool:
    """
    Validate care unit.

    Args:
        care_unit: Care unit to validate

    Returns:
        bool: True if valid, False otherwise

    Raises:
        ValidationError: If care unit is invalid
    """
    valid_units = {
        "cardiology",
        "emergency_department",
        "neurology",
        "surgical_ward",
        "operating_room",
        "intensive_care",
        "radiology",
        "general_ward",
    }

    if care_unit not in valid_units:
        raise ValidationError(f"Invalid care unit: {care_unit}. Must be one of {valid_units}")

    return True


def sanitize_string(value: str, max_length: int = 1000) -> str:
    """
    Sanitize string input.

    Args:
        value: String to sanitize
        max_length: Maximum allowed length

    Returns:
        str: Sanitized string

    Raises:
        ValidationError: If string is invalid
    """
    if not isinstance(value, str):
        raise ValidationError("Value must be a string")

    if len(value) > max_length:
        raise ValidationError(f"String exceeds maximum length of {max_length}")

    # Remove null bytes
    value = value.replace("\x00", "")

    return value.strip()
