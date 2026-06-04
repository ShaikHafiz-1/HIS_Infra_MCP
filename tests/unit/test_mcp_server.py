"""
Unit tests for MCP server implementation.

Tests cover tool registry, tool invocation, schema validation, and error handling.
"""

import pytest
from typing import Any, Dict

from mcp_server.mcp_server import MCPServer
from mcp_server.models.schemas import (
    MCPToolDefinition,
    ToolInputSchema,
    ToolInvocationRequest,
    ToolOutputSchema,
)
from mcp_server.utils.validators import ValidationError


@pytest.fixture
def mcp_server():
    """Create MCP server instance for testing."""
    return MCPServer(name="Test MCP Server")


@pytest.fixture
def sample_tool_definition():
    """Create sample tool definition for testing."""
    return MCPToolDefinition(
        name="test_tool",
        description="Test tool for unit testing",
        inputSchema=ToolInputSchema(
            type="object",
            properties={
                "patient_id": {"type": "string", "description": "Patient ID"},
                "include_details": {"type": "boolean", "description": "Include details"},
            },
            required=["patient_id"],
            additionalProperties=False,
        ),
        outputSchema=ToolOutputSchema(
            type="object",
            properties={
                "result": {"type": "string"},
                "status": {"type": "string"},
            },
            additionalProperties=False,
        ),
    )


@pytest.fixture
def sample_handler():
    """Create sample tool handler for testing."""
    async def handler(patient_id: str, include_details: bool = False) -> Dict[str, Any]:
        return {
            "result": f"Patient {patient_id}",
            "status": "success",
            "details": "included" if include_details else "excluded",
        }

    return handler


class TestMCPServerInitialization:
    """Tests for MCP server initialization."""

    def test_server_initialization(self, mcp_server):
        """Test MCP server initializes correctly."""
        assert mcp_server.name == "Test MCP Server"
        assert len(mcp_server.tools) == 0
        assert len(mcp_server.handlers) == 0
        assert mcp_server.invocation_count == 0
        assert mcp_server.error_count == 0

    def test_server_statistics(self, mcp_server):
        """Test server statistics are correct."""
        stats = mcp_server.get_statistics()
        assert stats["name"] == "Test MCP Server"
        assert stats["total_tools"] == 0
        assert stats["total_invocations"] == 0
        assert stats["total_errors"] == 0
        assert stats["error_rate"] == 0


class TestToolRegistry:
    """Tests for tool registry functionality."""

    def test_register_tool(self, mcp_server, sample_tool_definition, sample_handler):
        """Test registering a tool."""
        mcp_server.register_tool(sample_tool_definition, sample_handler)

        assert "test_tool" in mcp_server.tools
        assert mcp_server.tools["test_tool"].name == "test_tool"
        assert "test_tool" in mcp_server.handlers

    def test_register_duplicate_tool(self, mcp_server, sample_tool_definition, sample_handler):
        """Test registering duplicate tool raises error."""
        mcp_server.register_tool(sample_tool_definition, sample_handler)

        with pytest.raises(ValueError, match="already registered"):
            mcp_server.register_tool(sample_tool_definition, sample_handler)

    def test_unregister_tool(self, mcp_server, sample_tool_definition, sample_handler):
        """Test unregistering a tool."""
        mcp_server.register_tool(sample_tool_definition, sample_handler)
        assert "test_tool" in mcp_server.tools

        mcp_server.unregister_tool("test_tool")
        assert "test_tool" not in mcp_server.tools

    def test_unregister_nonexistent_tool(self, mcp_server):
        """Test unregistering nonexistent tool raises error."""
        with pytest.raises(ValueError, match="not registered"):
            mcp_server.unregister_tool("nonexistent_tool")

    def test_get_tool(self, mcp_server, sample_tool_definition, sample_handler):
        """Test getting tool definition."""
        mcp_server.register_tool(sample_tool_definition, sample_handler)

        tool = mcp_server.get_tool("test_tool")
        assert tool is not None
        assert tool.name == "test_tool"

    def test_get_nonexistent_tool(self, mcp_server):
        """Test getting nonexistent tool returns None."""
        tool = mcp_server.get_tool("nonexistent_tool")
        assert tool is None

    def test_list_tools(self, mcp_server, sample_tool_definition, sample_handler):
        """Test listing tools."""
        assert len(mcp_server.list_tools()) == 0

        mcp_server.register_tool(sample_tool_definition, sample_handler)
        tools = mcp_server.list_tools()

        assert len(tools) == 1
        assert tools[0].name == "test_tool"


