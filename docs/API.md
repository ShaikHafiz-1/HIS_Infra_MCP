# Hospital Clinical Intelligence MCP Platform — API Reference

Version 0.1.0 | Base URL: `http://localhost:8000`

---

## Overview

The Hospital Clinical Intelligence MCP Platform provides a Model Context Protocol (MCP) server that aggregates clinical data from HL7 v2, FHIR, DICOM, and device telemetry systems into structured, contextual responses for AI-assisted clinical decision support.

All data access is logged for HIPAA compliance. PHI fields are masked in audit logs.

---

## Authentication

All tool endpoints require a JWT Bearer token.

### Obtain Token

```
POST /api/v1/auth/token
Content-Type: application/json

{
  "username": "dr_smith",
  "password": "securepassword",
  "role": "physician",
  "care_units": ["cu-icu-001", "cu-ccu-001"]
}
```

**Response:**
```json
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer",
  "expires_in": 28800
}
```

Use the token as: `Authorization: Bearer <token>`

### Roles

| Role | Access Level |
|------|-------------|
| `physician` | Full access to all 10 tools |
| `nurse` | Patient context, care unit, device events, alarms, timeline |
| `technician` | Device events, alarm context only |
| `administrator` | Full access including administrative tools |

---

## Tool Invocation

All tools are invoked through a single endpoint:

```
POST /api/v1/tools/invoke
Authorization: Bearer <token>
Content-Type: application/json

{
  "tool_name": "<tool_name>",
  "arguments": { ... }
}
```

---

## Tool Reference

### 1. `get_patient_clinical_context`

Retrieve comprehensive clinical context for a patient.

**Input Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `patient_id` | string | Yes | Internal patient identifier |
| `include_timeline` | boolean | No (default: false) | Include event timeline |
| `include_devices` | boolean | No (default: true) | Include active devices |

**Output Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `patient` | object | Demographics (id, mrn, full_name, age, gender) |
| `encounter` | object | Current encounter details |
| `care_unit` | object | Assigned care unit |
| `diagnoses` | array | Active diagnoses |
| `medications` | array | Current medications |
| `clinicians` | array | Assigned clinicians |
| `devices` | array | Active monitoring devices |
| `recent_abnormal_observations` | array | Recent abnormal vitals/labs |
| `confidence_score` | float | Data confidence (0.0–1.0) |
| `source_references` | array | Data source provenance |

**Example Request:**
```json
{
  "tool_name": "get_patient_clinical_context",
  "arguments": {
    "patient_id": "PAT-12345",
    "include_devices": true
  }
}
```

**Access:** physician, nurse, administrator

---

### 2. `get_care_unit_summary`

Retrieve summary of all patients in a care unit.

**Input Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `care_unit_id` | string | Yes | Internal care unit identifier |

**Output Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `care_unit` | object | Care unit info |
| `active_patients` | array | All active patients with vitals |
| `critical_patients` | array | Patients with critical status |
| `patient_count` | integer | Total active patient count |
| `critical_patient_count` | integer | Critical patient count |
| `clinician_assignments` | array | Clinician workload summary |
| `confidence_score` | float | Data confidence |
| `source_references` | array | Data provenance |

**Access:** physician, nurse, administrator

---

### 3. `get_device_events_by_patient`

Retrieve device events for a patient within a time window.

**Input Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `patient_id` | string | Yes | Internal patient identifier |
| `start_time` | string | No | Start time in ISO 8601 format |
| `end_time` | string | No | End time in ISO 8601 format |
| `device_type` | string | No | Filter by device type |

**Output Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `patient_id` | string | Patient identifier |
| `device_events` | array | Alarm events, status changes, waveform events |
| `vital_trends` | array | Vital sign trend analysis |
| `event_count` | integer | Total event count |
| `time_window` | object | Applied time window |
| `confidence_score` | float | Data confidence |
| `source_references` | array | Data provenance |

**Access:** physician, nurse, technician, administrator

---

### 4. `get_patient_event_timeline`

Retrieve chronological timeline of clinical events.

**Input Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `patient_id` | string | Yes | Internal patient identifier |
| `start_time` | string | No | Start time ISO 8601 |
| `end_time` | string | No | End time ISO 8601 |
| `event_types` | array[string] | No | Filter: `vital_sign`, `alarm`, `medication`, `procedure`, `note`, `device_change` |

**Output Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `patient_id` | string | Patient identifier |
| `timeline` | array | Chronologically sorted events |
| `timeline[].timestamp` | string | ISO 8601 timestamp |
| `timeline[].event_type` | string | Event category |
| `timeline[].clinical_significance` | string | `normal`, `abnormal_low`, `abnormal_high`, `critical_low`, `critical_high`, `critical` |
| `timeline[].annotations` | array | Clinical annotations |
| `timeline[].confidence_score` | float | Event confidence |
| `event_count` | integer | Total events |
| `time_window` | object | Applied time window |
| `confidence_score` | float | Overall confidence |
| `source_references` | array | Data provenance |

**Access:** physician, nurse, administrator

---

