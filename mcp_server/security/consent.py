"""
Patient consent management for Hospital Clinical Intelligence MCP Platform.

Uses an opt-OUT model: data access is allowed by default unless an active
denial record exists. This matches clinical information systems where the
default is care delivery access.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple

from mcp_server.utils.logger import get_logger

logger = get_logger(__name__)


class ConsentScope(str, Enum):
    CLINICAL_DATA = "clinical_data"
    DIAGNOSTIC_IMAGING = "diagnostic_imaging"
    MEDICATION_HISTORY = "medication_history"
    ALL_DATA = "all_data"


@dataclass
class ConsentRecord:
    patient_id: str
    scope: ConsentScope
    granted: bool
    granted_at: datetime
    expires_at: Optional[datetime] = None
    care_unit_restriction: Optional[str] = None  # If set, restriction is unit-specific

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def is_active(self) -> bool:
        return not self.is_expired()


class ConsentManager:
    """
    In-memory patient consent management.

    Opt-OUT model: by default all access is allowed. Only an active denial
    record (granted=False) blocks access.
    """

    def __init__(self):
        # Keyed by (patient_id, scope, care_unit_restriction)
        self._records: Dict[Tuple, ConsentRecord] = {}

    def grant_consent(
        self,
        patient_id: str,
        scope: ConsentScope,
        care_unit: Optional[str] = None,
        duration_days: int = 365,
    ) -> ConsentRecord:
        """Grant consent for a patient/scope/care_unit combination."""
        now = datetime.now(timezone.utc)
        record = ConsentRecord(
            patient_id=patient_id,
            scope=scope,
            granted=True,
            granted_at=now,
            expires_at=now + timedelta(days=duration_days),
            care_unit_restriction=care_unit,
        )
        self._records[(patient_id, scope, care_unit)] = record
        logger.info(f"Consent granted: patient={patient_id} scope={scope} unit={care_unit}")
        return record

    def revoke_consent(
        self,
        patient_id: str,
        scope: ConsentScope,
        care_unit: Optional[str] = None,
    ) -> bool:
        """
        Revoke consent (create or update a denial record).

        Returns True if an existing grant was revoked, False if a new denial was created.
        """
        key = (patient_id, scope, care_unit)
        existing = self._records.get(key)
        now = datetime.now(timezone.utc)

        if existing and existing.granted:
            existing.granted = False
            existing.expires_at = None  # Denial doesn't expire
            logger.info(f"Consent revoked: patient={patient_id} scope={scope} unit={care_unit}")
            return True

        # Create denial record
        self._records[key] = ConsentRecord(
            patient_id=patient_id,
            scope=scope,
            granted=False,
            granted_at=now,
            expires_at=None,
            care_unit_restriction=care_unit,
        )
        logger.info(f"Consent denial created: patient={patient_id} scope={scope} unit={care_unit}")
        return False

    def check_consent(
        self,
        patient_id: str,
        scope: ConsentScope,
        care_unit: Optional[str] = None,
    ) -> bool:
        """
        Check if data access is allowed for a patient/scope.

        Opt-OUT: returns True unless an active denial record exists for:
        - The specific scope + care_unit combination
        - The ALL_DATA scope (which overrides all)
        """
        # Check ALL_DATA denial first (global block)
        all_data_key = (patient_id, ConsentScope.ALL_DATA, care_unit)
        all_data_record = self._records.get(all_data_key)
        if all_data_record and not all_data_record.granted and all_data_record.is_active():
            return False

        # Also check ALL_DATA without unit restriction
        global_all_data = self._records.get((patient_id, ConsentScope.ALL_DATA, None))
        if global_all_data and not global_all_data.granted and global_all_data.is_active():
            return False

        # Check specific scope
        key = (patient_id, scope, care_unit)
        record = self._records.get(key)
        if record and not record.granted and record.is_active():
            return False

        # Check without care unit restriction
        if care_unit is not None:
            key_no_unit = (patient_id, scope, None)
            record_no_unit = self._records.get(key_no_unit)
            if record_no_unit and not record_no_unit.granted and record_no_unit.is_active():
                return False

        return True  # Default: access allowed

    def get_patient_consents(self, patient_id: str) -> List[ConsentRecord]:
        """Return all consent records for a patient."""
        return [r for (pid, _, _), r in self._records.items() if pid == patient_id]

    def log_consent_check(
        self,
        patient_id: str,
        scope: ConsentScope,
        clinician_id: str,
        allowed: bool,
    ) -> None:
        """Log a consent check decision."""
        logger.info(
            f"Consent check: patient={patient_id} scope={scope} "
            f"clinician={clinician_id} allowed={allowed}"
        )


# Global singleton
consent_manager = ConsentManager()
