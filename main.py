"""
Main FastAPI application for Hospital Clinical Intelligence MCP Platform.

This module initializes the FastAPI application with MCP server integration,
middleware configuration, and route registration.
"""

import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from mcp_server.mcp_server import MCPServer
from mcp_server.routers import auth, health, mcp_tools
from mcp_server.routers import vitals_ws, copilot_router
from mcp_server.security.authorization import (
    AuthorizationError,
    PermissionDeniedError,
    CareUnitAccessError,
)
from mcp_server.tools.tool_registry import register_all_tools
from mcp_server.utils.logger import get_logger

# Initialize logger
logger = get_logger(__name__)

# Global MCP server instance
mcp_server: MCPServer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle (startup and shutdown).

    Args:
        app: FastAPI application instance
    """
    # Startup
    logger.info(
        f"Starting Hospital Clinical Intelligence MCP Platform "
        f"(environment={settings.environment})"
    )
    logger.info(f"Database URL: {settings.database_url}")
    logger.info(f"Redis URL: {settings.redis_url}")
    logger.info(f"RabbitMQ URL: {settings.rabbitmq_url}")

    # Initialize database
    from mcp_server.database.connection import DatabaseConnection
    await DatabaseConnection.initialize()

    # Initialize MCP server
    global mcp_server
    mcp_server = MCPServer(
        name="Hospital Clinical Intelligence MCP Server"
    )
    mcp_tools.set_mcp_server(mcp_server)
    
    # Register all tools
    await register_all_tools(mcp_server)
    logger.info("MCP server initialized with tools")

    # Set startup time for health checks
    from datetime import datetime, timezone
    from mcp_server.routers.health import set_startup_time
    set_startup_time(datetime.now(timezone.utc))

    yield

    # Shutdown
    logger.info("Shutting down Hospital Clinical Intelligence MCP Platform")
    await DatabaseConnection.close()


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    Returns:
        FastAPI: Configured FastAPI application instance
    """
    app = FastAPI(
        title="Hospital Clinical Intelligence MCP Platform",
        description="Clinical data integration and retrieval system built on MCP",
        version="0.1.0",
        docs_url="/api/docs" if settings.debug else None,
        redoc_url="/api/redoc" if settings.debug else None,
        openapi_url="/api/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    # Add request/response logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """Log HTTP requests and responses with request ID."""
        request_id = str(uuid4())
        request.state.request_id = request_id

        logger.debug(
            f"[{request_id}] {request.method} {request.url.path} - "
            f"Client: {request.client.host if request.client else 'unknown'}"
        )

        response = await call_next(request)

        logger.debug(
            f"[{request_id}] {request.method} {request.url.path} - "
            f"Status: {response.status_code}"
        )

        return response

    # Register routers
    app.include_router(auth.router)
    app.include_router(health.router)
    app.include_router(mcp_tools.router)
    app.include_router(vitals_ws.router)
    app.include_router(copilot_router.router)

    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root():
        """
        Root endpoint.

        Returns:
            dict: API information
        """
        return {
            "name": "Hospital Clinical Intelligence MCP Platform",
            "version": "0.1.0",
            "docs": "/api/docs" if settings.debug else None,
        }

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle uncaught exceptions."""
        request_id = getattr(request.state, "request_id", "unknown")

        logger.error(
            f"[{request_id}] Unhandled exception: {exc}",
            exc_info=True,
        )

        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "detail": str(exc) if settings.debug else "An error occurred",
                "request_id": request_id,
            },
        )

    # Authorization exception handlers
    @app.exception_handler(PermissionDeniedError)
    async def permission_denied_exception_handler(request: Request, exc: PermissionDeniedError):
        """Handle permission denied errors."""
        request_id = getattr(request.state, "request_id", "unknown")

        logger.warning(
            f"[{request_id}] Permission denied: {exc.message}",
        )

        return JSONResponse(
            status_code=403,
            content={
                "error": "PermissionDeniedError",
                "detail": exc.message,
                "request_id": request_id,
            },
        )

    @app.exception_handler(CareUnitAccessError)
    async def care_unit_access_exception_handler(request: Request, exc: CareUnitAccessError):
        """Handle care unit access errors."""
        request_id = getattr(request.state, "request_id", "unknown")

        logger.warning(
            f"[{request_id}] Care unit access denied: {exc.message}",
        )

        return JSONResponse(
            status_code=403,
            content={
                "error": "CareUnitAccessError",
                "detail": exc.message,
                "request_id": request_id,
            },
        )

    @app.exception_handler(AuthorizationError)
    async def authorization_exception_handler(request: Request, exc: AuthorizationError):
        """Handle general authorization errors."""
        request_id = getattr(request.state, "request_id", "unknown")

        logger.warning(
            f"[{request_id}] Authorization error: {exc.message}",
        )

        return JSONResponse(
            status_code=403,
            content={
                "error": "AuthorizationError",
                "detail": exc.message,
                "request_id": request_id,
            },
        )

    logger.info("FastAPI application created successfully")
    return app


# Create application instance
app = create_app()

if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting server on {settings.server_host}:{settings.server_port}")
    uvicorn.run(
        "main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