### 5. `get_alarm_context`

Retrieve detailed context for an alarm event.

**Input Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `alarm_id` | string | One of | Specific alarm event ID |
| `patient_id` | string | One of | Patient ID (returns most recent alarm) |

**Output Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `alarm` | object | Alarm details (type, severity, timestamp) |
| `clinical_significance` | string | Clinical severity classification |
| `patient` | object | Patient demographics |
| `encounter` | object | Encounter context |
| `vitals_before` | array | Vitals 15 minutes before alarm |
| `vitals_during` | array | Vitals during alarm |
| `vitals_after` | array | Vitals 15 minutes after alarm |
| `diagnoses` | array | Patient active diagnoses |
| `medications` | array | Current medications |
| `clinician_response` | object | Response time and action taken |
| `similar_historical_alarms` | array | Similar past alarms |
| `confidence_score` | float | Data confidence |
| `source_references` | array | Data provenance |

**Access:** physician, nurse, technician, administrator

---

### 6. `get_diagnostic_exam_context`

Retrieve diagnostic exam context including imaging and labs.

**Input Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `exam_id` | string | One of | Specific exam ID |
| `patient_id` | string | One of | Patient ID (returns most recent exam) |

**Output:** exam metadata, imaging studies (with DICOM metadata), lab results (with reference ranges and abnormality flags), contemporaneous vital signs, related clinical events.

**Access:** physician, administrator

---

### 7. `get_imaging_study_summary`

Retrieve imaging study summary with radiologist findings.

**Input Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `study_id` | string | One of | Specific study ID |
| `patient_id` | string | One of | Patient ID (returns most recent study) |

**Output:** study (modality, findings, report_status, follow_up_recommendations, DICOM metadata), contemporaneous vitals, related events, patient demographics.

**Access:** physician, administrator

---

### 8. `get_anesthesia_case_context`

Retrieve comprehensive anesthesia case context.

**Input Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `procedure_id` | string | One of | Specific procedure ID |
| `patient_id` | string | One of | Patient ID (returns most recent case) |

**Output:** case timeline, anesthesia agents, intraoperative vitals, ventilator settings, alarm events, recovery vitals, anesthesia notes.

**Access:** physician, administrator

---

### 9. `get_neuro_event_context`

Retrieve neurological event context including seizures and EEG.

**Input Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `patient_id` | string | One of | Patient identifier |
| `event_id` | string | One of | Specific neuro event ID |

**Output:** seizure events (with type, duration_seconds, EEG pattern), EEG findings, neuroimaging studies, vitals during/after event, seizure management medications, neurological assessments (GCS score).

**Access:** physician, administrator

---

### 10. `get_cardiology_event_context`

Retrieve cardiac event context including ECG and arrhythmias.

**Input Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `patient_id` | string | One of | Patient identifier |
| `event_id` | string | One of | Specific cardiac event ID |

**Output:** ECG events (arrhythmia_type, onset_timestamp), ECG waveform data, blood pressure trend, SpO₂ trend, cardiac alarm events, cardiac medications, related diagnostic exams, cardiac assessments (CHADS2-VASc score).

**Access:** physician, administrator

---

## Utility Endpoints

### List Tools
```
GET /api/v1/tools/list
```
Returns all registered tool definitions with schemas.

### Tool Schema
```
GET /api/v1/tools/{tool_name}/schema
```

### Health Check
```
GET /api/v1/health/health
```
Returns overall system health, DB connectivity, uptime.

### Readiness Check
```
GET /api/v1/health/ready
```
Returns 200 if ready to serve requests, 503 if not.

### Metrics
```
GET /api/v1/health/metrics
```
Returns Prometheus-format metrics for all tool invocations.

---

## Error Reference

| HTTP Status | Error | Description |
|-------------|-------|-------------|
| 400 | `ValidationError` | Invalid input parameters |
| 401 | `AuthenticationError` | Missing or invalid JWT token |
| 403 | `PermissionDeniedError` | Role lacks tool permission |
| 403 | `CareUnitAccessError` | Clinician not assigned to care unit |
| 404 | `ToolNotFoundError` | Tool name does not exist |
| 500 | `InternalServerError` | Unexpected server error |
| 503 | `ServiceUnavailable` | Server not ready (DB/Redis down) |

**Error Response Format:**
```json
{
  "error": "ValidationError",
  "detail": "patient_id must be a non-empty string",
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## Performance SLAs

| Tool | Target Response Time |
|------|---------------------|
| `get_care_unit_summary` | < 500ms |
| All other tools | < 2000ms |
| Cache hit (patient context) | < 50ms |

---

## HIPAA Compliance Notes

- All tool invocations are audit logged with clinician ID, patient ID, timestamp, and response time
- PHI fields (name, DOB, MRN, email, phone, address) are masked in audit logs
- Patient IDs (internal UUIDs) are retained for traceability
- Authentication attempts are logged with username masked (first 3 chars only)
- Authorization denials are logged with reason
- Audit logs are persisted to daily JSONL files with 7-year retention
- All network traffic should be TLS-encrypted in production
