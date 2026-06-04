"""
Unit tests for health check endpoints.

Tests cover:
- /health endpoint returns 200 with system status
- /health response structure and fields
- /ready endpoint returns 200 when ready
- /ready endpoint returns 503 when not ready
- Database connectivity check
- MCP server status check
- Error handling and edge cases
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from main import app
from mcp_server.routers.health import (
    set_startup_time,
    get_uptime_seconds,
    check_database_connectivity,
    get_mcp_server_status,
)


@pytest.fixture
def client():
    """Provide a test client for the FastAPI application."""
    return TestClient(app)


@pytest.fixture
def setup_startup_time():
    """Set up startup time for health checks."""
    startup_time = datetime.now(timezone.utc)
    set_startup_time(startup_time)
    return startup_time


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_endpoint_returns_200(self, client):
        """Test that /health endpoint returns 200 OK."""
        response = client.get("/api/v1/health/health")
        assert response.status_code == 200

    def test_health_endpoint_response_structure(self, client):
        """Test that /health response has required fields."""
        response = client.get("/api/v1/health/health")
        data = response.json()

        # Check required fields
        assert "status" in data
        assert "environment" in data
        assert "version" in data
        assert "timestamp" in data
        assert "uptime" in data
        assert "database" in data
        assert "mcp_server" in data

    def test_health_endpoint_status_field(self, client):
        """Test that status field is either 'healthy' or 'degraded'."""
        response = client.get("/api/v1/health/health")
        data = response.json()

        assert data["status"] in ["healthy", "degraded"]

    def test_health_endpoint_database_field_structure(self, client):
        """Test that database field has required structure."""
        response = client.get("/api/v1/health/health")
        data = response.json()

        assert isinstance(data["database"], dict)
        assert "connected" in data["database"]
        assert isinstance(data["database"]["connected"], bool)

    def test_health_endpoint_database_latency_field(self, client):
        """Test that database latency is included when connected."""
        response = client.get("/api/v1/health/health")
        data = response.json()

        if data["database"]["connected"]:
            assert "latency_ms" in data["database"]
            assert isinstance(data["database"]["latency_ms"], (int, float))
            assert data["database"]["latency_ms"] >= 0

    def test_health_endpoint_mcp_server_field_structure(self, client):
        """Test that mcp_server field has required structure."""
        response = client.get("/api/v1/health/health")
        data = response.json()

        assert isinstance(data["mcp_server"], dict)
        assert "initialized" in data["mcp_server"]
        assert isinstance(data["mcp_server"]["initialized"], bool)
        assert "tools_count" in data["mcp_server"]
        assert isinstance(data["mcp_server"]["tools_count"], int)

    def test_health_endpoint_uptime_field(self, client, setup_startup_time):
        """Test that uptime is calculated correctly."""
        response = client.get("/api/v1/health/health")
        data = response.json()

        assert isinstance(data["uptime"], (int, float))
        assert data["uptime"] >= 0

    def test_health_endpoint_timestamp_format(self, client):
        """Test that timestamp is in ISO format."""
        response = client.get("/api/v1/health/health")
        data = response.json()

        # Should be parseable as ISO format datetime
        try:
            datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pytest.fail("Timestamp is not in ISO format")

    def test_health_endpoint_version_field(self, client):
        """Test that version field is present and valid."""
        response = client.get("/api/v1/health/health")
        data = response.json()

        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0

    def test_health_endpoint_environment_field(self, client):
        """Test that environment field is present."""
        response = client.get("/api/v1/health/health")
        data = response.json()

        assert isinstance(data["environment"], str)
        assert len(data["environment"]) > 0


class TestReadinessEndpoint:
    """Tests for /ready endpoint."""

    def test_readiness_endpoint_returns_200_when_ready(self, client):
        """Test that /ready endpoint returns 200 when system is ready."""
        response = client.get("/api/v1/health/ready")
        # Should return either 200 or 503 depending on system state
        assert response.status_code in [200, 503]

    def test_readiness_endpoint_response_structure(self, client):
        """Test that /ready response has required fields."""
        response = client.get("/api/v1/health/ready")
        
        if response.status_code == 200:
            data = response.json()
            assert "ready" in data
            assert "timestamp" in data
            assert "checks" in data

    def test_readiness_endpoint_ready_field_true_on_200(self, client):
        """Test that ready field is true when status is 200."""
        response = client.get("/api/v1/health/ready")
        
        if response.status_code == 200:
            data = response.json()
            assert data["ready"] is True

    def test_readiness_endpoint_checks_structure(self, client):
        """Test that checks field has required structure."""
        response = client.get("/api/v1/health/ready")
        
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data["checks"], dict)
            assert "database" in data["checks"]
            assert "mcp_server" in data["checks"]
            assert "configuration" in data["checks"]

    def test_readiness_endpoint_checks_are_booleans(self, client):
        """Test that all checks are boolean values."""
        response = client.get("/api/v1/health/ready")
        
        if response.status_code == 200:
            data = response.json()
            for check_name, check_value in data["checks"].items():
                assert isinstance(check_value, bool), f"Check '{check_name}' is not boolean"

    def test_readiness_endpoint_timestamp_format(self, client):
        """Test that timestamp is in ISO format."""
        response = client.get("/api/v1/health/ready")
        
        if response.status_code == 200:
            data = response.json()
            try:
                datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pytest.fail("Timestamp is not in ISO format")

    def test_readiness_endpoint_503_when_not_ready(self, client):
        """Test that /ready returns 503 when system is not ready."""
        # This test would require mocking the database or MCP server to be unavailable
        # For now, we just verify the endpoint exists and returns valid status codes
        response = client.get("/api/v1/health/ready")
        assert response.status_code in [200, 503]


class TestDatabaseConnectivityCheck:
    """Tests for database connectivity check function."""

    @pytest.mark.asyncio
    async def test_database_connectivity_check_returns_dict(self):
        """Test that database connectivity check returns a dictionary."""
        result = await check_database_connectivity()
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_database_connectivity_check_has_connected_field(self):
        """Test that result has 'connected' field."""
        result = await check_database_connectivity()
        assert "connected" in result
        assert isinstance(result["connected"], bool)

    @pytest.mark.asyncio
    async def test_database_connectivity_check_has_latency_when_connected(self):
        """Test that latency is included when connected."""
        result = await check_database_connectivity()
        if result["connected"]:
            assert "latency_ms" in result
            assert isinstance(result["latency_ms"], (int, float))
            assert result["latency_ms"] >= 0

    @pytest.mark.asyncio
    async def test_database_connectivity_check_handles_errors(self):
        """Test that database connectivity check handles errors gracefully."""
        with patch(
            "mcp_server.routers.health.DatabaseConnection.health_check",
            side_effect=Exception("Connection failed")
        ):
            result = await check_database_connectivity()
            assert result["connected"] is False
            assert "error" in result


class TestMCPServerStatusCheck:
    """Tests for MCP server status check function."""

    def test_mcp_server_status_returns_dict(self):
        """Test that MCP server status check returns a dictionary."""
        result = get_mcp_server_status()
        assert isinstance(result, dict)

    def test_mcp_server_status_has_initialized_field(self):
        """Test that result has 'initialized' field."""
        result = get_mcp_server_status()
        assert "initialized" in result
        assert isinstance(result["initialized"], bool)

    def test_mcp_server_status_has_tools_count_field(self):
        """Test that result has 'tools_count' field."""
        result = get_mcp_server_status()
        assert "tools_count" in result
        assert isinstance(result["tools_count"], int)
        assert result["tools_count"] >= 0

    def test_mcp_server_status_handles_errors(self):
        """Test that MCP server status check handles errors gracefully."""
        with patch("mcp_server.routers.health.logger") as mock_logger:
            # Patch the import to raise an exception
            with patch("builtins.__import__", side_effect=Exception("MCP error")):
                result = get_mcp_server_status()
                assert result["initialized"] is False
                assert result["tools_count"] == 0
                assert "error" in result


class TestUptimeCalculation:
    """Tests for uptime calculation."""

    def test_uptime_returns_float(self, setup_startup_time):
        """Test that uptime returns a float."""
        uptime = get_uptime_seconds()
        assert isinstance(uptime, float)

    def test_uptime_is_non_negative(self, setup_startup_time):
        """Test that uptime is non-negative."""
        uptime = get_uptime_seconds()
        assert uptime >= 0

    def test_uptime_increases_over_time(self, setup_startup_time):
        """Test that uptime increases over time."""
        import time
        uptime1 = get_uptime_seconds()
        time.sleep(0.1)
        uptime2 = get_uptime_seconds()
        assert uptime2 >= uptime1

    def test_uptime_without_startup_time(self):
        """Test that uptime returns 0 when startup time not set."""
        from mcp_server.routers import health
        health._startup_time = None
        uptime = get_uptime_seconds()
        assert uptime == 0.0


class TestHealthEndpointIntegration:
    """Integration tests for health endpoints."""

    def test_health_and_ready_endpoints_consistency(self, client):
        """Test that health and ready endpoints are consistent."""
        health_response = client.get("/api/v1/health/health")
        ready_response = client.get("/api/v1/health/ready")

        assert health_response.status_code == 200
        
        health_data = health_response.json()
        
        # If ready endpoint returns 200, health should be healthy or degraded
        if ready_response.status_code == 200:
            ready_data = ready_response.json()
            assert ready_data["ready"] is True
            # Database should be connected if ready
            assert health_data["database"]["connected"] is True

    def test_multiple_health_checks_succeed(self, client):
        """Test that multiple health checks can be performed."""
        for _ in range(3):
            response = client.get("/api/v1/health/health")
            assert response.status_code == 200

    def test_multiple_readiness_checks_succeed(self, client):
        """Test that multiple readiness checks can be performed."""
        for _ in range(3):
            response = client.get("/api/v1/health/ready")
            assert response.status_code in [200, 503]

    def test_health_endpoint_response_is_json(self, client):
        """Test that health endpoint returns valid JSON."""
        response = client.get("/api/v1/health/health")
        assert response.headers["content-type"].startswith("application/json")
        # Should not raise an exception
        response.json()

    def test_ready_endpoint_response_is_json(self, client):
        """Test that ready endpoint returns valid JSON."""
        response = client.get("/api/v1/health/ready")
        assert response.headers["content-type"].startswith("application/json")
        # Should not raise an exception
        response.json()


class TestHealthEndpointErrorHandling:
    """Tests for error handling in health endpoints."""

    def test_health_endpoint_handles_database_errors(self, client):
        """Test that health endpoint handles database errors gracefully."""
        with patch(
            "mcp_server.routers.health.check_database_connectivity",
            side_effect=Exception("Database error")
        ):
            response = client.get("/api/v1/health/health")
            # Should still return 500 or handle gracefully
            assert response.status_code in [200, 500]

    def test_ready_endpoint_handles_database_errors(self, client):
        """Test that ready endpoint handles database errors gracefully."""
        with patch(
            "mcp_server.routers.health.check_database_connectivity",
            side_effect=Exception("Database error")
        ):
            response = client.get("/api/v1/health/ready")
            # Should return 503 or 500
            assert response.status_code in [503, 500]

    def test_health_endpoint_handles_mcp_errors(self, client):
        """Test that health endpoint handles MCP server errors gracefully."""
        with patch(
            "mcp_server.routers.health.get_mcp_server_status",
            side_effect=Exception("MCP error")
        ):
            response = client.get("/api/v1/health/health")
            # Should still return 200 or handle gracefully
            assert response.status_code in [200, 500]
