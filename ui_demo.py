"""
Hospital Clinical Intelligence MCP Platform — Streamlit UI Demo

Run with:
    streamlit run ui_demo.py

No external services required. Uses in-memory SQLite with demo patients.
"""

import asyncio
import threading
from datetime import datetime, timezone

import streamlit as st

# ── Page config (must be first Streamlit call) ─────────────────────────────
st.set_page_config(
    page_title="Hospital Clinical Intelligence Platform",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Async helper ───────────────────────────────────────────────────────────
def run_async(coro):
    """Run an async coroutine from a synchronous context (Streamlit)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ── Database + seed (cached so it only runs once per session) ──────────────
@st.cache_resource(show_spinner="Initialising demo database...")
def get_db():
    """Create in-memory SQLite database and return session factory."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)

    async def _setup():
        from mcp_server.database.models import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with SessionLocal() as s:
            await _seed(s)

    run_async(_setup())
    return SessionLocal


async def _seed(session):
    from mcp_server.database.models import (
        CareUnit, Patient, Encounter, Device, Clinician, ClinicianAssignment,
    )
    cu_icu  = CareUnit(id="UNIT-ICU-001",  name="Intensive Care Unit", code="ICU",    unit_type="intensive_care", is_active=True)
    cu_card = CareUnit(id="UNIT-CARD-001", name="Cardiology Ward",     code="CARDIO", unit_type="specialty",      is_active=True)
    cu_neuro= CareUnit(id="UNIT-NEURO-001",name="Neurology",           code="NEURO",  unit_type="specialty",      is_active=True)
    cu_ed   = CareUnit(id="UNIT-ED-001",   name="Emergency Dept",      code="ED",     unit_type="emergency",      is_active=True)

    patients = [
        Patient(id="PAT-001", first_name="Alice",   last_name="Johnson",  mrn="MRN-001", date_of_birth=datetime(1965,3,22,tzinfo=timezone.utc),  gender="F", is_active=True),
        Patient(id="PAT-002", first_name="Bob",     last_name="Martinez", mrn="MRN-002", date_of_birth=datetime(1978,8,14,tzinfo=timezone.utc),  gender="M", is_active=True),
        Patient(id="PAT-003", first_name="Carol",   last_name="Williams", mrn="MRN-003", date_of_birth=datetime(1952,11,5,tzinfo=timezone.utc),  gender="F", is_active=True),
        Patient(id="PAT-004", first_name="David",   last_name="Chen",     mrn="MRN-004", date_of_birth=datetime(1990,6,30,tzinfo=timezone.utc),  gender="M", is_active=True),
        Patient(id="PAT-005", first_name="Eleanor", last_name="Thompson", mrn="MRN-005", date_of_birth=datetime(1943,2,18,tzinfo=timezone.utc),  gender="F", is_active=True),
    ]
    encounters = [
        Encounter(id="ENC-001", patient_id="PAT-001", care_unit_id="UNIT-ICU-001",  encounter_type="inpatient", admission_time=datetime(2026,5,20,tzinfo=timezone.utc), is_active=True, chief_complaint="Chest pain",        admission_diagnosis="Acute MI"),
        Encounter(id="ENC-002", patient_id="PAT-002", care_unit_id="UNIT-CARD-001", encounter_type="inpatient", admission_time=datetime(2026,5,22,tzinfo=timezone.utc), is_active=True, chief_complaint="Palpitations",       admission_diagnosis="Atrial fibrillation"),
        Encounter(id="ENC-003", patient_id="PAT-003", care_unit_id="UNIT-ICU-001",  encounter_type="inpatient", admission_time=datetime(2026,5,19,tzinfo=timezone.utc), is_active=True, chief_complaint="Shortness of breath", admission_diagnosis="COPD exacerbation"),
        Encounter(id="ENC-004", patient_id="PAT-004", care_unit_id="UNIT-NEURO-001",encounter_type="inpatient", admission_time=datetime(2026,5,23,tzinfo=timezone.utc), is_active=True, chief_complaint="Seizure",             admission_diagnosis="New-onset epilepsy"),
        Encounter(id="ENC-005", patient_id="PAT-005", care_unit_id="UNIT-ED-001",   encounter_type="emergency", admission_time=datetime(2026,5,25,tzinfo=timezone.utc), is_active=True, chief_complaint="Fall / hip pain",     admission_diagnosis="Hip fracture"),
    ]
    devices = [
        Device(id="DEV-001", encounter_id="ENC-001", device_type="cardiac_monitor", device_name="Philips IntelliVue MX800",  serial_number="SN-001", manufacturer="Philips", model="MX800",    location="ICU Bed 3A", is_online=True,  battery_level=87.5,  calibration_status="calibrated", is_active=True),
        Device(id="DEV-002", encounter_id="ENC-001", device_type="ventilator",      device_name="Maquet Servo-U",            serial_number="SN-002", manufacturer="Maquet",  model="Servo-U",  location="ICU Bed 3A", is_online=True,  battery_level=100.0, calibration_status="calibrated", is_active=True),
        Device(id="DEV-003", encounter_id="ENC-002", device_type="cardiac_monitor", device_name="GE Healthcare CARESCAPE",   serial_number="SN-003", manufacturer="GE",      model="B450",     location="CARD Bed 7B",is_online=True,  battery_level=72.0,  calibration_status="calibrated", is_active=True),
        Device(id="DEV-004", encounter_id="ENC-003", device_type="pulse_oximeter",  device_name="Masimo Radical-7",          serial_number="SN-004", manufacturer="Masimo",  model="Radical",  location="ICU Bed 1C", is_online=True,  battery_level=55.0,  calibration_status="calibrated", is_active=True),
        Device(id="DEV-005", encounter_id="ENC-003", device_type="ventilator",      device_name="Draeger Evita Infinity V500",serial_number="SN-005", manufacturer="Draeger", model="V500",     location="ICU Bed 1C", is_online=False, battery_level=0.0,   calibration_status="due",        is_active=True),
    ]
    clinicians = [
        Clinician(id="CLIN-001", first_name="Sarah",   last_name="Smith",   email="sarah.smith@hospital.local",   role="physician", specialty="cardiology",       license_number="MD-001", is_active=True),
        Clinician(id="CLIN-002", first_name="Michael", last_name="Jones",   email="michael.jones@hospital.local", role="nurse",     specialty="critical_care",    license_number="RN-001", is_active=True),
        Clinician(id="CLIN-003", first_name="Linda",   last_name="Patel",   email="linda.patel@hospital.local",   role="physician", specialty="neurology",        license_number="MD-002", is_active=True),
        Clinician(id="CLIN-004", first_name="James",   last_name="Wilson",  email="james.wilson@hospital.local",  role="nurse",     specialty="emergency",        license_number="RN-002", is_active=True),
    ]
    assignments = [
        ClinicianAssignment(id="ASSIGN-001", clinician_id="CLIN-001", encounter_id="ENC-001", role="attending_physician", is_active=True),
        ClinicianAssignment(id="ASSIGN-002", clinician_id="CLIN-002", encounter_id="ENC-001", role="primary_nurse",       is_active=True),
        ClinicianAssignment(id="ASSIGN-003", clinician_id="CLIN-001", encounter_id="ENC-002", role="attending_physician", is_active=True),
        ClinicianAssignment(id="ASSIGN-004", clinician_id="CLIN-003", encounter_id="ENC-004", role="attending_physician", is_active=True),
        ClinicianAssignment(id="ASSIGN-005", clinician_id="CLIN-004", encounter_id="ENC-005", role="primary_nurse",       is_active=True),
    ]
    session.add_all([cu_icu, cu_card, cu_neuro, cu_ed] + patients + encounters + devices + clinicians + assignments)
    await session.commit()


# ── Styling ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.card {
    background: #1e2d3d;
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 10px;
    border-left: 4px solid #2196f3;
}
.card-critical { border-left-color: #f44336; }
.card-warning  { border-left-color: #ff9800; }
.card-ok       { border-left-color: #4caf50; }
.metric-big { font-size: 2.2rem; font-weight: 700; }
.label { font-size: 0.78rem; color: #90a4ae; text-transform: uppercase; letter-spacing: 0.05em; }
.badge-red   { background:#f44336; color:white; padding:2px 8px; border-radius:12px; font-size:0.75rem; }
.badge-amber { background:#ff9800; color:white; padding:2px 8px; border-radius:12px; font-size:0.75rem; }
.badge-green { background:#4caf50; color:white; padding:2px 8px; border-radius:12px; font-size:0.75rem; }
.badge-blue  { background:#2196f3; color:white; padding:2px 8px; border-radius:12px; font-size:0.75rem; }
</style>
""", unsafe_allow_html=True)


# ── Patient registry ───────────────────────────────────────────────────────
PATIENTS = {
    "PAT-001": {"name": "Alice Johnson",   "age": 61, "gender": "F", "mrn": "MRN-001", "unit": "Intensive Care Unit",  "diagnosis": "Acute MI",             "acuity": "critical"},
    "PAT-002": {"name": "Bob Martinez",    "age": 48, "gender": "M", "mrn": "MRN-002", "unit": "Cardiology Ward",      "diagnosis": "Atrial fibrillation",  "acuity": "moderate"},
    "PAT-003": {"name": "Carol Williams",  "age": 74, "gender": "F", "mrn": "MRN-003", "unit": "Intensive Care Unit",  "diagnosis": "COPD Exacerbation",    "acuity": "critical"},
    "PAT-004": {"name": "David Chen",      "age": 36, "gender": "M", "mrn": "MRN-004", "unit": "Neurology",            "diagnosis": "New-onset Epilepsy",   "acuity": "moderate"},
    "PAT-005": {"name": "Eleanor Thompson","age": 83, "gender": "F", "mrn": "MRN-005", "unit": "Emergency Dept",       "diagnosis": "Hip Fracture",         "acuity": "stable"},
}

ACUITY_BADGE = {
    "critical": '<span class="badge-red">CRITICAL</span>',
    "moderate": '<span class="badge-amber">MODERATE</span>',
    "stable":   '<span class="badge-green">STABLE</span>',
}

UNITS = {
    "UNIT-ICU-001":   "Intensive Care Unit",
    "UNIT-CARD-001":  "Cardiology Ward",
    "UNIT-NEURO-001": "Neurology",
    "UNIT-ED-001":    "Emergency Dept",
}


# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/hospital.png", width=60)
    st.title("Clinical Intelligence")
    st.caption("Hospital MCP Platform v0.1.0")
    st.divider()

    page = st.radio(
        "Navigation",
        ["🏠  Dashboard", "👤  Patient Explorer", "🏢  Care Units", "🔔  Alarms", "🔐  Auth & Security", "📊  Platform Metrics"],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("Demo mode — SQLite in-memory")
    st.caption("No external services required")


# ══════════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ══════════════════════════════════════════════════════════════════════════
if page == "🏠  Dashboard":
    st.title("🏥 Clinical Operations Dashboard")
    st.caption(f"Last updated: {datetime.now().strftime('%d %b %Y  %H:%M')}")

    # KPI row
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Patients", "5", delta="+2 today")
    c2.metric("Critical", "2", delta="+1", delta_color="inverse")
    c3.metric("Active Devices", "5", delta="3 online")
    c4.metric("Open Alarms", "3", delta="+1", delta_color="inverse")

    st.divider()

    # Patient census
    st.subheader("Patient Census")
    col_left, col_right = st.columns([3, 2])

    with col_left:
        for pid, info in PATIENTS.items():
            badge = ACUITY_BADGE[info["acuity"]]
            st.markdown(f"""
            <div class="card {'card-critical' if info['acuity']=='critical' else 'card-warning' if info['acuity']=='moderate' else 'card-ok'}">
                <div style="display:flex; justify-content:space-between; align-items:center">
                    <div>
                        <strong>{info['name']}</strong> &nbsp; {badge}
                        <div class="label">{info['mrn']} &nbsp;|&nbsp; {info['gender']}, {info['age']} yrs</div>
                    </div>
                    <div style="text-align:right">
                        <div style="font-size:0.85rem">{info['unit']}</div>
                        <div class="label">{info['diagnosis']}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    with col_right:
        st.subheader("Active Alarms")
        alarms = [
            ("PAT-001", "Alice Johnson",   "HIGH Heart Rate",   "high_heart_rate", "128 bpm", "red"),
            ("PAT-001", "Alice Johnson",   "Ventilator Alarm",  "high_pressure",   "38 cmH2O","orange"),
            ("PAT-003", "Carol Williams",  "SpO2 Low",          "spo2_critical",   "88%",     "red"),
        ]
        for pid, name, label, atype, val, color in alarms:
            icon = "🔴" if color == "red" else "🟠"
            st.markdown(f"""
            <div class="card card-{'critical' if color=='red' else 'warning'}">
                {icon} <strong>{label}</strong><br>
                <span class="label">{name} &nbsp;|&nbsp; {val}</span>
            </div>
            """, unsafe_allow_html=True)

        st.subheader("Device Status")
        devs = [
            ("Philips MX800",    "cardiac_monitor", "Online",  "green"),
            ("Maquet Servo-U",   "ventilator",      "Online",  "green"),
            ("GE CARESCAPE B450","cardiac_monitor", "Online",  "green"),
            ("Masimo Radical-7", "pulse_oximeter",  "Online",  "green"),
            ("Draeger V500",     "ventilator",      "Offline", "red"),
        ]
        for name, dtype, status, color in devs:
            icon = "🟢" if color == "green" else "🔴"
            st.markdown(f"{icon} **{name}** — `{dtype}` — *{status}*")


# ══════════════════════════════════════════════════════════════════════════
# PAGE: PATIENT EXPLORER
# ══════════════════════════════════════════════════════════════════════════
elif page == "👤  Patient Explorer":
    st.title("Patient Explorer")
    st.caption("Select a patient and tool to retrieve clinical context")

    col_sel, col_tool = st.columns([1, 1])
    with col_sel:
        patient_label = st.selectbox(
            "Patient",
            options=list(PATIENTS.keys()),
            format_func=lambda pid: f"{PATIENTS[pid]['name']} ({PATIENTS[pid]['mrn']})",
        )
    with col_tool:
        tool_choice = st.selectbox(
            "MCP Tool",
            [
                "get_patient_clinical_context",
                "get_device_events_by_patient",
                "get_patient_event_timeline",
                "get_alarm_context",
                "get_diagnostic_exam_context",
                "get_imaging_study_summary",
                "get_anesthesia_case_context",
                "get_neuro_event_context",
                "get_cardiology_event_context",
            ],
        )

    if st.button("Run Tool", type="primary", use_container_width=True):
        SessionLocal = get_db()

        with st.spinner(f"Calling {tool_choice}..."):
            async def _run():
                async with SessionLocal() as session:
                    if tool_choice == "get_patient_clinical_context":
                        from mcp_server.tools.patient_context import PatientContextTool
                        return await PatientContextTool.get_patient_clinical_context(session=session, patient_id=patient_label, include_devices=True)
                    elif tool_choice == "get_device_events_by_patient":
                        from mcp_server.tools.device_events import DeviceEventsTool
                        return await DeviceEventsTool.get_device_events_by_patient(session=session, patient_id=patient_label)
                    elif tool_choice == "get_patient_event_timeline":
                        from mcp_server.tools.event_timeline import EventTimelineTool
                        return await EventTimelineTool.get_patient_event_timeline(session=session, patient_id=patient_label)
                    elif tool_choice == "get_alarm_context":
                        from mcp_server.tools.alarm_context import AlarmContextTool
                        return await AlarmContextTool.get_alarm_context(session=session, patient_id=patient_label)
                    elif tool_choice == "get_diagnostic_exam_context":
                        from mcp_server.tools.diagnostic_exam import DiagnosticExamTool
                        return await DiagnosticExamTool.get_diagnostic_exam_context(session=session, patient_id=patient_label)
                    elif tool_choice == "get_imaging_study_summary":
                        from mcp_server.tools.imaging_summary import ImagingStudySummaryTool
                        return await ImagingStudySummaryTool.get_imaging_study_summary(session=session, patient_id=patient_label)
                    elif tool_choice == "get_anesthesia_case_context":
                        from mcp_server.tools.anesthesia_context import AnesthesiaCaseTool
                        return await AnesthesiaCaseTool.get_anesthesia_case_context(session=session, patient_id=patient_label)
                    elif tool_choice == "get_neuro_event_context":
                        from mcp_server.tools.neuro_context import NeuroEventTool
                        return await NeuroEventTool.get_neuro_event_context(session=session, patient_id=patient_label)
                    elif tool_choice == "get_cardiology_event_context":
                        from mcp_server.tools.cardiology_context import CardiologyEventTool
                        return await CardiologyEventTool.get_cardiology_event_context(session=session, patient_id=patient_label)

            result = run_async(_run())

        # ── Display result ──────────────────────────────────────────────
        pinfo = PATIENTS[patient_label]
        badge = ACUITY_BADGE[pinfo["acuity"]]
        st.markdown(f"""
        <div class="card">
            <strong>{pinfo['name']}</strong> &nbsp; {badge} &nbsp;
            <span class="label">{pinfo['mrn']} | {pinfo['unit']} | {pinfo['diagnosis']}</span>
        </div>
        """, unsafe_allow_html=True)

        if tool_choice == "get_patient_clinical_context":
            c1, c2, c3 = st.columns(3)
            c1.metric("Confidence Score", f"{result['confidence_score']:.0%}")
            c2.metric("Clinicians Assigned", len(result.get("clinicians", [])))
            c3.metric("Active Devices", len(result.get("devices", [])))

            tab1, tab2, tab3, tab4 = st.tabs(["Demographics", "Encounter", "Clinicians", "Devices"])
            with tab1:
                p = result["patient"]
                st.markdown(f"**Name:** {p['first_name']} {p['last_name']}")
                st.markdown(f"**MRN:** `{p['mrn']}`")
                st.markdown(f"**Gender:** {p.get('gender','—')}  **DOB:** {p.get('date_of_birth','—')}")
            with tab2:
                if result.get("encounter"):
                    enc = result["encounter"]
                    st.markdown(f"**Type:** {enc.get('encounter_type','—')}")
                    st.markdown(f"**Admitted:** {enc.get('admission_time','—')}")
                    st.markdown(f"**Chief Complaint:** {enc.get('chief_complaint','—')}")
                    st.markdown(f"**Diagnosis:** {enc.get('admission_diagnosis','—')}")
                    if result.get("care_unit"):
                        st.markdown(f"**Care Unit:** {result['care_unit']['name']}")
            with tab3:
                for clin in result.get("clinicians", []):
                    st.markdown(f"- **{clin['first_name']} {clin['last_name']}** — `{clin['role']}` / {clin.get('specialty','')}")
                if not result.get("clinicians"):
                    st.info("No clinicians assigned")
            with tab4:
                for dev in result.get("devices", []):
                    status = "🟢 Online" if dev.get("is_online") else "🔴 Offline"
                    st.markdown(f"- **{dev['device_name']}** (`{dev['device_type']}`) — {status} — Battery: {dev.get('battery_level',0):.0f}%")
                if not result.get("devices"):
                    st.info("No devices assigned")

        elif tool_choice == "get_patient_event_timeline":
            events = result.get("timeline", [])
            st.metric("Total Events", result.get("event_count", 0))
            if events:
                import pandas as pd
                df = pd.DataFrame([{
                    "Timestamp": e.get("timestamp","")[:19].replace("T"," "),
                    "Type": e.get("event_type",""),
                    "Significance": e.get("clinical_significance","normal"),
                    "Source": e.get("source",""),
                } for e in events])

                def color_sig(val):
                    colors = {
                        "critical": "background-color:#f44336; color:white",
                        "critical_high": "background-color:#f44336; color:white",
                        "critical_low": "background-color:#9c27b0; color:white",
                        "abnormal_high": "background-color:#ff9800; color:white",
                        "abnormal_low": "background-color:#2196f3; color:white",
                        "normal": "background-color:#4caf50; color:white",
                    }
                    return colors.get(val, "")

                styled = df.style.applymap(color_sig, subset=["Significance"])
                st.dataframe(styled, use_container_width=True, hide_index=True)
            else:
                st.info("No timeline events found")

        elif tool_choice == "get_alarm_context":
            alarm = result.get("alarm", {})
            sig = result.get("clinical_significance", "unknown")
            c1, c2, c3 = st.columns(3)
            c1.metric("Alarm Type", alarm.get("alarm_type", "—").replace("_", " ").title())
            c2.metric("Severity", alarm.get("severity", "—").upper())
            c3.metric("Value", f"{alarm.get('current_value','—')} {alarm.get('unit','')}")
            st.markdown(f"**Clinical Significance:** `{sig}`")
            st.markdown(f"**Device:** `{alarm.get('device_type','—')}` (ID: `{alarm.get('device_id','—')}`)")
            st.markdown(f"**Threshold:** {alarm.get('threshold','—')} {alarm.get('unit','')}")
            st.markdown(f"**Acknowledged:** {'Yes' if alarm.get('acknowledged') else 'No'}")
            st.metric("Confidence", f"{result.get('confidence_score',0):.0%}")

        elif tool_choice == "get_imaging_study_summary":
            study = result.get("study", {})
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Modality:** {study.get('modality','—')}")
                st.markdown(f"**Description:** {study.get('description','—')}")
                st.markdown(f"**Status:** `{study.get('report_status','—')}`")
                st.markdown(f"**Radiologist:** {study.get('radiologist','—')}")
                st.markdown(f"**Clinical Indication:** {study.get('clinical_indication','—')}")
            with col2:
                dicom = study.get("dicom_metadata", {})
                if dicom:
                    st.markdown("**DICOM Metadata**")
                    st.markdown(f"- Series: {dicom.get('series_count','—')}")
                    st.markdown(f"- Images: {dicom.get('image_count','—')}")
                    st.markdown(f"- Field Strength: {dicom.get('field_strength','—')}")
            if study.get("findings"):
                st.markdown("**Findings:**")
                st.info(study["findings"])
            if study.get("impression"):
                st.markdown("**Impression:**")
                st.success(study["impression"])
            if study.get("follow_up_recommendations"):
                st.markdown("**Follow-up:**")
                for rec in study["follow_up_recommendations"]:
                    st.markdown(f"- {rec}")

        elif tool_choice == "get_device_events_by_patient":
            c1, c2 = st.columns(2)
            c1.metric("Total Events", result.get("event_count", 0))
            c2.metric("Confidence", f"{result.get('confidence_score',0):.0%}")
            tw = result.get("time_window", {})
            st.caption(f"Time window: {tw.get('start_time','')[:10]} to {tw.get('end_time','')[:10]}")
            events = result.get("device_events", [])
            if events:
                import pandas as pd
                df = pd.DataFrame([{
                    "Time": e.get("timestamp","")[:19].replace("T"," "),
                    "Device": e.get("device_id",""),
                    "Type": e.get("event_type",""),
                    "Severity": e.get("severity",""),
                    "Message": e.get("message",""),
                } for e in events[:20]])
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No device events in window")

        else:
            # Generic JSON view for remaining tools
            st.metric("Confidence", f"{result.get('confidence_score',0):.0%}")
            st.json(result)


# ══════════════════════════════════════════════════════════════════════════
# PAGE: CARE UNITS
# ══════════════════════════════════════════════════════════════════════════
elif page == "🏢  Care Units":
    st.title("Care Unit Overview")

    unit_choice = st.selectbox(
        "Select Care Unit",
        options=list(UNITS.keys()),
        format_func=lambda uid: UNITS[uid],
    )

    if st.button("Load Unit Summary", type="primary"):
        SessionLocal = get_db()
        with st.spinner("Loading care unit summary..."):
            async def _load_unit():
                async with SessionLocal() as session:
                    from mcp_server.tools.care_unit_summary import CareUnitSummaryTool
                    return await CareUnitSummaryTool.get_care_unit_summary(session=session, care_unit_id=unit_choice)
            result = run_async(_load_unit())

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Patients",    result.get("patient_count", 0))
        c2.metric("Critical Patients", result.get("critical_patient_count", 0))
        c3.metric("Confidence",        f"{result.get('confidence_score',0):.0%}")
        cu = result.get("care_unit", {})
        c4.metric("Unit Code", cu.get("code", "—"))

        st.subheader(f"{cu.get('name','Unit')} — Active Patients")
        for p in result.get("active_patients", []):
            pid = p.get("patient_id","")
            pinfo = PATIENTS.get(pid, {})
            badge = ACUITY_BADGE.get(pinfo.get("acuity","stable"), "")
            st.markdown(f"""
            <div class="card">
                <strong>{pinfo.get('name', pid)}</strong> &nbsp; {badge}
                <span class="label"> &nbsp;|&nbsp; {pinfo.get('mrn','—')} &nbsp;|&nbsp; {pinfo.get('diagnosis','—')}</span>
            </div>
            """, unsafe_allow_html=True)

        if result.get("clinician_assignments"):
            st.subheader("Clinician Assignments")
            for ca in result["clinician_assignments"]:
                st.markdown(f"- **{ca.get('clinician_name', ca.get('clinician_id','?'))}** — `{ca.get('role','—')}`")


# ══════════════════════════════════════════════════════════════════════════
# PAGE: ALARMS
# ══════════════════════════════════════════════════════════════════════════
elif page == "🔔  Alarms":
    st.title("Active Alarm Console")

    alarm_data = [
        {"patient": "Alice Johnson",   "pid": "PAT-001", "type": "High Heart Rate",   "value": "128 bpm",  "threshold": "120 bpm",  "device": "Philips MX800",    "severity": "HIGH",     "time": "2026-05-25 14:32"},
        {"patient": "Carol Williams",  "pid": "PAT-003", "type": "SpO2 Critical Low",  "value": "88%",      "threshold": "92%",       "device": "Masimo Radical-7", "severity": "CRITICAL", "time": "2026-05-25 14:41"},
        {"patient": "Alice Johnson",   "pid": "PAT-001", "type": "High Airway Pressure","value":"38 cmH2O", "threshold": "35 cmH2O", "device": "Maquet Servo-U",   "severity": "MEDIUM",   "time": "2026-05-25 14:15"},
    ]

    sev_filter = st.multiselect("Filter by severity", ["CRITICAL", "HIGH", "MEDIUM"], default=["CRITICAL", "HIGH", "MEDIUM"])
    filtered = [a for a in alarm_data if a["severity"] in sev_filter]

    for alarm in filtered:
        color = "card-critical" if alarm["severity"] in ("CRITICAL","HIGH") else "card-warning"
        icon  = "🔴" if alarm["severity"] == "CRITICAL" else "🟠" if alarm["severity"] == "HIGH" else "🟡"
        st.markdown(f"""
        <div class="card {color}">
            <div style="display:flex; justify-content:space-between">
                <div>
                    {icon} <strong>{alarm['type']}</strong> &nbsp;
                    <span class="badge-{'red' if alarm['severity']=='CRITICAL' else 'amber' if alarm['severity']=='HIGH' else 'blue'}">{alarm['severity']}</span>
                    <div class="label">{alarm['patient']} &nbsp;|&nbsp; {alarm['device']}</div>
                </div>
                <div style="text-align:right">
                    <div style="font-size:1.1rem; font-weight:600">{alarm['value']}</div>
                    <div class="label">Threshold: {alarm['threshold']}</div>
                    <div class="label">{alarm['time']}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()
    st.subheader("Get Full Alarm Context")
    alarm_patient = st.selectbox(
        "Patient",
        options=list(PATIENTS.keys()),
        format_func=lambda pid: PATIENTS[pid]["name"],
    )
    if st.button("Load Alarm Context", type="primary"):
        SessionLocal = get_db()
        with st.spinner("Fetching alarm context..."):
            async def _load_alarm():
                async with SessionLocal() as session:
                    from mcp_server.tools.alarm_context import AlarmContextTool
                    return await AlarmContextTool.get_alarm_context(session=session, patient_id=alarm_patient)
            result = run_async(_load_alarm())

        alarm = result.get("alarm", {})
        st.success(f"Alarm retrieved: **{alarm.get('alarm_type','').replace('_',' ').title()}** — {alarm.get('current_value','?')} {alarm.get('unit','')}")
        col1, col2, col3 = st.columns(3)
        col1.metric("Severity", alarm.get("severity","—").upper())
        col2.metric("Value", f"{alarm.get('current_value','—')} {alarm.get('unit','')}")
        col3.metric("Threshold", f"{alarm.get('threshold','—')} {alarm.get('unit','')}")

        tab_vitals, tab_hist = st.tabs(["Vitals Context", "Similar Alarms"])
        with tab_vitals:
            for label, key in [("Before Alarm", "vitals_before"), ("During Alarm", "vitals_during"), ("After Alarm", "vitals_after")]:
                vitals = result.get(key, [])
                if vitals:
                    import pandas as pd
                    df = pd.DataFrame(vitals)
                    st.caption(label)
                    st.dataframe(df, use_container_width=True, hide_index=True)
        with tab_hist:
            similar = result.get("similar_historical_alarms", [])
            if similar:
                import pandas as pd
                st.dataframe(pd.DataFrame(similar), use_container_width=True, hide_index=True)
            else:
                st.info("No similar historical alarms found")


# ══════════════════════════════════════════════════════════════════════════
# PAGE: AUTH & SECURITY
# ══════════════════════════════════════════════════════════════════════════
elif page == "🔐  Auth & Security":
    st.title("Authentication & Security")

    tab_auth, tab_rbac, tab_audit = st.tabs(["JWT Auth", "Role Permissions", "Audit Log"])

    with tab_auth:
        st.subheader("Obtain JWT Token")
        col1, col2 = st.columns(2)
        with col1:
            username = st.selectbox("Username", ["dr_smith", "nurse_johnson", "tech_williams", "admin_brown"])
            passwords = {"dr_smith": "test_password_123", "nurse_johnson": "test_password_456",
                         "tech_williams": "test_password_789", "admin_brown": "test_password_admin"}
            password = st.text_input("Password", value=passwords.get(username, ""), type="password")
        with col2:
            st.markdown("**Test Credentials**")
            st.markdown("| User | Role | Tools |")
            st.markdown("|------|------|-------|")
            st.markdown("| dr_smith | Physician | All 10 |")
            st.markdown("| nurse_johnson | Nurse | 5 |")
            st.markdown("| tech_williams | Technician | 2 |")
            st.markdown("| admin_brown | Administrator | All 10 |")

        if st.button("Authenticate", type="primary"):
            from mcp_server.security.credentials import CredentialValidator
            from mcp_server.security.auth import AuthenticationManager
            clinician = CredentialValidator.validate_credentials(username, password)
            if clinician:
                auth = AuthenticationManager()
                token = auth.create_access_token(
                    clinician_id=clinician["id"], clinician_name=clinician["name"],
                    role=clinician["role"], care_units=clinician["care_units"],
                )
                st.success(f"Authenticated as **{clinician['name']}** ({clinician['role']})")
                st.code(f"Authorization: Bearer {token[:80]}...", language="http")
                payload = auth.verify_token(token)
                st.json({k: v for k, v in payload.items() if k not in ("exp","iat")})
            else:
                st.error("Invalid credentials")

    with tab_rbac:
        st.subheader("Role-Based Access Control Matrix")
        import pandas as pd
        tools = [
            "get_patient_clinical_context",
            "get_care_unit_summary",
            "get_device_events_by_patient",
            "get_alarm_context",
            "get_patient_event_timeline",
            "get_diagnostic_exam_context",
            "get_imaging_study_summary",
            "get_anesthesia_case_context",
            "get_neuro_event_context",
            "get_cardiology_event_context",
        ]
        roles = ["physician", "nurse", "technician", "administrator"]
        from mcp_server.security.authorization import RBACEngine, ClinicianRole
        role_enum = {r.value: r for r in ClinicianRole}
        matrix = {}
        for role in roles:
            perms = RBACEngine.ROLE_PERMISSIONS.get(role_enum.get(role), {})
            matrix[role.capitalize()] = ["✅" if perms.get(t) else "❌" for t in tools]

        df = pd.DataFrame(matrix, index=[t.replace("get_","").replace("_"," ").title() for t in tools])
        st.dataframe(df, use_container_width=True)

    with tab_audit:
        st.subheader("Audit Log (HIPAA Compliant)")
        from mcp_server.security.audit_logger import AuditLogger
        audit = AuditLogger(log_dir="demo_audit_logs")

        # Create some demo entries
        audit.log_tool_call("get_patient_clinical_context","CLIN-001","physician",{"patient_id":"PAT-001"},["PAT-001"],True, 142.3)
        audit.log_tool_call("get_alarm_context",           "CLIN-002","nurse",    {"patient_id":"PAT-003"},["PAT-003"],True, 88.5)
        audit.log_authentication_attempt("dr_smith", success=True)
        audit.log_authentication_attempt("bad_user", success=False, failure_reason="invalid credentials")
        audit.log_authorization_decision("CLIN-002","nurse","get_imaging_study_summary", allowed=False, reason="role restriction")

        logs = audit.get_recent_logs(limit=10)
        st.caption(f"{len(logs)} recent entries — PHI fields (name, DOB, MRN) are masked")

        import pandas as pd
        rows = []
        for entry in logs:
            rows.append({
                "Time":        entry.get("timestamp","")[:19].replace("T"," "),
                "Event":       entry.get("event_type","").replace("_"," ").title(),
                "Tool/User":   entry.get("tool_name") or entry.get("username_partial","—"),
                "Clinician":   entry.get("clinician_id","—"),
                "Success":     "Yes" if entry.get("success") else ("N/A" if "success" not in entry else "No"),
            })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.info("In production, logs are written to JSONL files with 7-year retention. PHI is never logged.")


# ══════════════════════════════════════════════════════════════════════════
# PAGE: PLATFORM METRICS
# ══════════════════════════════════════════════════════════════════════════
elif page == "📊  Platform Metrics":
    st.title("Platform Metrics & Observability")

    from mcp_server.utils.performance import PerformanceMonitor
    import pandas as pd
    import random

    monitor = PerformanceMonitor()
    # Simulate some tool calls
    tool_sim = {
        "get_patient_clinical_context": (80, 350, 0.02),
        "get_care_unit_summary":        (200, 480, 0.01),
        "get_device_events_by_patient": (50, 200, 0.03),
        "get_patient_event_timeline":   (100, 600, 0.02),
        "get_alarm_context":            (40, 180, 0.01),
    }
    random.seed(42)
    for tool, (lo, hi, err_rate) in tool_sim.items():
        for _ in range(50):
            ms = random.uniform(lo, hi)
            success = random.random() > err_rate
            monitor.record_tool_call(tool, ms, success)

    all_metrics = monitor.get_all_metrics()

    # Summary metrics
    total_calls  = sum(m["total_calls"]  for m in all_metrics.values())
    total_errors = sum(m["total_errors"] for m in all_metrics.values())
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Invocations", total_calls)
    c2.metric("Total Errors",      total_errors)
    c3.metric("Overall Error Rate",f"{total_errors/total_calls:.1%}" if total_calls else "0%")
    c4.metric("Tools Monitored",   len(all_metrics))

    st.divider()

    # Per-tool table
    st.subheader("Per-Tool Performance")
    rows = []
    for name, m in all_metrics.items():
        sla = 500 if "care_unit" in name else 2000
        p95 = m.get("p95_response_time_ms") or 0
        status = "✅ Within SLA" if p95 < sla else "⚠️ Exceeds SLA"
        rows.append({
            "Tool":        name.replace("get_","").replace("_"," ").title(),
            "Calls":       m["total_calls"],
            "Errors":      m["total_errors"],
            "Error Rate":  f"{m['error_rate']:.1%}",
            "Avg (ms)":    f"{m['avg_response_time_ms']:.0f}" if m['avg_response_time_ms'] else "—",
            "p95 (ms)":    f"{p95:.0f}",
            "SLA (ms)":    str(sla),
            "Status":      status,
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.divider()
    col_chart, col_slow = st.columns([2, 1])
    with col_chart:
        st.subheader("Avg Response Time by Tool (ms)")
        chart_data = pd.DataFrame({
            "Tool":    [r["Tool"]   for r in rows],
            "Avg ms":  [float(r["Avg (ms)"]) for r in rows],
            "p95 ms":  [float(r["p95 (ms)"]) for r in rows],
        }).set_index("Tool")
        st.bar_chart(chart_data)

    with col_slow:
        st.subheader("SLA Thresholds")
        st.markdown("""
        | Tool | Target |
        |------|--------|
        | Care Unit Summary | < 500ms |
        | All other tools | < 2000ms |
        | Cache hit | < 50ms |
        """)
        st.subheader("Prometheus Export")
        st.code(monitor.get_prometheus_metrics()[:300] + "\n...", language="text")
