# Hospital Clinical Intelligence MCP — Skills

This document maps every capability the platform must deliver, organised by care-unit role and cross-cutting concern. Each skill block names the MCP tool it relies on, the data sources it queries, and the acceptance criteria it satisfies.

---

## 1. Core Infrastructure Skills

### 1.1 MCP Server Bootstrap
**Tool layer:** `main.py` / FastAPI + Python MCP SDK  
**Satisfies:** Req 1 (all criteria)

| Step | What to build |
|------|--------------|
| 1 | Initialise FastAPI app and mount `MCPServer` from `mcp.server.fastapi` |
| 2 | Register all 10 tool definitions with `inputSchema` and `outputSchema` |
| 3 | Wire `@mcp_server.call_tool` dispatcher to each tool module |
| 4 | Enforce JWT/OAuth2 authentication on every incoming request |
| 5 | Add request-ID middleware and global exception handlers (400 / 403 / 500) |
| 6 | Support `asyncio`-based concurrent connections (100+ clients) |
| 7 | Expose `/health` and `/metrics` endpoints |

**Inputs:** config values (host, port, secret key, DB URL, Redis URL)  
**Outputs:** running MCP server accepting tool calls over HTTP/SSE

---

### 1.2 Configuration & Dependency Management
**File:** `config.py`, `requirements.txt`  
**Satisfies:** Req 1.4, Req 25, Req 27

- Load all settings from environment variables (12-factor app pattern)
- Required packages: `fastapi`, `mcp`, `sqlalchemy[asyncio]`, `asyncpg`, `redis`, `pydantic`, `python-jose[cryptography]`, `hl7`, `fhirclient`, `pynetdicom`, `pydicom`, `aiohttp`, `alembic`
- Expose `Settings` singleton via `config.get_settings()`

---

## 2. Data Ingestion Skills

### 2.1 HL7 v2 Ingestion
**File:** `ingestion/hl7_listener.py`, `ingestion/hl7_parser.py`  
**Satisfies:** Req 2

| Message Type | Fields to extract |
|---|---|
| ADT (A01/A02/A03/A08) | patient_id, encounter_id, care_unit, admission/discharge time |
| ORU R01 | patient_id, observation type, value, units, timestamp |
| ORM O01 | patient_id, order type, medication/procedure, clinician |
| MDM T02 | patient_id, note type, author, timestamp, content |

**Implementation steps:**
1. Open MLLP TCP socket on port 2575 (`socket.AF_INET`)
2. Strip `<VT>…<FS><CR>` framing and decode UTF-8
3. Parse with `hl7.parse()`, branch on `MSH-9` message type
4. Map IDs via `PatientIDMapper` and `EncounterIDMapper`
5. Normalise and persist via `DataNormalizer`
6. Send HL7 ACK; on parse failure log to `audit_logs` and reject

---

### 2.2 FHIR API Ingestion
**File:** `ingestion/fhir_client.py`  
**Satisfies:** Req 3

Resources to retrieve (REST GET with Bearer token):

| FHIR Resource | Internal table |
|---|---|
| Patient | `patients`, `patient_id_mapping` |
| Encounter | `encounters`, `encounter_id_mapping` |
| Observation | `observations` |
| DiagnosticReport | `diagnostic_exams` |
| ImagingStudy | `imaging_studies` |
| MedicationRequest | `medication_events` |
| Procedure | `procedures` |
| CarePlan | stored as JSON in `encounters` |

**Implementation steps:**
1. `aiohttp.ClientSession` with `Authorization: Bearer {token}`
2. Handle FHIR pagination (`Bundle.link[relation=next]`)
3. Map each resource to internal schema via `ResourceMapper`
4. Upsert with conflict resolution in `DataConsolidationEngine`

---

### 2.3 DICOM Metadata Ingestion
**File:** `ingestion/dicom_listener.py`  
**Satisfies:** Req 4

**Implementation steps:**
1. Create `pynetdicom.AE`, add supported SOP contexts (CT, MR, CR, US, NM, PT)
2. Handle `EVT_C_STORE`; extract: `PatientID`, `StudyInstanceUID`, `SeriesInstanceUID`, `Modality`, `StudyDate+StudyTime`, `StudyDescription`
3. Resolve `PatientID` → internal patient ID via `PatientIDMapper`
4. Store metadata in `imaging_studies`; return DICOM status `0x0000`

