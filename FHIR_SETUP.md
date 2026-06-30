# FHIR R4 Connector — Setup Guide

This guide shows how to connect the Hospital Clinical Intelligence MCP Platform
to a FHIR R4 server.  Three sandbox targets are documented, plus local Synthea
synthetic files.

---

## Architecture

```
FHIR Server / HL7 Feed
  └─→  mcp_server/fhir/connector.py   (httpx, sync + async)
          └─→  mcp_server/fhir/normalizer.py  (FHIR R4 → internal DTOs)
                  └─→  mcp_server/fhir/fhir_tools.py  (13 tool functions)
                          └─→  mcp_server/tools/fhir_tool_registry.py  (MCP tools)
                                  └─→  enterprise_platform.py  (_fhir_route)
                                          └─→  Copilot response
```

When `FHIR_BASE_URL` is **not set**, all queries fall back to the simulator
(existing behaviour, unchanged).  Set the variable to activate FHIR mode.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FHIR_BASE_URL` | _(empty — disabled)_ | FHIR R4 server base URL |
| `FHIR_AUTH_TYPE` | `none` | Auth mode: `none` \| `bearer` \| `basic` \| `oauth2` |
| `FHIR_TOKEN` | _(empty)_ | Bearer / OAuth2 access token |
| `FHIR_USERNAME` | _(empty)_ | Username for `basic` auth |
| `FHIR_PASSWORD` | _(empty)_ | Password for `basic` auth |
| `FHIR_TIMEOUT_SECONDS` | `10` | Per-request timeout |
| `FHIR_USE_SANDBOX_MODE` | `false` | Set `true` to auto-select HAPI public URL and disable auth |
| `FHIR_OAUTH_TOKEN_URL` | _(empty)_ | Token endpoint for `oauth2` mode |
| `FHIR_CLIENT_ID` | _(empty)_ | OAuth2 client ID |
| `FHIR_CLIENT_SECRET` | _(empty)_ | OAuth2 client secret |

> **Never commit secrets.**  Use a `.env` file (already in `.gitignore`) or
> your system's secret manager.

---

## Option 1 — HAPI FHIR Public Server (default sandbox)

No registration required.  Synthetic data only.

```bash
# .env or export before running
FHIR_BASE_URL=https://hapi.fhir.org/baseR4
FHIR_USE_SANDBOX_MODE=true
FHIR_AUTH_TYPE=none
```

Run the app:
```bash
streamlit run enterprise_platform.py
```

> **Note:** HAPI public server is shared; patient IDs change between sessions.
> Use the copilot to search: `fhir search John Smith`

### Example FHIR API calls (HAPI public)

```http
GET https://hapi.fhir.org/baseR4/Patient?name=Smith&_count=5
GET https://hapi.fhir.org/baseR4/Patient/592873
GET https://hapi.fhir.org/baseR4/Observation?patient=592873&category=vital-signs&_sort=-date
GET https://hapi.fhir.org/baseR4/Condition?patient=592873
GET https://hapi.fhir.org/baseR4/MedicationRequest?patient=592873
GET https://hapi.fhir.org/baseR4/Encounter?class=IMP&_count=20
```

---

## Option 2 — SMART Health IT Sandbox

Provides pre-loaded patient scenarios (including ICU-relevant patients).
Registration is free at <https://launch.smarthealthit.org/>.

```bash
FHIR_BASE_URL=https://r4.smarthealthit.org
FHIR_AUTH_TYPE=bearer
FHIR_TOKEN=<obtain from SMART Health IT developer portal>
```

### Obtaining a token (SMART standalone launch)

1. Register your app at <https://launch.smarthealthit.org/> → **App Launch**
2. Set launch URL: `http://localhost:8501` (Streamlit default)
3. Perform authorization: the tool returns a bearer token.
4. Set `FHIR_TOKEN=<token>` in your `.env`.

Tokens expire after 1 hour.  For `oauth2` mode with auto-refresh:

```bash
FHIR_BASE_URL=https://r4.smarthealthit.org
FHIR_AUTH_TYPE=oauth2
FHIR_OAUTH_TOKEN_URL=https://launch.smarthealthit.org/v/r4/auth/token
FHIR_CLIENT_ID=<your-client-id>
FHIR_CLIENT_SECRET=<your-client-secret>
```

---

## Option 3 — Epic Sandbox (MyChart / FHIR R4)

Epic's sandbox uses SMART on FHIR OAuth2.

1. Register at <https://fhir.epic.com/> → **Sign Up** → create a developer app.
2. Note your `client_id`.  Epic sandboxes use PKCE (public client) so
   `client_secret` is not needed for standalone apps.
3. Use the Epic sandbox non-production endpoint:

```bash
FHIR_BASE_URL=https://fhir.epic.com/interconnect-ambu-oauth/api/FHIR/R4
FHIR_AUTH_TYPE=bearer
FHIR_TOKEN=<token from Epic OAuth2 flow>
```

> Epic requires patient context for most resource queries; use patient-facing
> SMART launch rather than system/client-credentials.

---

## Option 4 — Local Synthea FHIR Bundles

