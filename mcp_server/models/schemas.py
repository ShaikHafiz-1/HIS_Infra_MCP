"""
Pydantic schemas for MCP server request/response handling.

This module defines all data models for MCP tool definitions, input parameters,
output responses, error handling, and audit logging.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class ToolInputSchema(BaseModel):
    """Schema for MCP tool input parameters."""

    type: str = Field(..., description="JSON schema type")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Input properties")
    required: List[str] = Field(default_factory=list, description="Required properties")
    additionalProperties: bool = Field(default=False, description="Allow additional properties")

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string", "description": "Patient identifier"}
                },
                "required": ["patient_id"],
                "additionalProperties": False,
            }
        }


class ToolOutputSchema(BaseModel):
    """Schema for MCP tool output responses."""

    type: str = Field(..., description="JSON schema type")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Output properties")
    additionalProperties: bool = Field(default=False, description="Allow additional properties")

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "type": "object",
                "properties": {
                    "patient": {"type": "object"},
                    "encounter": {"type": "object"},
                    "confidence_score": {"type": "number"},
                },
                "additionalProperties": False,
            }
        }


class MCPToolDefinition(BaseModel):
    """Definition of an MCP tool."""

    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    inputSchema: ToolInputSchema = Field(..., description="Input schema")
    outputSchema: Optional[ToolOutputSchema] = Field(None, description="Output schema")

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "name": "get_patient_clinical_context",
                "description": "Retrieve comprehensive clinical context for a patient",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "patient_id": {"type": "string"}
                    },
                    "required": ["patient_id"],
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "patient": {"type": "object"},
                        "encounter": {"type": "object"},
                    }
                },
            }
        }


class ToolInvocationRequest(BaseModel):
    """Request to invoke an MCP tool."""

    tool_name: str = Field(..., description="Name of the tool to invoke")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "tool_name": "get_patient_clinical_context",
                "arguments": {"patient_id": "PAT-12345"},
            }
        }


class ToolInvocationResponse(BaseModel):
    """Response from MCP tool invocation."""

    success: bool = Field(..., description="Whether tool invocation succeeded")
    tool_name: str = Field(..., description="Name of the tool invoked")
    result: Optional[Dict[str, Any]] = Field(None, description="Tool result")
    error: Optional[str] = Field(None, description="Error message if failed")
    execution_time_ms: float = Field(..., description="Execution time in milliseconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "success": True,
                "tool_name": "get_patient_clinical_context",
                "result": {
                    "patient": {"id": "PAT-12345", "name": "John Doe"},
                    "encounter": {"id": "ENC-67890"},
                },
                "error": None,
                "execution_time_ms": 125.5,
                "timestamp": "2024-01-15T10:30:00Z",
            }
        }


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str = Field(..., description="Error type")
    detail: str = Field(..., description="Error detail message")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "error": "ValidationError",
                "detail": "Patient ID must be a non-empty string",
                "request_id": "req-12345",
                "timestamp": "2024-01-15T10:30:00Z",
            }
        }


class AuditLogEntry(BaseModel):
    """Audit log entry for tracking data access."""

    log_id: str = Field(..., description="Unique log entry ID")
    timestamp: datetime = Field(..., description="Log timestamp")
    clinician_id: str = Field(..., description="Clinician ID")
    clinician_role: str = Field(..., description="Clinician role")
    care_unit: Optional[str] = Field(None, description="Care unit")
    tool_name: str = Field(..., description="MCP tool name")
    tool_arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    patient_ids_accessed: List[str] = Field(default_factory=list, description="Patient IDs accessed")
    data_types_accessed: List[str] = Field(default_factory=list, description="Data types accessed")
    success: bool = Field(..., description="Whether operation succeeded")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    response_time_ms: float = Field(..., description="Response time in milliseconds")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Client user agent")

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "log_id": "LOG-12345",
                "timestamp": "2024-01-15T10:30:00Z",
                "clinician_id": "CLIN-001",
                "clinician_role": "physician",
                "care_unit": "cardiology",
                "tool_name": "get_patient_clinical_context",
                "tool_arguments": {"patient_id": "PAT-12345"},
                "patient_ids_accessed": ["PAT-12345"],
                "data_types_accessed": ["demographics", "medications"],
                "success": True,
                "error_message": None,
                "response_time_ms": 125.5,
                "ip_address": "192.168.1.100",
                "user_agent": "MCP-Client/1.0",
            }
        }


class ToolListResponse(BaseModel):
    """Response containing list of available tools."""

    tools: List[MCPToolDefinition] = Field(..., description="List of available tools")
    total_count: int = Field(..., description="Total number of tools")

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "tools": [
                    {
                        "name": "get_patient_clinical_context",
                        "description": "Retrieve comprehensive clinical context for a patient",
                        "inputSchema": {"type": "object", "properties": {}},
                    }
                ],
                "total_count": 1,
            }
        }


class HealthCheckResponse(BaseModel):
    """Health check response model."""

    status: str = Field(..., description="Health status: 'healthy' or 'degraded'")
    environment: str = Field(..., description="Environment name")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Check timestamp")
    uptime: float = Field(..., description="Server uptime in seconds")
    database: Dict[str, Any] = Field(..., description="Database connectivity status and latency")
    mcp_server: Dict[str, Any] = Field(..., description="MCP server status and tool count")

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "environment": "production",
                "version": "0.1.0",
                "timestamp": "2024-01-15T10:30:00Z",
                "uptime": 3600.5,
                "database": {
                    "connected": True,
                    "latency_ms": 2.5,
                },
                "mcp_server": {
                    "initialized": True,
                    "tools_count": 10,
                },
            }
        }


class ReadinessCheckResponse(BaseModel):
    """Readiness check response model."""

    ready: bool = Field(..., description="Whether system is ready")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Check timestamp")
    checks: Dict[str, bool] = Field(..., description="Individual component readiness checks")

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "ready": True,
                "timestamp": "2024-01-15T10:30:00Z",
                "checks": {
                    "database": True,
                    "mcp_server": True,
                    "configuration": True,
                },
            }
        }


class MetricsResponse(BaseModel):
    """Prometheus metrics response model."""

    metrics: str = Field(..., description="Prometheus metrics in text format")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Metrics timestamp")

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "metrics": "# HELP mcp_tool_invocations_total Total MCP tool invocations\n...",
                "timestamp": "2024-01-15T10:30:00Z",
            }
        }


class ClinicianRole(str, Enum):
    """Enumeration of clinician roles."""

    PHYSICIAN = "physician"
    NURSE = "nurse"
    TECHNICIAN = "technician"
    ADMINISTRATOR = "administrator"


class ClinicianIdentity(BaseModel):
    """Clinician identity information from authentication token."""

    id: str = Field(..., description="Unique clinician identifier")
    name: str = Field(..., description="Clinician name")
    role: ClinicianRole = Field(..., description="Clinician role")
    care_units: List[str] = Field(default_factory=list, description="Assigned care unit IDs")

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "id": "CLIN-00000001-0000-0000-0000-000000000001",
                "name": "Dr. Sarah Smith",
                "role": "physician",
                "care_units": [
                    "UNIT-00000001-0000-0000-0000-000000000001",
                    "UNIT-00000002-0000-0000-0000-000000000002",
                ],
            }
        }


class TokenRequest(BaseModel):
    """Request to generate authentication token."""

    username: str = Field(..., description="Username for authentication")
    password: str = Field(..., description="Password for authentication")
    role: Optional[str] = Field(None, description="Override role (dev only)")
    care_units: Optional[List[str]] = Field(None, description="Override care units (dev only)")

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "username": "dr_smith",
                "password": "securepassword",
                "role": "physician",
                "care_units": ["cu-icu-001", "cu-ccu-001"],
            }
        }


class TokenResponse(BaseModel):
    """Response containing authentication token."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    clinician: ClinicianIdentity = Field(..., description="Authenticated clinician information")

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 28800,
                "clinician": {
                    "id": "CLIN-00000001-0000-0000-0000-000000000001",
                    "name": "Dr. Sarah Smith",
                    "role": "physician",
                    "care_units": ["UNIT-00000001-0000-0000-0000-000000000001"],
                },
            }
        }