---

### 2.4 Device Telemetry Ingestion
**File:** `ingestion/device_connector.py`  
**Satisfies:** Req 5

Device data types and handling:

| Data type | Storage target | Annotation |
|---|---|---|
| Vital signs (HR, SpO₂, BP, RR) | `observations` | Abnormality level, trend |
| Waveforms (ECG, art-line) | `observations` (compressed) | Arrhythmia flags |
| Alarm events | `alarm_events` | Severity classification |
| Device status | `devices.status` | Online/offline, calibration |
| Therapeutic settings | `observations` (ventilator/pump params) | Clinical significance |

**Implementation steps:**
1. Factory pattern: `connect_device(device_id, device_type, params)` returns typed handler
2. Associate device → patient via `device_patient_map` (maintained from ADT feeds)
3. Apply server-side timestamps for consistency (Req 5.7)
4. Flag stale data: alert if no reading within configured heartbeat window (Req 5.8)

---

## 3. Normalization & Mapping Skills

### 3.1 ID Mapping
**File:** `normalization/id_mapper.py`  
**Satisfies:** Req 6.1–6.5, Req 6.7

| Mapper class | Table | Cache key pattern |
|---|---|---|
| `PatientIDMapper` | `patient_id_mapping` | `pat:{source}:{ext_id}` |
| `EncounterIDMapper` | `encounter_id_mapping` | `enc:{source}:{ext_id}` |
| `DeviceIDMapper` | `device_id_mapping` | `dev:{source}:{ext_id}` |
| `ClinicalIDMapper` | `clinician_id_mapping` | `cli:{source}:{ext_id}` |

- In-memory dict cache + Redis L2 cache (TTL 1 h)
- On cache miss: SQL lookup → create new UUID-based internal ID
- Log potential duplicates to `audit_logs` (fuzzy match on demographics)

### 3.2 Care Unit Mapping
**File:** `normalization/care_unit_mapper.py`  
**Satisfies:** Req 6.4

Static map covers: `CARDIO`, `ED`, `NEURO`, `SURG`, `OR`, `ICU`, `RAD`, `GEN`  
Dynamic overrides stored in `care_unit_mapping` table; unmapped codes logged as warnings.

### 3.3 Data Consolidation
**File:** `normalization/consolidation.py`  
**Satisfies:** Req 6.6, Req 24

- `merge_demographics()`: last-write-wins with conflict log
- `consolidate_encounters()`: deduplicate by (patient_id, admission_time ± 1 h)
- `consolidate_observations()`: deduplicate by (patient_id, type, timestamp ± 30 s)

---

## 4. Clinical Context Engine Skills

### 4.1 Event Classification
**File:** `context_engine/event_classifier.py`  
**Satisfies:** Req 7, Req 8

Clinical significance levels: `normal` | `abnormal_low` | `abnormal_high` | `critical_low` | `critical_high`

Threshold table (configurable in DB):

| Vital | Critical low | Abnormal low | Abnormal high | Critical high |
|---|---|---|---|---|
| HR (bpm) | 30 | 50 | 120 | 150 |
| SpO₂ (%) | 85 | 90 | — | — |
| SBP (mmHg) | 70 | 90 | 160 | 200 |
| RR (br/min) | 6 | 10 | 25 | 35 |
| Temp (°C) | 34 | 36 | 38.5 | 40 |

### 4.2 Timeline Builder
**File:** `context_engine/timeline_builder.py`  
**Satisfies:** Req 8.4, Req 13

- Merge observations, alarm_events, medication_events, procedures sorted by timestamp ASC
- Annotate each entry with `preceding_events` (5-min lookback window)
- Paginate: default 200 events per call; accept `offset` parameter

### 4.3 Annotation Engine
**File:** `context_engine/annotation_engine.py`  
**Satisfies:** Req 7.1–7.8

Annotation types:
- `abnormal_value` — value outside threshold
- `trend` — increasing / decreasing / stable (linear regression, min 3 points)
- `clinical_context` — pre/intra/post procedure, during intervention
- `device_significance` — calibration state, last verified
- `medication_effect` — expected pharmacodynamic window

