"""
Tool registry for MCP server.

Registers all 10 MCP tools with the server.
"""

from typing import List, Optional

from mcp_server.mcp_server import MCPServer
from mcp_server.models.schemas import MCPToolDefinition, ToolInputSchema, ToolOutputSchema
from mcp_server.tools.patient_context import PatientContextTool
from mcp_server.tools.care_unit_summary import CareUnitSummaryTool
from mcp_server.tools.device_events import DeviceEventsTool
from mcp_server.tools.event_timeline import EventTimelineTool
from mcp_server.tools.alarm_context import AlarmContextTool
from mcp_server.tools.diagnostic_exam import DiagnosticExamTool
from mcp_server.tools.imaging_summary import ImagingStudySummaryTool
from mcp_server.tools.anesthesia_context import AnesthesiaCaseTool
from mcp_server.tools.neuro_context import NeuroEventTool
from mcp_server.tools.cardiology_context import CardiologyEventTool
from mcp_server.database.connection import DatabaseConnection
from mcp_server.tools.fhir_tool_registry import register_fhir_tools
from mcp_server.utils.logger import get_logger

logger = get_logger(__name__)


async def register_all_tools(mcp_server: MCPServer) -> None:
    """Register all MCP tools (10 simulator + 13 FHIR-backed)."""
    logger.info("Registering MCP tools...")

    await _register_patient_clinical_context(mcp_server)
    await _register_care_unit_summary(mcp_server)
    await _register_device_events(mcp_server)
    await _register_event_timeline(mcp_server)
    await _register_alarm_context(mcp_server)
    await _register_diagnostic_exam_context(mcp_server)
    await _register_imaging_study_summary(mcp_server)
    await _register_anesthesia_case_context(mcp_server)
    await _register_neuro_event_context(mcp_server)
    await _register_cardiology_event_context(mcp_server)

    # FHIR-backed tools (registered separately, no conflict with above 10)
    await register_fhir_tools(mcp_server)

    logger.info(f"Registered {len(mcp_server.list_tools())} tools")


# ---------------------------------------------------------------------------
# Helper: build a minimal tool definition
# ---------------------------------------------------------------------------

def _tool_def(name: str, description: str, properties: dict, required: list) -> MCPToolDefinition:
    return MCPToolDefinition(
        name=name,
        description=description,
        inputSchema=ToolInputSchema(
            type="object",
            properties=properties,
            required=required,
            additionalProperties=False,
        ),
        outputSchema=ToolOutputSchema(
            type="object",
            properties={"result": {"type": "object"}},
            additionalProperties=True,
        ),
    )


# ---------------------------------------------------------------------------
# Tool 1: get_patient_clinical_context
# ---------------------------------------------------------------------------

async def _register_patient_clinical_context(mcp_server: MCPServer) -> None:
    td = _tool_def(
        "get_patient_clinical_context",
        "Retrieve comprehensive clinical context for a patient including demographics, "
        "encounter information, diagnoses, medications, clinicians, devices, and recent observations",
        {
            "patient_id": {"type": "string", "description": "Internal patient identifier"},
            "include_timeline": {"type": "boolean", "description": "Include event timeline", "default": False},
            "include_devices": {"type": "boolean", "description": "Include active devices", "default": True},
        },
        ["patient_id"],
    )

    async def handler(patient_id: str, include_timeline: bool = False, include_devices: bool = True) -> dict:
        async for session in DatabaseConnection.get_session():
            return await PatientContextTool.get_patient_clinical_context(
                session=session, patient_id=patient_id,
                include_timeline=include_timeline, include_devices=include_devices,
            )

    mcp_server.register_tool(td, handler)
    logger.info("Registered tool: get_patient_clinical_context")


# ---------------------------------------------------------------------------
# Tool 2: get_care_unit_summary
# ---------------------------------------------------------------------------

async def _register_care_unit_summary(mcp_server: MCPServer) -> None:
    td = _tool_def(
        "get_care_unit_summary",
        "Retrieve summary of all patients in a care unit, including critical patients, "
        "abnormal vital trends, active alarms, and clinician assignments",
        {"care_unit_id": {"type": "string", "description": "Internal care unit identifier"}},
        ["care_unit_id"],
    )

    async def handler(care_unit_id: str) -> dict:
        async for session in DatabaseConnection.get_session():
            return await CareUnitSummaryTool.get_care_unit_summary(session=session, care_unit_id=care_unit_id)

    mcp_server.register_tool(td, handler)
    logger.info("Registered tool: get_care_unit_summary")


