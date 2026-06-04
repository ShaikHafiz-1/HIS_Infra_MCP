"""
Unit tests for authentication module.

Tests JWT token generation, validation, and clinician identity validation.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from mcp_server.security.auth import (
    AuthenticationManager,
    AuthenticationError,
    TokenExpiredError,
    InvalidTokenError,
    get_current_clinician,
)
from mcp_server.security.credentials import CredentialValidator, TEST_CREDENTIALS
from mcp_server.models.schemas import ClinicianIdentity, TokenResponse
from fastapi import HTTPException, status


class TestAuthenticationManager:
    """Tests for AuthenticationManager class."""

    @pytest.fixture
    def auth_manager(self):
        """Create an authentication manager for testing."""
        return AuthenticationManager(
            secret_key="test-secret-key",
            algorithm="HS256",
            expiration_hours=24,
        )

    def test_create_access_token_basic(self, auth_manager):
        """Test basic JWT token creation."""
        token = auth_manager.create_access_token(
            clinician_id="CLIN-001",
            clinician_name="Dr. Smith",
            role="physician",
            care_units=["UNIT-001"],
        )

        assert isinstance(token, str)
        assert len(token) > 0
        # JWT tokens have 3 parts separated by dots
        assert token.count(".") == 2

    def test_create_access_token_with_custom_expiration(self, auth_manager):
        """Test JWT token creation with custom expiration."""
        custom_expiration = timedelta(hours=1)
        token = auth_manager.create_access_token(
            clinician_id="CLIN-001",
            clinician_name="Dr. Smith",
            role="physician",
            expires_delta=custom_expiration,
        )

        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_without_care_units(self, auth_manager):
        """Test JWT token creation without care units."""
        token = auth_manager.create_access_token(
            clinician_id="CLIN-001",
            clinician_name="Dr. Smith",
            role="physician",
        )

        assert isinstance(token, str)
        payload = auth_manager.verify_token(token)
        assert payload["care_units"] == []

    def test_verify_token_valid(self, auth_manager):
        """Test verification of valid JWT token."""
        token = auth_manager.create_access_token(
            clinician_id="CLIN-001",
            clinician_name="Dr. Smith",
            role="physician",
            care_units=["UNIT-001", "UNIT-002"],
        )

        payload = auth_manager.verify_token(token)

        assert payload["sub"] == "CLIN-001"
        assert payload["name"] == "Dr. Smith"
        assert payload["role"] == "physician"
        assert payload["care_units"] == ["UNIT-001", "UNIT-002"]

    def test_verify_token_expired(self, auth_manager):
        """Test verification of expired JWT token."""
        # Create token with negative expiration (already expired)
        expired_token = auth_manager.create_access_token(
            clinician_id="CLIN-001",
            clinician_name="Dr. Smith",
            role="physician",
            expires_delta=timedelta(seconds=-1),
        )

        with pytest.raises(TokenExpiredError):
            auth_manager.verify_token(expired_token)

    def test_verify_token_invalid(self, auth_manager):
        """Test verification of invalid JWT token."""
        invalid_token = "invalid.token.here"

        with pytest.raises(InvalidTokenError):
            auth_manager.verify_token(invalid_token)

    def test_verify_token_tampered(self, auth_manager):
        """Test verification of tampered JWT token."""
        token = auth_manager.create_access_token(
            clinician_id="CLIN-001",
            clinician_name="Dr. Smith",
            role="physician",
        )

        # Tamper with token by changing a character
        tampered_token = token[:-5] + "xxxxx"

        with pytest.raises(InvalidTokenError):
            auth_manager.verify_token(tampered_token)

    def test_verify_token_missing_sub_claim(self, auth_manager):
        """Test verification of token missing 'sub' claim."""
        import jwt

        # Create token without 'sub' claim
        payload = {
            "name": "Dr. Smith",
            "role": "physician",
            "exp": datetime.utcnow() + timedelta(hours=24),
        }
        token = jwt.encode(
            payload, auth_manager.secret_key, algorithm=auth_manager.algorithm
        )

        with pytest.raises(InvalidTokenError):
            auth_manager.verify_token(token)

    def test_validate_clinician_identity_valid(self, auth_manager):
        """Test validation of valid clinician identity."""
        payload = {
            "sub": "CLIN-001",
            "name": "Dr. Smith",
            "role": "physician",
            "care_units": ["UNIT-001"],
        }

        clinician = auth_manager.validate_clinician_identity(payload)

        assert clinician["id"] == "CLIN-001"
        assert clinician["name"] == "Dr. Smith"
        assert clinician["role"] == "physician"
        assert clinician["care_units"] == ["UNIT-001"]

    def test_validate_clinician_identity_missing_name(self, auth_manager):
        """Test validation fails when name is missing."""
        payload = {
            "sub": "CLIN-001",
            "role": "physician",
        }

        with pytest.raises(InvalidTokenError):
            auth_manager.validate_clinician_identity(payload)

    def test_validate_clinician_identity_missing_role(self, auth_manager):
        """Test validation fails when role is missing."""
        payload = {
            "sub": "CLIN-001",
            "name": "Dr. Smith",
        }

        with pytest.raises(InvalidTokenError):
            auth_manager.validate_clinician_identity(payload)

    def test_validate_clinician_identity_missing_sub(self, auth_manager):
        """Test validation fails when sub is missing."""
        payload = {
            "name": "Dr. Smith",
            "role": "physician",
        }

        with pytest.raises(InvalidTokenError):
            auth_manager.validate_clinician_identity(payload)

    def test_token_roundtrip(self, auth_manager):
        """Test complete token creation and verification roundtrip."""
        original_clinician = {
            "id": "CLIN-001",
            "name": "Dr. Smith",
            "role": "physician",
            "care_units": ["UNIT-001", "UNIT-002"],
        }

        # Create token
        token = auth_manager.create_access_token(
            clinician_id=original_clinician["id"],
            clinician_name=original_clinician["name"],
            role=original_clinician["role"],
            care_units=original_clinician["care_units"],
        )

        # Verify and validate
        payload = auth_manager.verify_token(token)
        clinician = auth_manager.validate_clinician_identity(payload)

        assert clinician["id"] == original_clinician["id"]
        assert clinician["name"] == original_clinician["name"]
        assert clinician["role"] == original_clinician["role"]
        assert clinician["care_units"] == original_clinician["care_units"]


class TestCredentialValidator:
    """Tests for CredentialValidator class."""

    def test_validate_credentials_valid(self):
        """Test validation of valid credentials."""
        result = CredentialValidator.validate_credentials("dr_smith", "test_password_123")

        assert result is not None
        assert result["id"] == TEST_CREDENTIALS["dr_smith"]["clinician_id"]
        assert result["name"] == TEST_CREDENTIALS["dr_smith"]["name"]
        assert result["role"] == "physician"

    def test_validate_credentials_invalid_username(self):
        """Test validation fails with invalid username."""
        result = CredentialValidator.validate_credentials("invalid_user", "password")

        assert result is None

    def test_validate_credentials_invalid_password(self):
        """Test validation fails with invalid password."""
        result = CredentialValidator.validate_credentials("dr_smith", "wrong_password")

        assert result is None

    def test_validate_credentials_all_roles(self):
        """Test validation for all test credential roles."""
        roles = ["physician", "nurse", "technician", "administrator"]

        for username, credential in TEST_CREDENTIALS.items():
            result = CredentialValidator.validate_credentials(
                username, credential["password"]
            )

            assert result is not None
            assert result["role"] in roles

    def test_get_clinician_by_id_valid(self):
        """Test retrieval of clinician by valid ID."""
        clinician_id = TEST_CREDENTIALS["dr_smith"]["clinician_id"]
        result = CredentialValidator.get_clinician_by_id(clinician_id)

        assert result is not None
        assert result["id"] == clinician_id
        assert result["name"] == TEST_CREDENTIALS["dr_smith"]["name"]

    def test_get_clinician_by_id_invalid(self):
        """Test retrieval fails with invalid ID."""
        result = CredentialValidator.get_clinician_by_id("INVALID-ID")

        assert result is None

    def test_get_all_test_usernames(self):
        """Test retrieval of all test usernames."""
        usernames = CredentialValidator.get_all_test_usernames()

        assert len(usernames) == len(TEST_CREDENTIALS)
        assert "dr_smith" in usernames
        assert "nurse_johnson" in usernames
        assert "tech_williams" in usernames
        assert "admin_brown" in usernames

    def test_get_test_credentials_by_role_physician(self):
        """Test retrieval of physician credentials."""
        credentials = CredentialValidator.get_test_credentials_by_role("physician")

        assert len(credentials) > 0
        assert all(c["role"] == "physician" for c in credentials)

    def test_get_test_credentials_by_role_nurse(self):
        """Test retrieval of nurse credentials."""
        credentials = CredentialValidator.get_test_credentials_by_role("nurse")

        assert len(credentials) > 0
        assert all(c["role"] == "nurse" for c in credentials)

    def test_get_test_credentials_by_role_technician(self):
        """Test retrieval of technician credentials."""
        credentials = CredentialValidator.get_test_credentials_by_role("technician")

        assert len(credentials) > 0
        assert all(c["role"] == "technician" for c in credentials)

    def test_get_test_credentials_by_role_administrator(self):
        """Test retrieval of administrator credentials."""
        credentials = CredentialValidator.get_test_credentials_by_role("administrator")

        assert len(credentials) > 0
        assert all(c["role"] == "administrator" for c in credentials)

    def test_get_test_credentials_by_role_invalid(self):
        """Test retrieval with invalid role returns empty list."""
        credentials = CredentialValidator.get_test_credentials_by_role("invalid_role")

        assert credentials == []


class TestAuthenticationErrors:
    """Tests for authentication error classes."""

    def test_authentication_error(self):
        """Test AuthenticationError exception."""
        error = AuthenticationError("Test error")

        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_token_expired_error(self):
        """Test TokenExpiredError exception."""
        error = TokenExpiredError()

        assert "expired" in str(error).lower()
        assert isinstance(error, AuthenticationError)

    def test_invalid_token_error(self):
        """Test InvalidTokenError exception."""
        error = InvalidTokenError()

        assert "invalid" in str(error).lower()
        assert isinstance(error, AuthenticationError)


class TestGetCurrentClinicianDependency:
    """Tests for get_current_clinician dependency."""

    @pytest.mark.asyncio
    async def test_get_current_clinician_valid_token(self):
        """Test getting current clinician with valid token."""
        auth_manager = AuthenticationManager(
            secret_key="test-secret-key",
            algorithm="HS256",
            expiration_hours=24,
        )

        token = auth_manager.create_access_token(
            clinician_id="CLIN-001",
            clinician_name="Dr. Smith",
            role="physician",
            care_units=["UNIT-001"],
        )

        # Mock HTTPAuthCredentials
        credentials = MagicMock()
        credentials.credentials = token

        # Patch auth_manager in the module
        with patch("mcp_server.security.auth.auth_manager", auth_manager):
            result = await get_current_clinician(credentials)

            assert result["id"] == "CLIN-001"
            assert result["name"] == "Dr. Smith"
            assert result["role"] == "physician"

    @pytest.mark.asyncio
    async def test_get_current_clinician_expired_token(self):
        """Test getting current clinician with expired token."""
        auth_manager = AuthenticationManager(
            secret_key="test-secret-key",
            algorithm="HS256",
            expiration_hours=24,
        )

        # Create expired token
        expired_token = auth_manager.create_access_token(
            clinician_id="CLIN-001",
            clinician_name="Dr. Smith",
            role="physician",
            expires_delta=timedelta(seconds=-1),
        )

        credentials = MagicMock()
        credentials.credentials = expired_token

        with patch("mcp_server.security.auth.auth_manager", auth_manager):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_clinician(credentials)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "expired" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_get_current_clinician_invalid_token(self):
        """Test getting current clinician with invalid token."""
        auth_manager = AuthenticationManager(
            secret_key="test-secret-key",
            algorithm="HS256",
            expiration_hours=24,
        )

        credentials = MagicMock()
        credentials.credentials = "invalid.token.here"

        with patch("mcp_server.security.auth.auth_manager", auth_manager):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_clinician(credentials)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
