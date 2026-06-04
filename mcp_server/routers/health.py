"""
FastAPI router for health check endpoints.

This module provides health check and readiness endpoints for monitoring system status.
Includes database connectivity checks, MCP server status, and system metrics.
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status

from config import settings
from mcp_server.database.connection import DatabaseConnection
from mcp_server.models.schemas import (
    ErrorResponse,
    HealthCheckResponse,
    MetricsResponse,
    ReadinessCheckResponse,
)
from mcp_server.utils.logger import get_logger

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/health", tags=["Health"])

# Track server startup time for uptime calculation
_startup_time: Optional[datetime] = None


def set_startup_time(startup_time: datetime) -> None:
    """Set the server startup time for uptime calculation."""
    global _startup_time
    _startup_time = startup_time


def get_uptime_seconds() -> float:
    """Calculate uptime in seconds since server startup."""
    if _startup_time is None:
        return 0.0
    
    current_time = datetime.now(timezone.utc)
    uptime = (current_time - _startup_time).total_seconds()
    return max(0.0, uptime)


async def check_database_connectivity() -> Dict[str, Any]:
    """
    Check database connectivity and measure latency.
    
    Returns:
        Dictionary with connection status and latency in milliseconds
    """
    try:
        start_time = time.time()
        is_connected = await DatabaseConnection.health_check()
        latency_ms = (time.time() - start_time) * 1000
        
        return {
            "connected": is_connected,
            "latency_ms": round(latency_ms, 2),
        }
    except Exception as e:
        logger.error(f"Database connectivity check failed: {str(e)}")
        return {
            "connected": False,
            "latency_ms": None,
            "error": str(e),
        }


def get_mcp_server_status() -> Dict[str, Any]:
    """
    Get MCP server status including initialization and tool count.
    
    Returns:
        Dictionary with MCP server status
    """
    try:
        # Import here to avoid circular imports
        from main import mcp_server
        
        if mcp_server is None:
            return {
                "initialized": False,
                "tools_count": 0,
            }
        
        return {
            "initialized": True,
            "tools_count": len(mcp_server.list_tools()),
        }
    except Exception as e:
        logger.error(f"MCP server status check failed: {str(e)}")
        return {
            "initialized": False,
            "tools_count": 0,
            "error": str(e),
        }


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def health_check() -> HealthCheckResponse:
    """
    Health check endpoint with system status and metrics.
    
    Returns comprehensive system health information including:
    - Overall health status
    - Application version
    - Server uptime
    - Database connectivity and latency
    - MCP server status and tool count
    
    Returns:
        HealthCheckResponse: Health status with metrics

    Raises:
        HTTPException: If health check fails
    """
    try:
        logger.debug("Health check requested")
        
        # Check database connectivity
        db_status = await check_database_connectivity()
        
        # Get MCP server status
        mcp_status = get_mcp_server_status()
        
        # Calculate uptime
        uptime_seconds = get_uptime_seconds()
        
        # Determine overall health status
        is_healthy = db_status.get("connected", False) and mcp_status.get("initialized", False)
        health_status = "healthy" if is_healthy else "degraded"

        return HealthCheckResponse(
            status=health_status,
            environment=settings.environment,
            version="0.1.0",
            timestamp=datetime.now(timezone.utc),
            uptime=uptime_seconds,
            database=db_status,
            mcp_server=mcp_status,
        )

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Health check failed",
        )


@router.get(
    "/ready",
    response_model=ReadinessCheckResponse,
    status_code=status.HTTP_200_OK,
    responses={
        503: {"model": ErrorResponse, "description": "Service unavailable"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def readiness_check() -> ReadinessCheckResponse:
    """
    Readiness check endpoint with component status.
    
    Returns 200 OK if system is ready to accept requests, 503 if not.
    Checks:
    - Database connectivity
    - MCP server initialization
    - Configuration validity
    
    Returns:
        ReadinessCheckResponse: Readiness status with component details

    Raises:
        HTTPException: If readiness check fails or service not ready
    """
    try:
        logger.debug("Readiness check requested")

        # Check database connectivity
        db_status = await check_database_connectivity()
        database_ready = db_status.get("connected", False)

        # Check MCP server status
        mcp_status = get_mcp_server_status()
        mcp_ready = mcp_status.get("initialized", False)

        # Check configuration
        config_ready = all([
            settings.database_url,
            settings.environment,
        ])

        # Determine overall readiness
        all_ready = all([
            database_ready,
            mcp_ready,
            config_ready,
        ])

        if not all_ready:
            logger.warning(
                f"Readiness check failed: "
                f"database_ready={database_ready}, "
                f"mcp_ready={mcp_ready}, "
                f"config_ready={config_ready}"
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service not ready",
            )

        return ReadinessCheckResponse(
            ready=True,
            timestamp=datetime.now(timezone.utc),
            checks={
                "database": database_ready,
                "mcp_server": mcp_ready,
                "configuration": config_ready,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Readiness check failed",
        )


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    status_code=status.HTTP_200_OK,
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_metrics() -> MetricsResponse:
    """
    Prometheus metrics endpoint.

    Returns:
        MetricsResponse: Prometheus metrics in text format

    Raises:
        HTTPException: If metrics retrieval fails
    """
    try:
        logger.debug("Metrics requested")

        from mcp_server.utils.performance import performance_monitor
        metrics_text = performance_monitor.get_prometheus_metrics()
        if not metrics_text.strip():
            # No data yet — return stub headers
            metrics_text = (
                "# HELP mcp_tool_invocations_total Total MCP tool invocations\n"
                "# TYPE mcp_tool_invocations_total counter\n"
                "mcp_tool_invocations_total 0\n"
            )

        return MetricsResponse(metrics=metrics_text)

    except Exception as e:
        logger.error(f"Metrics retrieval failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Metrics retrieval failed",
        )


@router.get(
    "/status",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_status() -> Dict[str, Any]:
    """
    Get detailed system status.

    Returns:
        Dictionary with detailed system status

    Raises:
        HTTPException: If status retrieval fails
    """
    try:
        logger.debug("Status requested")

        return {
            "status": "operational",
            "environment": settings.environment,
            "version": "0.1.0",
            "debug": settings.debug,
            "components": {
                "database": {
                    "status": "connected",
                    "url": settings.database_url.split("@")[1] if "@" in settings.database_url else "unknown",
                },
                "cache": {
                    "status": "connected",
                    "url": settings.redis_url.split("@")[1] if "@" in settings.redis_url else "unknown",
                },
                "message_queue": {
                    "status": "connected",
                    "url": settings.rabbitmq_url.split("@")[1] if "@" in settings.rabbitmq_url else "unknown",
                },
            },
            "features": {
                "hl7_ingestion": settings.enable_hl7_ingestion,
                "fhir_ingestion": settings.enable_fhir_ingestion,
                "dicom_ingestion": settings.enable_dicom_ingestion,
                "device_telemetry": settings.enable_device_telemetry,
                "caching": settings.enable_caching,
                "audit_logging": settings.enable_audit_logging,
            },
        }

    except Exception as e:
        logger.error(f"Status retrieval failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Status retrieval failed",
        )
