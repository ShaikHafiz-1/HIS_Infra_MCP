# Hospital Clinical Intelligence MCP Platform

**Production-grade clinical AI platform** combining live patient monitoring, Model Context Protocol (MCP) tool execution, RAG-grounded evidence retrieval, and Claude AI synthesis with HIPAA-compliant audit logging.

> Architecture-review ready · Interview-demo ready · AI-first · MCP-native · RAG-grounded

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                 Streamlit Enterprise UI (6 pages)                    │
│  Command Center · Clinical Intelligence · Patient Explorer          │
│  AI Copilot · MCP Operations · Compliance & Audit                   │
└────────────────────────┬────────────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
   ┌──────────┐   ┌──────────┐   ┌──────────────┐
   │ Simulator│   │  FastAPI │   │ RAG Pipeline │
   │ WebSocket│   │  MCP     │   │ TF-IDF/     │
   │ Port 8001│   │  Server  │   │ sklearn      │
   │ 5 pts    │   │ Port 8000│   │ 4 clinical   │
   │ 5 scenes │   │ 10 tools │   │ protocols    │
   └──────────┘   └────┬─────┘   └──────────────┘
                       │
              ┌────────┴────────┐
              ▼                 ▼
        ┌──────────┐    ┌──────────────┐
        │PostgreSQL│    │    Redis     │
        │TimescaleDB│   │   Cache +    │
        │pgvector  │    │  Rate Limit  │
        └──────────┘    └──────────────┘
```

**Query pipeline:** Intent classification → Parallel MCP tool execution → RAG retrieval → Claude synthesis → Safety guardrails → HIPAA audit log → Response

---

## Features

### Phase 1 — Frontend (6 pages)
- **Command Center**: Live KPIs, unit risk heatmap, deterioration predictions, CRISIS alarm panel, live ECG/trend sparklines
- **Clinical Intelligence**: AI finding cards with full evidence trail (MCP tools + RAG citations + confidence scores)
- **Patient Explorer**: Per-patient 6-tab deep-dive (vitals, alarms, devices, timeline, AI assessment)
- **AI Copilot**: Claude Haiku chat with real-time MCP tool trace panel + RAG sources + safety guardrails
- **MCP Operations**: Tool registry, p50/p99 latency, health dashboard, recent API call log
- **Compliance & Audit**: HIPAA audit log with PHI masking, compliance score, access analytics, CSV export

### Phase 2 — Backend
- FastAPI MCP Server with 10 registered clinical tools
- PostgreSQL/TimescaleDB for time-series vitals
- Redis for session caching and rate limiting
- WebSocket endpoint for real-time vital sign streaming (`/api/v1/vitals/stream`)
- REST Copilot endpoint (`POST /api/v1/copilot/query`)
- JWT auth + RBAC with 4 clinician roles

### Phase 3 — Patient Monitor Simulator
- 5 physiologically realistic patients, 5 clinical scenarios
- WebSocket streaming: HR, SpO2, RR, BP, Temp, EtCO2, ECG every 2 seconds
- NEWS2 calculation (RCP 2017) in real-time
- IEC 60601-1-8 alarm tiers: CRISIS / WARNING / ADVISORY

| Patient | Scenario | Key Feature |
|---------|----------|-------------|
| Carol Williams (PT-001) | Respiratory Deterioration | SpO2 drops 1%/90s, Draeger V500 offline at 60s |
| Alice Johnson (PT-002) | Sepsis Risk | Temp rises 0.1°C/60s, MAP drops progressively |
| Eleanor Thompson (PT-003) | Arrhythmia | Periodic high-HR bursts, PVC ECG pattern |
| Bob Martinez (PT-004) | Post-Op Instability | MAP dip/recovery/second dip pattern |
| David Chen (PT-005) | Device Disconnect | All vitals → NaN after 5 minutes |

### Phase 4 — MCP Tool Execution
Every AI Copilot response shows:
- Tools called (1–4 parallel) with arguments
- Per-tool latency in milliseconds
- Success/failure status
- Structured result summary

10 registered tools: `get_patient_clinical_context`, `get_care_unit_summary`, `get_device_events_by_patient`, `get_patient_event_timeline`, `get_alarm_context`, `get_diagnostic_exam_context`, `get_imaging_study_summary`, `get_anesthesia_case_context`, `get_neuro_event_context`, `get_cardiology_event_context`

### Phase 5 — RAG Pipeline
- 4 clinical knowledge documents (~800 words each)
- Chunked with 200-word windows, 40-word overlap
- TF-IDF retrieval (scikit-learn preferred, pure-Python fallback)
- Top-3 chunks retrieved per query with confidence scores
- Source citations shown in every AI response

| Document | Coverage |
|----------|----------|
| `sepsis_protocol.md` | Sepsis-3, SIRS, qSOFA, Sepsis Six Bundle |
| `respiratory_protocol.md` | SpO2 targets, O2 devices, NEWS2 scoring |
| `alarm_management_policy.md` | IEC 60601-1-8 tiers, thresholds, artefact decision tree |
| `device_troubleshooting.md` | SpO2/ECG/NIBP/ventilator/pump troubleshooting |

### Phase 6 — AI Copilot Safety Guardrails
- Advisory-only framing ("may suggest", "clinical review recommended")
- Diagnosis language detection and flagging
- Treatment order language detection and flagging
- Explicit escalation recommendation when risk = CRITICAL
- Confidence score (0.0–1.0) computed from tool success rate + RAG scores
- Every response includes human-in-the-loop note

### Phase 7 — HIPAA Compliance
- PHI masking: `first_name`, `last_name`, `date_of_birth`, `mrn`, `ssn`, `address` never logged
- JSONL audit log: one file per day, 7-year retention policy
- Every tool call logged with: `timestamp`, `clinician_id`, `clinician_role`, `tool_name`, `patient_ids_accessed`, `success`, `response_time_ms`
- JWT authentication with 8-hour session timeout
- RBAC: physician / nurse / technician / administrator roles

---

## Quick Start

### Option A — Streamlit only (no Docker, no backend)

```bash
# Install dependencies
pip install streamlit pandas anthropic scikit-learn

