"""
Authorization module for Hospital Clinical Intelligence MCP Platform.

This module provides role-based access control (RBAC) for MCP tools and care unit access.
It enforces role hierarchies, tool permissions, and care unit assignments.
"""

import logging
from typing import Dict, List, Optional

from mcp_server.models.schemas import ClinicianRole
from mcp_server.utils.logger import get_logger

logger = get_logger(__name__)


class AuthorizationError(Exception):
    """Authorization failed."""

    def __init__(self, message: str = "Authorization failed"):
        self.message = message
        self.status_code = 403
        super().__init__(self.message)


class PermissionDeniedError(AuthorizationError):
    """Permission denied for requested action."""

    def __init__(self, message: str = "Permission denied"):
        super().__init__(message)


class CareUnitAccessError(AuthorizationError):
    """Clinician not assigned to requested care unit."""

    def __init__(self, care_unit_id: str):
        super().__init__(f"Not assigned to care unit: {care_unit_id}")


class RoleHierarchy:
    """Defines role hierarchy for authorization checks."""

    # Role hierarchy: higher index = higher privilege
    HIERARCHY = {
        ClinicianRole.TECHNICIAN: 0,
        ClinicianRole.NURSE: 1,
        ClinicianRole.PHYSICIAN: 2,
        ClinicianRole.ADMINISTRATOR: 3,
    }

    @classmethod
    def get_level(cls, role: str) -> int:
        """
        Get hierarchy level for a role.

        Args:
            role: Role name

        Returns:
            int: Hierarchy level (higher = more privileged)
        """
        return cls.HIERARCHY.get(role, -1)

    @classmethod
    def is_higher_or_equal(cls, role1: str, role2: str) -> bool:
        """
        Check if role1 has equal or higher privilege than role2.

        Args:
            role1: First role
            role2: Second role

        Returns:
            bool: True if role1 >= role2 in hierarchy
        """
        return cls.get_level(role1) >= cls.get_level(role2)