### 4.4 Confidence Scoring
**File:** `context_engine/confidence_scorer.py`  
**Satisfies:** Req 7.8, Req 8.8

Score factors (multiplicative):
- Source reliability: FHIR = 1.0, HL7 = 0.97, device telemetry = 0.95, manual entry = 0.90
- Data age: < 1 h = 1.0, 1–24 h = 0.9, > 24 h = 0.7
- Calibration: calibrated = 1.0, uncalibrated = 0.8, unknown = 0.85
- Completeness: deduct 0.05 per missing mandatory field

---

## 5. MCP Tool Skills (10 Tools)

### Tool 1 — `get_patient_clinical_context`
**File:** `tools/patient_context.py`  
**Satisfies:** Req 9  
**Roles allowed:** all clinical roles  

**Inputs:**
```json
{ "patient_id": "string", "include_timeline": false, "include_devices": true }
```

**Output fields:**
- `patient`: demographics (id, mrn, name, dob, age, gender)
- `encounter`: id, care_unit, admission_time, clinicians[]
- `diagnoses`: [{icd_code, description, severity, onset_date}]
- `medications`: [{name, dosage, route, indication, prescribed_by}]
- `clinicians`: [{id, name, role, contact}]
- `devices`: [{id, type, model, status, last_reading}]
- `recent_observations`: last 10 abnormal vitals with annotations
- `recent_events`: last 5 clinical events (procedures, exams, alarms)
- `timeline`: (if `include_timeline=true`) 24-h event list
- `confidence_score`: 0.0–1.0
- `source_references`: [{system, resource_id, timestamp}]

**Cache:** Redis key `patient_context:{patient_id}`, TTL 5 min; invalidate on new ADT/ORU

---

### Tool 2 — `get_care_unit_summary`
**File:** `tools/care_unit_summary.py`  
**Satisfies:** Req 10  
**Roles allowed:** charge nurse, attending, unit manager, administrator  

**Inputs:**
```json
{ "care_unit_id": "string" }
```

**Output fields:**
- `total_patients`: integer
- `critical_patients`: [{patient_id, mrn, name, trigger_alarms[]}]
- `patients`: [{patient_id, mrn, name, is_critical, recent_observations, active_alarms, assigned_clinicians}]
- `active_alarms`: aggregated across unit, sorted by severity DESC
- `recent_procedures`: last 24 h
- `clinician_assignments`: [{clinician_id, name, role, patient_count}]
- `confidence_scores`: per-patient map

**Cache:** Redis key `care_unit:{care_unit_id}`, TTL 1 min

---

### Tool 3 — `get_device_events_by_patient`
**File:** `tools/device_events.py`  
**Satisfies:** Req 11  
**Roles allowed:** all clinical roles  

**Inputs:**
```json
{
  "patient_id": "string",
  "start_time": "ISO8601",
  "end_time": "ISO8601",
  "device_type": "string|null"
}
```

**Output fields:**
- `alarm_events`: [{type, severity, threshold, timestamp, device_id, device_model, acknowledged}]
- `status_changes`: [{device_id, change_type, from, to, timestamp}]
- `waveform_events`: [{event_type, timestamp, description}]
- `setting_changes`: [{device_id, parameter, old_value, new_value, timestamp}]
- `vital_observations`: time-series array
- `trends`: [{vital_type, direction, slope, r_squared}]
- `correlated_events`: clinical events within ±5 min of each alarm
- `source_references`, `confidence_scores`

---

### Tool 4 — `get_diagnostic_exam_context`
**File:** `tools/diagnostic_exam.py`  
**Satisfies:** Req 12  
**Roles allowed:** all clinical roles  

**Inputs:**
```json
{ "exam_id": "string|null", "patient_id": "string|null" }
```

At least one of `exam_id` or `patient_id` required.

**Output fields:**
- `exam`: {id, type, indication, timestamp, result_status, findings}
- `imaging_studies`: [{modality, study_id, description, report_status, radiologist}]
- `dicom_metadata`: {patient_id, study_uid, series_uid, modality, sop_class}
- `lab_results`: [{test_name, value, unit, reference_range, abnormal_flag}]
- `vital_signs`: observations ±30 min of exam
- `related_events`: clinical events ±1 h of exam
- `source_references`, `confidence_scores`

