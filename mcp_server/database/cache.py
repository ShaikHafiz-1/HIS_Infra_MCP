"""
Redis Caching Layer for Hospital Clinical Intelligence MCP Platform.

Provides TTL-based caching for frequently accessed clinical data.
Falls back to no-cache mode gracefully when Redis is unavailable.
"""

import json
from typing import Any, Dict, Optional

from mcp_server.utils.logger import get_logger

logger = get_logger(__name__)

# Cache TTL values in seconds
TTL = {
    "patient_context": 300,       # 5 minutes
    "care_unit_summary": 60,      # 1 minute
    "device_events": 120,         # 2 minutes
    "event_timeline": 180,        # 3 minutes
    "alarm_context": 60,          # 1 minute
    "clinical_thresholds": 3600,  # 1 hour
}


class CacheLayer:
    """
    Redis-backed cache with graceful fallback when Redis is unavailable.

    In development without Redis, all operations are no-ops and the cache
    always returns None (miss). Production should configure REDIS_URL.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self._redis_url = redis_url
        self._client = None
        self._available = False
        self._in_memory: Dict[str, Any] = {}  # Fallback for testing
        self._connect()

    def _connect(self) -> None:
        """Attempt to connect to Redis."""
        try:
            import redis as redis_lib
            self._client = redis_lib.from_url(self._redis_url, decode_responses=True,
                                               socket_connect_timeout=2)
            self._client.ping()
            self._available = True
            logger.info(f"Redis cache connected: {self._redis_url}")
        except Exception as e:
            self._available = False
            logger.warning(f"Redis unavailable, using in-memory fallback: {e}")

    # --- Patient context ---

    def get_patient_context(
        self, patient_id: str, include_devices: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Retrieve cached patient context."""
        key = f"patient_context:{patient_id}:devices={include_devices}"
        return self._get(key)

    def set_patient_context(
        self, patient_id: str, context: Dict[str, Any], include_devices: bool = True
    ) -> None:
        """Cache patient context."""
        key = f"patient_context:{patient_id}:devices={include_devices}"
        self._set(key, context, TTL["patient_context"])

    def invalidate_patient_context(self, patient_id: str) -> None:
        """Invalidate patient context cache for all variants."""
        for flag in (True, False):
            self._delete(f"patient_context:{patient_id}:devices={flag}")

    # --- Care unit summary ---

    def get_care_unit_summary(self, care_unit_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached care unit summary."""
        return self._get(f"care_unit_summary:{care_unit_id}")

    def set_care_unit_summary(self, care_unit_id: str, summary: Dict[str, Any]) -> None:
        """Cache care unit summary."""
        self._set(f"care_unit_summary:{care_unit_id}", summary, TTL["care_unit_summary"])

    # --- Device events ---

    def get_device_events(self, patient_id: str, window_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached device events."""
        return self._get(f"device_events:{patient_id}:{window_key}")

    def set_device_events(self, patient_id: str, window_key: str, data: Dict[str, Any]) -> None:
        """Cache device events."""
        self._set(f"device_events:{patient_id}:{window_key}", data, TTL["device_events"])

    # --- Clinical thresholds ---

    def get_clinical_thresholds(self, vital_type: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached clinical thresholds."""
        return self._get(f"thresholds:{vital_type}")

    def set_clinical_thresholds(self, vital_type: str, thresholds: Dict[str, Any]) -> None:
        """Cache clinical thresholds."""
        self._set(f"thresholds:{vital_type}", thresholds, TTL["clinical_thresholds"])

    # --- Internal helpers ---

    def _get(self, key: str) -> Optional[Any]:
        if self._available and self._client:
            try:
                value = self._client.get(key)
                return json.loads(value) if value else None
            except Exception as e:
                logger.warning(f"Cache GET error for {key}: {e}")
        # Fallback
        entry = self._in_memory.get(key)
        return entry.get("value") if entry else None

    def _set(self, key: str, value: Any, ttl: int) -> None:
        if self._available and self._client:
            try:
                self._client.setex(key, ttl, json.dumps(value, default=str))
                return
            except Exception as e:
                logger.warning(f"Cache SET error for {key}: {e}")
        # Fallback (no real TTL enforcement in memory for simplicity)
        self._in_memory[key] = {"value": value}

    def _delete(self, key: str) -> None:
        if self._available and self._client:
            try:
                self._client.delete(key)
                return
            except Exception as e:
                logger.warning(f"Cache DELETE error for {key}: {e}")
        self._in_memory.pop(key, None)

    def flush_all(self) -> None:
        """Clear entire cache (use in testing only)."""
        self._in_memory.clear()
        if self._available and self._client:
            try:
                self._client.flushdb()
            except Exception:
                pass

    @property
    def is_available(self) -> bool:
        """Whether Redis is connected and available."""
        return self._available


# Global cache instance
cache = CacheLayer()
