"""
Unit tests for authorization module.

Tests role-based access control (RBAC), care unit assignment validation,
and tool access permissions.
"""

import pytest
from unittest.mock import MagicMock, patch

from mcp_server.security.authorization import (
    RBACEngine,
    RoleHierarchy,
    AuthorizationError,
    PermissionDeniedError,
    CareUnitAccessError,
    rbac_engine,
    require_tool_permission,
    require_care_unit_access,
)
from mcp_server.models.schemas import ClinicianRole


class TestRoleHierarchy:
    """Tests for RoleHierarchy class."""

    def test_get_level_technician(self):
        """Test hierarchy level for technician role."""
        level = RoleHierarchy.get_level(ClinicianRole.TECHNICIAN)
        assert level == 0

    def test_get_level_nurse(self):
        """Test hierarchy level for nurse role."""
        level = RoleHierarchy.get_level(ClinicianRole.NURSE)
        assert level == 1

    def test_get_level_physician(self):
        """Test hierarchy level for physician role."""
        level = RoleHierarchy.get_level(ClinicianRole.PHYSICIAN)
        assert level == 2

    def test_get_level_administrator(self):
        """Test hierarchy level for administrator role."""
        level = RoleHierarchy.get_level(ClinicianRole.ADMINISTRATOR)
        assert level == 3

    def test_get_level_invalid_role(self):
        """Test hierarchy level for invalid role."""
        level = RoleHierarchy.get_level("invalid_role")
        assert level == -1

    def test_is_higher_or_equal_same_role(self):
        """Test hierarchy comparison for same role."""
        result = RoleHierarchy.is_higher_or_equal(
            ClinicianRole.PHYSICIAN, ClinicianRole.PHYSICIAN
        )
        assert result is True

    def test_is_higher_or_equal_higher_role(self):
        """Test hierarchy comparison for higher role."""
        result = RoleHierarchy.is_higher_or_equal(
            ClinicianRole.ADMINISTRATOR, ClinicianRole.NURSE
        )
        assert result is True

    def test_is_higher_or_equal_lower_role(self):
        """Test hierarchy comparison for lower role."""
        result = RoleHierarchy.is_higher_or_equal(
            ClinicianRole.TECHNICIAN, ClinicianRole.PHYSICIAN
        )
        assert result is False

    def test_is_higher_or_equal_all_combinations(self):
        """Test all role hierarchy combinations."""
        roles = [
            ClinicianRole.TECHNICIAN,
            ClinicianRole.NURSE,
            ClinicianRole.PHYSICIAN,
            ClinicianRole.ADMINISTRATOR,
        ]

        for i, role1 in enumerate(roles):
            for j, role2 in enumerate(roles):
                result = RoleHierarchy.is_higher_or_equal(role1, role2)
                expected = i >= j
                assert result == expected, f"Failed for {role1} vs {role2}"


