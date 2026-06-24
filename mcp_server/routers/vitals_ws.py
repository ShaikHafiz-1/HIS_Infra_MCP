"""
WebSocket router — real-time patient vital sign streaming.

Clients connect to ws://<host>/api/v1/vitals/stream and receive a JSON
frame every 2 seconds containing all patient snapshots.

Each frame:
{
  "ts": <unix epoch float>,
  "patients": [<VitalSnapshot dict>, ...]
}
"""

import asyncio
import json
import time
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/api/v1/vitals", tags=["Vitals Streaming"])

# Connected WebSocket clients
_active_connections: Set[WebSocket] = set()


@router.websocket("/stream")
async def vitals_stream(websocket: WebSocket):
    """Stream live vital sign snapshots to connected UI clients."""
    await websocket.accept()
    _active_connections.add(websocket)
    try:
        from simulator.patient_monitor import get_simulator
        sim = get_simulator()

        while True:
            snaps = sim.get_all_snapshots()
            profs = {p.patient_id: p for p in sim.get_all_profiles()}
            payload = {
                "ts": time.time(),
                "patients": [
                    {
                        **sim.snapshot_as_dict(s),
                        "name":         profs[s.patient_id].name,
                        "unit":         profs[s.patient_id].unit,
                        "bed":          profs[s.patient_id].bed,
                        "scenario":     profs[s.patient_id].scenario,
                        "admission_dx": profs[s.patient_id].admission_dx,
                    }
                    for s in snaps
                ],
            }
            await websocket.send_text(json.dumps(payload, default=str))
            await asyncio.sleep(2.0)

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        _active_connections.discard(websocket)


@router.get("/snapshot")
async def get_vitals_snapshot():
    """REST fallback: current snapshot for all patients (for non-WS clients)."""
    from simulator.patient_monitor import get_simulator
    sim   = get_simulator()
    snaps = sim.get_all_snapshots()
    profs = {p.patient_id: p for p in sim.get_all_profiles()}
    return {
        "ts": time.time(),
        "patients": [
            {
                **sim.snapshot_as_dict(s),
                "name":         profs[s.patient_id].name,
                "unit":         profs[s.patient_id].unit,
                "bed":          profs[s.patient_id].bed,
                "scenario":     profs[s.patient_id].scenario,
                "admission_dx": profs[s.patient_id].admission_dx,
            }
            for s in snaps
        ],
    }


@router.get("/alarms")
async def get_active_alarms():
    """All currently active alarms across all patients, sorted by severity."""
    from simulator.patient_monitor import get_simulator
    sim    = get_simulator()
    alarms = sim.get_active_alarms()
    profs  = {p.patient_id: p for p in sim.get_all_profiles()}
    return [
        {
            **a.__dict__,
            "patient_name": profs.get(a.patient_id, type("", (), {"name": "Unknown"})()).name,
            "unit":         profs.get(a.patient_id, type("", (), {"unit": "Unknown"})()).unit,
            "bed":          profs.get(a.patient_id, type("", (), {"bed": "Unknown"})()).bed,
        }
        for a in alarms
    ]


@router.get("/connections")
async def connection_count():
    """Return number of active WebSocket connections (for MCP Ops dashboard)."""
    return {"active_ws_connections": len(_active_connections)}
