"""
Test credentials for development and testing.

This module provides test clinician credentials for development and testing purposes.
In production, credentials should be managed through the hospital identity provider.
"""

from typing import Dict, List, Optional

# Test clinician credentials for development
TEST_CREDENTIALS = {
    "dr_smith": {
        "password": "test_password_123",
        "clinician_id": "CLIN-00000001-0000-0000-0000-000000000001",
        "name": "Dr. Sarah Smith",
        "role": "physician",
        "care_units": [
            "UNIT-00000001-0000-0000-0000-000000000001",  # Cardiology
            "UNIT-00000002-0000-0000-0000-000000000002",  # ICU
        ],
    },
    "nurse_johnson": {
        "password": "test_password_456",
        "clinician_id": "CLIN-00000002-0000-0000-0000-000000000002",
        "name": "Nurse John Johnson",
        "role": "nurse",
        "care_units": [
            "UNIT-00000002-0000-0000-0000-000000000002",  # ICU
        ],
    },
    "tech_williams": {
        "password": "test_password_789",
        "clinician_id": "CLIN-00000003-0000-0000-0000-000000000003",
        "name": "Tech Mike Williams",
        "role": "technician",
        "care_units": [
            "UNIT-00000001-0000-0000-0000-000000000001",  # Cardiology
            "UNIT-00000002-0000-0000-0000-000000000002",  # ICU
        ],
    },
    "admin_brown": {
        "password": "test_password_admin",
        "clinician_id": "CLIN-00000004-0000-0000-0000-000000000004",
        "name": "Admin Jane Brown",
        "role": "administrator",
        "care_units": [
            "UNIT-00000001-0000-0000-0000-000000000001",  # Cardiology
            "UNIT-00000002-0000-0000-0000-000000000002",  # ICU
            "UNIT-00000003-0000-0000-0000-000000000003",  # ED
        ],
    },
}


class CredentialValidator:
    """Validates test credentials for development and testing."""

    @staticmethod
    def validate_credentials(username: str, password: str) -> Optional[Dict]:
        """
        Validate test credentials.

        Args:
            username: Username to validate
            password: Password to validate

        Returns:
            dict: Clinician information if credentials are valid, None otherwise
        """
        if username not in TEST_CREDENTIALS:
            return None

        credential = TEST_CREDENTIALS[username]

        if credential["password"] != password:
            return None

        return {
            "id": credential["clinician_id"],
            "name": credential["name"],
            "role": credential["role"],
            "care_units": credential["care_units"],
        }

    @staticmethod
    def get_clinician_by_id(clinician_id: str) -> Optional[Dict]:
        """
        Get clinician information by ID.

        Args:
            clinician_id: Clinician ID to look up

        Returns:
            dict: Clinician information if found, None otherwise
        """
        for credential in TEST_CREDENTIALS.values():
            if credential["clinician_id"] == clinician_id:
                return {
                    "id": credential["clinician_id"],
                    "name": credential["name"],
                    "role": credential["role"],
                    "care_units": credential["care_units"],
                }
        return None

    @staticmethod
    def get_all_test_usernames() -> List[str]:
        """
        Get list of all test usernames.

        Returns:
            list: List of test usernames
        """
        return list(TEST_CREDENTIALS.keys())

    @staticmethod
    def get_test_credentials_by_role(role: str) -> List[Dict]:
        """
        Get test credentials for a specific role.

        Args:
            role: Role to filter by (physician, nurse, technician, administrator)

        Returns:
            list: List of test credentials for the role
        """
        credentials = []
        for username, credential in TEST_CREDENTIALS.items():
            if credential["role"] == role:
                credentials.append(
                    {
                        "username": username,
                        "password": credential["password"],
                        "clinician_id": credential["clinician_id"],
                        "name": credential["name"],
                        "role": credential["role"],
                        "care_units": credential["care_units"],
                    }
                )
        return credentials
