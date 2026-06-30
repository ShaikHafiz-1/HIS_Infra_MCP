"""
FHIR MCP Tool Registry.

Registers 13 new FHIR-backed tools alongside the existing 10 simulator tools.
Tool names are prefixed with 'fhir_' to avoid collision with existing tools.

Each handler delegates to mcp_server.fhir.fhir_tools (business logic) via
asyncio.to_thread() so the synchronous FHIR connector doesn't block the
FastAPI event loop.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from mcp_server.mcp_server import MCPServer
from mcp_server.models.schemas import MCPToolDefinition, ToolInputSchema, ToolOutputSchema
from mcp_server.utils.logger import get_logger

logger = get_logger(__name__)


def _fhir_tool_def(name: str, description: str, properties: dict, required: list) -> MCPToolDefinition:
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


async def register_fhir_tools(mcp_server: MCPServer) -> None:
    """Register all 13 FHIR-backed MCP tools."""
    logger.info("Registering FHIR MCP tools...")

    await _reg_fhir_get_patient(mcp_server)
    await _reg_fhir_search_patients(mcp_server)
    await _reg_fhir_get_patient_vitals(mcp_server)
    await _reg_fhir_get_patient_conditions(mcp_server)
    await _reg_fhir_get_patient_medications(mcp_server)
    await _reg_fhir_get_patient_encounters(mcp_server)
    await _reg_fhir_get_icu_patients(mcp_server)
    await _reg_fhir_get_patients_with_low_spo2(mcp_server)
    await _reg_fhir_get_patients_with_high_news2(mcp_server)
    await _reg_fhir_get_patients_with_arrhythmia(mcp_server)
    await _reg_fhir_get_connected_devices(mcp_server)
    await _reg_fhir_get_patient_timeline(mcp_server)
    await _reg_fhir_summarize_patient_status(mcp_server)

    logger.info("Registered 13 FHIR MCP tools")


# ---------------------------------------------------------------------------
# Tool 1 — fhir_get_patient
# ---------------------------------------------------------------------------

async def _reg_fhir_get_patient(mcp_server: MCPServer) -> None:
    td = _fhir_tool_def(
        "fhir_get_patient",
        "Retrieve a FHIR patient by ID including demographics, vitals, conditions, "
        "medications, devices, and allergies from the configured FHIR R4 server. "
        "Falls back to simulator if FHIR is not configured.",
        {"patient_id": {"type": "string", "description": "FHIR Patient resource ID"}},
        ["patient_id"],
    )

    async def handler(patient_id: str) -> dict:
        from mcp_server.fhir.fhir_tools import get_patient_by_id
        return await asyncio.to_thread(get_patient_by_id, patient_id)

    mcp_server.register_tool(td, handler)
    logger.info("Registered FHIR tool: fhir_get_patient")


# ---------------------------------------------------------------------------
# Tool 2 — fhir_search_patients
# ---------------------------------------------------------------------------

async def _reg_fhir_search_patients(mcp_server: MCPServer) -> None:
    td = _fhir_tool_def(
        "fhir_search_patients",
        "Search FHIR patients by name. Returns list of matching patients with demographics.",
        {"name": {"type": "string", "description": "Patient name or partial name to search"}},
        ["name"],
    )

    async def handler(name: str) -> dict:
        from mcp_server.fhir.fhir_tools import search_patients
        return await asyncio.to_thread(search_patients, name)

    mcp_server.register_tool(td, handler)
    logger.info("Registered FHIR tool: fhir_search_patients")


# ---------------------------------------------------------------------------
# Tool 3 — fhir_get_patient_vitals
# ---------------------------------------------------------------------------

async def _reg_fhir_get_patient_vitals(mcp_server: MCPServer) -> None:
    td = _fhir_tool_def(
        "fhir_get_patient_vitals",
        "Retrieve latest vital signs from FHIR Observations (HR, SpO2, RR, BP, Temp). "
        "Computes NEWS2 score from retrieved values.",
        {
            "patient_id": {"type": "string", "description": "FHIR Patient resource ID"},
            "limit":      {"type": "integer", "description": "Max observations to fetch (default 20)", "default": 20},
        },
        ["patient_id"],
    )

    async def handler(patient_id: str, limit: int = 20) -> dict:
        from mcp_server.fhir.fhir_tools import get_patient_vitals
        return await asyncio.to_thread(get_patient_vitals, patient_id, limit)

    mcp_server.register_tool(td, handler)
    logger.info("Registered FHIR tool: fhir_get_patient_vitals")


# ---------------------------------------------------------------------------
# Tool 4 — fhir_get_patient_conditions
# ---------------------------------------------------------------------------

async def _reg_fhir_get_patient_conditions(mcp_server: MCPServer) -> None:
    td = _fhir_tool_def(
        "fhir_get_patient_conditions",
        "Retrieve active clinical conditions and diagnoses for a FHIR patient.",
        {"patient_id": {"type": "string", "description": "FHIR Patient resource ID"}},
        ["patient_id"],
    )

    async def handler(patient_id: str) -> dict:
        from mcp_server.fhir.fhir_tools import get_patient_conditions
        return await asyncio.to_thread(get_patient_conditions, patient_id)

    mcp_server.register_tool(td, handler)
    logger.info("Registered FHIR tool: fhir_get_patient_conditions")


# ---------------------------------------------------------------------------
# Tool 5 — fhir_get_patient_medications
# ---------------------------------------------------------------------------

async def _reg_fhir_get_patient_medications(mcp_server: MCPServer) -> None:
    td = _fhir_tool_def(
        "fhir_get_patient_medications",
        "Retrieve active MedicationRequests for a FHIR patient.",
        {"patient_id": {"type": "string", "description": "FHIR Patient resource ID"}},
        ["patient_id"],
    )

    async def handler(patient_id: str) -> dict:
        from mcp_server.fhir.fhir_tools import get_patient_medications
        return await asyncio.to_thread(get_patient_medications, patient_id)

    mcp_server.register_tool(td, handler)
    logger.info("Registered FHIR tool: fhir_get_patient_medications")


# ---------------------------------------------------------------------------
# Tool 6 — fhir_get_patient_encounters
# ---------------------------------------------------------------------------

async def _reg_fhir_get_patient_encounters(mcp_server: MCPServer) -> None:
    td = _fhir_tool_def(
        "fhir_get_patient_encounters",
        "Retrieve encounter history for a FHIR patient including admissions and ED visits.",
        {"patient_id": {"type": "string", "description": "FHIR Patient resource ID"}},
        ["patient_id"],
    )

    async def handler(patient_id: str) -> dict:
        from mcp_server.fhir.fhir_tools import get_patient_encounters
        return await asyncio.to_thread(get_patient_encounters, patient_id)

    mcp_server.register_tool(td, handler)
    logger.info("Registered FHIR tool: fhir_get_patient_encounters")


# ---------------------------------------------------------------------------
# Tool 7 — fhir_get_icu_patients
# ---------------------------------------------------------------------------

async def _reg_fhir_get_icu_patients(mcp_server: MCPServer) -> None:
    td = _fhir_tool_def(
        "fhir_get_icu_patients",
        "Retrieve all current inpatient (IMP class) encounters from FHIR as an ICU census. "
        "Returns patient list with demographics and encounter metadata.",
        {},
        [],
    )

    async def handler() -> dict:
        from mcp_server.fhir.fhir_tools import get_icu_patients
        return await asyncio.to_thread(get_icu_patients)

    mcp_server.register_tool(td, handler)
    logger.info("Registered FHIR tool: fhir_get_icu_patients")


# ---------------------------------------------------------------------------
# Tool 8 — fhir_get_patients_with_low_spo2
# ---------------------------------------------------------------------------

async def _reg_fhir_get_patients_with_low_spo2(mcp_server: MCPServer) -> None:
    td = _fhir_tool_def(
        "fhir_get_patients_with_low_spo2",
        "Find FHIR patients with SpO2 observations below a specified threshold. "
        "Queries Observation resources with code 59408-5 (pulse oximetry).",
        {
            "threshold": {
                "type": "number",
                "description": "SpO2 percentage threshold (default 90.0)",
                "default": 90.0,
            }
        },
        [],
    )

    async def handler(threshold: float = 90.0) -> dict:
        from mcp_server.fhir.fhir_tools import get_patients_with_low_spo2
        return await asyncio.to_thread(get_patients_with_low_spo2, threshold)

    mcp_server.register_tool(td, handler)
    logger.info("Registered FHIR tool: fhir_get_patients_with_low_spo2")


# ---------------------------------------------------------------------------
# Tool 9 — fhir_get_patients_with_high_news2
# ---------------------------------------------------------------------------

async def _reg_fhir_get_patients_with_high_news2(mcp_server: MCPServer) -> None:
    td = _fhir_tool_def(
        "fhir_get_patients_with_high_news2",
        "Find FHIR patients with NEWS2 score at or above threshold. "
        "Retrieves inpatient encounters, fetches vitals, and computes NEWS2 per RCP 2017.",
        {
            "threshold": {
                "type": "integer",
                "description": "NEWS2 score threshold (default 5 = High risk)",
                "default": 5,
            }
        },
        [],
    )

    async def handler(threshold: int = 5) -> dict:
        from mcp_server.fhir.fhir_tools import get_patients_with_high_news2
        return await asyncio.to_thread(get_patients_with_high_news2, threshold)

    mcp_server.register_tool(td, handler)
    logger.info("Registered FHIR tool: fhir_get_patients_with_high_news2")


# ---------------------------------------------------------------------------
# Tool 10 — fhir_get_patients_with_arrhythmia
# ---------------------------------------------------------------------------

async def _reg_fhir_get_patients_with_arrhythmia(mcp_server: MCPServer) -> None:
    td = _fhir_tool_def(
        "fhir_get_patients_with_arrhythmia",
        "Find FHIR patients with arrhythmia conditions (SNOMED 698247002, ICD-10 I49.9/I48).",
        {},
        [],
    )

    async def handler() -> dict:
        from mcp_server.fhir.fhir_tools import get_patients_with_arrhythmia
        return await asyncio.to_thread(get_patients_with_arrhythmia)

    mcp_server.register_tool(td, handler)
    logger.info("Registered FHIR tool: fhir_get_patients_with_arrhythmia")


# ---------------------------------------------------------------------------
# Tool 11 — fhir_get_connected_devices
# ---------------------------------------------------------------------------

async def _reg_fhir_get_connected_devices(mcp_server: MCPServer) -> None:
    td = _fhir_tool_def(
        "fhir_get_connected_devices",
        "Retrieve Device resources associated with a FHIR patient.",
        {"patient_id": {"type": "string", "description": "FHIR Patient resource ID"}},
        ["patient_id"],
    )

    async def handler(patient_id: str) -> dict:
        from mcp_server.fhir.fhir_tools import get_connected_devices
        return await asyncio.to_thread(get_connected_devices, patient_id)

    mcp_server.register_tool(td, handler)
    logger.info("Registered FHIR tool: fhir_get_connected_devices")


# ---------------------------------------------------------------------------
# Tool 12 — fhir_get_patient_timeline
# ---------------------------------------------------------------------------

async def _reg_fhir_get_patient_timeline(mcp_server: MCPServer) -> None:
    td = _fhir_tool_def(
        "fhir_get_patient_timeline",
        "Build a chronological clinical event timeline for a FHIR patient from "
        "Encounters, Observations, and Procedures.",
        {"patient_id": {"type": "string", "description": "FHIR Patient resource ID"}},
        ["patient_id"],
    )

    async def handler(patient_id: str) -> dict:
        from mcp_server.fhir.fhir_tools import get_patient_timeline
        return await asyncio.to_thread(get_patient_timeline, patient_id)

    mcp_server.register_tool(td, handler)
    logger.info("Registered FHIR tool: fhir_get_patient_timeline")


# ---------------------------------------------------------------------------
# Tool 13 — fhir_summarize_patient_status
# ---------------------------------------------------------------------------

async def _reg_fhir_summarize_patient_status(mcp_server: MCPServer) -> None:
    td = _fhir_tool_def(
        "fhir_summarize_patient_status",
        "Generate a full clinical status summary for a FHIR patient: demographics, "
        "vitals, conditions, medications, allergies, devices, and NEWS2 risk assessment.",
        {"patient_id": {"type": "string", "description": "FHIR Patient resource ID"}},
        ["patient_id"],
    )

    async def handler(patient_id: str) -> dict:
        from mcp_server.fhir.fhir_tools import summarize_patient_status
        return await asyncio.to_thread(summarize_patient_status, patient_id)

    mcp_server.register_tool(td, handler)
    logger.info("Registered FHIR tool: fhir_summarize_patient_status")
