"""
MCP Server implementation for Hospital Clinical Intelligence Platform.

This module implements the core MCP server functionality including tool registry,
tool execution, input/output validation, and request/response handling.
"""

import time
from typing import Any, Callable, Dict, List, Optional

from mcp_server.models.schemas import (
    MCPToolDefinition,
    ToolInvocationRequest,
    ToolInvocationResponse,
    ToolInputSchema,
    ToolOutputSchema,
)
from mcp_server.utils.logger import get_logger
from mcp_server.utils.validators import ValidationError

logger = get_logger(__name__)


class MCPServer:
    """
    MCP Server implementation for managing tools and handling invocations.

    This class manages the tool registry, validates inputs/outputs, and
    executes tool handlers with proper error handling and logging.
    """

    def __init__(self, name: str = "Hospital Clinical Intelligence MCP Server"):
        """
        Initialize MCP Server.

        Args:
            name: Server name
        """
        self.name = name
        self.tools: Dict[str, MCPToolDefinition] = {}
        self.handlers: Dict[str, Callable] = {}
        self.invocation_count = 0
        self.error_count = 0

        logger.info(f"Initializing MCP Server: {name}")

    def register_tool(
        self,
        tool_definition: MCPToolDefinition,
        handler: Callable,
    ) -> None:
        """
        Register an MCP tool with its handler.

        Args:
            tool_definition: Tool definition with name, description, and schemas
            handler: Async callable that handles tool invocation

        Raises:
            ValueError: If tool name is already registered
        """
        if tool_definition.name in self.tools:
            raise ValueError(f"Tool '{tool_definition.name}' is already registered")

        self.tools[tool_definition.name] = tool_definition
        self.handlers[tool_definition.name] = handler

        logger.info(f"Registered tool: {tool_definition.name}")

    def unregister_tool(self, tool_name: str) -> None:
        """
        Unregister an MCP tool.

        Args:
            tool_name: Name of tool to unregister

        Raises:
            ValueError: If tool is not registered
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' is not registered")

        del self.tools[tool_name]
        del self.handlers[tool_name]

        logger.info(f"Unregistered tool: {tool_name}")

    def get_tool(self, tool_name: str) -> Optional[MCPToolDefinition]:
        """
        Get tool definition by name.

        Args:
            tool_name: Name of tool

        Returns:
            MCPToolDefinition if found, None otherwise
        """
        return self.tools.get(tool_name)

    def list_tools(self) -> List[MCPToolDefinition]:
        """
        List all registered tools.

        Returns:
            List of tool definitions
        """
        return list(self.tools.values())

    def validate_input(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> bool:
        """
        Validate tool input arguments against schema.

        Args:
            tool_name: Name of tool
            arguments: Input arguments to validate

        Returns:
            True if valid

        Raises:
            ValidationError: If validation fails
        """
        tool = self.get_tool(tool_name)
        if not tool:
            raise ValidationError(f"Tool '{tool_name}' not found")

        input_schema = tool.inputSchema

        # Check required fields
        for required_field in input_schema.required:
            if required_field not in arguments:
                raise ValidationError(
                    f"Missing required argument: {required_field}"
                )

        # Check field types
        for field_name, field_value in arguments.items():
            if field_name not in input_schema.properties:
                if not input_schema.additionalProperties:
                    raise ValidationError(
                        f"Unexpected argument: {field_name}"
                    )
                continue

            field_schema = input_schema.properties[field_name]
            expected_type = field_schema.get("type")

            if expected_type and not self._check_type(field_value, expected_type):
                raise ValidationError(
                    f"Invalid type for argument '{field_name}': "
                    f"expected {expected_type}, got {type(field_value).__name__}"
                )

        return True

    def validate_output(
        self,
        tool_name: str,
        result: Dict[str, Any],
    ) -> bool:
        """
        Validate tool output against schema.

        Args:
            tool_name: Name of tool
            result: Output result to validate

        Returns:
            True if valid

        Raises:
            ValidationError: If validation fails
        """
        tool = self.get_tool(tool_name)
        if not tool or not tool.outputSchema:
            # No output schema defined, skip validation
            return True

        output_schema = tool.outputSchema

        # Check output type
        if output_schema.type == "object" and not isinstance(result, dict):
            raise ValidationError(
                f"Invalid output type: expected object, got {type(result).__name__}"
            )

        return True

    async def invoke_tool(
        self,
        request: ToolInvocationRequest,
    ) -> ToolInvocationResponse:
        """
        Invoke an MCP tool with input validation and error handling.

        Args:
            request: Tool invocation request

        Returns:
            Tool invocation response

        Raises:
            ValidationError: If input validation fails
        """
        tool_name = request.tool_name
        arguments = request.arguments
        start_time = time.time()

        try:
            # Validate input
            self.validate_input(tool_name, arguments)

            # Get handler
            handler = self.handlers.get(tool_name)
            if not handler:
                raise ValueError(f"No handler registered for tool '{tool_name}'")

            # Execute handler
            logger.debug(f"Invoking tool: {tool_name} with arguments: {arguments}")
            result = await handler(**arguments)

            # Validate output
            self.validate_output(tool_name, result)

            # Calculate execution time
            execution_time_ms = (time.time() - start_time) * 1000

            self.invocation_count += 1

            logger.info(
                f"Tool invocation succeeded: {tool_name} "
                f"(execution_time={execution_time_ms:.2f}ms)"
            )

            return ToolInvocationResponse(
                success=True,
                tool_name=tool_name,
                result=result,
                error=None,
                execution_time_ms=execution_time_ms,
            )

        except ValidationError as e:
            execution_time_ms = (time.time() - start_time) * 1000
            self.error_count += 1

            logger.warning(
                f"Tool invocation validation error: {tool_name} - {str(e)}"
            )

            return ToolInvocationResponse(
                success=False,
                tool_name=tool_name,
                result=None,
                error=f"Validation Error: {str(e)}",
                execution_time_ms=execution_time_ms,
            )

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            self.error_count += 1

            logger.error(
                f"Tool invocation error: {tool_name} - {str(e)}",
                exc_info=True,
            )

            return ToolInvocationResponse(
                success=False,
                tool_name=tool_name,
                result=None,
                error=f"Execution Error: {str(e)}",
                execution_time_ms=execution_time_ms,
            )

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get server statistics.

        Returns:
            Dictionary with server statistics
        """
        return {
            "name": self.name,
            "total_tools": len(self.tools),
            "total_invocations": self.invocation_count,
            "total_errors": self.error_count,
            "error_rate": (
                self.error_count / self.invocation_count
                if self.invocation_count > 0
                else 0
            ),
        }

    @staticmethod
    def _check_type(value: Any, expected_type: str) -> bool:
        """
        Check if value matches expected JSON schema type.

        Args:
            value: Value to check
            expected_type: Expected JSON schema type

        Returns:
            True if type matches
        """
        type_mapping = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None),
        }

        expected_python_type = type_mapping.get(expected_type)
        if expected_python_type is None:
            return True  # Unknown type, skip check

        return isinstance(value, expected_python_type)
