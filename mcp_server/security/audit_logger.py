"""
Audit Logger for Hospital Clinical Intelligence MCP Platform.

Logs all tool invocations, data access, authentication events, and
authorization decisions with PHI-safe masking.
"""

import glob
import json
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from mcp_server.utils.logger import get_logger

logger = get_logger(__name__)

# PHI fields that must never appear in logs
_PHI_FIELD_NAMES = {"first_name", "last_name", "full_name", "name", "email",
                    "phone", "address", "date_of_birth", "mrn"}


def _mask_phi(data: Any, depth: int = 0) -> Any:
    """Recursively mask PHI fields in dicts and lists for safe logging."""
    if depth > 5:
        return data
    if isinstance(data, dict):
        return {k: ("[MASKED]" if k in _PHI_FIELD_NAMES else _mask_phi(v, depth + 1))
                for k, v in data.items()}
    if isinstance(data, list):
        return [_mask_phi(item, depth + 1) for item in data]
    return data


class AuditLogger:
    """
    Comprehensive audit logger for HIPAA-compliant access tracking.

    All logs are PHI-safe: patient names, MRNs, DOBs are masked.
    Patient IDs (internal UUIDs) are retained for traceability.
    """

    _MAX_IN_MEMORY = 10_000

    def __init__(self, log_dir: str = "audit_logs"):
        self._log_store: List[Dict[str, Any]] = []
        self._log_dir = log_dir
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create audit log directory '{log_dir}': {e}")

    def _write_to_file(self, entry: Dict[str, Any]) -> None:
        """Append entry to today's daily audit log file."""
        try:
            day_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            path = os.path.join(self._log_dir, f"audit_{day_str}.jsonl")
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as e:
            logger.warning(f"Could not write audit log to file: {e}")

    def _store(self, entry: Dict[str, Any]) -> None:
        """Add entry to in-memory store (capped) and write to file."""
        if len(self._log_store) >= self._MAX_IN_MEMORY:
            self._log_store = self._log_store[-(self._MAX_IN_MEMORY // 2):]
        self._log_store.append(entry)
        self._write_to_file(entry)

    def log_tool_call(
        self,
        tool_name: str,
        clinician_id: str,
        clinician_role: str,
        arguments: Dict[str, Any],
        patient_ids: List[str],
        success: bool,
        response_time_ms: float,
        error_message: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> str:
        """
        Log an MCP tool invocation.

        Returns:
            log_id: Unique log entry identifier
        """
        log_id = f"LOG-{uuid.uuid4()}"
        entry = {
            "log_id": log_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "tool_invocation",
            "tool_name": tool_name,
            "clinician_id": clinician_id,
            "clinician_role": clinician_role,
            "arguments": _mask_phi(arguments),
            "patient_ids_accessed": patient_ids,
            "success": success,
            "response_time_ms": response_time_ms,
            "error_message": error_message,
            "ip_address": ip_address,
        }
        self._store(entry)
        if success:
            logger.info(f"AUDIT: tool={tool_name} clinician={clinician_id} "
                        f"patients={patient_ids} success=True time={response_time_ms:.1f}ms")
        else:
            logger.warning(f"AUDIT: tool={tool_name} clinician={clinician_id} "
                           f"patients={patient_ids} success=False error={error_message}")
        return log_id

    def log_authentication_attempt(
        self,
        username: str,
        success: bool,
        ip_address: Optional[str] = None,
        failure_reason: Optional[str] = None,
    ) -> str:
        """Log an authentication attempt (success or failure)."""
        log_id = f"LOG-{uuid.uuid4()}"
        # Do not log the username in detail—only log a hash or partial for traceability
        safe_username = username[:3] + "***" if len(username) > 3 else "***"
        entry = {
            "log_id": log_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "authentication",
            "username_partial": safe_username,
            "success": success,
            "ip_address": ip_address,
            "failure_reason": failure_reason,
        }
        self._store(entry)
        if success:
            logger.info(f"AUDIT: auth success user={safe_username} ip={ip_address}")
        else:
            logger.warning(f"AUDIT: auth failed user={safe_username} reason={failure_reason}")
        return log_id

    def log_authorization_decision(
        self,
        clinician_id: str,
        clinician_role: str,
        tool_name: str,
        allowed: bool,
        reason: Optional[str] = None,
    ) -> str:
        """Log an authorization decision (allow or deny)."""
        log_id = f"LOG-{uuid.uuid4()}"
        entry = {
            "log_id": log_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "authorization_decision",
            "clinician_id": clinician_id,
            "clinician_role": clinician_role,
            "tool_name": tool_name,
            "allowed": allowed,
            "reason": reason,
        }
        self._store(entry)
        if allowed:
            logger.debug(f"AUDIT: auth_check ALLOW clinician={clinician_id} tool={tool_name}")
        else:
            logger.warning(f"AUDIT: auth_check DENY clinician={clinician_id} tool={tool_name} reason={reason}")
        return log_id

    def log_data_access(
        self,
        clinician_id: str,
        patient_id: str,
        data_types: List[str],
        tool_name: str,
    ) -> str:
        """Log access to patient data."""
        log_id = f"LOG-{uuid.uuid4()}"
        entry = {
            "log_id": log_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "data_access",
            "clinician_id": clinician_id,
            "patient_id": patient_id,
            "data_types": data_types,
            "tool_name": tool_name,
        }
        self._store(entry)
        logger.info(f"AUDIT: data_access clinician={clinician_id} patient={patient_id} types={data_types}")
        return log_id

    def log_ingestion_error(self, source: str, message_snippet: str, error: str) -> str:
        """Log a data ingestion error."""
        log_id = f"LOG-{uuid.uuid4()}"
        entry = {
            "log_id": log_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "ingestion_error",
            "source": source,
            "message_snippet": message_snippet[:100],
            "error": error,
        }
        self._store(entry)
        logger.error(f"AUDIT: ingestion_error source={source} error={error}")
        return log_id

    def get_recent_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve most recent audit log entries."""
        return list(reversed(self._log_store[-limit:]))

    def get_logs_for_patient(self, patient_id: str) -> List[Dict[str, Any]]:
        """Retrieve all audit log entries for a patient."""
        return [e for e in self._log_store
                if patient_id in e.get("patient_ids_accessed", [])
                or e.get("patient_id") == patient_id]

    def get_logs_for_clinician(self, clinician_id: str) -> List[Dict[str, Any]]:
        """Retrieve all audit log entries for a clinician."""
        return [e for e in self._log_store if e.get("clinician_id") == clinician_id]

    def load_logs_from_files(
        self, start_date: date, end_date: date
    ) -> List[Dict[str, Any]]:
        """Load historical audit log entries from daily JSONL files."""
        results: List[Dict[str, Any]] = []
        current = start_date
        while current <= end_date:
            path = os.path.join(self._log_dir, f"audit_{current.isoformat()}.jsonl")
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                results.append(json.loads(line))
                except Exception as e:
                    logger.warning(f"Could not read audit log file '{path}': {e}")
            current += timedelta(days=1)
        return results

    def get_retention_status(self) -> Dict[str, Any]:
        """Return summary of audit log files on disk."""
        pattern = os.path.join(self._log_dir, "audit_*.jsonl")
        files = sorted(glob.glob(pattern))
        dates = []
        for f in files:
            base = os.path.basename(f)
            # Extract date portion: audit_YYYY-MM-DD.jsonl
            try:
                date_str = base[6:16]
                dates.append(date_str)
            except Exception:
                pass
        return {
            "log_directory": self._log_dir,
            "file_count": len(files),
            "earliest_date": dates[0] if dates else None,
            "latest_date": dates[-1] if dates else None,
            "in_memory_entries": len(self._log_store),
        }


# Global audit logger instance
audit_logger = AuditLogger()
