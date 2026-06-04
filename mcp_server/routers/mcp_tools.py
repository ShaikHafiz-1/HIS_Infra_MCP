"""
FastAPI router for MCP tool endpoints.

This module provides REST API endpoints for tool invocation, listing, and schema retrieval.
"""

import time
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from config import settings
from mcp_server.models.schemas import (
    ErrorResponse,
    MCPToolDefinition,
    ToolInvocationRequest,
    ToolInvocationResponse,
    ToolListResponse,
    ToolInputSchema,
    ToolOutputSchema,
)
from mcp_server.mcp_server import MCPServer
from mcp_server.utils.logger import get_logger
from mcp_server.utils.validators import ValidationError

logger = get_logger(__name__)

# Global MCP server instance (will be set by main.py)
_mcp_server: MCPServer = None


def get_mcp_server() -> MCPServer:
    """
    Get the global MCP server instance.

    Returns:
        MCPServer: Global MCP server instance

    Raises:
        HTTPException: If MCP server is not initialized
    """
    if _mcp_server is None:
        logger.error("MCP server not initialized")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP server not initialized",
        )
    return _mcp_server


def set_mcp_server(server: MCPServer) -> None:
    """
    Set the global MCP server instance.

    Args:
        server: MCPServer instance to set
    """
    global _mcp_server
    _mcp_server = server
    logger.info("MCP server instance set")


# Create router
router = APIRouter(prefix="/api/v1/tools", tags=["MCP Tools"])


@router.post(
    "/invoke",
    response_model=ToolInvocationResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        404: {"model": ErrorResponse, "description": "Tool not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def invoke_tool(
    request: ToolInvocationRequest,
    http_request: Request,
    mcp_server: MCPServer = Depends(get_mcp_server),
) -> ToolInvocationResponse:
    """
    Invoke an MCP tool.

    Args:
        request: Tool invocation request
        http_request: HTTP request object
        mcp_server: MCP server instance

    Returns:
        ToolInvocationResponse: Tool invocation result

    Raises:
        HTTPException: If tool not found or invocation fails
    """
    try:
        # Check if tool exists
        tool = mcp_server.get_tool(request.tool_name)
        if not tool:
            logger.warning(f"Tool not found: {request.tool_name}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tool '{request.tool_name}' not found",
            )

        # Invoke tool with performance tracking
        t0 = time.monotonic()
        response = await mcp_server.invoke_tool(request)
        elapsed_ms = (time.monotonic() - t0) * 1000

        try:
            from mcp_server.utils.performance import performance_monitor
            performance_monitor.record_tool_call(
                request.tool_name, elapsed_ms, response.success
            )
        except Exception:
            pass

        logger.info(
            f"Tool invoked: {request.tool_name} - "
            f"Success: {response.success} - "
            f"Time: {elapsed_ms:.2f}ms"
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error invoking tool: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/list",
    response_model=ToolListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def list_tools(
    mcp_server: MCPServer = Depends(get_mcp_server),
) -> ToolListResponse:
    """
    List all available MCP tools.

    Args:
        mcp_server: MCP server instance

    Returns:
        ToolListResponse: List of available tools

    Raises:
        HTTPException: If listing fails
    """
    try:
        tools = mcp_server.list_tools()
        logger.debug(f"Listed {len(tools)} tools")

        return ToolListResponse(
            tools=tools,
            total_count=len(tools),
        )

    except Exception as e:
        logger.error(f"Error listing tools: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/{tool_name}/schema",
    response_model=MCPToolDefinition,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse, "description": "Tool not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_tool_schema(
    tool_name: str,
    mcp_server: MCPServer = Depends(get_mcp_server),
) -> MCPToolDefinition:
    """
    Get schema for a specific MCP tool.

    Args:
        tool_name: Name of the tool
        mcp_server: MCP server instance

    Returns:
        MCPToolDefinition: Tool definition with schema

    Raises:
        HTTPException: If tool not found
    """
    try:
        tool = mcp_server.get_tool(tool_name)
        if not tool:
            logger.warning(f"Tool schema not found: {tool_name}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tool '{tool_name}' not found",
            )

        logger.debug(f"Retrieved schema for tool: {tool_name}")
        return tool

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tool schema: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/{tool_name}/input-schema",
    response_model=ToolInputSchema,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse, "description": "Tool not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_tool_input_schema(
    tool_name: str,
    mcp_server: MCPServer = Depends(get_mcp_server),
) -> ToolInputSchema:
    """
    Get input schema for a specific MCP tool.

    Args:
        tool_name: Name of the tool
        mcp_server: MCP server instance

    Returns:
        ToolInputSchema: Input schema for the tool

    Raises:
        HTTPException: If tool not found
    """
    try:
        tool = mcp_server.get_tool(tool_name)
        if not tool:
            logger.warning(f"Tool input schema not found: {tool_name}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tool '{tool_name}' not found",
            )

        logger.debug(f"Retrieved input schema for tool: {tool_name}")
        return tool.inputSchema

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tool input schema: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/{tool_name}/output-schema",
    response_model=ToolOutputSchema,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse, "description": "Tool not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_tool_output_schema(
    tool_name: str,
    mcp_server: MCPServer = Depends(get_mcp_server),
) -> ToolOutputSchema:
    """
    Get output schema for a specific MCP tool.

    Args:
        tool_name: Name of the tool
        mcp_server: MCP server instance

    Returns:
        ToolOutputSchema: Output schema for the tool

    Raises:
        HTTPException: If tool not found or no output schema defined
    """
    try:
        tool = mcp_server.get_tool(tool_name)
        if not tool:
            logger.warning(f"Tool output schema not found: {tool_name}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tool '{tool_name}' not found",
            )

        if not tool.outputSchema:
            logger.warning(f"No output schema defined for tool: {tool_name}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No output schema defined for tool '{tool_name}'",
            )

        logger.debug(f"Retrieved output schema for tool: {tool_name}")
        return tool.outputSchema

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tool output schema: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/stats",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_tool_statistics(
    mcp_server: MCPServer = Depends(get_mcp_server),
) -> Dict[str, Any]:
    """
    Get MCP server statistics.

    Args:
        mcp_server: MCP server instance

    Returns:
        Dictionary with server statistics

    Raises:
        HTTPException: If retrieval fails
    """
    try:
        stats = mcp_server.get_statistics()
        logger.debug("Retrieved MCP server statistics")
        return stats

    except Exception as e:
        logger.error(f"Error getting tool statistics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
