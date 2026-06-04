"""
Hospital Clinical Intelligence MCP Platform — Quick Demo

Runs entirely in-memory (SQLite, no external services needed).
Seeds two patients and demonstrates all 10 MCP tools.

Usage:
    python demo.py
"""

import asyncio
import json
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# ── bootstrap ──────────────────────────────────────────────────────────────

ENGINE = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
SESSION = sessionmaker(ENGINE, class_=AsyncSession, expire_on_commit=False, autoflush=False)


async def _seed(session: AsyncSession) -> None:
    """Create minimal clinical data for the demo."""
    from mcp_server.database.models import (
        CareUnit, Patient, Encounter, Device, Clinician, ClinicianAssignment,
    )

    cu_icu = CareUnit(id="UNIT-ICU-001", name="Intensive Care Unit", code="ICU",
                      unit_type="intensive_care", is_active=True)
    cu_card = CareUnit(id="UNIT-CARD-001", name="Cardiology", code="CARDIO",
                       unit_type="specialty", is_active=True)

    alice = Patient(id="PAT-001", first_name="Alice", last_name="Johnson",
                    mrn="MRN-001", date_of_birth=datetime(1965, 3, 22, tzinfo=timezone.utc),
                    gender="F", is_active=True)
    bob = Patient(id="PAT-002", first_name="Bob", last_name="Martinez",
                  mrn="MRN-002", date_of_birth=datetime(1978, 8, 14, tzinfo=timezone.utc),
                  gender="M", is_active=True)

    enc_alice = Encounter(
        id="ENC-001", patient_id="PAT-001", care_unit_id="UNIT-ICU-001",
        encounter_type="inpatient",
        admission_time=datetime(2026, 5, 20, tzinfo=timezone.utc),
        is_active=True, chief_complaint="Chest pain",
        admission_diagnosis="Acute MI",
    )
    enc_bob = Encounter(
        id="ENC-002", patient_id="PAT-002", care_unit_id="UNIT-CARD-001",
        encounter_type="inpatient",
        admission_time=datetime(2026, 5, 22, tzinfo=timezone.utc),
        is_active=True, chief_complaint="Palpitations",
        admission_diagnosis="Atrial fibrillation",
    )

    monitor = Device(
        id="DEV-001", encounter_id="ENC-001",
        device_type="cardiac_monitor", device_name="Philips IntelliVue MX800",
        serial_number="SN-MX800-001", manufacturer="Philips", model="MX800",
        location="Bed 3A", is_online=True, battery_level=87.5,
        calibration_status="calibrated", is_active=True,
    )
    vent = Device(
        id="DEV-002", encounter_id="ENC-001",
        device_type="ventilator", device_name="Maquet Servo-U",
        serial_number="SN-SERVO-001", manufacturer="Maquet", model="Servo-U",
        location="Bed 3A", is_online=True, battery_level=100.0,
        calibration_status="calibrated", is_active=True,
    )

    dr_smith = Clinician(
        id="CLIN-001", first_name="Sarah", last_name="Smith",
        email="sarah.smith@hospital.local", role="physician",
        specialty="cardiology", license_number="MD-001", is_active=True,
    )
    nurse_jones = Clinician(
        id="CLIN-002", first_name="Mike", last_name="Jones",
        email="mike.jones@hospital.local", role="nurse",
        specialty="critical_care", license_number="RN-001", is_active=True,
    )

    assign1 = ClinicianAssignment(
        id="ASSIGN-001", clinician_id="CLIN-001", encounter_id="ENC-001",
        role="attending_physician", is_active=True,
    )
    assign2 = ClinicianAssignment(
        id="ASSIGN-002", clinician_id="CLIN-002", encounter_id="ENC-001",
        role="primary_nurse", is_active=True,
    )

    session.add_all([
        cu_icu, cu_card, alice, bob,
        enc_alice, enc_bob, monitor, vent,
        dr_smith, nurse_jones, assign1, assign2,
    ])
    await session.commit()


# ── helpers ────────────────────────────────────────────────────────────────

