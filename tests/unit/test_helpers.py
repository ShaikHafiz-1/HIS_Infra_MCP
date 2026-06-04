"""Tests for helper utilities."""

import pytest
from datetime import datetime, timedelta

from mcp_server.utils.helpers import (
    generate_id,
    generate_patient_id,
    generate_encounter_id,
    generate_device_id,
    hash_string,
    get_current_timestamp,
    get_timestamp_iso,
    add_hours,
    add_days,
    mask_phi,
    mask_patient_name,
    mask_mrn,
    mask_medication_name,
    mask_diagnostic_code,
    paginate_list,
    flatten_dict,
    merge_dicts,
)


class TestIDGeneration:
    """Test ID generation utilities."""

    def test_generate_id_without_prefix(self):
        """Test generating ID without prefix."""
        id1 = generate_id()
        id2 = generate_id()
        assert id1 != id2
        assert len(id1) == 36  # UUID length

    def test_generate_id_with_prefix(self):
        """Test generating ID with prefix."""
        id1 = generate_id("TEST")
        assert id1.startswith("TEST-")

    def test_generate_patient_id(self):
        """Test generating patient ID."""
        patient_id = generate_patient_id()
        assert patient_id.startswith("PAT-")

    def test_generate_encounter_id(self):
        """Test generating encounter ID."""
        encounter_id = generate_encounter_id()
        assert encounter_id.startswith("ENC-")

    def test_generate_device_id(self):
        """Test generating device ID."""
        device_id = generate_device_id()
        assert device_id.startswith("DEV-")


class TestHashFunction:
    """Test hash function."""

    def test_hash_string_sha256(self):
        """Test SHA256 hashing."""
        hash1 = hash_string("test", "sha256")
        hash2 = hash_string("test", "sha256")
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length

    def test_hash_string_sha512(self):
        """Test SHA512 hashing."""
        hash1 = hash_string("test", "sha512")
        assert len(hash1) == 128  # SHA512 hex length

    def test_hash_string_md5(self):
        """Test MD5 hashing."""
        hash1 = hash_string("test", "md5")
        assert len(hash1) == 32  # MD5 hex length

    def test_hash_string_invalid_algorithm(self):
        """Test invalid hash algorithm."""
        with pytest.raises(ValueError):
            hash_string("test", "invalid")


class TestTimestampFunctions:
    """Test timestamp functions."""

    def test_get_current_timestamp(self):
        """Test getting current timestamp."""
        ts = get_current_timestamp()
        assert isinstance(ts, datetime)

    def test_get_timestamp_iso(self):
        """Test getting ISO format timestamp."""
        ts = get_timestamp_iso()
        assert isinstance(ts, str)
        assert "T" in ts  # ISO format includes T

    def test_add_hours(self):
        """Test adding hours to datetime."""
        now = datetime.now()
        future = add_hours(now, 2)
        assert (future - now).total_seconds() == 2 * 3600

    def test_add_days(self):
        """Test adding days to datetime."""
        now = datetime.now()
        future = add_days(now, 5)
        assert (future - now).days == 5


class TestPHIMasking:
    """Test PHI masking functions."""

    def test_mask_phi_basic(self):
        """Test basic PHI masking."""
        masked = mask_phi("1234567890", show_chars=2)
        assert masked == "********90"

    def test_mask_phi_short_string(self):
        """Test masking short string."""
        masked = mask_phi("12", show_chars=2)
        assert masked == "**"

    def test_mask_patient_name(self):
        """Test masking patient name."""
        masked = mask_patient_name("John Smith")
        assert "Smith" not in masked
        assert "John" not in masked

    def test_mask_mrn(self):
        """Test masking medical record number."""
        masked = mask_mrn("123456789")
        assert masked.endswith("789")

    def test_mask_medication_name(self):
        """Test masking medication name."""
        masked = mask_medication_name("Aspirin")
        assert len(masked) == len("Aspirin")

    def test_mask_diagnostic_code(self):
        """Test masking diagnostic code."""
        masked = mask_diagnostic_code("I10")
        assert len(masked) == len("I10")


class TestPagination:
    """Test pagination utility."""

    def test_paginate_list_first_page(self):
        """Test paginating first page."""
        items = list(range(100))
        result = paginate_list(items, page=1, page_size=10)
        assert len(result["items"]) == 10
        assert result["items"][0] == 0
        assert result["total"] == 100
        assert result["page"] == 1

    def test_paginate_list_second_page(self):
        """Test paginating second page."""
        items = list(range(100))
        result = paginate_list(items, page=2, page_size=10)
        assert len(result["items"]) == 10
        assert result["items"][0] == 10

    def test_paginate_list_last_page(self):
        """Test paginating last page."""
        items = list(range(100))
        result = paginate_list(items, page=10, page_size=10)
        assert len(result["items"]) == 10
        assert result["items"][0] == 90

    def test_paginate_list_invalid_page(self):
        """Test paginating with invalid page number."""
        items = list(range(100))
        result = paginate_list(items, page=0, page_size=10)
        assert result["page"] == 1


class TestDictFunctions:
    """Test dictionary utility functions."""

    def test_flatten_dict_simple(self):
        """Test flattening simple nested dict."""
        d = {"a": {"b": 1, "c": 2}}
        result = flatten_dict(d)
        assert result["a.b"] == 1
        assert result["a.c"] == 2

    def test_flatten_dict_deep(self):
        """Test flattening deeply nested dict."""
        d = {"a": {"b": {"c": 1}}}
        result = flatten_dict(d)
        assert result["a.b.c"] == 1

    def test_flatten_dict_with_list(self):
        """Test flattening dict with list."""
        d = {"a": [1, 2, 3]}
        result = flatten_dict(d)
        assert result["a[0]"] == 1
        assert result["a[1]"] == 2

    def test_merge_dicts_simple(self):
        """Test merging simple dicts."""
        d1 = {"a": 1}
        d2 = {"b": 2}
        result = merge_dicts(d1, d2)
        assert result == {"a": 1, "b": 2}

    def test_merge_dicts_override(self):
        """Test merging dicts with override."""
        d1 = {"a": 1}
        d2 = {"a": 2}
        result = merge_dicts(d1, d2)
        assert result["a"] == 2
