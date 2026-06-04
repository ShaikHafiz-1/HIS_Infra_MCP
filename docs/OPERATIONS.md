# Hospital Clinical Intelligence MCP Platform — Operations Guide

Version 0.1.0 | Last Updated: 2025-05-25

---

## Table of Contents

1. [Deployment](#deployment)
2. [Configuration Reference](#configuration-reference)
3. [Docker Operations](#docker-operations)
4. [Kubernetes Operations](#kubernetes-operations)
5. [Database Operations](#database-operations)
6. [Monitoring and Observability](#monitoring-and-observability)
7. [Security Operations](#security-operations)
8. [Data Retention and Compliance](#data-retention-and-compliance)
9. [Troubleshooting](#troubleshooting)
10. [Scaling](#scaling)
11. [Backup and Recovery](#backup-and-recovery)
12. [Incident Response](#incident-response)

---

## Deployment

### Prerequisites

| Dependency | Minimum Version | Notes |
|------------|----------------|-------|
| Python | 3.12+ | Required |
| PostgreSQL | 15+ | Primary data store |
| Redis | 7+ | Caching layer |
| RabbitMQ | 3.12+ | Message queue (optional, degrades gracefully) |
| Docker | 24+ | Container runtime |
| kubectl | 1.28+ | Kubernetes CLI |

### Local Development Setup

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate    # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with local settings

# Run database migrations
alembic upgrade head

# Seed development data (optional)
python scripts/seed_data.py

# Start the server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Production Setup

```bash
# Set environment variables (do not use .env in production)
export ENVIRONMENT=production
export DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/hospital_mcp
export REDIS_URL=redis://:pass@host:6379/0
export RABBITMQ_URL=amqp://user:pass@host:5672/
export SECRET_KEY=<64-char-random-hex>
export JWT_SECRET_KEY=<64-char-random-hex>
export ALLOWED_HOSTS=your-domain.com

# Run with 4 workers (adjust to CPU count)
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## Configuration Reference

All settings are managed through environment variables (see `config.py`).

### Core Settings

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `ENVIRONMENT` | `development` | No | `development`, `staging`, `production` |
| `DEBUG` | `false` | No | Enable debug logging |
| `SECRET_KEY` | — | Yes (prod) | App secret key (min 32 chars) |
| `ALLOWED_HOSTS` | `*` | Yes (prod) | Comma-separated allowed host list |
| `HOST` | `0.0.0.0` | No | Bind address |
| `PORT` | `8000` | No | Bind port |
| `WORKERS` | `4` | No | Uvicorn worker count |

### Database Settings

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./hospital_mcp.db` | Yes | Async DB connection string |
| `DB_POOL_SIZE` | `10` | No | Connection pool size |
| `DB_MAX_OVERFLOW` | `20` | No | Max overflow connections |
| `DB_POOL_TIMEOUT` | `30` | No | Pool checkout timeout (seconds) |

### Cache Settings

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `REDIS_URL` | `redis://localhost:6379/0` | No | Redis connection URL |
| `ENABLE_CACHING` | `true` | No | Toggle cache layer |
| `CACHE_TTL_PATIENT` | `300` | No | Patient context TTL (seconds) |
| `CACHE_TTL_CARE_UNIT` | `60` | No | Care unit summary TTL (seconds) |
| `CACHE_TTL_DEVICE` | `30` | No | Device events TTL (seconds) |

### Message Queue Settings

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `RABBITMQ_URL` | `amqp://guest:guest@localhost:5672/` | No | RabbitMQ connection URL |
| `ENABLE_HL7_INGESTION` | `true` | No | Toggle HL7 v2 ingestion |
| `ENABLE_FHIR_INGESTION` | `true` | No | Toggle FHIR R4 ingestion |
| `ENABLE_DICOM_INGESTION` | `true` | No | Toggle DICOM listener |
| `ENABLE_DEVICE_TELEMETRY` | `true` | No | Toggle device telemetry |

### Security Settings

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `JWT_SECRET_KEY` | — | Yes (prod) | JWT signing key (min 32 chars) |
| `JWT_ALGORITHM` | `HS256` | No | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `480` | No | Token lifetime (minutes) |
| `ENABLE_AUDIT_LOGGING` | `true` | No | Toggle audit logging |
| `AUDIT_LOG_DIR` | `audit_logs` | No | Directory for JSONL audit files |

---

## Docker Operations

### Build and Run

```bash
# Build image
docker build -t hospital-mcp:latest .

# Run standalone (development)
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/hospital_mcp \
  -e REDIS_URL=redis://host:6379/0 \
  hospital-mcp:latest

# Run with Docker Compose (full stack)
docker compose up -d

# View logs
docker compose logs -f mcp_server

# Stop all services
docker compose down

# Remove all data volumes (DESTRUCTIVE)
docker compose down -v
```

### Docker Compose Services

| Service | Port | Description |
|---------|------|-------------|
| `mcp_server` | 8000 | Main application server |
| `db` | 5432 | PostgreSQL database |
| `redis` | 6379 | Redis cache |
| `rabbitmq` | 5672, 15672 | RabbitMQ + Management UI |

### Health Checks

```bash
# Check container health
docker inspect --format='{{.State.Health.Status}}' hospital_mcp_mcp_server_1

# Manual health check
curl http://localhost:8000/api/v1/health/health

# Readiness check
curl http://localhost:8000/api/v1/health/ready
```

---

## Kubernetes Operations

### Deploy to Kubernetes

```bash
# Create namespace
kubectl create namespace hospital-mcp

# Create secrets (NEVER commit to git)
kubectl create secret generic hospital-mcp-secrets \
  --namespace hospital-mcp \
  --from-literal=DATABASE_URL="postgresql+asyncpg://user:pass@db:5432/hospital_mcp" \
  --from-literal=REDIS_URL="redis://:pass@redis:6379/0" \
  --from-literal=RABBITMQ_URL="amqp://user:pass@rabbitmq:5672/" \
  --from-literal=SECRET_KEY="$(openssl rand -hex 32)" \
  --from-literal=JWT_SECRET_KEY="$(openssl rand -hex 32)"

# Apply manifests
kubectl apply -f k8s/ --namespace hospital-mcp

# Verify deployment
kubectl get pods --namespace hospital-mcp
kubectl get svc --namespace hospital-mcp
```

### Common kubectl Commands

```bash
# View pod logs
kubectl logs -f deployment/hospital-mcp --namespace hospital-mcp

# Scale deployment manually
kubectl scale deployment hospital-mcp --replicas=5 --namespace hospital-mcp

# Rolling restart (picks up new config)
kubectl rollout restart deployment/hospital-mcp --namespace hospital-mcp

# Check rollout status
kubectl rollout status deployment/hospital-mcp --namespace hospital-mcp

# Rollback if needed
kubectl rollout undo deployment/hospital-mcp --namespace hospital-mcp

# Exec into a pod
kubectl exec -it deployment/hospital-mcp --namespace hospital-mcp -- /bin/bash

# View HPA status
kubectl get hpa --namespace hospital-mcp

# View resource usage
kubectl top pods --namespace hospital-mcp
```

### Kubernetes Manifest Summary

| File | Resource | Purpose |
|------|----------|---------|
| `k8s/configmap.yaml` | ConfigMap | Non-secret environment configuration |
| `k8s/deployment.yaml` | Deployment | 3-replica app deployment with probes |
| `k8s/service.yaml` | Service | ClusterIP service on port 80 |
| `k8s/hpa.yaml` | HorizontalPodAutoscaler | Auto-scaling 2–10 pods |
| `k8s/ingress.yaml` | Ingress | nginx ingress with TLS via cert-manager |

---

## Database Operations

### Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Check current migration state
alembic current

# Generate a new migration
alembic revision --autogenerate -m "description"

# Rollback one migration
alembic downgrade -1

# Rollback to a specific revision
alembic downgrade <revision_id>
```

### Maintenance

```bash
# Connect to database
psql $DATABASE_URL

# Vacuum and analyze (run during low-traffic window)
VACUUM ANALYZE;

# Check table sizes
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

# Check active connections
SELECT count(*), state FROM pg_stat_activity GROUP BY state;

# Kill idle connections (use with care)
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
WHERE state = 'idle' AND query_start < now() - interval '1 hour';
```

### Index Health

Key indexes to monitor for query performance:

| Table | Index | Columns |
|-------|-------|---------|
| `patients` | patient_mrn_idx | mrn |
| `encounters` | encounter_patient_idx | patient_id, is_active |
| `observations` | obs_patient_time_idx | patient_id, recorded_at |
| `device_events` | device_event_patient_idx | patient_id, event_time |
| `audit_logs` | audit_clinician_idx | clinician_id, timestamp |

---

## Monitoring and Observability

### Prometheus Metrics

Access metrics at `GET /api/v1/health/metrics`. Exported counters and histograms:

| Metric | Type | Description |
|--------|------|-------------|
| `mcp_tool_invocations_total` | Counter | Total invocations by tool |
| `mcp_tool_errors_total` | Counter | Total errors by tool |
| `mcp_tool_response_time_ms` | Gauge | Average response time |
| `mcp_tool_response_time_p95_ms` | Gauge | 95th percentile response time |
| `mcp_tool_slow_queries_total` | Counter | Queries exceeding SLA thresholds |

### Performance SLAs

| Tool | Target | Alert Threshold |
|------|--------|----------------|
| `get_care_unit_summary` | < 500ms | > 750ms |
| All other tools | < 2000ms | > 3000ms |
| Cache hit (patient context) | < 50ms | > 100ms |

### Structured Logging

All logs are JSON-structured. Key log fields:

```json
{
  "timestamp": "2025-05-25T10:30:00Z",
  "level": "INFO",
  "logger": "mcp_server.tools.patient_context",
  "message": "Patient context retrieved",
  "patient_id": "PAT-12345",
  "response_time_ms": 145.2,
  "cache_hit": false
}
```

Log levels by environment:
- `development`: DEBUG
- `staging`: INFO
- `production`: WARNING (adjust as needed)

### System Status Endpoint

```bash
curl http://localhost:8000/api/v1/health/status
```

Returns component status for database, Redis cache, and RabbitMQ.

---

## Security Operations

### JWT Token Management

Tokens expire after 8 hours (480 minutes) by default. To revoke all tokens:

```bash
# Rotate JWT secret key (invalidates all existing tokens)
# 1. Generate new key
NEW_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")

# 2. Update secret in Kubernetes
kubectl patch secret hospital-mcp-secrets --namespace hospital-mcp \
  --type='json' -p="[{\"op\":\"replace\",\"path\":\"/data/JWT_SECRET_KEY\",\"value\":\"$(echo -n $NEW_KEY | base64)\"}]"

# 3. Rolling restart to pick up new key
kubectl rollout restart deployment/hospital-mcp --namespace hospital-mcp
```

### Role-Based Access Control

| Role | Clinical Context | Care Unit | Device Events | Imaging | Cardiology/Neuro/Anesthesia |
|------|:---:|:---:|:---:|:---:|:---:|
| `physician` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `nurse` | ✓ | ✓ | ✓ | ✗ | ✗ |
| `technician` | ✗ | ✗ | ✓ | ✗ | ✗ |
| `administrator` | ✓ | ✓ | ✓ | ✓ | ✓ |

Care unit restrictions: Clinicians can only access patients in their assigned `care_units` (JWT claim). Administrators bypass care unit restrictions.

### Audit Log Review

```bash
# View today's audit log
cat audit_logs/audit_$(date +%Y-%m-%d).jsonl | jq .

# Search for specific clinician actions
grep "clinician_id" audit_logs/audit_2025-05-25.jsonl | jq 'select(.clinician_id == "dr_smith")'

# Find authorization denials
grep "DENY" audit_logs/audit_2025-05-25.jsonl | jq .

# Count tool invocations by tool name
cat audit_logs/audit_2025-05-25.jsonl | jq -r '.tool_name' | sort | uniq -c | sort -rn
```

### PHI Protection

PHI fields are automatically masked in audit logs:
- Full name → first 2 chars + `***`
- MRN → `***`
- Date of birth → year only
- Email, phone, address → `***`

Patient internal UUIDs (e.g., `PAT-12345`) are retained in audit logs for traceability.

---

## Data Retention and Compliance

### Retention Policies (HIPAA Compliant)

| Data Type | Retention | Archive After |
|-----------|-----------|--------------|
| Audit logs | 7 years | 2 years |
| Patient records | 10 years | 5 years |
| Imaging data | 7 years | 3 years |
| Clinical notes | 10 years | 5 years |
| Device telemetry | 3 years | 1 year |

### Running Retention Checks

```python
from mcp_server.utils.retention import retention_manager
from datetime import datetime, timezone

# Generate retention report
report = retention_manager.generate_retention_report(
    records=[...],  # list of dicts with created_at and data_type
    data_type="audit_logs"
)
print(f"Total: {report['total']}, Expired: {report['expired']}, Archive: {report['archive']}")

# Check if a specific record should be deleted
should_delete = retention_manager.is_expired(record, "patient_records")
```

### Audit Log File Management

Audit logs are written to daily JSONL files in `AUDIT_LOG_DIR`:
- Files: `audit_logs/audit_YYYY-MM-DD.jsonl`
- Rotation: automatic (one file per day)
- 7-year retention required

```bash
# Check audit log retention status (via API)
curl -H "Authorization: Bearer <admin_token>" \
  http://localhost:8000/api/v1/tools/invoke \
  -d '{"tool_name": "get_audit_retention_status"}'
```

---

## Troubleshooting

### Service Won't Start

**Symptom**: Server exits immediately on startup.

1. Check environment variables are set:
   ```bash
   python -c "from config import settings; print(settings.database_url)"
   ```
2. Verify database is reachable:
   ```bash
   psql $DATABASE_URL -c "SELECT 1"
   ```
3. Check for port conflicts:
   ```bash
   netstat -tulpn | grep 8000
   ```
4. Review startup logs for `ERROR` entries.

### Database Connection Failures

**Symptom**: `GET /api/v1/health/ready` returns 503 with `database: false`.

1. Verify database is running and accepting connections
2. Check `DATABASE_URL` format (must use `+asyncpg` driver)
3. Check connection pool exhaustion:
   ```bash
   # In psql
   SELECT count(*) FROM pg_stat_activity WHERE datname = 'hospital_mcp';
   ```
4. Increase `DB_POOL_SIZE` if hitting limits
5. Check firewall rules between app and DB hosts

### Redis Cache Failures

**Symptom**: Cache always misses, elevated response times.

The system degrades gracefully if Redis is unavailable — all tools still function but without caching. To diagnose:

```bash
redis-cli -u $REDIS_URL ping
# Expected: PONG

redis-cli -u $REDIS_URL info memory
```

Cache failures are logged at WARNING level and do not cause tool failures.

### High Response Times

**Symptom**: Tools exceed SLA thresholds (> 2000ms).

1. Check `/api/v1/health/metrics` for p95 response times
2. Check `/api/v1/tools/stats` for per-tool statistics
3. Identify slow queries: look for `SLOW_QUERY` log entries
4. Common causes:
   - Missing database indexes → run `EXPLAIN ANALYZE` on slow queries
   - Redis unavailable → check cache hit rate
   - Database connection pool exhausted → increase `DB_POOL_SIZE`
   - Insufficient workers → increase `WORKERS` env var

### JWT Authentication Failures

**Symptom**: All requests return 401 Unauthorized.

1. Verify `JWT_SECRET_KEY` is set and matches across all app instances
2. Check token expiry (`expires_in` in token response)
3. Ensure `Authorization: Bearer <token>` header is present
4. Check clock skew between client and server (JWT uses timestamps)

### RabbitMQ Connection Issues

**Symptom**: Messages not being ingested, `rabbitmq` shown as disconnected.

The system degrades gracefully — no messages are lost if RabbitMQ is temporarily unavailable (messages queue in the source system). To reconnect:

```bash
# Check RabbitMQ status
curl -u guest:guest http://localhost:15672/api/overview

# View queue depths
curl -u guest:guest http://localhost:15672/api/queues | jq '.[].messages'
```

The connector will automatically retry connections on next publish/consume attempt.

### Tool Returns Partial Data

**Symptom**: A tool returns fewer fields than expected or `confidence_score` is low (< 0.5).

1. Low confidence score indicates data quality issues — check source system connectivity
2. Partial data is expected when:
   - Patient has no associated devices → `devices: []`
   - No active encounter → limited clinical context
   - No labs/vitals recorded → `recent_abnormal_observations: []`
3. Check `source_references` in the response to identify which data sources were available

### Permission Denied Errors

**Symptom**: 403 errors for valid users.

1. Verify clinician role in JWT payload: `python -c "import jwt; print(jwt.decode('<token>', options={'verify_signature': False}))"`
2. Check care unit assignment in JWT (`care_units` claim)
3. Review RBAC tool permission table above
4. Check audit logs for `DENY` entries with reason

---

## Scaling

### Vertical Scaling (Kubernetes)

Edit `k8s/deployment.yaml` resource limits:

```yaml
resources:
  requests:
    memory: "512Mi"   # Increase for large patient volumes
    cpu: "500m"
  limits:
    memory: "1Gi"     # 2x request is typical
    cpu: "1000m"
```

### Horizontal Scaling (HPA)

The HPA (`k8s/hpa.yaml`) auto-scales between 2 and 10 pods based on:
- CPU utilization > 70%
- Memory utilization > 80%

To manually adjust HPA bounds:

```bash
kubectl patch hpa hospital-mcp-hpa --namespace hospital-mcp \
  --type='json' -p='[{"op":"replace","path":"/spec/maxReplicas","value":20}]'
```

### Database Connection Pool Sizing

Formula: `DB_POOL_SIZE = (workers × 2) + overhead`

For 4 workers: `DB_POOL_SIZE=10`, `DB_MAX_OVERFLOW=20` (default)
For 8 workers: `DB_POOL_SIZE=20`, `DB_MAX_OVERFLOW=40`

### Cache Sizing

Redis memory usage estimate:
- Patient context cache: ~50KB per patient, TTL 5 min
- Care unit summary: ~200KB per unit, TTL 1 min
- Peak hospital load (500 active patients): ~25–50MB

Use `redis-cli info memory` to monitor usage.

---

## Backup and Recovery

### Database Backup

```bash
# Full backup (run daily in cron)
pg_dump $DATABASE_URL | gzip > backups/hospital_mcp_$(date +%Y%m%d).sql.gz

# Restore from backup
gunzip -c backups/hospital_mcp_20250525.sql.gz | psql $DATABASE_URL

# Kubernetes CronJob for automated backup (example)
kubectl create job --from=cronjob/hospital-mcp-backup manual-backup-$(date +%s) \
  --namespace hospital-mcp
```

### Audit Log Backup

Audit JSONL files must be retained for 7 years per HIPAA requirements:

```bash
# Sync audit logs to object storage (example with AWS S3)
aws s3 sync audit_logs/ s3://hospital-mcp-audit-logs/ \
  --storage-class STANDARD_IA \
  --sse AES256

# Verify upload
aws s3 ls s3://hospital-mcp-audit-logs/ --recursive
```

### Recovery Time Objectives

| Component | RTO Target | RPO Target |
|-----------|-----------|-----------|
| Application | < 5 min (k8s reschedule) | N/A (stateless) |
| Database | < 30 min | < 1 hour (WAL archiving) |
| Redis cache | < 2 min (auto-reconnect) | N/A (cache, not source of truth) |
| Audit logs | < 1 hour (restore from S3) | < 1 day (daily backup) |

---

## Incident Response

### Severity Levels

| Severity | Criteria | Response Time |
|----------|----------|--------------|
| P1 Critical | All tools unavailable, data loss risk | 15 min |
| P2 High | Single tool unavailable, auth failures | 1 hour |
| P3 Medium | Elevated error rate > 5%, latency SLA breach | 4 hours |
| P4 Low | Single patient data issue, non-critical warning | Next business day |

### P1 Response Checklist

1. **Assess blast radius**: Check `/api/v1/health/health` from multiple regions
2. **Check recent deployments**: `kubectl rollout history deployment/hospital-mcp`
3. **Roll back if needed**: `kubectl rollout undo deployment/hospital-mcp`
4. **Check database**: `psql $DATABASE_URL -c "SELECT 1"` + connection count
5. **Check audit logs**: Look for unusual spikes in error rate
6. **Notify stakeholders**: Follow your organization's incident communication plan
7. **Document**: Record timeline, root cause, and remediation in incident log

### Post-Incident Review

After every P1 or P2 incident:
1. Timeline reconstruction from logs
2. Root cause analysis (5-whys)
3. Action items to prevent recurrence
4. Update runbook if applicable
5. Review HIPAA breach notification requirements if PHI was involved

---

## HIPAA Compliance Checklist

- [ ] All network traffic uses TLS 1.2+ in production
- [ ] JWT tokens expire within 8 hours (configured)
- [ ] Audit logging enabled (`ENABLE_AUDIT_LOGGING=true`)
- [ ] Audit logs retained for 7 years
- [ ] PHI masking verified in audit log output
- [ ] Database connections use SSL (`?sslmode=require` in DATABASE_URL)
- [ ] Backups encrypted at rest
- [ ] Access logs reviewed regularly
- [ ] Staff complete annual HIPAA training
- [ ] Business Associate Agreements in place with all vendors
- [ ] Breach notification procedure documented and tested