class TestInputValidation:
    """Tests for input validation."""

    def test_validate_valid_input(self, mcp_server, sample_tool_definition, sample_handler):
        """Test validating valid input."""
        mcp_server.register_tool(sample_tool_definition, sample_handler)

        result = mcp_server.validate_input(
            "test_tool",
            {"patient_id": "PAT-123"},
        )
        assert result is True

    def test_validate_input_with_optional_field(self, mcp_server, sample_tool_definition, sample_handler):
        """Test validating input with optional field."""
        mcp_server.register_tool(sample_tool_definition, sample_handler)

        result = mcp_server.validate_input(
            "test_tool",
            {"patient_id": "PAT-123", "include_details": True},
        )
        assert result is True

    def test_validate_missing_required_field(self, mcp_server, sample_tool_definition, sample_handler):
        """Test validating input with missing required field."""
        mcp_server.register_tool(sample_tool_definition, sample_handler)

        with pytest.raises(ValidationError, match="Missing required argument"):
            mcp_server.validate_input("test_tool", {})

    def test_validate_invalid_field_type(self, mcp_server, sample_tool_definition, sample_handler):
        """Test validating input with invalid field type."""
        mcp_server.register_tool(sample_tool_definition, sample_handler)

        with pytest.raises(ValidationError, match="Invalid type"):
            mcp_server.validate_input(
                "test_tool",
                {"patient_id": 123},  # Should be string
            )

    def test_validate_unexpected_field(self, mcp_server, sample_tool_definition, sample_handler):
        """Test validating input with unexpected field."""
        mcp_server.register_tool(sample_tool_definition, sample_handler)

        with pytest.raises(ValidationError, match="Unexpected argument"):
            mcp_server.validate_input(
                "test_tool",
                {"patient_id": "PAT-123", "unexpected_field": "value"},
            )

    def test_validate_input_nonexistent_tool(self, mcp_server):
        """Test validating input for nonexistent tool."""
        with pytest.raises(ValidationError, match="not found"):
            mcp_server.validate_input("nonexistent_tool", {})


class TestOutputValidation:
    """Tests for output validation."""

    def test_validate_valid_output(self, mcp_server, sample_tool_definition, sample_handler):
        """Test validating valid output."""
        mcp_server.register_tool(sample_tool_definition, sample_handler)

        result = mcp_server.validate_output(
            "test_tool",
            {"result": "test", "status": "success"},
        )
        assert result is True

    def test_validate_invalid_output_type(self, mcp_server, sample_tool_definition, sample_handler):
        """Test validating output with invalid type."""
        mcp_server.register_tool(sample_tool_definition, sample_handler)

        with pytest.raises(ValidationError, match="Invalid output type"):
            mcp_server.validate_output("test_tool", "invalid")

    def test_validate_output_no_schema(self, mcp_server):
        """Test validating output when no schema defined."""
        tool_def = MCPToolDefinition(
            name="no_schema_tool",
            description="Tool without output schema",
            inputSchema=ToolInputSchema(
                type="object",
                properties={},
                required=[],
            ),
            outputSchema=None,
        )

        async def handler():
            return {"result": "test"}

        mcp_server.register_tool(tool_def, handler)

        # Should not raise error when no schema defined
        result = mcp_server.validate_output("no_schema_tool", {"result": "test"})
        assert result is True


