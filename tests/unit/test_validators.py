"""Tests for input validation utilities."""

import pytest
from datetime import datetime, timedelta

from mcp_server.utils.validators import (
    ValidationError,
    validate_patient_id,
    validate_encounter_id,
    validate_device_id,
    validate_time_window,
    validate_uuid,
    validate_email,
    validate_role,
    validate_care_unit,
    sanitize_string,
)


class TestPatientIDValidation:
    """Test patient ID validation."""

    def test_valid_patient_id(self):
        """Test valid patient ID."""
        assert validate_patient_id("PAT-12345678-1234-1234-1234-123456789012")

    def test_valid_patient_id_simple(self):
        """Test valid simple patient ID."""
        assert validate_patient_id("PAT123456")

    def test_invalid_patient_id_empty(self):
        """Test invalid empty patient ID."""
        with pytest.raises(ValidationError):
            validate_patient_id("")

    def test_invalid_patient_id_none(self):
        """Test invalid None patient ID."""
        with pytest.raises(ValidationError):
            validate_patient_id(None)

    def test_invalid_patient_id_special_chars(self):
        """Test invalid patient ID with special characters."""
        with pytest.raises(ValidationError):
            validate_patient_id("PAT@#$%")

    def test_invalid_patient_id_too_long(self):
        """Test invalid patient ID that's too long."""
        with pytest.raises(ValidationError):
            validate_patient_id("PAT" + "A" * 300)


class TestEncounterIDValidation:
    """Test encounter ID validation."""

    def test_valid_encounter_id(self):
        """Test valid encounter ID."""
        assert validate_encounter_id("ENC-12345678-1234-1234-1234-123456789012")

    def test_invalid_encounter_id_empty(self):
        """Test invalid empty encounter ID."""
        with pytest.raises(ValidationError):
            validate_encounter_id("")


class TestDeviceIDValidation:
    """Test device ID validation."""

    def test_valid_device_id(self):
        """Test valid device ID."""
        assert validate_device_id("DEV-12345678-1234-1234-1234-123456789012")

    def test_invalid_device_id_empty(self):
        """Test invalid empty device ID."""
        with pytest.raises(ValidationError):
            validate_device_id("")


class TestTimeWindowValidation:
    """Test time window validation."""

    def test_valid_time_window(self):
        """Test valid time window."""
        start = datetime.now()
        end = start + timedelta(hours=1)
        assert validate_time_window(start, end)

    def test_invalid_time_window_same_time(self):
        """Test invalid time window with same start and end."""
        now = datetime.now()
        with pytest.raises(ValidationError):
            validate_time_window(now, now)

    def test_invalid_time_window_reversed(self):
        """Test invalid time window with reversed times."""
        start = datetime.now()
        end = start - timedelta(hours=1)
        with pytest.raises(ValidationError):
            validate_time_window(start, end)

    def test_invalid_time_window_too_large(self):
        """Test invalid time window that's too large."""
        start = datetime.now()
        end = start + timedelta(days=400)
        with pytest.raises(ValidationError):
            validate_time_window(start, end)


class TestUUIDValidation:
    """Test UUID validation."""

    def test_valid_uuid(self):
        """Test valid UUID."""
        assert validate_uuid("12345678-1234-1234-1234-123456789012")

    def test_invalid_uuid(self):
        """Test invalid UUID."""
        with pytest.raises(ValidationError):
            validate_uuid("not-a-uuid")


class TestEmailValidation:
    """Test email validation."""

    def test_valid_email(self):
        """Test valid email."""
        assert validate_email("user@example.com")

    def test_invalid_email_no_at(self):
        """Test invalid email without @."""
        with pytest.raises(ValidationError):
            validate_email("userexample.com")

    def test_invalid_email_no_domain(self):
        """Test invalid email without domain."""
        with pytest.raises(ValidationError):
            validate_email("user@")


class TestRoleValidation:
    """Test role validation."""

    def test_valid_role_physician(self):
        """Test valid physician role."""
        assert validate_role("physician")

    def test_valid_role_nurse(self):
        """Test valid nurse role."""
        assert validate_role("nurse")

    def test_valid_role_technician(self):
        """Test valid technician role."""
        assert validate_role("technician")

    def test_valid_role_administrator(self):
        """Test valid administrator role."""
        assert validate_role("administrator")

    def test_invalid_role(self):
        """Test invalid role."""
        with pytest.raises(ValidationError):
            validate_role("invalid_role")


class TestCareUnitValidation:
    """Test care unit validation."""

    def test_valid_care_unit_cardiology(self):
        """Test valid cardiology care unit."""
        assert validate_care_unit("cardiology")

    def test_valid_care_unit_icu(self):
        """Test valid ICU care unit."""
        assert validate_care_unit("intensive_care")

    def test_invalid_care_unit(self):
        """Test invalid care unit."""
        with pytest.raises(ValidationError):
            validate_care_unit("invalid_unit")


class TestStringSanitization:
    """Test string sanitization."""

    def test_sanitize_valid_string(self):
        """Test sanitizing valid string."""
        result = sanitize_string("  hello world  ")
        assert result == "hello world"

    def test_sanitize_string_with_null_bytes(self):
        """Test sanitizing string with null bytes."""
        result = sanitize_string("hello\x00world")
        assert result == "helloworld"

    def test_sanitize_string_too_long(self):
        """Test sanitizing string that's too long."""
        with pytest.raises(ValidationError):
            sanitize_string("A" * 2000, max_length=1000)

    def test_sanitize_non_string(self):
        """Test sanitizing non-string value."""
        with pytest.raises(ValidationError):
            sanitize_string(123)