---

### Tool 5 — `get_patient_event_timeline`
**File:** `tools/event_timeline.py`  
**Satisfies:** Req 13  
**Roles allowed:** all clinical roles  

**Inputs:**
```json
{
  "patient_id": "string",
  "start_time": "ISO8601",
  "end_time": "ISO8601",
  "event_types": ["observation","alarm","medication","procedure","exam","note","device"]
}
```

**Output fields:**
- `timeline`: [{timestamp, event_type, event, annotations, clinical_significance, confidence_score}]
- `summary`: {total_events, critical_count, abnormal_count}
- `source_references`

---

### Tool 6 — `get_alarm_context`
**File:** `tools/alarm_context.py`  
**Satisfies:** Req 14  
**Roles allowed:** all clinical roles  

**Inputs:**
```json
{ "alarm_id": "string" }
```

**Output fields:**
- `alarm`: {id, type, severity, threshold, timestamp, device_id, device_type}
- `vitals_before`: observations 10 min pre-alarm
- `vitals_during`: observations during alarm duration
- `vitals_after`: observations 10 min post-alarm
- `patient_diagnoses`: active diagnoses at alarm time
- `patient_medications`: active medications at alarm time
- `recent_interventions`: clinical events ±30 min
- `clinician_response`: {acknowledged_by, acknowledged_at, response_note}
- `historical_similar_alarms`: last 5 alarms of same type for patient
- `source_references`, `confidence_score`

---

### Tool 7 — `get_imaging_study_summary`
**File:** `tools/imaging_summary.py`  
**Satisfies:** Req 15  
**Roles allowed:** all clinical roles; radiology tools also for radiologists  

**Inputs:**
```json
{ "study_id": "string|null", "patient_id": "string|null" }
```

**Output fields:**
- `study`: {modality, timestamp, description, report_status}
- `radiologist_report`: {findings, impression, recommendations, status}
- `clinical_indication`: string
- `vital_signs`: observations ±30 min
- `related_events`: procedures, medications, alarms ±2 h
- `follow_up`: [{recommendation, urgency}]
- `source_references`, `confidence_score`

---

### Tool 8 — `get_anesthesia_case_context`
**File:** `tools/anesthesia_context.py`  
**Satisfies:** Req 16  
**Roles allowed:** anesthesiologist, CRNA, OR nurse  

**Inputs:**
```json
{ "procedure_id": "string|null", "patient_id": "string|null" }
```

**Output fields:**
- `anesthesia_period`: {start_time, end_time, duration_minutes, type}
- `agents`: [{drug_name, dosage, route, administration_time, cumulative_dose}]
- `vital_signs`: full intra-op time-series (HR, BP, SpO₂, EtCO₂, temp)
- `ventilator_events`: [{parameter, value, timestamp}]
- `alarm_events`: intra-op alarms sorted by severity
- `recovery_period`: {start, end, vital_signs, discharge_criteria_met}
- `anesthesia_notes`: clinician documentation
- `source_references`, `confidence_score`

---

### Tool 9 — `get_neuro_event_context`
**File:** `tools/neuro_context.py`  
**Satisfies:** Req 17  
**Roles allowed:** neurologist, neuro ICU nurse, neurosurgery  

**Inputs:**
```json
{ "patient_id": "string|null", "event_id": "string|null" }
```

**Output fields:**
- `seizure_events`: [{timestamp, duration_seconds, seizure_type, postictal_duration}]
- `eeg_findings`: [{timestamp, finding_type, description, abnormality_level}]
- `neuroimaging`: [{modality, study_id, timestamp, findings, impression}]
- `vital_signs_during_event`: observations bracketing each seizure
- `seizure_medications`: [{drug, dosage, route, given_at, effect_observed}]
- `neuro_assessments`: clinician notes, GCS scores, focal deficits
- `source_references`, `confidence_score`

---

### Tool 10 — `get_cardiology_event_context`
**File:** `tools/cardiology_context.py`  
**Satisfies:** Req 18  
**Roles allowed:** cardiologist, cardiac ICU nurse, electrophysiology  

**Inputs:**
```json
{ "patient_id": "string|null", "event_id": "string|null" }
```