class AuthenticationErrorResponse(BaseModel):
    """Authentication error response model."""

    error: str = Field(..., description="Error type")
    detail: str = Field(..., description="Error detail message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "error": "AuthenticationError",
                "detail": "Invalid credentials",
                "timestamp": "2024-01-15T10:30:00Z",
            }
        }


class AuthorizationErrorResponse(BaseModel):
    """Authorization error response model."""

    error: str = Field(..., description="Error type")
    detail: str = Field(..., description="Error detail message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "error": "PermissionDeniedError",
                "detail": "Role physician cannot access tool get_anesthesia_case_context",
                "timestamp": "2024-01-15T10:30:00Z",
            }
        }


class RolePermissions(BaseModel):
    """Role permissions model."""

    role: ClinicianRole = Field(..., description="Clinician role")
    accessible_tools: List[str] = Field(..., description="List of accessible tools")
    tool_permissions: Dict[str, bool] = Field(..., description="Detailed tool permissions")

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "role": "physician",
                "accessible_tools": [
                    "get_patient_clinical_context",
                    "get_care_unit_summary",
                ],
                "tool_permissions": {
                    "get_patient_clinical_context": True,
                    "get_care_unit_summary": True,
                    "get_device_events_by_patient": True,
                },
            }
        }


class CareUnitAssignment(BaseModel):
    """Care unit assignment model."""

    care_unit_id: str = Field(..., description="Care unit identifier")
    care_unit_name: str = Field(..., description="Care unit name")
    assigned_at: datetime = Field(..., description="Assignment timestamp")

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "care_unit_id": "UNIT-00000001-0000-0000-0000-000000000001",
                "care_unit_name": "Cardiology",
                "assigned_at": "2024-01-01T08:00:00Z",
            }
        }


class ClinicianAuthorizationInfo(BaseModel):
    """Complete authorization information for a clinician."""

    clinician_id: str = Field(..., description="Clinician identifier")
    clinician_name: str = Field(..., description="Clinician name")
    role: ClinicianRole = Field(..., description="Clinician role")
    care_units: List[CareUnitAssignment] = Field(..., description="Assigned care units")
    accessible_tools: List[str] = Field(..., description="Accessible tools")
    role_hierarchy_level: int = Field(..., description="Role hierarchy level (higher = more privileged)")

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "clinician_id": "CLIN-00000001-0000-0000-0000-000000000001",
                "clinician_name": "Dr. Sarah Smith",
                "role": "physician",
                "care_units": [
                    {
                        "care_unit_id": "UNIT-00000001-0000-0000-0000-000000000001",
                        "care_unit_name": "Cardiology",
                        "assigned_at": "2024-01-01T08:00:00Z",
                    }
                ],
                "accessible_tools": [
                    "get_patient_clinical_context",
                    "get_care_unit_summary",
                ],
                "role_hierarchy_level": 2,
            }
        }