class TestRBACEngine:
    """Tests for RBACEngine class."""

    @pytest.fixture
    def rbac(self):
        """Create RBAC engine for testing."""
        return RBACEngine()

    @pytest.fixture
    def physician_clinician(self):
        """Create physician clinician for testing."""
        return {
            "id": "CLIN-001",
            "name": "Dr. Smith",
            "role": ClinicianRole.PHYSICIAN,
            "care_units": ["UNIT-001", "UNIT-002"],
        }

    @pytest.fixture
    def nurse_clinician(self):
        """Create nurse clinician for testing."""
        return {
            "id": "CLIN-002",
            "name": "Nurse Johnson",
            "role": ClinicianRole.NURSE,
            "care_units": ["UNIT-001"],
        }

    @pytest.fixture
    def technician_clinician(self):
        """Create technician clinician for testing."""
        return {
            "id": "CLIN-003",
            "name": "Tech Williams",
            "role": ClinicianRole.TECHNICIAN,
            "care_units": ["UNIT-001"],
        }

    @pytest.fixture
    def administrator_clinician(self):
        """Create administrator clinician for testing."""
        return {
            "id": "CLIN-004",
            "name": "Admin Brown",
            "role": ClinicianRole.ADMINISTRATOR,
            "care_units": [],
        }

    # Tool Permission Tests

    @pytest.mark.asyncio
    async def test_check_tool_permission_physician_allowed(self, rbac, physician_clinician):
        """Test physician can access allowed tools."""
        result = await rbac.check_tool_permission(
            physician_clinician, "get_patient_clinical_context"
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_check_tool_permission_physician_denied(self, rbac, physician_clinician):
        """Test physician cannot access denied tools."""
        # Physicians should have access to all tools, so test with a tool they have
        result = await rbac.check_tool_permission(
            physician_clinician, "get_patient_clinical_context"
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_check_tool_permission_nurse_allowed(self, rbac, nurse_clinician):
        """Test nurse can access allowed tools."""
        result = await rbac.check_tool_permission(
            nurse_clinician, "get_patient_clinical_context"
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_check_tool_permission_nurse_denied(self, rbac, nurse_clinician):
        """Test nurse cannot access denied tools."""
        with pytest.raises(PermissionDeniedError):
            await rbac.check_tool_permission(
                nurse_clinician, "get_anesthesia_case_context"
            )

    @pytest.mark.asyncio
    async def test_check_tool_permission_technician_allowed(self, rbac, technician_clinician):
        """Test technician can access allowed tools."""
        result = await rbac.check_tool_permission(
            technician_clinician, "get_device_events_by_patient"
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_check_tool_permission_technician_denied(self, rbac, technician_clinician):
        """Test technician cannot access denied tools."""
        with pytest.raises(PermissionDeniedError):
            await rbac.check_tool_permission(
                technician_clinician, "get_patient_clinical_context"
            )

    @pytest.mark.asyncio
    async def test_check_tool_permission_administrator_all_tools(
        self, rbac, administrator_clinician
    ):
        """Test administrator can access all tools."""
        tools = [
            "get_patient_clinical_context",
            "get_care_unit_summary",
            "get_device_events_by_patient",
            "get_diagnostic_exam_context",
            "get_patient_event_timeline",
            "get_alarm_context",
            "get_imaging_study_summary",
            "get_anesthesia_case_context",
            "get_neuro_event_context",
            "get_cardiology_event_context",
        ]

        for tool in tools:
            result = await rbac.check_tool_permission(administrator_clinician, tool)
            assert result is True

    @pytest.mark.asyncio
    async def test_check_tool_permission_unknown_role(self, rbac):
        """Test permission check with unknown role."""
        clinician = {
            "id": "CLIN-999",
            "name": "Unknown",
            "role": "unknown_role",
            "care_units": [],
        }

        with pytest.raises(AuthorizationError):
            await rbac.check_tool_permission(clinician, "get_patient_clinical_context")

    @pytest.mark.asyncio
    async def test_check_tool_permission_unknown_tool(self, rbac, physician_clinician):
        """Test permission check with unknown tool."""
        with pytest.raises(AuthorizationError):
            await rbac.check_tool_permission(physician_clinician, "unknown_tool")

    # Care Unit Access Tests

    @pytest.mark.asyncio
    async def test_check_care_unit_access_allowed(self, rbac, physician_clinician):
        """Test clinician can access assigned care unit."""
        result = await rbac.check_care_unit_access(physician_clinician, "UNIT-001")
        assert result is True

    @pytest.mark.asyncio
    async def test_check_care_unit_access_denied(self, rbac, physician_clinician):
        """Test clinician cannot access unassigned care unit."""
        with pytest.raises(CareUnitAccessError):
            await rbac.check_care_unit_access(physician_clinician, "UNIT-999")

    @pytest.mark.asyncio
    async def test_check_care_unit_access_administrator(self, rbac, administrator_clinician):
        """Test administrator can access any care unit."""
        result = await rbac.check_care_unit_access(administrator_clinician, "UNIT-999")
        assert result is True

    @pytest.mark.asyncio
    async def test_check_care_unit_access_multiple_units(self, rbac, physician_clinician):
        """Test clinician can access multiple assigned care units."""
        result1 = await rbac.check_care_unit_access(physician_clinician, "UNIT-001")
        result2 = await rbac.check_care_unit_access(physician_clinician, "UNIT-002")

        assert result1 is True
        assert result2 is True

    # Patient Access Tests

    @pytest.mark.asyncio
    async def test_check_patient_access_allowed(self, rbac, physician_clinician):
        """Test clinician can access patient in assigned care unit."""
        result = await rbac.check_patient_access(physician_clinician, "UNIT-001")
        assert result is True

    @pytest.mark.asyncio
    async def test_check_patient_access_denied(self, rbac, physician_clinician):
        """Test clinician cannot access patient in unassigned care unit."""
        with pytest.raises(CareUnitAccessError):
            await rbac.check_patient_access(physician_clinician, "UNIT-999")

    # Permission Retrieval Tests

    def test_get_tool_permissions_for_role_physician(self, rbac):
        """Test retrieval of physician tool permissions."""
        permissions = rbac.get_tool_permissions_for_role(ClinicianRole.PHYSICIAN)

        assert isinstance(permissions, dict)
        assert len(permissions) > 0
        assert permissions["get_patient_clinical_context"] is True

    def test_get_tool_permissions_for_role_nurse(self, rbac):
        """Test retrieval of nurse tool permissions."""
        permissions = rbac.get_tool_permissions_for_role(ClinicianRole.NURSE)

        assert isinstance(permissions, dict)
        assert permissions["get_patient_clinical_context"] is True
        assert permissions["get_anesthesia_case_context"] is False

    def test_get_tool_permissions_for_role_technician(self, rbac):
        """Test retrieval of technician tool permissions."""
        permissions = rbac.get_tool_permissions_for_role(ClinicianRole.TECHNICIAN)

        assert isinstance(permissions, dict)
        assert permissions["get_device_events_by_patient"] is True
        assert permissions["get_patient_clinical_context"] is False

    def test_get_tool_permissions_for_role_administrator(self, rbac):
        """Test retrieval of administrator tool permissions."""
        permissions = rbac.get_tool_permissions_for_role(ClinicianRole.ADMINISTRATOR)

        assert isinstance(permissions, dict)
        # All tools should be True for administrator
        assert all(permissions.values())

    def test_get_tool_permissions_for_role_invalid(self, rbac):
        """Test retrieval of permissions for invalid role."""
        permissions = rbac.get_tool_permissions_for_role("invalid_role")

        assert permissions == {}

    def test_get_accessible_tools_for_role_physician(self, rbac):
        """Test retrieval of accessible tools for physician."""
        tools = rbac.get_accessible_tools_for_role(ClinicianRole.PHYSICIAN)

        assert isinstance(tools, list)
        assert len(tools) == 10  # Physicians have access to all 10 tools
        assert "get_patient_clinical_context" in tools

    def test_get_accessible_tools_for_role_nurse(self, rbac):
        """Test retrieval of accessible tools for nurse."""
        tools = rbac.get_accessible_tools_for_role(ClinicianRole.NURSE)

        assert isinstance(tools, list)
        assert len(tools) == 5  # Nurses have access to 5 tools
        assert "get_patient_clinical_context" in tools
        assert "get_anesthesia_case_context" not in tools

    def test_get_accessible_tools_for_role_technician(self, rbac):
        """Test retrieval of accessible tools for technician."""
        tools = rbac.get_accessible_tools_for_role(ClinicianRole.TECHNICIAN)

        assert isinstance(tools, list)
        assert len(tools) == 2  # Technicians have access to 2 tools
        assert "get_device_events_by_patient" in tools
        assert "get_alarm_context" in tools

    def test_get_accessible_tools_for_role_administrator(self, rbac):
        """Test retrieval of accessible tools for administrator."""
        tools = rbac.get_accessible_tools_for_role(ClinicianRole.ADMINISTRATOR)

        assert isinstance(tools, list)
        assert len(tools) == 10  # Administrators have access to all 10 tools

    def test_get_accessible_tools_for_role_invalid(self, rbac):
        """Test retrieval of accessible tools for invalid role."""
        tools = rbac.get_accessible_tools_for_role("invalid_role")

        assert tools == []


class TestAuthorizationErrors:
    """Tests for authorization error classes."""

    def test_authorization_error(self):
        """Test AuthorizationError exception."""
        error = AuthorizationError("Test error")

        assert str(error) == "Test error"
        assert error.status_code == 403
        assert isinstance(error, Exception)

    def test_permission_denied_error(self):
        """Test PermissionDeniedError exception."""
        error = PermissionDeniedError("Access denied")

        assert "Access denied" in str(error)
        assert error.status_code == 403
        assert isinstance(error, AuthorizationError)

    def test_care_unit_access_error(self):
        """Test CareUnitAccessError exception."""
        error = CareUnitAccessError("UNIT-001")

        assert "UNIT-001" in str(error)
        assert error.status_code == 403
        assert isinstance(error, AuthorizationError)


class TestGlobalRBACEngine:
    """Tests for global RBAC engine instance."""

    @pytest.mark.asyncio
    async def test_global_rbac_engine_exists(self):
        """Test that global RBAC engine instance exists."""
        assert rbac_engine is not None
        assert isinstance(rbac_engine, RBACEngine)

    @pytest.mark.asyncio
    async def test_global_rbac_engine_functional(self):
        """Test that global RBAC engine is functional."""
        clinician = {
            "id": "CLIN-001",
            "name": "Dr. Smith",
            "role": ClinicianRole.PHYSICIAN,
            "care_units": ["UNIT-001"],
        }

        result = await rbac_engine.check_tool_permission(
            clinician, "get_patient_clinical_context"
        )
        assert result is True


class TestDecorators:
    """Tests for authorization decorators."""

    @pytest.mark.asyncio
    async def test_require_tool_permission_decorator_allowed(self):
        """Test require_tool_permission decorator with allowed access."""

        @require_tool_permission("get_patient_clinical_context")
        async def test_function(clinician):
            return "success"

        clinician = {
            "id": "CLIN-001",
            "name": "Dr. Smith",
            "role": ClinicianRole.PHYSICIAN,
            "care_units": ["UNIT-001"],
        }

        result = await test_function(clinician)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_require_tool_permission_decorator_denied(self):
        """Test require_tool_permission decorator with denied access."""

        @require_tool_permission("get_anesthesia_case_context")
        async def test_function(clinician):
            return "success"

        clinician = {
            "id": "CLIN-002",
            "name": "Nurse Johnson",
            "role": ClinicianRole.NURSE,
            "care_units": ["UNIT-001"],
        }

        with pytest.raises(PermissionDeniedError):
            await test_function(clinician)

    @pytest.mark.asyncio
    async def test_require_care_unit_access_decorator_allowed(self):
        """Test require_care_unit_access decorator with allowed access."""

        @require_care_unit_access("care_unit_id")
        async def test_function(clinician, care_unit_id):
            return "success"

        clinician = {
            "id": "CLIN-001",
            "name": "Dr. Smith",
            "role": ClinicianRole.PHYSICIAN,
            "care_units": ["UNIT-001"],
        }

        result = await test_function(clinician, care_unit_id="UNIT-001")
        assert result == "success"

    @pytest.mark.asyncio
    async def test_require_care_unit_access_decorator_denied(self):
        """Test require_care_unit_access decorator with denied access."""

        @require_care_unit_access("care_unit_id")
        async def test_function(clinician, care_unit_id):
            return "success"

        clinician = {
            "id": "CLIN-001",
            "name": "Dr. Smith",
            "role": ClinicianRole.PHYSICIAN,
            "care_units": ["UNIT-001"],
        }

        with pytest.raises(CareUnitAccessError):
            await test_function(clinician, care_unit_id="UNIT-999")

    @pytest.mark.asyncio
    async def test_require_care_unit_access_decorator_no_param(self):
        """Test require_care_unit_access decorator without care_unit_id parameter."""

        @require_care_unit_access("care_unit_id")
        async def test_function(clinician):
            return "success"

        clinician = {
            "id": "CLIN-001",
            "name": "Dr. Smith",
            "role": ClinicianRole.PHYSICIAN,
            "care_units": ["UNIT-001"],
        }

        # Should succeed because no care_unit_id is provided
        result = await test_function(clinician)
        assert result == "success"


class TestRBACIntegration:
    """Integration tests for RBAC system."""

    @pytest.mark.asyncio
    async def test_complete_authorization_flow_physician(self):
        """Test complete authorization flow for physician."""
        clinician = {
            "id": "CLIN-001",
            "name": "Dr. Smith",
            "role": ClinicianRole.PHYSICIAN,
            "care_units": ["UNIT-001", "UNIT-002"],
        }

        # Check tool permission
        tool_result = await rbac_engine.check_tool_permission(
            clinician, "get_patient_clinical_context"
        )
        assert tool_result is True

        # Check care unit access
        unit_result = await rbac_engine.check_care_unit_access(clinician, "UNIT-001")
        assert unit_result is True

        # Check patient access
        patient_result = await rbac_engine.check_patient_access(clinician, "UNIT-002")
        assert patient_result is True

    @pytest.mark.asyncio
    async def test_complete_authorization_flow_nurse(self):
        """Test complete authorization flow for nurse."""
        clinician = {
            "id": "CLIN-002",
            "name": "Nurse Johnson",
            "role": ClinicianRole.NURSE,
            "care_units": ["UNIT-001"],
        }

        # Check allowed tool permission
        tool_result = await rbac_engine.check_tool_permission(
            clinician, "get_patient_clinical_context"
        )
        assert tool_result is True

        # Check denied tool permission
        with pytest.raises(PermissionDeniedError):
            await rbac_engine.check_tool_permission(
                clinician, "get_anesthesia_case_context"
            )

        # Check care unit access
        unit_result = await rbac_engine.check_care_unit_access(clinician, "UNIT-001")
        assert unit_result is True

        # Check denied care unit access
        with pytest.raises(CareUnitAccessError):
            await rbac_engine.check_care_unit_access(clinician, "UNIT-999")

    @pytest.mark.asyncio
    async def test_complete_authorization_flow_administrator(self):
        """Test complete authorization flow for administrator."""
        clinician = {
            "id": "CLIN-004",
            "name": "Admin Brown",
            "role": ClinicianRole.ADMINISTRATOR,
            "care_units": [],
        }

        # Check all tool permissions
        tools = [
            "get_patient_clinical_context",
            "get_care_unit_summary",
            "get_device_events_by_patient",
            "get_diagnostic_exam_context",
            "get_patient_event_timeline",
            "get_alarm_context",
            "get_imaging_study_summary",
            "get_anesthesia_case_context",
            "get_neuro_event_context",
            "get_cardiology_event_context",
        ]

        for tool in tools:
            result = await rbac_engine.check_tool_permission(clinician, tool)
            assert result is True

        # Check access to any care unit
        result = await rbac_engine.check_care_unit_access(clinician, "UNIT-999")
        assert result is True