**Output fields:**
- `ecg_events`: [{timestamp, rhythm, rate, interpretation, alarm_triggered}]
- `ecg_waveforms`: references to stored waveform segments
- `hemodynamics`: {bp_trend, spo2_trend, mean_arterial_pressure_trend}
- `cardiac_alarms`: [{alarm_type, severity, timestamp, device}]
- `cardiac_medications`: [{drug, dosage, indication, given_at}]
- `cardiac_imaging`: [{modality (echo/cath), findings, ejection_fraction}]
- `cardiology_notes`: assessments, care plans
- `source_references`, `confidence_score`

---

## 6. Security Skills

### 6.1 Authentication
**File:** `security/auth.py`  
**Satisfies:** Req 19.1–19.4

- `POST /token` accepts username + password; validates against hospital LDAP/OAuth2 IdP
- Issues HS256 JWT (8-hour expiry) containing: `sub`, `name`, `role`, `care_units[]`
- Dependency `get_current_user` decodes and validates token on every request
- Failed auth attempts logged to `audit_logs` with IP address

### 6.2 Role-Based Access Control
**File:** `security/rbac.py`  
**Satisfies:** Req 19.5–19.8

Role permission matrix:

| Role | Tools accessible | Patient scope |
|---|---|---|
| physician | all 10 tools | assigned care units |
| nurse | tools 1–6 | assigned care units |
| anesthesiologist | tools 1, 3–8 | OR / ICU only |
| cardiologist | tools 1, 3–7, 10 | cardiology units |
| neurologist | tools 1, 3–7, 9 | neurology units |
| radiologist | tools 4, 7 | all units (read imaging only) |
| administrator | tools 1–2 (PHI masked) | all units |

- `check_patient_access(user, patient_id)`: verifies patient's care unit ∈ user's `care_units`
- `check_care_unit_access(user, care_unit_id)`: verifies unit ∈ user's `care_units`
- Denied access → 403 + audit log entry

### 6.3 Patient Consent
**File:** `security/consent.py`  
**Satisfies:** Req 20

- `consent_preferences` table: `(patient_id, data_type, care_unit_id, granted: bool)`
- `check_consent(patient_id, user)` called before any PHI is returned
- Supports granular consent: by data type (imaging, meds, notes) and by care unit

### 6.4 PHI Masking
**File:** `security/phi_masking.py`  
**Satisfies:** Req 22

- Audit logs: replace `patient_name` with `patient_id`; truncate `mrn` to last 4 chars
- Error messages: strip medication names, ICD codes, patient identifiers
- Admin role responses: mask name → initials, DOB → age only

### 6.5 Audit Logging
**File:** `security/audit_logger.py`  
**Satisfies:** Req 21

Every log entry contains:
```
clinician_id | tool_name | patient_id | action | parameters (JSONB) |
result_summary | timestamp | ip_address
```

- Stored in `audit_logs` table (PostgreSQL, encrypted at rest via pgcrypto)
- `GET /admin/audit-logs` endpoint with filters: clinician, patient, date range, tool
- Retention: 7 years minimum (Req 21.9, Req 26.2)

---

## 7. Storage Skills

### 7.1 Database Setup
**Files:** `database/connection.py`, `database/migrations/`  
**Satisfies:** Req 24, Req 25

- Async SQLAlchemy engine with `asyncpg` driver
- Alembic migration for all tables defined in design.md §Storage Layer Design
- Partitioned `observations` table by month (Req 25.6)
- All indexes defined in design.md §Indexing Strategy

### 7.2 Redis Cache
**File:** `database/cache.py`  
**Satisfies:** Req 25.5

| Cache key | TTL |
|---|---|
| `patient_context:{id}` | 5 min |
| `care_unit:{id}` | 1 min |
| `device_events:{id}` | 2 min |
| `thresholds:{vital_type}` | 1 h |

Cache invalidation events: new ADT admission/transfer/discharge, new ORU result, new alarm.

### 7.3 Data Retention & Archival
**File:** `database/partitioning.py`  
**Satisfies:** Req 26

- Monthly partition creation job (cron, 1st of month)
- Archive partitions older than 24 months to cold storage (S3 or equivalent)
- Purge data beyond retention period only after confirmation + audit log

---

