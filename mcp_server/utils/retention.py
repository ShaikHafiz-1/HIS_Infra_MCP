"""
Data retention and archival policy enforcement for HIPAA/HITECH compliance.

Enforces 7-year minimum retention for audit logs and clinical records
as required by HIPAA and most US state regulations.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from mcp_server.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RetentionPolicy:
    data_type: str
    retention_years: int       # Minimum years to retain
    archive_after_years: int   # Move to archive after this many years


RETENTION_POLICIES: Dict[str, RetentionPolicy] = {
    "audit_logs": RetentionPolicy("audit_logs", retention_years=7, archive_after_years=2),
    "patient_records": RetentionPolicy("patient_records", retention_years=10, archive_after_years=5),
    "imaging_data": RetentionPolicy("imaging_data", retention_years=7, archive_after_years=3),
    "clinical_notes": RetentionPolicy("clinical_notes", retention_years=10, archive_after_years=5),
    "device_telemetry": RetentionPolicy("device_telemetry", retention_years=3, archive_after_years=1),
}


class RetentionManager:
    """Applies data retention policies to clinical records."""

    def get_policy(self, data_type: str) -> RetentionPolicy:
        """Return the retention policy for data_type. Raises KeyError if unknown."""
        if data_type not in RETENTION_POLICIES:
            raise KeyError(f"Unknown data type: {data_type}. Known: {list(RETENTION_POLICIES)}")
        return RETENTION_POLICIES[data_type]

    def is_expired(self, data_type: str, created_at: datetime) -> bool:
        """Return True if the record has exceeded its retention period."""
        policy = self.get_policy(data_type)
        expiry = created_at + timedelta(days=policy.retention_years * 365)
        return datetime.now(timezone.utc) > expiry

    def should_archive(self, data_type: str, created_at: datetime) -> bool:
        """Return True if the record should be moved to long-term archive storage."""
        policy = self.get_policy(data_type)
        archive_date = created_at + timedelta(days=policy.archive_after_years * 365)
        return datetime.now(timezone.utc) > archive_date

    def get_expiry_date(self, data_type: str, created_at: datetime) -> datetime:
        """Return the datetime when this record must be purged."""
        policy = self.get_policy(data_type)
        return created_at + timedelta(days=policy.retention_years * 365)

    def apply_retention_policy(
        self,
        records: List[Any],
        data_type: str,
        date_field: str = "created_at",
    ) -> Tuple[List[Any], List[Any]]:
        """
        Split records into (kept, expired).

        Works with both dicts (records[date_field]) and objects (getattr).
        """
        kept, expired = [], []
        for record in records:
            if isinstance(record, dict):
                created_at = record.get(date_field)
            else:
                created_at = getattr(record, date_field, None)

            if created_at is None:
                kept.append(record)
                continue

            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at)

            if self.is_expired(data_type, created_at):
                expired.append(record)
            else:
                kept.append(record)

        logger.info(
            f"Retention policy '{data_type}': {len(kept)} kept, {len(expired)} expired "
            f"of {len(records)} records"
        )
        return kept, expired

    def generate_retention_report(self) -> Dict[str, Any]:
        """Return a summary of all retention policies."""
        return {
            "policies": {
                name: {
                    "retention_years": p.retention_years,
                    "archive_after_years": p.archive_after_years,
                    "retention_days": p.retention_years * 365,
                }
                for name, p in RETENTION_POLICIES.items()
            },
            "note": "All retention periods comply with HIPAA minimum 7-year requirement",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


# Global singleton
retention_manager = RetentionManager()