# ---------------------------------------------------------------------------
# Tool 3: get_device_events_by_patient
# ---------------------------------------------------------------------------

async def _register_device_events(mcp_server: MCPServer) -> None:
    td = _tool_def(
        "get_device_events_by_patient",
        "Retrieve device events for a patient within a time window including alarms, "
        "status changes, waveform events, setting changes, and vital sign trends",
        {
            "patient_id": {"type": "string", "description": "Internal patient identifier"},
            "start_time": {"type": "string", "description": "Start time ISO format (optional)"},
            "end_time": {"type": "string", "description": "End time ISO format (optional)"},
            "device_type": {"type": "string", "description": "Filter by device type (optional)"},
        },
        ["patient_id"],
    )

    async def handler(patient_id: str, start_time: Optional[str] = None,
                      end_time: Optional[str] = None, device_type: Optional[str] = None) -> dict:
        async for session in DatabaseConnection.get_session():
            return await DeviceEventsTool.get_device_events_by_patient(
                session=session, patient_id=patient_id,
                start_time=start_time, end_time=end_time, device_type=device_type,
            )

    mcp_server.register_tool(td, handler)
    logger.info("Registered tool: get_device_events_by_patient")


# ---------------------------------------------------------------------------
# Tool 4: get_patient_event_timeline
# ---------------------------------------------------------------------------

async def _register_event_timeline(mcp_server: MCPServer) -> None:
    td = _tool_def(
        "get_patient_event_timeline",
        "Retrieve a chronological timeline of clinical events for a patient including "
        "vital signs, alarms, medications, procedures, notes, and device changes",
        {
            "patient_id": {"type": "string", "description": "Internal patient identifier"},
            "start_time": {"type": "string", "description": "Start time ISO format (optional)"},
            "end_time": {"type": "string", "description": "End time ISO format (optional)"},
            "event_types": {"type": "array", "description": "Filter by event types (optional)",
                            "items": {"type": "string"}},
        },
        ["patient_id"],
    )

    async def handler(patient_id: str, start_time: Optional[str] = None,
                      end_time: Optional[str] = None, event_types: Optional[List[str]] = None) -> dict:
        async for session in DatabaseConnection.get_session():
            return await EventTimelineTool.get_patient_event_timeline(
                session=session, patient_id=patient_id,
                start_time=start_time, end_time=end_time, event_types=event_types,
            )

    mcp_server.register_tool(td, handler)
    logger.info("Registered tool: get_patient_event_timeline")


# ---------------------------------------------------------------------------
# Tool 5: get_alarm_context
# ---------------------------------------------------------------------------

async def _register_alarm_context(mcp_server: MCPServer) -> None:
    td = _tool_def(
        "get_alarm_context",
        "Retrieve detailed context for an alarm event including vital signs before/during/after, "
        "device source, patient diagnoses, medications, and clinician response",
        {
            "alarm_id": {"type": "string", "description": "Alarm event ID (optional)"},
            "patient_id": {"type": "string", "description": "Patient ID (optional)"},
        },
        [],
    )

    async def handler(alarm_id: Optional[str] = None, patient_id: Optional[str] = None) -> dict:
        async for session in DatabaseConnection.get_session():
            return await AlarmContextTool.get_alarm_context(
                session=session, alarm_id=alarm_id, patient_id=patient_id,
            )

    mcp_server.register_tool(td, handler)
    logger.info("Registered tool: get_alarm_context")


# ---------------------------------------------------------------------------
# Tool 6: get_diagnostic_exam_context
# ---------------------------------------------------------------------------

async def _register_diagnostic_exam_context(mcp_server: MCPServer) -> None:
    td = _tool_def(
        "get_diagnostic_exam_context",
        "Retrieve diagnostic exam context including DICOM metadata, imaging findings, "
        "lab results with reference ranges, contemporaneous vital signs, and related events",
        {
            "exam_id": {"type": "string", "description": "Exam ID (optional)"},
            "patient_id": {"type": "string", "description": "Patient ID (optional)"},
        },
        [],
    )

    async def handler(exam_id: Optional[str] = None, patient_id: Optional[str] = None) -> dict:
        async for session in DatabaseConnection.get_session():
            return await DiagnosticExamTool.get_diagnostic_exam_context(
                session=session, exam_id=exam_id, patient_id=patient_id,
            )

    mcp_server.register_tool(td, handler)
    logger.info("Registered tool: get_diagnostic_exam_context")