## 8. Validation & Error Handling Skills

**File:** `utils/validators.py`  
**Satisfies:** Req 23

Validators to implement:

| Validator | Check |
|---|---|
| `validate_patient_id` | UUID format + existence in `patients` table |
| `validate_encounter_id` | UUID format + existence + patient match |
| `validate_device_id` | UUID format + existence in `devices` table |
| `validate_time_window` | `start < end`, max window 30 days, ISO8601 format |
| `validate_care_unit_id` | UUID or known code in `care_units` |

Error response shape:
```json
{ "error": "ValidationError", "field": "patient_id", "detail": "...", "request_id": "..." }
```

HTTP status codes: 400 validation, 401 auth, 403 authz, 404 not found, 500 internal.

---

## 9. Performance Skills

**Satisfies:** Req 25

| Target | Mechanism |
|---|---|
| Patient context < 500 ms | Redis cache + composite DB indexes |
| Care unit summary < 1000 ms | Pre-aggregation job every 30 s + cache |
| 100+ concurrent clients | FastAPI async + connection pool (max 100) |
| Slow query detection | Log queries > 200 ms; expose via `/metrics` |

---

## 10. Test Data & Simulation Skills

**Satisfies:** Req 30

When `APP_ENV=test`, activate:

- `generate_test_patients(n)` — synthetic demographics for all 8 care units
- `simulate_device_stream(patient_id, duration_s)` — realistic vital sign time-series
- `inject_alarm_sequence(patient_id, scenario)` — scenarios: `sepsis_onset`, `cardiac_event`, `seizure`, `hypoxia`
- `simulate_fhir_feed()` — webhook-style FHIR Bundle events
- `simulate_hl7_stream()` — ADT/ORU message sequence over loopback TCP

Seed script: `python -m utils.seed_test_data --patients 200 --days 7`

---

## 11. MCP Client Skills

**File:** `mcp_client/client.py`  
**Satisfies:** Req 29

- Connect via `mcp.ClientSession` (SSE transport)
- `authenticate(username, password)` → store JWT, refresh before expiry
- `call_tool(name, args)` → validated request, formatted response
- NL query mapping: lightweight intent classifier maps free-text to tool + args
- Query history: persisted in `~/.hospital_mcp/history.json`
- Auto-reconnect with exponential backoff (max 5 attempts, 30 s ceiling)

---

## 12. Monitoring Skills

**Satisfies:** Req 27

Expose `/metrics` (Prometheus format):
- `mcp_tool_calls_total{tool, status}`
- `mcp_tool_latency_seconds{tool}` (histogram)
- `db_pool_available_connections`
- `hl7_messages_ingested_total{type, status}`
- `device_telemetry_lag_seconds{device_id}`
- `cache_hit_ratio{cache_key_prefix}`

Alert conditions (integrate with PagerDuty / alertmanager):
- Error rate > 5 % over 5 min
- DB pool exhaustion (< 5 free connections)
- Ingestion lag > 30 s for any device
- Disk > 85 % on DB host

---

## Skill Build Order (Recommended)

```
Phase 1 — Foundation
  1.2 Config & deps
  7.1 Database schema + migrations
  6.5 Audit logger (needed everywhere)

Phase 2 — Ingestion
  2.1 HL7 listener
  2.2 FHIR client
  2.3 DICOM listener
  2.4 Device connector
  3.1 ID mapping
  3.2 Care unit mapping
  3.3 Data consolidation

Phase 3 — Context Engine
  4.1 Event classifier
  4.2 Timeline builder
  4.3 Annotation engine
  4.4 Confidence scorer

Phase 4 — Security
  6.1 Authentication
  6.2 RBAC
  6.3 Consent
  6.4 PHI masking

Phase 5 — Tools (parallelize within phase)
  Tools 1–4 (patient, care unit, devices, diagnostics)
  Tools 5–7 (timeline, alarm, imaging)
  Tools 8–10 (anesthesia, neuro, cardiology)

Phase 6 — Storage & Performance
  7.2 Redis cache
  7.3 Retention/archival
  8   Validators
  9   Performance tuning

Phase 7 — Operations
  1.1 Health/metrics endpoints
  10  Test data simulator
  11  MCP client
  12  Monitoring alerts
```