[Synthea](https://github.com/synthetichealth/synthea) generates realistic
synthetic patient data exported as FHIR R4 bundles.

### Generate data

```bash
# Install Synthea (Java required)
git clone https://github.com/synthetichealth/synthea.git
cd synthea
./run_synthea -p 100 --exporter.fhir.export=true
# Output: output/fhir/*.json
```

### Load into HAPI FHIR (local Docker)

```bash
docker run -p 8080:8080 hapiproject/hapi:latest
```

Upload bundles:
```bash
for f in output/fhir/*.json; do
  curl -X POST http://localhost:8080/fhir \
       -H "Content-Type: application/fhir+json" \
       -d @"$f"
done
```

Configure the connector:
```bash
FHIR_BASE_URL=http://localhost:8080/fhir
FHIR_AUTH_TYPE=none
```

---

## Copilot Example Questions

The AI Copilot routes queries containing the word **`fhir`** to the FHIR
connector.  Simulator data continues to handle all other queries.

| Question | Handler | Tool |
|----------|---------|------|
| `fhir search John Smith` | `_handle_fhir_search_patients` | `fhir_search_patients` |
| `fhir patient 592873` | `_handle_fhir_patient_by_id` | `fhir_get_patient` |
| `fhir icu census` | `_handle_fhir_icu_census` | `fhir_get_icu_patients` |
| `fhir patients with low spo2` | `_handle_fhir_low_spo2` | `fhir_get_patients_with_low_spo2` |
| `fhir patients with arrhythmia` | `_handle_fhir_arrhythmia` | `fhir_get_patients_with_arrhythmia` |
| `fhir timeline for patient 592873` | `_handle_fhir_patient_timeline` | `fhir_get_patient_timeline` |
| `fhir summarize patient 592873` | `_handle_fhir_summarize_patient` | `fhir_summarize_patient_status` |

---

## Example Expected Responses

### `fhir search John Smith`
```
Found 3 patient(s) matching 'john smith':
- John Smith | FHIR ID: `592873` | Age: 54 | Gender: male
- John A Smith | FHIR ID: `593100` | Age: 31 | Gender: male
- ...
```

### `fhir icu census`
```
FHIR Inpatient Census — 7 active encounter(s)
- Margaret Lowe | MRN: 00123 | Admitted: 2026-06-28
- Thomas Hill   | MRN: 00456 | Admitted: 2026-06-29
- ...
Source: FHIR R4 (https://hapi.fhir.org/baseR4)
```

### `fhir patients with low spo2`
```
4 patient(s) with SpO2 < 90% (FHIR R4):
- Patient/592873 — SpO2 87.0% at 2026-06-30T09:15
- Patient/593100 — SpO2 88.5% at 2026-06-30T09:22
- ...
```

---

## Registered MCP Tools

| # | Tool name | FHIR query |
|---|-----------|------------|
| 1 | `fhir_get_patient` | `GET /Patient/{id}` |
| 2 | `fhir_search_patients` | `GET /Patient?name={name}` |
| 3 | `fhir_get_patient_vitals` | `GET /Observation?patient={id}&category=vital-signs` |
| 4 | `fhir_get_patient_conditions` | `GET /Condition?patient={id}` |
| 5 | `fhir_get_patient_medications` | `GET /MedicationRequest?patient={id}` |
| 6 | `fhir_get_patient_encounters` | `GET /Encounter?patient={id}` |
| 7 | `fhir_get_icu_patients` | `GET /Encounter?class=IMP` |
| 8 | `fhir_get_patients_with_low_spo2` | `GET /Observation?code=59408-5&value-quantity=lt{n}` |
| 9 | `fhir_get_patients_with_high_news2` | Derived: encounters + vitals + NEWS2 computation |
| 10 | `fhir_get_patients_with_arrhythmia` | `GET /Condition?code=698247002` |
| 11 | `fhir_get_connected_devices` | `GET /Device?patient={id}` |
| 12 | `fhir_get_patient_timeline` | Encounter + Observation + Procedure by date |
| 13 | `fhir_summarize_patient_status` | All of the above, aggregated |

---

## Assumptions and Known Gaps

| # | Assumption / Gap | Impact |
|---|-----------------|--------|
| 1 | FHIR R4 only (not DSTU2 or R3) | Queries will fail against older servers |
| 2 | Vital signs must be LOINC-coded (see `normalizer.py::LOINC_VITALS`) | Non-LOINC obs are skipped |
| 3 | NEWS2 is computed from available obs; missing parameters reduce accuracy | Score may be 0 if < 3 params present |
| 4 | OAuth2 token refresh is client-credentials only | PKCE / authorization-code flow not supported |
| 5 | `fhir_get_icu_patients` fetches patient demographics one-by-one (N+1) | Slow for large censuses; add `_include=Encounter:patient` when server supports it |
| 6 | No PHI in log output (patient IDs are logged at DEBUG level only) | Log level must be >= INFO in production |
| 7 | Simulator continues to handle all non-`fhir`-prefixed queries | Mixed mode by design; one source at a time |
| 8 | No offline caching of FHIR data | Queries fail gracefully if server is unreachable |
| 9 | Device/DeviceMetric resources are modelled but DeviceMetric live readings are not pulled | Add DeviceMetric support for real-time waveforms |
| 10 | DiagnosticReport and AllergyIntolerance resources are normalised but not yet wired into intent handlers | Add `_handle_fhir_allergies` and `_handle_fhir_labs` as a next step |
