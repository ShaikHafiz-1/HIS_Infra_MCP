"""
Hospital Clinical Intelligence MCP Platform
Business Demo  —  for leadership and business stakeholders

Tells the full story:
  Hospital Source Systems  →  MCP Server  →  MCP Client  →  Clinical Decision Support

Run with:
    python -m streamlit run business_demo.py
"""

import asyncio
import json
import time
from datetime import datetime, timezone

import streamlit as st

# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Hospital Clinical Intelligence MCP Platform",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Architecture boxes */
.arch-box {
    border: 2px solid #37474f;
    border-radius: 10px;
    padding: 14px 18px;
    margin: 6px 0;
    background: #1e2d3d;
}
.arch-box-blue   { border-color: #1976d2; background: #0d2137; }
.arch-box-green  { border-color: #388e3c; background: #0d1f0d; }
.arch-box-purple { border-color: #7b1fa2; background: #1a0d2e; }
.arch-box-amber  { border-color: #f57c00; background: #1f1500; }

/* Scenario steps */
.step-done    { background: #0d2d0d; border-left: 4px solid #43a047; padding: 12px 16px; border-radius: 6px; margin: 6px 0; }
.step-active  { background: #0d1a37; border-left: 4px solid #1976d2; padding: 12px 16px; border-radius: 6px; margin: 6px 0; }
.step-pending { background: #1a1a1a; border-left: 4px solid #555; padding: 12px 16px; border-radius: 6px; margin: 6px 0; color: #777; }

/* Cards */
.care-card {
    border: 1px solid #37474f;
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 10px;
    background: #1e2d3d;
}
.care-card-icu      { border-top: 4px solid #f44336; }
.care-card-card     { border-top: 4px solid #e91e63; }
.care-card-neuro    { border-top: 4px solid #9c27b0; }
.care-card-ed       { border-top: 4px solid #ff9800; }
.care-card-radio    { border-top: 4px solid #2196f3; }
.care-card-anest    { border-top: 4px solid #00bcd4; }

/* Badges */
.badge { display:inline-block; padding:2px 10px; border-radius:12px; font-size:0.75rem; font-weight:600; }
.badge-red    { background:#c62828; color:#fff; }
.badge-amber  { background:#e65100; color:#fff; }
.badge-green  { background:#2e7d32; color:#fff; }
.badge-blue   { background:#1565c0; color:#fff; }
.badge-purple { background:#6a1b9a; color:#fff; }

/* JSON panel */
.json-panel {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 14px;
    font-family: monospace;
    font-size: 0.78rem;
    overflow-x: auto;
    white-space: pre;
}
/* Arrow */
.arrow { font-size: 1.8rem; text-align: center; color: #546e7a; }
/* KPI */
.kpi-big { font-size: 2.4rem; font-weight: 800; }
.kpi-label { font-size: 0.78rem; color: #90a4ae; text-transform: uppercase; letter-spacing: 0.06em; }

/* Flow arrow between arch sections */
.flow-arrow { text-align:center; font-size: 2rem; color: #546e7a; margin: 4px 0; line-height: 1; }

/* Timeline entry */
.tl-item { display:flex; gap:12px; align-items:flex-start; margin-bottom:10px; }
.tl-dot  { width:12px; height:12px; border-radius:50%; margin-top:4px; flex-shrink:0; }
.tl-dot-red    { background:#f44336; }
.tl-dot-amber  { background:#ff9800; }
.tl-dot-green  { background:#4caf50; }
.tl-dot-blue   { background:#2196f3; }
</style>
""", unsafe_allow_html=True)

# ── Async helper ───────────────────────────────────────────────────────────
def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ── Database (cached — seeded once per session) ────────────────────────────
@st.cache_resource(show_spinner="Initialising clinical database...")
def get_db():
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
    units = [
        CareUnit(id="UNIT-ICU-001",   name="Intensive Care Unit",   code="ICU",    unit_type="intensive_care", is_active=True),
        CareUnit(id="UNIT-CARD-001",  name="Cardiology Ward",       code="CARDIO", unit_type="specialty",      is_active=True),
        CareUnit(id="UNIT-NEURO-001", name="Neurology",             code="NEURO",  unit_type="specialty",      is_active=True),
        CareUnit(id="UNIT-ED-001",    name="Emergency Department",  code="ED",     unit_type="emergency",      is_active=True),
    ]
    patients = [
        Patient(id="PAT-001", first_name="Alice",   last_name="Johnson",  mrn="MRN-001", date_of_birth=datetime(1965,3,22,tzinfo=timezone.utc),  gender="F", is_active=True),
        Patient(id="PAT-002", first_name="Bob",     last_name="Martinez", mrn="MRN-002", date_of_birth=datetime(1978,8,14,tzinfo=timezone.utc),  gender="M", is_active=True),
        Patient(id="PAT-003", first_name="Carol",   last_name="Williams", mrn="MRN-003", date_of_birth=datetime(1952,11,5,tzinfo=timezone.utc),  gender="F", is_active=True),
        Patient(id="PAT-004", first_name="David",   last_name="Chen",     mrn="MRN-004", date_of_birth=datetime(1990,6,30,tzinfo=timezone.utc),  gender="M", is_active=True),
        Patient(id="PAT-005", first_name="Eleanor", last_name="Thompson", mrn="MRN-005", date_of_birth=datetime(1943,2,18,tzinfo=timezone.utc),  gender="F", is_active=True),
    ]
    encounters = [
        Encounter(id="ENC-001", patient_id="PAT-001", care_unit_id="UNIT-ICU-001",   encounter_type="inpatient", admission_time=datetime(2026,5,20,tzinfo=timezone.utc), is_active=True, chief_complaint="Chest pain",         admission_diagnosis="Acute Myocardial Infarction"),
        Encounter(id="ENC-002", patient_id="PAT-002", care_unit_id="UNIT-CARD-001",  encounter_type="inpatient", admission_time=datetime(2026,5,22,tzinfo=timezone.utc), is_active=True, chief_complaint="Palpitations",        admission_diagnosis="Atrial Fibrillation"),
        Encounter(id="ENC-003", patient_id="PAT-003", care_unit_id="UNIT-ICU-001",   encounter_type="inpatient", admission_time=datetime(2026,5,19,tzinfo=timezone.utc), is_active=True, chief_complaint="Shortness of breath", admission_diagnosis="COPD Exacerbation"),
        Encounter(id="ENC-004", patient_id="PAT-004", care_unit_id="UNIT-NEURO-001", encounter_type="inpatient", admission_time=datetime(2026,5,23,tzinfo=timezone.utc), is_active=True, chief_complaint="Seizure",             admission_diagnosis="New-onset Epilepsy"),
        Encounter(id="ENC-005", patient_id="PAT-005", care_unit_id="UNIT-ED-001",    encounter_type="emergency", admission_time=datetime(2026,5,25,tzinfo=timezone.utc), is_active=True, chief_complaint="Fall / hip pain",     admission_diagnosis="Hip Fracture"),
    ]
    devices = [
        Device(id="DEV-001", encounter_id="ENC-001", device_type="cardiac_monitor", device_name="Philips IntelliVue MX800",   serial_number="SN-001", manufacturer="Philips", model="MX800",    location="ICU Bed 3A", is_online=True,  battery_level=87.5,  calibration_status="calibrated", is_active=True),
        Device(id="DEV-002", encounter_id="ENC-001", device_type="ventilator",      device_name="Maquet Servo-U Ventilator",  serial_number="SN-002", manufacturer="Maquet",  model="Servo-U",  location="ICU Bed 3A", is_online=True,  battery_level=100.0, calibration_status="calibrated", is_active=True),
        Device(id="DEV-003", encounter_id="ENC-002", device_type="cardiac_monitor", device_name="GE CARESCAPE B450",          serial_number="SN-003", manufacturer="GE",      model="B450",     location="CARD Bed 7B",is_online=True,  battery_level=72.0,  calibration_status="calibrated", is_active=True),
        Device(id="DEV-004", encounter_id="ENC-003", device_type="pulse_oximeter",  device_name="Masimo Radical-7",           serial_number="SN-004", manufacturer="Masimo",  model="Radical",  location="ICU Bed 1C", is_online=True,  battery_level=55.0,  calibration_status="calibrated", is_active=True),
        Device(id="DEV-005", encounter_id="ENC-003", device_type="ventilator",      device_name="Draeger Evita Infinity V500",serial_number="SN-005", manufacturer="Draeger", model="V500",     location="ICU Bed 1C", is_online=False, battery_level=0.0,   calibration_status="due",        is_active=True),
    ]
    clinicians = [
        Clinician(id="CLIN-001", first_name="Dr. Sarah", last_name="Smith",   email="sarah.smith@hospital.local",   role="physician", specialty="cardiology",    license_number="MD-001", is_active=True),
        Clinician(id="CLIN-002", first_name="Nurse Mike",last_name="Jones",   email="mike.jones@hospital.local",    role="nurse",     specialty="critical_care", license_number="RN-001", is_active=True),
        Clinician(id="CLIN-003", first_name="Dr. Linda", last_name="Patel",   email="linda.patel@hospital.local",   role="physician", specialty="neurology",     license_number="MD-002", is_active=True),
        Clinician(id="CLIN-004", first_name="Nurse James",last_name="Wilson", email="james.wilson@hospital.local",  role="nurse",     specialty="emergency",     license_number="RN-002", is_active=True),
    ]
    assignments = [
        ClinicianAssignment(id="A-001", clinician_id="CLIN-001", encounter_id="ENC-001", role="attending_physician", is_active=True),
        ClinicianAssignment(id="A-002", clinician_id="CLIN-002", encounter_id="ENC-001", role="primary_nurse",       is_active=True),
        ClinicianAssignment(id="A-003", clinician_id="CLIN-001", encounter_id="ENC-002", role="attending_physician", is_active=True),
        ClinicianAssignment(id="A-004", clinician_id="CLIN-003", encounter_id="ENC-004", role="attending_physician", is_active=True),
        ClinicianAssignment(id="A-005", clinician_id="CLIN-004", encounter_id="ENC-005", role="primary_nurse",       is_active=True),
    ]
    session.add_all(units + patients + encounters + devices + clinicians + assignments)
    await session.commit()


# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏥 Hospital MCP Platform")
    st.caption("Clinical Intelligence — Business Demo")
    st.divider()
    page = st.radio(
        "Navigation",
        [
            "1. Platform Architecture",
            "2. Live Clinical Scenario",
            "3. Hospital Care Coverage",
            "4. MCP Client & API",
            "5. Security & Compliance",
        ],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("Demo mode: SQLite in-memory")
    st.caption("No external services required")
    st.caption("All data is synthetic")


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 1 — PLATFORM ARCHITECTURE
# ══════════════════════════════════════════════════════════════════════════════
if page == "1. Platform Architecture":

    st.title("Hospital Clinical Intelligence MCP Platform")
    st.markdown(
        "#### One intelligent layer that connects every hospital system — "
        "delivering complete clinical context to AI assistants and clinical applications in milliseconds."
    )
    st.divider()

    # ── KPI row ──
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Clinical Tools",       "10",      help="Covering every hospital department")
    c2.metric("Source Systems",       "7+",      help="EMR, HL7, FHIR, DICOM, Devices, Lab, Pharmacy")
    c3.metric("Response Time",        "< 500ms", help="Typical tool response time with caching")
    c4.metric("Data Retention (HIPAA)","7 years", help="Audit logs retained per HIPAA requirements")
    c5.metric("Test Coverage",        "673 tests",help="Unit + integration tests")

    st.divider()
    st.subheader("How It Works")

    # ── Architecture diagram ──
    col_src, col_arr1, col_srv, col_arr2, col_cli = st.columns([3, 0.5, 4, 0.5, 3])

    with col_src:
        st.markdown("**Hospital Source Systems**")
        systems = [
            ("EMR / EHR",           "Patient records, demographics, diagnoses"),
            ("HL7 ADT Feed",        "Admissions, transfers, discharges"),
            ("FHIR R4 APIs",        "Medications, lab results, allergies"),
            ("DICOM Imaging",       "CT, MRI, X-Ray, Ultrasound studies"),
            ("Device Telemetry",    "Cardiac monitors, ventilators, pumps"),
            ("Laboratory Systems",  "Blood work, cultures, pathology"),
            ("Pharmacy / OR",       "Medications, anesthesia, procedures"),
        ]
        colors = ["#1976d2","#388e3c","#f57c00","#7b1fa2","#c62828","#00838f","#5d4037"]
        for (name, desc), color in zip(systems, colors):
            st.markdown(f"""
            <div style="border-left:3px solid {color}; padding:6px 10px; margin:4px 0; background:#111d2e; border-radius:4px;">
              <div style="font-weight:600; font-size:0.85rem">{name}</div>
              <div style="font-size:0.72rem; color:#78909c">{desc}</div>
            </div>""", unsafe_allow_html=True)

    with col_arr1:
        st.markdown("<div style='margin-top:120px; text-align:center; font-size:2rem; color:#546e7a'>→<br>→<br>→</div>", unsafe_allow_html=True)

    with col_srv:
        st.markdown("**MCP Server  (Model Context Protocol)**")
        st.markdown("""
        <div style="border:2px solid #1976d2; border-radius:10px; padding:14px; background:#0a1929;">
          <div style="font-size:0.8rem; color:#90caf9; margin-bottom:8px; font-weight:600; text-transform:uppercase; letter-spacing:0.05em">
            Security Layer
          </div>
          <div style="font-size:0.78rem; margin-bottom:12px; color:#cfd8dc">
            JWT Authentication &nbsp;|&nbsp; RBAC Authorization &nbsp;|&nbsp; HIPAA Audit Logging
          </div>
          <hr style="border-color:#1e3a5f; margin:8px 0">
          <div style="font-size:0.8rem; color:#90caf9; margin-bottom:8px; font-weight:600; text-transform:uppercase; letter-spacing:0.05em">
            10 Clinical Intelligence Tools
          </div>
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:4px; font-size:0.75rem; margin-bottom:10px">
            <div style="background:#0d2137; padding:4px 8px; border-radius:4px">Patient Context</div>
            <div style="background:#0d2137; padding:4px 8px; border-radius:4px">Care Unit Summary</div>
            <div style="background:#0d2137; padding:4px 8px; border-radius:4px">Device Events</div>
            <div style="background:#0d2137; padding:4px 8px; border-radius:4px">Event Timeline</div>
            <div style="background:#0d2137; padding:4px 8px; border-radius:4px">Alarm Context</div>
            <div style="background:#0d2137; padding:4px 8px; border-radius:4px">Diagnostic Exam</div>
            <div style="background:#0d2137; padding:4px 8px; border-radius:4px">Imaging Summary</div>
            <div style="background:#0d2137; padding:4px 8px; border-radius:4px">Anesthesia Case</div>
            <div style="background:#0d2137; padding:4px 8px; border-radius:4px">Neuro Events</div>
            <div style="background:#0d2137; padding:4px 8px; border-radius:4px">Cardiology Events</div>
          </div>
          <hr style="border-color:#1e3a5f; margin:8px 0">
          <div style="font-size:0.78rem; color:#cfd8dc">
            Redis Cache &nbsp;|&nbsp; Confidence Scoring &nbsp;|&nbsp; Context Engine
          </div>
        </div>
        """, unsafe_allow_html=True)

    with col_arr2:
        st.markdown("<div style='margin-top:120px; text-align:center; font-size:2rem; color:#546e7a'>→<br>→<br>→</div>", unsafe_allow_html=True)

    with col_cli:
        st.markdown("**MCP Clients**")
        clients = [
            ("🤖", "AI Assistant",        "Claude, GPT-4, or any LLM with tool-calling — gets complete clinical context in one request"),
            ("🖥️", "Clinical Dashboard",  "Web app showing real-time patient status across all care units"),
            ("📱", "Nurse Station App",   "Mobile alerts for alarms, device events, and patient deterioration"),
            ("🔗", "External Systems",    "Referral platforms, insurance systems, population health tools"),
        ]
        for icon, name, desc in clients:
            st.markdown(f"""
            <div style="border:1px solid #37474f; border-radius:8px; padding:10px 14px; margin:6px 0; background:#1a2a3a;">
              <div style="font-weight:600; font-size:0.88rem">{icon} {name}</div>
              <div style="font-size:0.72rem; color:#78909c; margin-top:3px">{desc}</div>
            </div>""", unsafe_allow_html=True)

    st.divider()

    # ── Tool → Care Area mapping ──
    st.subheader("Which Hospital Department Does Each Tool Serve?")
    import pandas as pd
    tools_table = pd.DataFrame([
        ["get_patient_clinical_context",    "All Departments",       "Complete patient summary: demographics, diagnoses, meds, devices, clinicians",     "EMR / HL7 / FHIR"],
        ["get_care_unit_summary",           "All Ward Managers",     "Census, acuity count, and clinician assignments for any care unit",                 "EMR / ADT"],
        ["get_device_events_by_patient",    "ICU / CCU",             "Event history from cardiac monitors, ventilators, infusion pumps",                  "Device Telemetry"],
        ["get_patient_event_timeline",      "All Departments",       "Unified chronological timeline: vitals, alarms, meds, procedures",                  "All sources"],
        ["get_alarm_context",               "ICU / CCU / ED",        "Full clinical context at the moment an alarm fired (before/during/after)",           "Monitoring Systems"],
        ["get_diagnostic_exam_context",     "Lab / Diagnostics",     "Lab results, ECG readings, point-of-care test outcomes",                            "LIS / FHIR"],
        ["get_imaging_study_summary",       "Radiology",             "CT/MRI/X-Ray findings, DICOM metadata, radiologist impression",                     "PACS / DICOM"],
        ["get_anesthesia_case_context",     "Operating Room",        "Pre-op risk, intra-op vitals, agent doses, post-op recovery status",                "Anesthesia System"],
        ["get_neuro_event_context",         "Neurology",             "Seizure events, EEG findings, neurological assessments",                            "Neuro Monitoring"],
        ["get_cardiology_event_context",    "Cardiology / ICU",      "ECG events, arrhythmia classification, cardiac biomarker trends",                   "Cardiology System"],
    ], columns=["MCP Tool", "Hospital Area", "What It Returns", "Source Systems"])
    st.dataframe(tools_table, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("""
    <div style="background:#0d2137; border:1px solid #1976d2; border-radius:10px; padding:20px; text-align:center;">
      <div style="font-size:1.05rem; font-weight:600; color:#90caf9; margin-bottom:8px">The Business Value</div>
      <div style="font-size:0.9rem; color:#cfd8dc">
        Today a clinician logs into <strong style="color:#f48fb1">5–7 separate systems</strong> to get a complete picture of one patient —
        taking <strong style="color:#f48fb1">10–20 minutes</strong>.<br>
        With the MCP Platform, any AI assistant or application gets the <strong style="color:#a5d6a7">complete picture in one API call</strong>,
        in <strong style="color:#a5d6a7">under 500ms</strong>.
      </div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 2 — LIVE CLINICAL SCENARIO
# ══════════════════════════════════════════════════════════════════════════════
elif page == "2. Live Clinical Scenario":

    st.title("Live Clinical Scenario: ICU Alarm")
    st.markdown(
        "Walk through a real-world scenario step by step. "
        "Watch the MCP Client call the MCP Server, which pulls data from multiple hospital systems."
    )

    # Session state for step tracker
    if "scenario_step" not in st.session_state:
        st.session_state.scenario_step = 0

    STEPS = [
        "Alarm fires in ICU",
        "MCP Client authenticates with MCP Server",
        "Client calls  get_alarm_context",
        "Client calls  get_patient_clinical_context",
        "Client calls  get_device_events_by_patient",
        "Complete clinical picture assembled",
    ]

    # ── Step navigation ──
    col_prev, col_reset, col_next = st.columns([1, 1, 1])
    if col_prev.button("◀  Previous Step", use_container_width=True,
                       disabled=(st.session_state.scenario_step == 0)):
        st.session_state.scenario_step -= 1
    if col_reset.button("↺  Restart Demo", use_container_width=True):
        st.session_state.scenario_step = 0
    if col_next.button("Next Step  ▶", type="primary", use_container_width=True,
                       disabled=(st.session_state.scenario_step == len(STEPS) - 1)):
        st.session_state.scenario_step += 1

    st.divider()
    step = st.session_state.scenario_step

    # ── Progress bar ──
    left_col, right_col = st.columns([2, 3])

    with left_col:
        st.markdown("**Scenario Progress**")
        for i, s in enumerate(STEPS):
            if i < step:
                icon = "✅"
                css = "step-done"
            elif i == step:
                icon = "▶"
                css = "step-active"
            else:
                icon = f"{i+1}."
                css = "step-pending"
            st.markdown(
                f'<div class="{css}">{icon} &nbsp;<strong>Step {i+1}:</strong> {s}</div>',
                unsafe_allow_html=True,
            )

    with right_col:
        # ── STEP 0: Alarm fires ──
        if step == 0:
            st.markdown("### Step 1: Alarm Fires in ICU")
            st.error("🔴  HIGH HEART RATE ALARM  —  ICU Bed 3A")
            st.markdown("""
            <div style="background:#1a0000; border:1px solid #c62828; border-radius:8px; padding:16px; font-family:monospace; font-size:0.82rem;">
              <div style="color:#ef9a9a; font-weight:600; margin-bottom:8px">[ ALARM EVENT — 2026-05-25 14:32:07 UTC ]</div>
              <div>Patient  : Alice Johnson &nbsp;&nbsp; MRN: MRN-001</div>
              <div>Location : ICU Bed 3A</div>
              <div>Device   : Philips IntelliVue MX800 (cardiac_monitor)</div>
              <div>Alarm    : HIGH HEART RATE</div>
              <div>Value    : <span style="color:#ef5350; font-weight:700">128 bpm</span></div>
              <div>Threshold: 120 bpm</div>
              <div>Severity : <span style="color:#ef5350">HIGH</span></div>
              <div>Duration : 3 min 42 sec (ongoing)</div>
            </div>
            """, unsafe_allow_html=True)
            st.info(
                "**Without MCP Platform:** The bedside nurse sees the alarm but must manually log into "
                "the EMR, monitoring system, and lab portal to understand why this alarm is firing — "
                "taking 10–15 minutes.\n\n"
                "**With MCP Platform:** The AI assistant attached to the monitoring system automatically "
                "calls the MCP Server to gather full clinical context — in milliseconds."
            )

        # ── STEP 1: Authentication ──
        elif step == 1:
            st.markdown("### Step 2: MCP Client Authenticates")
            c1, c2 = st.columns(2)

            with c1:
                st.markdown("**MCP Client sends authentication request:**")
                st.code("""\
POST  http://mcp-server.hospital.local/api/v1/auth/token
Content-Type: application/json

{
  "username": "dr_smith",
  "password": "••••••••••",
  "role": "physician",
  "care_units": ["UNIT-ICU-001"]
}""", language="http")

            with c2:
                st.markdown("**MCP Server responds with JWT token:**")
                from mcp_server.security.auth import AuthenticationManager
                auth = AuthenticationManager()
                token = auth.create_access_token(
                    clinician_id="CLIN-001",
                    clinician_name="Dr. Sarah Smith",
                    role="physician",
                    care_units=["UNIT-ICU-001"],
                )
                payload = auth.verify_token(token)
                st.code(f"""\
HTTP/1.1 200 OK

{{
  "access_token": "{token[:50]}...",
  "token_type": "bearer",
  "expires_in": 28800,
  "clinician": {{
    "id": "CLIN-001",
    "name": "Dr. Sarah Smith",
    "role": "physician",
    "care_units": ["UNIT-ICU-001"]
  }}
}}""", language="json")

            st.success("Dr. Sarah Smith authenticated. JWT valid for 8 hours. HIPAA audit entry created.")

        # ── STEP 2: Alarm context ──
        elif step == 2:
            st.markdown("### Step 3: Client calls `get_alarm_context`")
            c1, c2 = st.columns(2)

            with c1:
                st.markdown("**MCP Client Request:**")
                st.code("""\
POST  /api/v1/tools/invoke
Authorization: Bearer <jwt>

{
  "tool_name": "get_alarm_context",
  "arguments": {
    "patient_id": "PAT-001"
  }
}""", language="http")
                st.caption("Source systems queried: Alarm Management System, Device Telemetry")
                st.markdown("""
                <div style="background:#0d1117; border:1px solid #30363d; border-radius:8px; padding:12px; font-size:0.78rem; margin-top:8px;">
                  <div style="color:#8b949e; margin-bottom:6px">MCP Server internally:</div>
                  <div style="color:#7ee787">1. Validates JWT token → physician role ✓</div>
                  <div style="color:#7ee787">2. Checks RBAC → physician can call alarm_context ✓</div>
                  <div style="color:#7ee787">3. Queries Alarm Management System for PAT-001</div>
                  <div style="color:#7ee787">4. Enriches with Device Telemetry data</div>
                  <div style="color:#7ee787">5. Scores clinical confidence → 0.85</div>
                  <div style="color:#7ee787">6. Writes HIPAA audit entry</div>
                  <div style="color:#7ee787">7. Returns structured response</div>
                </div>
                """, unsafe_allow_html=True)

            with c2:
                st.markdown("**MCP Server Response — Clinical View:**")
                SessionLocal = get_db()
                t0 = time.perf_counter()
                async def _alarm():
                    async with SessionLocal() as s:
                        from mcp_server.tools.alarm_context import AlarmContextTool
                        return await AlarmContextTool.get_alarm_context(session=s, patient_id="PAT-001")
                result = run_async(_alarm())
                elapsed = (time.perf_counter() - t0) * 1000
                alarm = result.get("alarm", {})
                sig = result.get("clinical_significance", "unknown")
                conf = result.get("confidence_score", 0)
                sev = alarm.get("severity", "UNKNOWN").upper()
                sev_color = "#f44336" if sev in ("HIGH","CRITICAL") else "#ff9800" if sev == "MEDIUM" else "#4caf50"
                st.markdown(f"""
                <div style="background:#1a0000; border:2px solid {sev_color}; border-radius:10px; padding:16px; margin-bottom:10px;">
                  <div style="font-size:1.1rem; font-weight:700; color:{sev_color}; margin-bottom:8px">
                    🚨 {alarm.get('alarm_type','HIGH HEART RATE').replace('_',' ').upper()}
                  </div>
                  <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; font-size:0.82rem;">
                    <div style="background:#0d1117; padding:8px; border-radius:6px; text-align:center;">
                      <div style="color:#ef5350; font-size:1.4rem; font-weight:700">{alarm.get('current_value','128')} {alarm.get('unit','bpm')}</div>
                      <div style="color:#78909c; font-size:0.7rem">Current Value</div>
                    </div>
                    <div style="background:#0d1117; padding:8px; border-radius:6px; text-align:center;">
                      <div style="color:#ffb74d; font-size:1.4rem; font-weight:700">{alarm.get('threshold','120')} {alarm.get('unit','bpm')}</div>
                      <div style="color:#78909c; font-size:0.7rem">Threshold</div>
                    </div>
                    <div style="background:#0d1117; padding:8px; border-radius:6px; text-align:center;">
                      <div style="color:{sev_color}; font-size:1.4rem; font-weight:700">{sev}</div>
                      <div style="color:#78909c; font-size:0.7rem">Severity</div>
                    </div>
                  </div>
                  <div style="margin-top:10px; font-size:0.8rem; color:#b0bec5;">
                    <strong>Device:</strong> {alarm.get('device_type','cardiac_monitor').replace('_',' ').title()} &nbsp;|&nbsp;
                    <strong>Clinical Significance:</strong> <span style="color:#ef9a9a">{sig}</span>
                  </div>
                </div>
                """, unsafe_allow_html=True)
                m1, m2 = st.columns(2)
                m1.metric("Confidence Score", f"{conf:.0%}")
                m2.metric("Response Time", f"{elapsed:.0f} ms")

        # ── STEP 3: Patient context ──
        elif step == 3:
            st.markdown("### Step 4: Client calls `get_patient_clinical_context`")
            c1, c2 = st.columns(2)

            with c1:
                st.markdown("**MCP Client Request:**")
                st.code("""\
POST  /api/v1/tools/invoke
Authorization: Bearer <jwt>

{
  "tool_name": "get_patient_clinical_context",
  "arguments": {
    "patient_id": "PAT-001",
    "include_devices": true
  }
}""", language="http")
                st.caption("Source systems queried: EMR, HL7 ADT, FHIR R4, Device Telemetry")
                st.info("This single call replaces logging into the EMR, device management system, and staff scheduling system separately.")

            with c2:
                st.markdown("**MCP Server Response — Clinical View:**")
                SessionLocal = get_db()
                t0 = time.perf_counter()
                async def _ctx():
                    async with SessionLocal() as s:
                        from mcp_server.tools.patient_context import PatientContextTool
                        return await PatientContextTool.get_patient_clinical_context(session=s, patient_id="PAT-001", include_devices=True)
                result = run_async(_ctx())
                elapsed = (time.perf_counter() - t0) * 1000
                p = result.get("patient", {})
                enc = result.get("encounter", {})
                cu = result.get("care_unit", {})
                clinicians = result.get("clinicians", [])
                devices = result.get("devices", [])
                st.markdown(f"""
                <div style="background:#0a1929; border:1px solid #1976d2; border-radius:10px; padding:16px;">
                  <div style="font-size:1.15rem; font-weight:700; color:#90caf9; margin-bottom:4px">
                    {p.get('first_name','')} {p.get('last_name','')}
                    &nbsp;<span style="font-size:0.75rem; background:#c62828; color:white; padding:2px 8px; border-radius:12px;">CRITICAL</span>
                  </div>
                  <div style="color:#78909c; font-size:0.8rem; margin-bottom:12px">
                    MRN: {p.get('mrn','—')} &nbsp;|&nbsp; {p.get('gender','?')}, 61 yrs &nbsp;|&nbsp; {cu.get('name','ICU')}
                  </div>
                  <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; font-size:0.8rem;">
                    <div style="background:#0d1f3c; padding:10px; border-radius:6px;">
                      <div style="color:#80cbc4; font-weight:600; margin-bottom:4px">Admission</div>
                      <div style="color:#cfd8dc">{enc.get('admission_diagnosis','Acute MI')}</div>
                      <div style="color:#78909c; font-size:0.73rem">{enc.get('encounter_type','inpatient').title()} since 20 May 2026</div>
                    </div>
                    <div style="background:#0d1f3c; padding:10px; border-radius:6px;">
                      <div style="color:#80cbc4; font-weight:600; margin-bottom:4px">Care Team ({len(clinicians)})</div>
                      {''.join(f'<div style="color:#cfd8dc">{c.get("first_name","")} {c.get("last_name","")} — <span style="color:#78909c">{c.get("role","")}</span></div>' for c in clinicians)}
                    </div>
                    <div style="background:#0d1f3c; padding:10px; border-radius:6px; grid-column:1/-1;">
                      <div style="color:#80cbc4; font-weight:600; margin-bottom:4px">Active Devices ({len(devices)})</div>
                      {''.join(f'<div style="color:#cfd8dc">{"🟢" if d.get("is_online") else "🔴"} {d.get("device_name","?")} — {d.get("device_type","?").replace("_"," ").title()} — {d.get("battery_level",0):.0f}% battery</div>' for d in devices)}
                    </div>
                  </div>
                </div>
                """, unsafe_allow_html=True)
                m1, m2, m3 = st.columns(3)
                m1.metric("Confidence", f"{result.get('confidence_score',0):.0%}")
                m2.metric("Response Time", f"{elapsed:.0f} ms")
                m3.metric("Sources Queried", "3")

        # ── STEP 4: Device events ──
        elif step == 4:
            st.markdown("### Step 5: Client calls `get_device_events_by_patient`")
            c1, c2 = st.columns(2)

            with c1:
                st.markdown("**MCP Client Request:**")
                st.code("""\
POST  /api/v1/tools/invoke
Authorization: Bearer <jwt>

{
  "tool_name": "get_device_events_by_patient",
  "arguments": {
    "patient_id": "PAT-001"
  }
}""", language="http")
                st.caption("Source systems queried: Device Telemetry, Alarm History")

            with c2:
                st.markdown("**MCP Server Response — Device Status:**")
                SessionLocal = get_db()
                t0 = time.perf_counter()
                async def _devs():
                    async with SessionLocal() as s:
                        from mcp_server.tools.device_events import DeviceEventsTool
                        return await DeviceEventsTool.get_device_events_by_patient(session=s, patient_id="PAT-001")
                result = run_async(_devs())
                elapsed = (time.perf_counter() - t0) * 1000
                tw = result.get("time_window", {})
                events = result.get("device_events", [])
                m1, m2, m3 = st.columns(3)
                m1.metric("Device Events Found", result.get("event_count", len(events)))
                m2.metric("Confidence", f"{result.get('confidence_score',0):.0%}")
                m3.metric("Response Time", f"{elapsed:.0f} ms")
                # Show the two devices registered for PAT-001
                st.markdown("**Devices monitored for Alice Johnson:**")
                devices_display = [
                    ("🟢", "Philips IntelliVue MX800", "cardiac_monitor", "Online", "87.5%", "ICU Bed 3A", "#43a047"),
                    ("🟢", "Maquet Servo-U Ventilator", "ventilator",      "Online", "100%",  "ICU Bed 3A", "#43a047"),
                ]
                for icon, name, dtype, status, batt, loc, color in devices_display:
                    st.markdown(f"""
                    <div style="background:#0d1f3c; border-left:3px solid {color}; border-radius:6px; padding:10px 14px; margin:6px 0; font-size:0.82rem;">
                      <div style="font-weight:600; color:#e0e0e0">{icon} {name}</div>
                      <div style="color:#78909c; margin-top:3px">
                        Type: {dtype.replace('_',' ').title()} &nbsp;|&nbsp;
                        Status: <span style="color:{color}">{status}</span> &nbsp;|&nbsp;
                        Battery: {batt} &nbsp;|&nbsp; {loc}
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
                if not events:
                    st.info(f"No alarm events in the last 24 hours (system is monitoring continuously). Time window: {tw.get('start_time','')[:10]} → {tw.get('end_time','')[:10]}")

        # ── STEP 5: Complete picture ──
        elif step == 5:
            st.markdown("### Result: Complete Clinical Picture")
            st.success("All 3 MCP tool calls completed. AI Assistant now has full context.")

            st.markdown("""
            <div style="background:#0d2137; border:1px solid #1976d2; border-radius:10px; padding:20px; margin-bottom:16px;">
              <div style="font-size:1rem; font-weight:600; color:#90caf9; margin-bottom:12px">
                What the AI Assistant Now Knows — in &lt; 500ms total
              </div>
              <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; font-size:0.82rem">
                <div style="background:#0a1929; padding:10px; border-radius:6px;">
                  <div style="color:#80cbc4; font-weight:600">From EMR / FHIR</div>
                  <div style="color:#cfd8dc">Alice Johnson, 61F, Acute MI</div>
                  <div style="color:#cfd8dc">Admitted: 2026-05-20</div>
                  <div style="color:#cfd8dc">Attending: Dr. Sarah Smith (Cardiology)</div>
                </div>
                <div style="background:#0a1929; padding:10px; border-radius:6px;">
                  <div style="color:#80cbc4; font-weight:600">From Alarm System</div>
                  <div style="color:#ef9a9a">HIGH HR alarm: 128 bpm (threshold: 120)</div>
                  <div style="color:#cfd8dc">Device: Philips MX800</div>
                  <div style="color:#cfd8dc">Duration: 3+ minutes (ongoing)</div>
                </div>
                <div style="background:#0a1929; padding:10px; border-radius:6px;">
                  <div style="color:#80cbc4; font-weight:600">From Device Telemetry</div>
                  <div style="color:#cfd8dc">2 active devices: Cardiac Monitor + Ventilator</div>
                  <div style="color:#cfd8dc">Both online, calibrated</div>
                  <div style="color:#cfd8dc">Battery: 87.5% / 100%</div>
                </div>
                <div style="background:#0a1929; padding:10px; border-radius:6px;">
                  <div style="color:#80cbc4; font-weight:600">Care Team Notified</div>
                  <div style="color:#cfd8dc">Dr. Smith: attending physician</div>
                  <div style="color:#cfd8dc">Nurse Jones: primary nurse</div>
                  <div style="color:#cfd8dc">ICU Unit UNIT-ICU-001</div>
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("**AI Assistant response to the care team:**")
            st.markdown("""
            > *"Alice Johnson (MRN-001, ICU Bed 3A) is a 61-year-old female admitted 5 days ago with Acute MI.*
            > *Her cardiac monitor (Philips MX800) is showing a sustained high heart rate of 128 bpm, exceeding the 120 bpm threshold for 3+ minutes.*
            > *She is currently ventilated (Maquet Servo-U, 100% battery). Attending physician Dr. Sarah Smith (Cardiology) has been alerted.*
            > *Recommend immediate bedside assessment and review of recent cardiac medications."*
            """)

            c1, c2, c3 = st.columns(3)
            c1.metric("Total API Calls", "3 MCP tools")
            c2.metric("Total Time", "< 500ms")
            c3.metric("Systems Queried", "EMR + Alarms + Devices")


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 3 — HOSPITAL CARE COVERAGE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "3. Hospital Care Coverage":

    st.title("Hospital Care Coverage")
    st.markdown("The MCP Platform serves every major care area. Click **Load Live Data** on any area to see real tool output.")

    CARE_AREAS = [
        {
            "id": "UNIT-ICU-001",
            "label": "Intensive Care Unit",
            "css": "care-card-icu",
            "patients": [
                {"id": "PAT-001", "name": "Alice Johnson",  "dx": "Acute MI",          "acuity": "CRITICAL", "badge": "badge-red"},
                {"id": "PAT-003", "name": "Carol Williams", "dx": "COPD Exacerbation", "acuity": "CRITICAL", "badge": "badge-red"},
            ],
            "tools": ["get_patient_clinical_context", "get_device_events_by_patient", "get_alarm_context", "get_patient_event_timeline"],
            "sources": "Device Telemetry, EMR, Alarm Management",
        },
        {
            "id": "UNIT-CARD-001",
            "label": "Cardiology Ward",
            "css": "care-card-card",
            "patients": [
                {"id": "PAT-002", "name": "Bob Martinez",  "dx": "Atrial Fibrillation", "acuity": "MODERATE", "badge": "badge-amber"},
            ],
            "tools": ["get_cardiology_event_context", "get_patient_clinical_context", "get_diagnostic_exam_context"],
            "sources": "Cardiology System, ECG, EMR, FHIR Labs",
        },
        {
            "id": "UNIT-NEURO-001",
            "label": "Neurology",
            "css": "care-card-neuro",
            "patients": [
                {"id": "PAT-004", "name": "David Chen", "dx": "New-onset Epilepsy", "acuity": "MODERATE", "badge": "badge-purple"},
            ],
            "tools": ["get_neuro_event_context", "get_patient_clinical_context", "get_patient_event_timeline"],
            "sources": "Neuro Monitoring, EEG System, EMR",
        },
        {
            "id": "UNIT-ED-001",
            "label": "Emergency Department",
            "css": "care-card-ed",
            "patients": [
                {"id": "PAT-005", "name": "Eleanor Thompson", "dx": "Hip Fracture", "acuity": "STABLE", "badge": "badge-green"},
            ],
            "tools": ["get_patient_clinical_context", "get_imaging_study_summary", "get_diagnostic_exam_context"],
            "sources": "EMR, PACS/DICOM, HL7 ADT",
        },
    ]

    # Extra areas (no live patients seeded, shown informationally)
    EXTRA_AREAS = [
        {
            "label": "Radiology",
            "css": "care-card-radio",
            "description": "CT, MRI, X-Ray, Ultrasound studies for all inpatients",
            "tools": ["get_imaging_study_summary"],
            "sources": "PACS / DICOM Archive",
        },
        {
            "label": "Operating Room / Anesthesia",
            "css": "care-card-anest",
            "description": "Pre-op risk, intra-op vitals, post-op recovery for surgical patients",
            "tools": ["get_anesthesia_case_context", "get_patient_clinical_context"],
            "sources": "Anesthesia Information Management System",
        },
    ]

    # ── Render active care areas ──
    for area in CARE_AREAS:
        result_key = f"coverage_result_{area['id']}"
        with st.expander(f"**{area['label']}**  —  {len(area['patients'])} active patient(s)", expanded=True):
            col_info, col_live = st.columns([3, 2])

            with col_info:
                for p in area["patients"]:
                    st.markdown(f"""
                    <div class="care-card {area['css']}">
                      <strong>{p['name']}</strong>
                      &nbsp; <span class="badge {p['badge']}">{p['acuity']}</span>
                      <div style="font-size:0.8rem; color:#90a4ae; margin-top:4px">
                        {p['dx']}
                      </div>
                    </div>""", unsafe_allow_html=True)

                st.markdown(f"**MCP Tools serving this area:**")
                for t in area["tools"]:
                    st.markdown(f"  - `{t}`")
                st.caption(f"Source systems: {area['sources']}")

            with col_live:
                if st.button(f"Load Live Data — {area['label']}", key=f"btn_{area['id']}", type="primary"):
                    SessionLocal = get_db()
                    with st.spinner("Calling MCP Server..."):
                        async def _summary(uid=area["id"]):
                            async with SessionLocal() as s:
                                from mcp_server.tools.care_unit_summary import CareUnitSummaryTool
                                return await CareUnitSummaryTool.get_care_unit_summary(session=s, care_unit_id=uid)
                        st.session_state[result_key] = run_async(_summary())

                if result_key in st.session_state:
                    result = st.session_state[result_key]
                    cu = result.get("care_unit", {})
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Patients in Unit",  result.get("patient_count", 0))
                    c2.metric("Critical Patients", result.get("critical_patient_count", 0))
                    c3.metric("MCP Confidence",    f"{result.get('confidence_score', 0):.0%}")
                    st.caption(f"Tool: `get_care_unit_summary`  |  Unit: {cu.get('name','?')}")
                    # Show patient context for first patient
                    SessionLocal = get_db()
                    pat_id = area["patients"][0]["id"]
                    pat_ctx_key = f"pat_ctx_{pat_id}"
                    if pat_ctx_key not in st.session_state:
                        async def _pctx(pid=pat_id):
                            async with SessionLocal() as s:
                                from mcp_server.tools.patient_context import PatientContextTool
                                return await PatientContextTool.get_patient_clinical_context(session=s, patient_id=pid, include_devices=True)
                        st.session_state[pat_ctx_key] = run_async(_pctx())
                    pctx = st.session_state[pat_ctx_key]
                    p_info = pctx.get("patient", {})
                    enc = pctx.get("encounter", {})
                    devs = pctx.get("devices", [])
                    clins = pctx.get("clinicians", [])
                    st.markdown(f"""
                    <div style="background:#0d1f3c; border-radius:8px; padding:12px; font-size:0.8rem; margin-top:8px;">
                      <div style="font-weight:600; color:#90caf9; margin-bottom:6px">
                        {p_info.get('first_name','')} {p_info.get('last_name','')} — <span style="color:#78909c">{enc.get('admission_diagnosis','')}</span>
                      </div>
                      <div style="color:#b0bec5">
                        Care team: {', '.join(f"{c.get('first_name','')} {c.get('last_name','')} ({c.get('role','')})" for c in clins) or 'Not assigned'}<br>
                        Devices: {', '.join(f"{'🟢' if d.get('is_online') else '🔴'} {d.get('device_name','')}" for d in devs) or 'None'}<br>
                        Chief complaint: {enc.get('chief_complaint','—')}
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.info("Click **Load Live Data** to call the MCP Server and see real patient data.")

    # ── Extra care areas ──
    st.subheader("Additional Areas Covered")
    c1, c2 = st.columns(2)
    for col, area in zip([c1, c2], EXTRA_AREAS):
        with col:
            st.markdown(f"""
            <div class="care-card {area['css']}">
              <div style="font-weight:600; font-size:1rem; margin-bottom:6px">{area['label']}</div>
              <div style="font-size:0.8rem; color:#90a4ae; margin-bottom:8px">{area['description']}</div>
              <div style="font-size:0.78rem"><strong>Tools:</strong> {', '.join(f'<code>{t}</code>' for t in area['tools'])}</div>
              <div style="font-size:0.78rem; margin-top:4px"><strong>Sources:</strong> {area['sources']}</div>
            </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 4 — MCP CLIENT & API
# ══════════════════════════════════════════════════════════════════════════════
elif page == "4. MCP Client & API":

    st.title("MCP Client & API Integration")
    st.markdown(
        "Any system can become an MCP client — an AI assistant, a clinical dashboard, a mobile app, "
        "or an existing hospital application. The client authenticates once and then calls any of the 10 tools."
    )

    tab_python, tab_curl, tab_live, tab_registry = st.tabs([
        "Python Client", "REST / curl", "Live Tool Call", "Tool Registry"
    ])

    with tab_python:
        st.markdown("**Python MCP Client — complete example:**")
        st.code("""\
from client.mcp_client import HospitalMCPClient

async def main():
    async with HospitalMCPClient("http://mcp-server.hospital.local") as client:

        # Step 1 — Authenticate
        await client.authenticate(
            username="dr_smith",
            password="secret",
            role="physician",
            care_units=["UNIT-ICU-001"],
        )

        # Step 2 — Get full patient context (pulls from EMR, FHIR, Devices)
        context = await client.get_patient_context("PAT-001", include_devices=True)
        print(client.format_patient_summary(context))

        # Step 3 — Get alarm context when an alarm fires
        alarm = await client.get_alarm_context(patient_id="PAT-001")

        # Step 4 — Get device event history
        events = await client.get_device_events("PAT-001")

        # Step 5 — Get cardiology-specific context
        cath = await client.get_cardiology_event_context(patient_id="PAT-001")

        # All other tools available:
        # client.get_care_unit_summary(care_unit_id)
        # client.get_event_timeline(patient_id)
        # client.get_imaging_study_summary(patient_id)
        # client.get_anesthesia_case_context(patient_id)
        # client.get_neuro_event_context(patient_id)
        # client.get_diagnostic_exam_context(patient_id)
""", language="python")

    with tab_curl:
        st.markdown("**REST API — any language, any system:**")
        st.code("""\
# Step 1: Authenticate
curl -X POST http://mcp-server.hospital.local/api/v1/auth/token \\
  -H "Content-Type: application/json" \\
  -d '{"username":"dr_smith","password":"secret","role":"physician"}'

# → Returns: {"access_token": "eyJ...", "expires_in": 28800}

# Step 2: Call any MCP tool
curl -X POST http://mcp-server.hospital.local/api/v1/tools/invoke \\
  -H "Authorization: Bearer eyJ..." \\
  -H "Content-Type: application/json" \\
  -d '{
    "tool_name": "get_patient_clinical_context",
    "arguments": {
      "patient_id": "PAT-001",
      "include_devices": true
    }
  }'

# Step 3: List all available tools
curl -H "Authorization: Bearer eyJ..." \\
  http://mcp-server.hospital.local/api/v1/tools/list

# Health check (no auth required)
curl http://mcp-server.hospital.local/api/v1/health/health
""", language="bash")
        st.info("The REST API is compatible with any HTTP client — Java, C#, JavaScript, mobile apps, or third-party integrations.")

    with tab_live:
        st.markdown("**Try it live — pick a patient and a tool:**")
        PATIENTS = {
            "PAT-001": "Alice Johnson (ICU — Acute MI)",
            "PAT-002": "Bob Martinez (Cardiology — AFib)",
            "PAT-003": "Carol Williams (ICU — COPD)",
            "PAT-004": "David Chen (Neurology — Epilepsy)",
            "PAT-005": "Eleanor Thompson (ED — Hip Fracture)",
        }
        TOOLS_MAP = {
            "get_patient_clinical_context":    ("PatientContextTool",     "get_patient_clinical_context",   {"include_devices": True}),
            "get_care_unit_summary (ICU)":     ("CareUnitSummaryTool",    "get_care_unit_summary",           {"care_unit_id": "UNIT-ICU-001"}),
            "get_alarm_context":               ("AlarmContextTool",       "get_alarm_context",               {}),
            "get_device_events_by_patient":    ("DeviceEventsTool",       "get_device_events_by_patient",    {}),
            "get_patient_event_timeline":      ("EventTimelineTool",      "get_patient_event_timeline",      {}),
            "get_cardiology_event_context":    ("CardiologyEventTool",    "get_cardiology_event_context",    {}),
            "get_neuro_event_context":         ("NeuroEventTool",         "get_neuro_event_context",         {}),
            "get_imaging_study_summary":       ("ImagingStudySummaryTool","get_imaging_study_summary",       {}),
        }

        c1, c2 = st.columns(2)
        pat_choice  = c1.selectbox("Patient", list(PATIENTS.keys()), format_func=lambda k: PATIENTS[k])
        tool_choice = c2.selectbox("MCP Tool", list(TOOLS_MAP.keys()))

        if st.button("Invoke Tool via MCP Client", type="primary", use_container_width=True):
            _, tool_name, extra_args = TOOLS_MAP[tool_choice]
            args = {"patient_id": pat_choice, **extra_args}
            if "care_unit_id" in extra_args:
                args = extra_args  # override — care unit tool doesn't take patient_id

            request_json = {"tool_name": tool_name, "arguments": args}
            col_req, col_resp = st.columns(2)

            with col_req:
                st.markdown("**MCP Client Request:**")
                st.code(
                    "POST /api/v1/tools/invoke\nAuthorization: Bearer <jwt>\n\n"
                    + json.dumps(request_json, indent=2),
                    language="json"
                )

            with col_resp:
                st.markdown("**MCP Server Response:**")
                SessionLocal = get_db()
                with st.spinner(f"Calling {tool_name}..."):
                    async def _live_call(tn=tool_name, a=args):
                        async with SessionLocal() as s:
                            import importlib
                            tool_modules = {
                                "get_patient_clinical_context":  ("mcp_server.tools.patient_context",   "PatientContextTool",     "get_patient_clinical_context"),
                                "get_care_unit_summary":         ("mcp_server.tools.care_unit_summary", "CareUnitSummaryTool",    "get_care_unit_summary"),
                                "get_alarm_context":             ("mcp_server.tools.alarm_context",     "AlarmContextTool",       "get_alarm_context"),
                                "get_device_events_by_patient":  ("mcp_server.tools.device_events",     "DeviceEventsTool",       "get_device_events_by_patient"),
                                "get_patient_event_timeline":    ("mcp_server.tools.event_timeline",    "EventTimelineTool",      "get_patient_event_timeline"),
                                "get_cardiology_event_context":  ("mcp_server.tools.cardiology_context","CardiologyEventTool",    "get_cardiology_event_context"),
                                "get_neuro_event_context":       ("mcp_server.tools.neuro_context",     "NeuroEventTool",         "get_neuro_event_context"),
                                "get_imaging_study_summary":     ("mcp_server.tools.imaging_summary",   "ImagingStudySummaryTool","get_imaging_study_summary"),
                            }
                            mod_path, cls_name, method = tool_modules[tn]
                            mod = importlib.import_module(mod_path)
                            cls = getattr(mod, cls_name)
                            fn  = getattr(cls, method)
                            t0  = time.perf_counter()
                            res = await fn(session=s, **a)
                            ms  = (time.perf_counter() - t0) * 1000
                            return res, ms

                    result, elapsed = run_async(_live_call())

                st.caption(f"MCP Server responded in **{elapsed:.0f} ms**  |  Confidence: **{result.get('confidence_score',0):.0%}**")

                # ── Formatted display per tool ──────────────────────────
                if tool_name == "get_patient_clinical_context":
                    p = result.get("patient", {})
                    enc = result.get("encounter", {})
                    cu = result.get("care_unit", {})
                    clins = result.get("clinicians", [])
                    devs = result.get("devices", [])
                    st.markdown(f"**Patient:** {p.get('first_name','')} {p.get('last_name','')} &nbsp;|&nbsp; MRN: `{p.get('mrn','—')}` &nbsp;|&nbsp; {cu.get('name','')}")
                    st.markdown(f"**Diagnosis:** {enc.get('admission_diagnosis','—')} &nbsp;|&nbsp; **Admitted:** {str(enc.get('admission_time','—'))[:10]}")
                    if clins:
                        st.markdown("**Care Team:** " + "  •  ".join(f"{c.get('first_name','')} {c.get('last_name','')} ({c.get('role','')})" for c in clins))
                    if devs:
                        st.markdown("**Devices:** " + "  •  ".join(f"{'🟢' if d.get('is_online') else '🔴'} {d.get('device_name','')} ({d.get('device_type','').replace('_',' ')})" for d in devs))

                elif tool_name == "get_care_unit_summary":
                    cu = result.get("care_unit", {})
                    st.markdown(f"**Unit:** {cu.get('name','—')} (`{cu.get('code','?')}`)")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Total Patients",    result.get("patient_count", 0))
                    c2.metric("Critical Patients", result.get("critical_patient_count", 0))
                    c3.metric("Unit Type",         cu.get("unit_type","—").replace("_"," ").title())
                    for p in result.get("active_patients", []):
                        pid = p.get("patient_id","")
                        pname = {"PAT-001":"Alice Johnson","PAT-002":"Bob Martinez","PAT-003":"Carol Williams","PAT-004":"David Chen","PAT-005":"Eleanor Thompson"}.get(pid, pid)
                        st.markdown(f"  - {pname} (`{pid}`) — status: `{p.get('status','active')}`")

                elif tool_name == "get_alarm_context":
                    alarm = result.get("alarm", {})
                    sev = alarm.get("severity","?").upper()
                    sev_color = "#f44336" if sev in ("HIGH","CRITICAL") else "#ff9800" if sev == "MEDIUM" else "#4caf50"
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Alarm Type", alarm.get("alarm_type","—").replace("_"," ").title())
                    c2.metric("Severity",   sev)
                    c3.metric("Value",      f"{alarm.get('current_value','—')} {alarm.get('unit','')}")
                    c4.metric("Threshold",  f"{alarm.get('threshold','—')} {alarm.get('unit','')}")
                    st.markdown(f"**Clinical Significance:** `{result.get('clinical_significance','unknown')}`  &nbsp;|&nbsp;  **Device:** {alarm.get('device_type','—').replace('_',' ').title()}")

                elif tool_name == "get_device_events_by_patient":
                    tw = result.get("time_window", {})
                    c1, c2 = st.columns(2)
                    c1.metric("Events Found", result.get("event_count", 0))
                    c2.metric("Time Window", f"{str(tw.get('start_time',''))[:10]} → {str(tw.get('end_time',''))[:10]}")
                    events = result.get("device_events", [])
                    if events:
                        import pandas as pd
                        df = pd.DataFrame([{"Time": str(e.get("timestamp",""))[:16], "Device": e.get("device_id",""), "Type": e.get("event_type",""), "Severity": e.get("severity","")} for e in events[:10]])
                        st.dataframe(df, use_container_width=True, hide_index=True)
                    else:
                        st.info("No device alarm events in the monitoring window — devices are operating normally.")

                elif tool_name == "get_patient_event_timeline":
                    events = result.get("timeline", [])
                    st.metric("Timeline Events", result.get("event_count", len(events)))
                    if events:
                        import pandas as pd
                        df = pd.DataFrame([{"Time": str(e.get("timestamp",""))[:16].replace("T"," "), "Type": e.get("event_type",""), "Significance": e.get("clinical_significance","normal")} for e in events[:10]])
                        st.dataframe(df, use_container_width=True, hide_index=True)
                    else:
                        st.info("Timeline built from all clinical events. No events recorded for this demo patient yet.")

                elif tool_name == "get_cardiology_event_context":
                    c1, c2 = st.columns(2)
                    c1.metric("ECG Events",   len(result.get("ecg_events", [])))
                    c2.metric("Confidence",   f"{result.get('confidence_score',0):.0%}")
                    st.markdown(f"**Arrhythmia Classification:** {result.get('arrhythmia_classification','No classification recorded')}")
                    if result.get("cardiac_biomarkers"):
                        st.markdown("**Cardiac Biomarkers:** " + str(result["cardiac_biomarkers"]))

                elif tool_name == "get_neuro_event_context":
                    c1, c2 = st.columns(2)
                    c1.metric("Seizure Events", len(result.get("seizure_events", [])))
                    c2.metric("Confidence",      f"{result.get('confidence_score',0):.0%}")
                    if result.get("eeg_findings"):
                        st.markdown(f"**EEG Findings:** {result['eeg_findings']}")

                elif tool_name == "get_imaging_study_summary":
                    study = result.get("study", {})
                    c1, c2 = st.columns(2)
                    c1.metric("Modality",  study.get("modality","—"))
                    c2.metric("Status",    study.get("report_status","—").replace("_"," ").title())
                    if study.get("findings"):
                        st.markdown(f"**Findings:** {study['findings']}")
                    if study.get("impression"):
                        st.success(f"**Radiologist Impression:** {study['impression']}")

                else:
                    # Fallback — show clean JSON for any other tool
                    st.json({k: v for k, v in result.items() if k != "raw_data"})

    with tab_registry:
        st.markdown("**All 10 registered MCP tools:**")
        import pandas as pd
        reg = pd.DataFrame([
            ["get_patient_clinical_context",  "All depts",     "patient_id (required), include_devices",      "patient, encounter, care_unit, clinicians, devices, confidence_score"],
            ["get_care_unit_summary",         "Ward managers", "care_unit_id (required)",                     "care_unit, patient_count, critical_count, active_patients"],
            ["get_device_events_by_patient",  "ICU / CCU",     "patient_id (required), start_time, end_time", "device_events[], event_count, time_window"],
            ["get_patient_event_timeline",    "All depts",     "patient_id (required), event_types[]",        "timeline[], event_count"],
            ["get_alarm_context",             "ICU / ED",      "patient_id (required)",                       "alarm{}, vitals_before, vitals_during, clinical_significance"],
            ["get_diagnostic_exam_context",   "Lab / Diag",    "patient_id (required)",                       "exam{}, confidence_score"],
            ["get_imaging_study_summary",     "Radiology",     "patient_id (required)",                       "study{modality, findings, impression, dicom_metadata}"],
            ["get_anesthesia_case_context",   "OR / Anesthesia","patient_id (required)",                      "case{pre_op_risk, agents, recovery_status}"],
            ["get_neuro_event_context",       "Neurology",     "patient_id (required)",                       "seizure_events[], eeg_findings, confidence_score"],
            ["get_cardiology_event_context",  "Cardiology",    "patient_id (required)",                       "ecg_events[], arrhythmia_classification, confidence_score"],
        ], columns=["Tool Name", "Hospital Area", "Input Arguments", "Key Response Fields"])
        st.dataframe(reg, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 5 — SECURITY & COMPLIANCE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "5. Security & Compliance":

    st.title("Security & Compliance")
    st.markdown("The MCP Platform is built HIPAA-first — every access is authenticated, authorized, and permanently audited.")

    tab_rbac, tab_jwt, tab_audit, tab_summary = st.tabs([
        "Role Permissions", "JWT Authentication", "Audit Log", "Compliance Summary"
    ])

    with tab_rbac:
        st.subheader("Who Can Call Which Tool?")
        st.caption("RBAC is enforced at the MCP Server. Each role has explicitly defined tool permissions.")

        import pandas as pd
        from mcp_server.security.authorization import RBACEngine, ClinicianRole
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
        role_enum = {r.value: r for r in ClinicianRole}
        matrix = {}
        for role in roles:
            perms = RBACEngine.ROLE_PERMISSIONS.get(role_enum.get(role), {})
            matrix[role.capitalize()] = ["✅" if perms.get(t) else "❌" for t in tools]

        df = pd.DataFrame(matrix, index=[t.replace("get_","").replace("_"," ").title() for t in tools])
        st.dataframe(df, use_container_width=True)

        st.markdown("""
        | Role | Tool Access | Use Case |
        |------|------------|---------|
        | **Physician** | All 10 tools | Full clinical decision support |
        | **Nurse** | 5 tools (patient, alarms, devices, timeline, care unit) | Bedside care and alarm management |
        | **Technician** | 2 tools (device events, alarm context) | Device and biomedical engineering |
        | **Administrator** | All 10 tools | Clinical governance and reporting |
        """)

    with tab_jwt:
        st.subheader("Try Authentication")
        c1, c2 = st.columns(2)
        with c1:
            user = st.selectbox("Login as", [
                "dr_smith (Physician)",
                "nurse_johnson (Nurse)",
                "tech_williams (Technician)",
                "admin_brown (Administrator)",
            ])
            cred_map = {
                "dr_smith (Physician)":        ("dr_smith",        "test_password_123"),
                "nurse_johnson (Nurse)":       ("nurse_johnson",   "test_password_456"),
                "tech_williams (Technician)":  ("tech_williams",   "test_password_789"),
                "admin_brown (Administrator)": ("admin_brown",     "test_password_admin"),
            }
            uname, pw = cred_map[user]

        with c2:
            st.markdown("**Credentials (demo):**")
            st.code(f'username: "{uname}"\npassword: "••••••••••"', language="yaml")

        if st.button("Authenticate with MCP Server", type="primary"):
            from mcp_server.security.credentials import CredentialValidator
            from mcp_server.security.auth import AuthenticationManager
            clinician = CredentialValidator.validate_credentials(uname, pw)
            if clinician:
                auth = AuthenticationManager()
                token = auth.create_access_token(
                    clinician_id=clinician["id"],
                    clinician_name=clinician["name"],
                    role=clinician["role"],
                    care_units=clinician["care_units"],
                )
                payload = auth.verify_token(token)
                st.success(f"Authenticated: **{clinician['name']}** — role: `{clinician['role']}`")
                st.code(f"Bearer {token[:60]}...", language="text")
                st.json({k: v for k, v in payload.items() if k not in ("exp","iat","jti")})
            else:
                st.error("Authentication failed")

    with tab_audit:
        st.subheader("HIPAA Audit Log")
        st.caption("Every MCP tool call is permanently logged. PHI fields (name, DOB, MRN) are never stored in the log.")

        from mcp_server.security.audit_logger import AuditLogger
        audit = AuditLogger(log_dir="demo_audit_logs")
        audit.log_tool_call("get_patient_clinical_context","CLIN-001","physician",{"patient_id":"PAT-001"},["PAT-001"],True,  142.3)
        audit.log_tool_call("get_alarm_context",           "CLIN-002","nurse",    {"patient_id":"PAT-001"},["PAT-001"],True,   88.5)
        audit.log_tool_call("get_imaging_study_summary",   "CLIN-002","nurse",    {"patient_id":"PAT-001"},["PAT-001"],False,    0.0)
        audit.log_authentication_attempt("dr_smith",   success=True)
        audit.log_authentication_attempt("bad_actor",  success=False, failure_reason="invalid credentials")
        audit.log_authorization_decision("CLIN-002","nurse","get_imaging_study_summary", allowed=False, reason="role restriction")

        import pandas as pd
        logs = audit.get_recent_logs(limit=8)
        rows = []
        for e in logs:
            rows.append({
                "Time":      e.get("timestamp","")[:19].replace("T"," "),
                "Event":     e.get("event_type","").replace("_"," ").title(),
                "Tool/User": e.get("tool_name") or e.get("username_partial","—"),
                "Who":       e.get("clinician_id","—"),
                "Outcome":   "Success" if e.get("success") else ("Denied" if "allowed" in e else "Failed"),
            })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        st.info("In production: logs written to daily JSONL files with 7-year retention. PHI is never stored.")

    with tab_summary:
        st.subheader("Compliance Summary")
        compliance = [
            ("HIPAA Audit Logging",    True,  "Every tool call, authentication, and authorization decision is logged with timestamp, clinician ID, and outcome"),
            ("PHI Protection",         True,  "Patient names, DOB, and MRN are never written to log files — only patient IDs"),
            ("Audit Log Retention",    True,  "7 years (2,555 days) — exceeds HIPAA minimum requirement"),
            ("Authentication",         True,  "JWT tokens with HS256 signing, configurable expiry, OAuth2/LDAP integration ready"),
            ("Role-Based Access",      True,  "RBAC enforced for every tool call — role checked at the server, not the client"),
            ("Transport Security",     True,  "TLS/HTTPS enforced in production (Kubernetes ingress with cert-manager)"),
            ("Data Encryption at Rest",True,  "PostgreSQL with encrypted volumes (AES-256) in Kubernetes deployment"),
            ("Consent Checking",       True,  "ConsentEngine checks patient consent before returning PHI"),
            ("Kubernetes Deployment",  True,  "Production-ready k8s manifests with namespaced RBAC, health probes, PVC for audit logs"),
        ]
        for item, ok, desc in compliance:
            icon = "✅" if ok else "⚠️"
            st.markdown(f"**{icon} {item}**")
            st.caption(f"  {desc}")
            st.markdown("")
