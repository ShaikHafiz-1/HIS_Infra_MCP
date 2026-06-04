"""
Hospital Clinical Intelligence MCP Client.

Python client library for interacting with the Hospital MCP server.
Supports authentication, all 10 clinical tools, and result formatting.

Usage (async):
    async with HospitalMCPClient("http://localhost:8000") as client:
        token = await client.authenticate("dr_smith", "password", "physician")
        context = await client.get_patient_context("PAT-001")

Usage (sync):
    client = SyncHospitalMCPClient("http://localhost:8000")
    token = client.authenticate("dr_smith", "password", "physician")
    context = client.get_patient_context("PAT-001")
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False


class MCPClientError(Exception):
    """Base error for MCP client operations."""

    def __init__(self, message: str, status_code: int = 0, detail: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class AuthenticationError(MCPClientError):
    """Raised when authentication fails."""


class ToolNotFoundError(MCPClientError):
    """Raised when the requested tool does not exist."""


class HospitalMCPClient:
    """
    Async client for the Hospital Clinical Intelligence MCP server.

    Manages authentication tokens and provides typed methods for all 10 tools.
    """

    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 30):
        if not _HAS_HTTPX:
            raise ImportError("httpx is required: pip install httpx")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._token: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "HospitalMCPClient":
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
        )
        return self

    async def __aexit__(self, *_) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
            )
        return self._client

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def authenticate(
        self,
        username: str,
        password: str,
        role: str = "physician",
        care_units: Optional[List[str]] = None,
    ) -> str:
        """
        Authenticate with the MCP server and store the JWT token.

        Returns:
            str: JWT access token
        """
        client = self._get_client()
        try:
            resp = await client.post(
                "/api/v1/auth/token",
                json={
                    "username": username,
                    "password": password,
                    "role": role,
                    "care_units": care_units or [],
                },
            )
            if resp.status_code == 401:
                raise AuthenticationError("Authentication failed: invalid credentials", 401)
            if resp.status_code != 200:
                raise AuthenticationError(
                    f"Authentication failed: HTTP {resp.status_code}",
                    resp.status_code,
                    resp.text,
                )
            data = resp.json()
            self._token = data.get("access_token") or data.get("token")
            if not self._token:
                raise AuthenticationError("No token in response")
            return self._token
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise MCPClientError(f"Cannot connect to MCP server at {self._base_url}: {e}")

    # ------------------------------------------------------------------
    # Internal tool invocation
    # ------------------------------------------------------------------

    async def _invoke_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """POST /api/v1/tools/invoke — calls the named tool with arguments."""
        client = self._get_client()
        headers = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        try:
            resp = await client.post(
                "/api/v1/tools/invoke",
                json={"tool_name": tool_name, "arguments": arguments},
                headers=headers,
            )
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise MCPClientError(f"Cannot connect to MCP server: {e}")

        if resp.status_code == 404:
            raise ToolNotFoundError(f"Tool not found: {tool_name}", 404)
        if resp.status_code == 401:
            raise AuthenticationError("Unauthorized: please call authenticate() first", 401)
        if resp.status_code == 403:
            raise MCPClientError(f"Permission denied for tool {tool_name}", 403)
        if resp.status_code != 200:
            raise MCPClientError(
                f"Tool invocation failed: HTTP {resp.status_code}",
                resp.status_code,
                resp.text,
            )

        data = resp.json()
        # Unwrap ToolInvocationResponse envelope
        if "result" in data:
            return data["result"]
        return data

    # ------------------------------------------------------------------
    # The 10 clinical tools
    # ------------------------------------------------------------------

    async def get_patient_context(
        self,
        patient_id: str,
        include_timeline: bool = False,
        include_devices: bool = True,
    ) -> Dict[str, Any]:
        """Retrieve comprehensive clinical context for a patient."""
        return await self._invoke_tool("get_patient_clinical_context", {
            "patient_id": patient_id,
            "include_timeline": include_timeline,
            "include_devices": include_devices,
        })

    async def get_care_unit_summary(self, care_unit_id: str) -> Dict[str, Any]:
        """Retrieve summary of all patients in a care unit."""
        return await self._invoke_tool("get_care_unit_summary", {
            "care_unit_id": care_unit_id,
        })

    async def get_device_events(
        self,
        patient_id: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        device_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve device events for a patient."""
        args: Dict[str, Any] = {"patient_id": patient_id}
        if start_time:
            args["start_time"] = start_time
        if end_time:
            args["end_time"] = end_time
        if device_type:
            args["device_type"] = device_type
        return await self._invoke_tool("get_device_events_by_patient", args)

    async def get_event_timeline(
        self,
        patient_id: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        event_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Retrieve chronological event timeline for a patient."""
        args: Dict[str, Any] = {"patient_id": patient_id}
        if start_time:
            args["start_time"] = start_time
        if end_time:
            args["end_time"] = end_time
        if event_types:
            args["event_types"] = event_types
        return await self._invoke_tool("get_patient_event_timeline", args)

    async def get_alarm_context(
        self,
        alarm_id: Optional[str] = None,
        patient_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve detailed context for an alarm event."""
        args: Dict[str, Any] = {}
        if alarm_id:
            args["alarm_id"] = alarm_id
        if patient_id:
            args["patient_id"] = patient_id
        return await self._invoke_tool("get_alarm_context", args)

    async def get_diagnostic_exam_context(
        self,
        exam_id: Optional[str] = None,
        patient_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve diagnostic exam context."""
        args: Dict[str, Any] = {}
        if exam_id:
            args["exam_id"] = exam_id
        if patient_id:
            args["patient_id"] = patient_id
        return await self._invoke_tool("get_diagnostic_exam_context", args)

    async def get_imaging_study_summary(
        self,
        study_id: Optional[str] = None,
        patient_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve imaging study summary."""
        args: Dict[str, Any] = {}
        if study_id:
            args["study_id"] = study_id
        if patient_id:
            args["patient_id"] = patient_id
        return await self._invoke_tool("get_imaging_study_summary", args)

    async def get_anesthesia_case_context(
        self,
        procedure_id: Optional[str] = None,
        patient_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve anesthesia case context."""
        args: Dict[str, Any] = {}
        if procedure_id:
            args["procedure_id"] = procedure_id
        if patient_id:
            args["patient_id"] = patient_id
        return await self._invoke_tool("get_anesthesia_case_context", args)

    async def get_neuro_event_context(
        self,
        patient_id: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve neurological event context."""
        args: Dict[str, Any] = {}
        if patient_id:
            args["patient_id"] = patient_id
        if event_id:
            args["event_id"] = event_id
        return await self._invoke_tool("get_neuro_event_context", args)

    async def get_cardiology_event_context(
        self,
        patient_id: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve cardiac event context."""
        args: Dict[str, Any] = {}
        if patient_id:
            args["patient_id"] = patient_id
        if event_id:
            args["event_id"] = event_id
        return await self._invoke_tool("get_cardiology_event_context", args)

    # ------------------------------------------------------------------
    # Utility endpoints
    # ------------------------------------------------------------------

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all available MCP tools."""
        client = self._get_client()
        headers = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        try:
            resp = await client.get("/api/v1/tools/list", headers=headers)
            if resp.status_code != 200:
                raise MCPClientError(f"Failed to list tools: HTTP {resp.status_code}")
            data = resp.json()
            return data.get("tools", data)
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise MCPClientError(f"Cannot connect to MCP server: {e}")

    async def health_check(self) -> Dict[str, Any]:
        """Check server health."""
        client = self._get_client()
        try:
            resp = await client.get("/api/v1/health/health")
            return resp.json()
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            return {"status": "unreachable", "error": str(e)}

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def format_patient_summary(context: Dict[str, Any]) -> str:
        """Format patient context as human-readable text."""
        p = context.get("patient", {})
        enc = context.get("encounter", {})
        cu = context.get("care_unit", {})
        lines = [
            f"Patient: {p.get('full_name', 'Unknown')} (MRN: {p.get('mrn', 'N/A')})",
            f"  Age/Gender: {p.get('age', '?')} / {p.get('gender', 'N/A')}",
        ]
        if enc:
            lines.append(f"  Encounter: {enc.get('encounter_type', '?')} since {enc.get('admission_time', '?')[:10]}")
        if cu:
            lines.append(f"  Care Unit: {cu.get('name', '?')} ({cu.get('unit_type', '?')})")
        diags = context.get("diagnoses", [])
        if diags:
            lines.append(f"  Diagnoses: {', '.join(d.get('name', '?') for d in diags[:3])}")
        meds = context.get("medications", [])
        if meds:
            lines.append(f"  Medications: {', '.join(m.get('name', '?') for m in meds[:3])}")
        devices = context.get("devices", [])
        if devices:
            lines.append(f"  Devices: {', '.join(d.get('device_type', '?') for d in devices[:3])}")
        lines.append(f"  Confidence: {context.get('confidence_score', 0):.0%}")
        return "\n".join(lines)

    @staticmethod
    def format_timeline(timeline_result: Dict[str, Any]) -> str:
        """Format timeline result as human-readable text."""
        events = timeline_result.get("timeline", [])
        lines = [
            f"Timeline for patient {timeline_result.get('patient_id', '?')} "
            f"({len(events)} events):",
            "-" * 60,
        ]
        for e in events:
            ts = e.get("timestamp", "")[:16].replace("T", " ")
            etype = e.get("event_type", "?").upper()
            sig = e.get("clinical_significance", "normal")
            flag = " [!]" if sig not in ("normal", "unknown") else ""
            ev = e.get("event", {})
            detail = (
                ev.get("vital_type") or ev.get("alarm_type") or
                ev.get("medication_name") or ev.get("event_type") or ""
            )
            lines.append(f"  {ts}  {etype:<12}  {detail:<20}  {sig}{flag}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Synchronous wrapper
# ---------------------------------------------------------------------------

class SyncHospitalMCPClient:
    """
    Synchronous wrapper around HospitalMCPClient for non-async contexts.

    Uses asyncio.run() internally — do not use inside an already-running event loop.
    """

    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 30):
        self._async_client = HospitalMCPClient(base_url, timeout)

    def _run(self, coro):
        return asyncio.run(coro)

    def authenticate(self, username, password, role="physician", care_units=None):
        return self._run(self._async_client.authenticate(username, password, role, care_units))

    def get_patient_context(self, patient_id, include_timeline=False, include_devices=True):
        return self._run(self._async_client.get_patient_context(patient_id, include_timeline, include_devices))

    def get_care_unit_summary(self, care_unit_id):
        return self._run(self._async_client.get_care_unit_summary(care_unit_id))

    def get_device_events(self, patient_id, start_time=None, end_time=None, device_type=None):
        return self._run(self._async_client.get_device_events(patient_id, start_time, end_time, device_type))

    def get_event_timeline(self, patient_id, start_time=None, end_time=None, event_types=None):
        return self._run(self._async_client.get_event_timeline(patient_id, start_time, end_time, event_types))

    def get_alarm_context(self, alarm_id=None, patient_id=None):
        return self._run(self._async_client.get_alarm_context(alarm_id, patient_id))

    def get_diagnostic_exam_context(self, exam_id=None, patient_id=None):
        return self._run(self._async_client.get_diagnostic_exam_context(exam_id, patient_id))

    def get_imaging_study_summary(self, study_id=None, patient_id=None):
        return self._run(self._async_client.get_imaging_study_summary(study_id, patient_id))

    def get_anesthesia_case_context(self, procedure_id=None, patient_id=None):
        return self._run(self._async_client.get_anesthesia_case_context(procedure_id, patient_id))

    def get_neuro_event_context(self, patient_id=None, event_id=None):
        return self._run(self._async_client.get_neuro_event_context(patient_id, event_id))

    def get_cardiology_event_context(self, patient_id=None, event_id=None):
        return self._run(self._async_client.get_cardiology_event_context(patient_id, event_id))

    def list_tools(self):
        return self._run(self._async_client.list_tools())

    def health_check(self):
        return self._run(self._async_client.health_check())