class TestToolInvocation:
    """Tests for tool invocation."""

    @pytest.mark.asyncio
    async def test_invoke_tool_success(self, mcp_server, sample_tool_definition, sample_handler):
        """Test successful tool invocation."""
        mcp_server.register_tool(sample_tool_definition, sample_handler)

        request = ToolInvocationRequest(
            tool_name="test_tool",
            arguments={"patient_id": "PAT-123"},
        )

        response = await mcp_server.invoke_tool(request)

        assert response.success is True
        assert response.tool_name == "test_tool"
        assert response.result is not None
        assert response.result["result"] == "Patient PAT-123"
        assert response.error is None
        assert response.execution_time_ms > 0
        assert mcp_server.invocation_count == 1
        assert mcp_server.error_count == 0

    @pytest.mark.asyncio
    async def test_invoke_tool_with_optional_args(self, mcp_server, sample_tool_definition, sample_handler):
        """Test tool invocation with optional arguments."""
        mcp_server.register_tool(sample_tool_definition, sample_handler)

        request = ToolInvocationRequest(
            tool_name="test_tool",
            arguments={"patient_id": "PAT-123", "include_details": True},
        )

        response = await mcp_server.invoke_tool(request)

        assert response.success is True
        assert response.result["details"] == "included"

    @pytest.mark.asyncio
    async def test_invoke_tool_validation_error(self, mcp_server, sample_tool_definition, sample_handler):
        """Test tool invocation with validation error."""
        mcp_server.register_tool(sample_tool_definition, sample_handler)

        request = ToolInvocationRequest(
            tool_name="test_tool",
            arguments={},  # Missing required patient_id
        )

        response = await mcp_server.invoke_tool(request)

        assert response.success is False
        assert response.error is not None
        assert "Validation Error" in response.error
        assert mcp_server.invocation_count == 0
        assert mcp_server.error_count == 1

    @pytest.mark.asyncio
    async def test_invoke_nonexistent_tool(self, mcp_server):
        """Test invoking nonexistent tool."""
        request = ToolInvocationRequest(
            tool_name="nonexistent_tool",
            arguments={},
        )

        response = await mcp_server.invoke_tool(request)

        assert response.success is False
        assert response.error is not None
        assert mcp_server.error_count == 1


class TestTypeChecking:
    """Tests for type checking utility."""

    def test_check_string_type(self, mcp_server):
        """Test checking string type."""
        assert mcp_server._check_type("test", "string") is True
        assert mcp_server._check_type(123, "string") is False

    def test_check_number_type(self, mcp_server):
        """Test checking number type."""
        assert mcp_server._check_type(123, "number") is True
        assert mcp_server._check_type(123.45, "number") is True
        assert mcp_server._check_type("123", "number") is False

    def test_check_integer_type(self, mcp_server):
        """Test checking integer type."""
        assert mcp_server._check_type(123, "integer") is True
        assert mcp_server._check_type(123.45, "integer") is False

    def test_check_boolean_type(self, mcp_server):
        """Test checking boolean type."""
        assert mcp_server._check_type(True, "boolean") is True
        assert mcp_server._check_type(False, "boolean") is True
        assert mcp_server._check_type(1, "boolean") is False

    def test_check_array_type(self, mcp_server):
        """Test checking array type."""
        assert mcp_server._check_type([1, 2, 3], "array") is True
        assert mcp_server._check_type("test", "array") is False

    def test_check_object_type(self, mcp_server):
        """Test checking object type."""
        assert mcp_server._check_type({"key": "value"}, "object") is True
        assert mcp_server._check_type("test", "object") is False

    def test_check_null_type(self, mcp_server):
        """Test checking null type."""
        assert mcp_server._check_type(None, "null") is True
        assert mcp_server._check_type("test", "null") is False

    def test_check_unknown_type(self, mcp_server):
        """Test checking unknown type."""
        # Unknown types should return True (skip check)
        assert mcp_server._check_type("anything", "unknown_type") is True


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_handler_exception(self, mcp_server):
        """Test handling exception in tool handler."""
        tool_def = MCPToolDefinition(
            name="error_tool",
            description="Tool that raises exception",
            inputSchema=ToolInputSchema(
                type="object",
                properties={},
                required=[],
            ),
        )

        async def error_handler():
            raise RuntimeError("Test error")

        mcp_server.register_tool(tool_def, error_handler)

        request = ToolInvocationRequest(
            tool_name="error_tool",
            arguments={},
        )

        response = await mcp_server.invoke_tool(request)

        assert response.success is False
        assert "Execution Error" in response.error
        assert mcp_server.error_count == 1