class RBACEngine:
    """Role-Based Access Control engine for MCP tools."""

    # Tool permissions by role
    ROLE_PERMISSIONS = {
        ClinicianRole.PHYSICIAN: {
            "get_patient_clinical_context": True,
            "get_care_unit_summary": True,
            "get_device_events_by_patient": True,
            "get_diagnostic_exam_context": True,
            "get_patient_event_timeline": True,
            "get_alarm_context": True,
            "get_imaging_study_summary": True,
            "get_anesthesia_case_context": True,
            "get_neuro_event_context": True,
            "get_cardiology_event_context": True,
        },
        ClinicianRole.NURSE: {
            "get_patient_clinical_context": True,
            "get_care_unit_summary": True,
            "get_device_events_by_patient": True,
            "get_alarm_context": True,
            "get_patient_event_timeline": True,
            "get_diagnostic_exam_context": False,
            "get_imaging_study_summary": False,
            "get_anesthesia_case_context": False,
            "get_neuro_event_context": False,
            "get_cardiology_event_context": False,
        },
        ClinicianRole.TECHNICIAN: {
            "get_patient_clinical_context": False,
            "get_care_unit_summary": False,
            "get_device_events_by_patient": True,
            "get_alarm_context": True,
            "get_patient_event_timeline": False,
            "get_diagnostic_exam_context": False,
            "get_imaging_study_summary": False,
            "get_anesthesia_case_context": False,
            "get_neuro_event_context": False,
            "get_cardiology_event_context": False,
        },
        ClinicianRole.ADMINISTRATOR: {
            "get_patient_clinical_context": True,
            "get_care_unit_summary": True,
            "get_device_events_by_patient": True,
            "get_diagnostic_exam_context": True,
            "get_patient_event_timeline": True,
            "get_alarm_context": True,
            "get_imaging_study_summary": True,
            "get_anesthesia_case_context": True,
            "get_neuro_event_context": True,
            "get_cardiology_event_context": True,
        },
    }

    async def check_tool_permission(
        self, clinician: Dict, tool_name: str
    ) -> bool:
        """
        Check if clinician has permission to use a tool.

        Args:
            clinician: Clinician identity dict with 'role' key
            tool_name: Name of the tool to check

        Returns:
            bool: True if permission granted

        Raises:
            PermissionDeniedError: If permission denied
            AuthorizationError: If role not recognized
        """
        role = clinician.get("role")

        if role not in self.ROLE_PERMISSIONS:
            logger.warning(f"Unknown role: {role}")
            raise AuthorizationError(f"Unknown role: {role}")

        permissions = self.ROLE_PERMISSIONS[role]

        if tool_name not in permissions:
            logger.warning(
                f"Unknown tool: {tool_name} for role: {role}"
            )
            raise AuthorizationError(f"Unknown tool: {tool_name}")

        has_permission = permissions[tool_name]

        if not has_permission:
            logger.warning(
                f"Permission denied: clinician {clinician.get('id')} "
                f"(role={role}) cannot access tool {tool_name}"
            )
            raise PermissionDeniedError(
                f"Role {role} cannot access tool {tool_name}"
            )

        logger.debug(
            f"Permission granted: clinician {clinician.get('id')} "
            f"(role={role}) can access tool {tool_name}"
        )
        return True

    async def check_care_unit_access(
        self, clinician: Dict, care_unit_id: str
    ) -> bool:
        """
        Check if clinician has access to a care unit.

        Args:
            clinician: Clinician identity dict with 'care_units' key
            care_unit_id: ID of the care unit to check

        Returns:
            bool: True if access granted

        Raises:
            CareUnitAccessError: If clinician not assigned to care unit
        """
        assigned_units = clinician.get("care_units", [])

        # Administrators have access to all care units
        if clinician.get("role") == ClinicianRole.ADMINISTRATOR:
            logger.debug(
                f"Administrator {clinician.get('id')} has access to all care units"
            )
            return True

        if care_unit_id not in assigned_units:
            logger.warning(
                f"Care unit access denied: clinician {clinician.get('id')} "
                f"not assigned to care unit {care_unit_id}"
            )
            raise CareUnitAccessError(care_unit_id)

        logger.debug(
            f"Care unit access granted: clinician {clinician.get('id')} "
            f"assigned to care unit {care_unit_id}"
        )
        return True

    async def check_patient_access(
        self, clinician: Dict, patient_care_unit: str
    ) -> bool:
        """
        Check if clinician can access a patient based on care unit assignment.

        Args:
            clinician: Clinician identity dict
            patient_care_unit: Care unit where patient is located

        Returns:
            bool: True if access granted

        Raises:
            CareUnitAccessError: If clinician not assigned to patient's care unit
        """
        return await self.check_care_unit_access(clinician, patient_care_unit)

    def get_tool_permissions_for_role(self, role: str) -> Dict[str, bool]:
        """
        Get all tool permissions for a role.

        Args:
            role: Role name

        Returns:
            dict: Tool permissions for the role
        """
        return self.ROLE_PERMISSIONS.get(role, {})

    def get_accessible_tools_for_role(self, role: str) -> List[str]:
        """
        Get list of tools accessible by a role.

        Args:
            role: Role name

        Returns:
            list: Names of accessible tools
        """
        permissions = self.get_tool_permissions_for_role(role)
        return [tool for tool, allowed in permissions.items() if allowed]


# Global RBAC engine instance
rbac_engine = RBACEngine()


class AuthorizationManager:
    """
    Synchronous authorization checks for testing and middleware use.

    Wraps RBACEngine logic without async and returns bool instead of raising.
    """

    def check_tool_access(self, clinician: Dict, tool_name: str) -> bool:
        """Return True if clinician's role permits tool access, False otherwise."""
        role = clinician.get("role")
        permissions = RBACEngine.ROLE_PERMISSIONS.get(role)
        if permissions is None:
            return False
        return bool(permissions.get(tool_name, False))

    def check_care_unit_access(self, clinician: Dict, care_unit_id: str) -> bool:
        """Return True if clinician is assigned to care_unit_id (admins always True)."""
        if clinician.get("role") == ClinicianRole.ADMINISTRATOR:
            return True
        return care_unit_id in clinician.get("care_units", [])


def require_tool_permission(tool_name: str):
    """
    Decorator to enforce tool permission checks.

    Args:
        tool_name: Name of the tool being protected

    Returns:
        function: Decorator function
    """

    def decorator(func):
        async def wrapper(clinician: Dict, *args, **kwargs):
            await rbac_engine.check_tool_permission(clinician, tool_name)
            return await func(clinician, *args, **kwargs)

        return wrapper

    return decorator


def require_care_unit_access(care_unit_param: str = "care_unit_id"):
    """
    Decorator to enforce care unit access checks.

    Args:
        care_unit_param: Name of the parameter containing care unit ID

    Returns:
        function: Decorator function
    """

    def decorator(func):
        async def wrapper(clinician: Dict, *args, **kwargs):
            care_unit_id = kwargs.get(care_unit_param)
            if care_unit_id:
                await rbac_engine.check_care_unit_access(clinician, care_unit_id)
            return await func(clinician, *args, **kwargs)

        return wrapper

    return decorator