# Run the platform
streamlit run enterprise_platform.py
```

Open **http://localhost:8501** — the simulator starts automatically.

Optional: enter your `sk-ant-…` Anthropic API key in the sidebar for real Claude AI responses.

### Option B — With FastAPI backend

```bash
# Terminal 1 — API server
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Terminal 2 — UI
streamlit run enterprise_platform.py
```

### Option C — Full Docker Compose

```bash
# Copy and configure environment
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY, SECRET_KEY

# Build and start all services
docker compose up --build

# Access:
# UI:  http://localhost:8501
# API: http://localhost:8000/api/docs
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | (empty) | Required for real Claude AI responses |
| `DATABASE_URL` | `sqlite+aiosqlite:///./hci.db` | PostgreSQL URL for production |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `SECRET_KEY` | changeme | JWT signing secret (32+ chars for production) |
| `ENVIRONMENT` | `development` | `development` / `production` |
| `DEBUG` | `true` | Enables `/api/docs` OpenAPI UI |

---

## API Reference

### MCP Tools
```
POST /api/v1/tools/invoke      — invoke any MCP tool
GET  /api/v1/tools/list        — list all registered tools
GET  /api/v1/tools/stats       — tool call statistics
```

### AI Copilot
```
POST /api/v1/copilot/query     — full MCP-RAG-Claude pipeline
GET  /api/v1/copilot/rag/documents — list RAG knowledge base
POST /api/v1/copilot/rag/search    — raw TF-IDF search
```

### Vitals Streaming
```
WS   /api/v1/vitals/stream     — WebSocket: all patients every 2s
GET  /api/v1/vitals/snapshot   — REST fallback: current state
GET  /api/v1/vitals/alarms     — active alarms across all patients
```

### Auth & Health
```
POST /api/v1/auth/token        — get JWT token
GET  /health                   — service health check
```

---

## Project Structure

```
Hospital_MCP/
├── enterprise_platform.py      # Streamlit UI — all 6 pages
├── main.py                     # FastAPI application
├── config.py                   # Settings / environment
├── requirements.txt
├── docker-compose.yml
├── Dockerfile.ui               # Streamlit container
├── Dockerfile.api              # FastAPI container
├── DEMO_SCRIPT.md              # 10-step respiratory deterioration demo
│
├── simulator/
│   └── patient_monitor.py      # Physiological patient simulator
│
├── mcp_server/
│   ├── mcp_server.py           # MCPServer core
│   ├── models/schemas.py       # Pydantic models
│   ├── tools/tool_registry.py  # 10 MCP tools
│   ├── routers/
│   │   ├── auth.py
│   │   ├── health.py
│   │   ├── mcp_tools.py
│   │   ├── vitals_ws.py        # WebSocket streaming
│   │   └── copilot_router.py   # AI Copilot endpoint
│   ├── copilot/
│   │   └── workflow.py         # MCP-RAG-Claude orchestrator
│   ├── rag/
│   │   ├── pipeline.py         # TF-IDF retrieval pipeline
│   │   └── knowledge/
│   │       ├── sepsis_protocol.md
│   │       ├── respiratory_protocol.md
│   │       ├── alarm_management_policy.md
│   │       └── device_troubleshooting.md
│   ├── security/
│   │   ├── audit_logger.py     # HIPAA audit logging
│   │   └── authorization.py    # RBAC
│   └── database/
│       ├── connection.py
│       └── models.py
│
├── tests/
│   ├── test_tools_integration.py
│   ├── test_rag.py
│   ├── test_copilot.py
│   └── test_simulator.py
│
└── demo_audit_logs/            # HIPAA audit JSONL files
```

---

## Design Decisions

**Simulator over mock data**: Real physiological trajectories (1%/90s SpO2 decline, NEWS2 real-time, 5 clinical scenarios) make the demo verifiable and interview-ready.

**TF-IDF RAG over embeddings**: Zero-latency at import, no external API calls, deterministic retrieval. Scikit-learn when available, pure Python fallback. Embeddings (pgvector) can replace this for production without changing the interface.

**Safety guardrails as code not prompt**: Advisory framing and prohibited language detection are Python functions that run on every response regardless of LLM output. The LLM cannot bypass them.

**HIPAA audit logging first**: Every tool call is logged before the response is sent. Audit completeness is guaranteed even if the response itself fails.

---

## Demo

See [DEMO_SCRIPT.md](DEMO_SCRIPT.md) for the full 10-step respiratory deterioration walkthrough.