# ---------------------------------------------------------------------------
# Tool 7: get_imaging_study_summary
# ---------------------------------------------------------------------------

async def _register_imaging_study_summary(mcp_server: MCPServer) -> None:
    td = _tool_def(
        "get_imaging_study_summary",
        "Retrieve imaging study summary with radiologist report, findings, "
        "contemporaneous vital signs, related events, and follow-up recommendations",
        {
            "study_id": {"type": "string", "description": "Study ID (optional)"},
            "patient_id": {"type": "string", "description": "Patient ID (optional)"},
        },
        [],
    )

    async def handler(study_id: Optional[str] = None, patient_id: Optional[str] = None) -> dict:
        async for session in DatabaseConnection.get_session():
            return await ImagingStudySummaryTool.get_imaging_study_summary(
                session=session, study_id=study_id, patient_id=patient_id,
            )

    mcp_server.register_tool(td, handler)
    logger.info("Registered tool: get_imaging_study_summary")


# ---------------------------------------------------------------------------
# Tool 8: get_anesthesia_case_context
# ---------------------------------------------------------------------------

async def _register_anesthesia_case_context(mcp_server: MCPServer) -> None:
    td = _tool_def(
        "get_anesthesia_case_context",
        "Retrieve comprehensive anesthesia case context including agents, vital signs, "
        "ventilator settings, alarm events, recovery vitals, and anesthesia notes",
        {
            "procedure_id": {"type": "string", "description": "Procedure ID (optional)"},
            "patient_id": {"type": "string", "description": "Patient ID (optional)"},
        },
        [],
    )

    async def handler(procedure_id: Optional[str] = None, patient_id: Optional[str] = None) -> dict:
        async for session in DatabaseConnection.get_session():
            return await AnesthesiaCaseTool.get_anesthesia_case_context(
                session=session, procedure_id=procedure_id, patient_id=patient_id,
            )

    mcp_server.register_tool(td, handler)
    logger.info("Registered tool: get_anesthesia_case_context")


# ---------------------------------------------------------------------------
# Tool 9: get_neuro_event_context
# ---------------------------------------------------------------------------

async def _register_neuro_event_context(mcp_server: MCPServer) -> None:
    td = _tool_def(
        "get_neuro_event_context",
        "Retrieve neurological event context including seizures, EEG findings, "
        "neuroimaging, vital signs, management medications, and clinical assessments",
        {
            "patient_id": {"type": "string", "description": "Patient ID (optional)"},
            "event_id": {"type": "string", "description": "Neuro event ID (optional)"},
        },
        [],
    )

    async def handler(patient_id: Optional[str] = None, event_id: Optional[str] = None) -> dict:
        async for session in DatabaseConnection.get_session():
            return await NeuroEventTool.get_neuro_event_context(
                session=session, patient_id=patient_id, event_id=event_id,
            )

    mcp_server.register_tool(td, handler)
    logger.info("Registered tool: get_neuro_event_context")


# ---------------------------------------------------------------------------
# Tool 10: get_cardiology_event_context
# ---------------------------------------------------------------------------

async def _register_cardiology_event_context(mcp_server: MCPServer) -> None:
    td = _tool_def(
        "get_cardiology_event_context",
        "Retrieve cardiac event context including ECG events, arrhythmias, "
        "hemodynamic trends, cardiac medications, related diagnostics, and assessments",
        {
            "patient_id": {"type": "string", "description": "Patient ID (optional)"},
            "event_id": {"type": "string", "description": "Cardiac event ID (optional)"},
        },
        [],
    )

    async def handler(patient_id: Optional[str] = None, event_id: Optional[str] = None) -> dict:
        async for session in DatabaseConnection.get_session():
            return await CardiologyEventTool.get_cardiology_event_context(
                session=session, patient_id=patient_id, event_id=event_id,
            )

    mcp_server.register_tool(td, handler)
    logger.info("Registered tool: get_cardiology_event_context")