def _header(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def _show(label: str, value) -> None:
    if isinstance(value, (dict, list)):
        print(f"  {label}: {json.dumps(value, default=str, indent=4)[:400]}")
    else:
        print(f"  {label}: {value}")


# ── demo runs ──────────────────────────────────────────────────────────────

async def demo_patient_context(session: AsyncSession) -> None:
    from mcp_server.tools.patient_context import PatientContextTool

    _header("Tool 1 — get_patient_clinical_context")
    ctx = await PatientContextTool.get_patient_clinical_context(
        session=session, patient_id="PAT-001", include_devices=True,
    )
    print(f"  Patient     : {ctx['patient']['first_name']} {ctx['patient']['last_name']}")
    print(f"  MRN         : {ctx['patient']['mrn']}")
    print(f"  Gender/DOB  : {ctx['patient']['gender']} / {ctx['patient']['date_of_birth']}")
    print(f"  Care Unit   : {ctx['care_unit']['name']}")
    print(f"  Diagnosis   : {ctx['encounter']['admission_diagnosis']}")
    print(f"  Clinicians  : {[c['last_name'] + ' (' + c['role'] + ')' for c in ctx['clinicians']]}")
    print(f"  Devices     : {[d['device_name'] for d in ctx['devices']]}")
    print(f"  Confidence  : {ctx['confidence_score']}")


async def demo_care_unit_summary(session: AsyncSession) -> None:
    from mcp_server.tools.care_unit_summary import CareUnitSummaryTool

    _header("Tool 2 — get_care_unit_summary")
    summary = await CareUnitSummaryTool.get_care_unit_summary(
        session=session, care_unit_id="UNIT-ICU-001",
    )
    print(f"  Unit        : {summary['care_unit']['name']}")
    print(f"  Patients    : {summary['patient_count']}")
    print(f"  Critical    : {summary['critical_patient_count']}")
    for p in summary["active_patients"]:
        print(f"    - Patient {p['patient_id']}: {p.get('status', 'active')}")


async def demo_device_events(session: AsyncSession) -> None:
    from mcp_server.tools.device_events import DeviceEventsTool

    _header("Tool 3 — get_device_events_by_patient")
    result = await DeviceEventsTool.get_device_events_by_patient(
        session=session, patient_id="PAT-001",
    )
    print(f"  Patient     : {result['patient_id']}")
    print(f"  Events      : {result['event_count']}")
    print(f"  Time window : {result['time_window']}")
    print(f"  Confidence  : {result['confidence_score']}")


async def demo_event_timeline(session: AsyncSession) -> None:
    from mcp_server.tools.event_timeline import EventTimelineTool

    _header("Tool 4 — get_patient_event_timeline")
    result = await EventTimelineTool.get_patient_event_timeline(
        session=session, patient_id="PAT-001",
    )
    print(f"  Patient     : {result['patient_id']}")
    print(f"  Events      : {result['event_count']}")
    print(f"  Timeline    : {len(result['timeline'])} entries")
    for evt in result["timeline"][:3]:
        print(f"    [{evt['event_type']:15s}] {evt['timestamp']} — {evt['clinical_significance']}")


async def demo_alarm_context(session: AsyncSession) -> None:
    from mcp_server.tools.alarm_context import AlarmContextTool

    _header("Tool 5 — get_alarm_context")
    result = await AlarmContextTool.get_alarm_context(
        session=session, patient_id="PAT-001",
    )
    print(f"  Patient     : {result['patient']['id']}")
    print(f"  Alarm       : {result['alarm']}")
    print(f"  Significance: {result['clinical_significance']}")
    print(f"  Confidence  : {result['confidence_score']}")


async def demo_diagnostic_exam(session: AsyncSession) -> None:
    from mcp_server.tools.diagnostic_exam import DiagnosticExamTool

    _header("Tool 6 — get_diagnostic_exam_context")
    result = await DiagnosticExamTool.get_diagnostic_exam_context(
        session=session, patient_id="PAT-001",
    )
    print(f"  Exam        : {result['exam']}")
    print(f"  Confidence  : {result['confidence_score']}")


async def demo_imaging_summary(session: AsyncSession) -> None:
    from mcp_server.tools.imaging_summary import ImagingStudySummaryTool

    _header("Tool 7 — get_imaging_study_summary")
    result = await ImagingStudySummaryTool.get_imaging_study_summary(
        session=session, patient_id="PAT-001",
    )
    print(f"  Study       : {result['study']}")
    print(f"  Confidence  : {result['confidence_score']}")


async def demo_anesthesia(session: AsyncSession) -> None:
    from mcp_server.tools.anesthesia_context import AnesthesiaCaseTool

    _header("Tool 8 — get_anesthesia_case_context")
    result = await AnesthesiaCaseTool.get_anesthesia_case_context(
        session=session, patient_id="PAT-001",
    )
    print(f"  Case        : {result['case']}")
    print(f"  Confidence  : {result['confidence_score']}")


async def demo_neuro(session: AsyncSession) -> None:
    from mcp_server.tools.neuro_context import NeuroEventTool

    _header("Tool 9 — get_neuro_event_context")
    result = await NeuroEventTool.get_neuro_event_context(
        session=session, patient_id="PAT-001",
    )
    print(f"  Seizure events : {len(result['seizure_events'])}")
    print(f"  Confidence     : {result['confidence_score']}")


async def demo_cardiology(session: AsyncSession) -> None:
    from mcp_server.tools.cardiology_context import CardiologyEventTool

    _header("Tool 10 — get_cardiology_event_context")
    result = await CardiologyEventTool.get_cardiology_event_context(
        session=session, patient_id="PAT-001",
    )
    print(f"  ECG events  : {len(result['ecg_events'])}")
    print(f"  Confidence  : {result['confidence_score']}")


async def demo_auth_and_rbac() -> None:
    """Show JWT creation and RBAC checks (no DB needed)."""
    from mcp_server.security.auth import AuthenticationManager
    from mcp_server.security.authorization import RBACEngine, PermissionDeniedError

    _header("Authentication & RBAC")

    auth = AuthenticationManager(secret_key="demo-secret-key-min-32-chars-long!!", expiration_hours=8)
    token = auth.create_access_token(
        clinician_id="CLIN-001", clinician_name="Dr. Sarah Smith",
        role="physician", care_units=["UNIT-ICU-001"],
    )
    print(f"  JWT token   : {token[:60]}...")

    payload = auth.verify_token(token)
    print(f"  Verified    : sub={payload['sub']} role={payload['role']}")

    rbac = RBACEngine()
    clinician = {"id": "CLIN-001", "role": "physician", "care_units": ["UNIT-ICU-001"]}

    allowed = await rbac.check_tool_permission(clinician, "get_patient_clinical_context")
    print(f"  Physician -> get_patient_clinical_context : {allowed}")

    nurse = {"id": "CLIN-002", "role": "nurse", "care_units": ["UNIT-ICU-001"]}
    try:
        await rbac.check_tool_permission(nurse, "get_imaging_study_summary")
        print("  Nurse -> get_imaging_study_summary : True")
    except PermissionDeniedError:
        print("  Nurse -> get_imaging_study_summary : DENIED [OK]")

    tech = {"id": "CLIN-003", "role": "technician", "care_units": []}
    try:
        await rbac.check_tool_permission(tech, "get_patient_clinical_context")
    except PermissionDeniedError:
        print("  Technician -> get_patient_clinical_context : DENIED [OK]")


async def demo_audit_log() -> None:
    """Show audit logging."""
    from mcp_server.security.audit_logger import AuditLogger

    _header("Audit Logging (HIPAA)")
    audit = AuditLogger(log_dir="demo_audit_logs")

    log_id = audit.log_tool_call(
        tool_name="get_patient_clinical_context",
        clinician_id="CLIN-001",
        clinician_role="physician",
        arguments={"patient_id": "PAT-001"},
        patient_ids=["PAT-001"],
        success=True,
        response_time_ms=142.3,
    )
    audit.log_authentication_attempt("dr_smith", success=True)
    audit.log_authorization_decision("CLIN-002", "nurse", "get_imaging_study_summary", allowed=False, reason="role restriction")

    logs = audit.get_recent_logs(limit=3)
    print(f"  Log entries : {len(logs)}")
    for entry in logs:
        print(f"    [{entry['event_type']:25s}] {entry.get('tool_name', entry.get('username_partial', entry.get('clinician_id', '?')))}")
    print(f"  Log ID      : {log_id}")


async def demo_performance() -> None:
    """Show performance monitoring."""
    from mcp_server.utils.performance import PerformanceMonitor

    _header("Performance Monitoring")
    monitor = PerformanceMonitor()
    for ms in [120.5, 95.2, 210.8, 88.1, 175.3]:
        monitor.record_tool_call("get_patient_clinical_context", ms, success=True)
    monitor.record_tool_call("get_patient_clinical_context", 2500.0, success=False)

    m = monitor.get_tool_metrics("get_patient_clinical_context")
    print(f"  Tool        : {m.tool_name}")
    print(f"  Total calls : {m.total_calls}")
    print(f"  Errors      : {m.total_errors}  (error rate: {m.error_rate:.1%})")
    print(f"  Avg time    : {m.avg_response_time_ms:.1f}ms")
    print(f"  p95 time    : {m.p95_response_time_ms:.1f}ms")
    slow = monitor.get_slow_query_report()
    print(f"  Slow queries: {len(slow)}")


# ── main ───────────────────────────────────────────────────────────────────

async def main() -> None:
    from mcp_server.database.models import Base

    print("\n" + "="*60)
    print("  Hospital Clinical Intelligence MCP Platform -- Demo")
    print("="*60)
    print("  Mode: in-memory SQLite (no external services required)")

    # Create schema and seed data
    async with ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SESSION() as session:
        await _seed(session)

    # Run each demo section
    async with SESSION() as session:
        await demo_patient_context(session)
        await demo_care_unit_summary(session)
        await demo_device_events(session)
        await demo_event_timeline(session)
        await demo_alarm_context(session)
        await demo_diagnostic_exam(session)
        await demo_imaging_summary(session)
        await demo_anesthesia(session)
        await demo_neuro(session)
        await demo_cardiology(session)

    # Non-DB demos
    await demo_auth_and_rbac()
    await demo_audit_log()
    await demo_performance()

    await ENGINE.dispose()

    print("\n" + "="*60)
    print("  Demo complete: all 10 tools + auth/RBAC/audit/perf shown")
    print("="*60 + "\n")


if __name__ == "__main__":
    import logging
    logging.disable(logging.WARNING)  # suppress Redis/DB connection warnings for clean output
    asyncio.run(main())
