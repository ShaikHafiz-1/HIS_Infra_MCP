"""Helper utilities for the MCP server."""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


def generate_id(prefix: str = "") -> str:
    """
    Generate a unique ID with optional prefix.

    Args:
        prefix: Optional prefix for the ID

    Returns:
        str: Generated ID
    """
    unique_id = str(uuid.uuid4())
    if prefix:
        return f"{prefix}-{unique_id}"
    return unique_id


def generate_patient_id() -> str:
    """Generate a unique patient ID."""
    return generate_id("PAT")


def generate_encounter_id() -> str:
    """Generate a unique encounter ID."""
    return generate_id("ENC")


def generate_device_id() -> str:
    """Generate a unique device ID."""
    return generate_id("DEV")


def hash_string(value: str, algorithm: str = "sha256") -> str:
    """
    Hash a string value.

    Args:
        value: String to hash
        algorithm: Hash algorithm to use

    Returns:
        str: Hashed value
    """
    if algorithm == "sha256":
        return hashlib.sha256(value.encode()).hexdigest()
    elif algorithm == "sha512":
        return hashlib.sha512(value.encode()).hexdigest()
    elif algorithm == "md5":
        return hashlib.md5(value.encode()).hexdigest()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")


def get_current_timestamp() -> datetime:
    """
    Get current timestamp in UTC.

    Returns:
        datetime: Current UTC timestamp
    """
    return datetime.now(timezone.utc)


def get_timestamp_iso() -> str:
    """
    Get current timestamp as ISO format string.

    Returns:
        str: Current timestamp in ISO format
    """
    return get_current_timestamp().isoformat()


def add_hours(dt: datetime, hours: int) -> datetime:
    """
    Add hours to a datetime.

    Args:
        dt: Base datetime
        hours: Number of hours to add

    Returns:
        datetime: New datetime with hours added
    """
    return dt + timedelta(hours=hours)


def add_days(dt: datetime, days: int) -> datetime:
    """
    Add days to a datetime.

    Args:
        dt: Base datetime
        days: Number of days to add

    Returns:
        datetime: New datetime with days added
    """
    return dt + timedelta(days=days)


def mask_phi(value: str, mask_char: str = "*", show_chars: int = 2) -> str:
    """
    Mask PHI (Protected Health Information) in a string.

    Args:
        value: String to mask
        mask_char: Character to use for masking
        show_chars: Number of characters to show at end

    Returns:
        str: Masked string
    """
    if len(value) <= show_chars:
        return mask_char * len(value)

    visible = value[-show_chars:]
    masked = mask_char * (len(value) - show_chars)
    return masked + visible


def mask_patient_name(name: str) -> str:
    """
    Mask patient name for logging.

    Args:
        name: Patient name to mask

    Returns:
        str: Masked patient name
    """
    parts = name.split()
    if len(parts) == 0:
        return mask_phi(name)

    # Mask first name, show last initial
    masked_parts = []
    for i, part in enumerate(parts):
        if i == len(parts) - 1:  # Last part (surname)
            masked_parts.append(part[0] + "*" * (len(part) - 1))
        else:
            masked_parts.append("*" * len(part))

    return " ".join(masked_parts)


def mask_mrn(mrn: str) -> str:
    """
    Mask medical record number for logging.

    Args:
        mrn: Medical record number to mask

    Returns:
        str: Masked MRN
    """
    return mask_phi(mrn, show_chars=3)


def mask_medication_name(medication: str) -> str:
    """
    Mask medication name for logging.

    Args:
        medication: Medication name to mask

    Returns:
        str: Masked medication name
    """
    return mask_phi(medication, show_chars=1)


def mask_diagnostic_code(code: str) -> str:
    """
    Mask diagnostic code for logging.

    Args:
        code: Diagnostic code to mask

    Returns:
        str: Masked diagnostic code
    """
    return mask_phi(code, show_chars=2)


def paginate_list(items: List[Any], page: int = 1, page_size: int = 10) -> Dict[str, Any]:
    """
    Paginate a list of items.

    Args:
        items: List of items to paginate
        page: Page number (1-indexed)
        page_size: Number of items per page

    Returns:
        dict: Paginated result with items, total, page, and page_size
    """
    if page < 1:
        page = 1

    if page_size < 1:
        page_size = 10

    total = len(items)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size

    return {
        "items": items[start_idx:end_idx],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


def flatten_dict(d: Dict[str, Any], parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
    """
    Flatten a nested dictionary.

    Args:
        d: Dictionary to flatten
        parent_key: Parent key prefix
        sep: Separator for nested keys

    Returns:
        dict: Flattened dictionary
    """
    items: List[tuple] = []

    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k

        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    items.extend(flatten_dict(item, f"{new_key}[{i}]", sep=sep).items())
                else:
                    items.append((f"{new_key}[{i}]", item))
        else:
            items.append((new_key, v))

    return dict(items)


def merge_dicts(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge multiple dictionaries.

    Args:
        *dicts: Dictionaries to merge

    Returns:
        dict: Merged dictionary
    """
    result: Dict[str, Any] = {}

    for d in dicts:
        if isinstance(d, dict):
            result.update(d)

    return result
