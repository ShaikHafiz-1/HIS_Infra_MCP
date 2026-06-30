"""
FHIR R4 Connector — lightweight real-time query layer.

Exposes both synchronous (Streamlit/intent-router safe) and async
(FastAPI-compatible) interfaces over the same httpx transport.

Configuration (environment variables — never hardcode secrets):
    FHIR_BASE_URL           Base URL of FHIR server (empty = disabled)
    FHIR_AUTH_TYPE          none | bearer | basic | oauth2
    FHIR_TOKEN              Bearer token (for bearer / oauth2 modes)
    FHIR_USERNAME           Username (for basic mode)
    FHIR_PASSWORD           Password (for basic mode)
    FHIR_TIMEOUT_SECONDS    Per-request timeout (default 10)
    FHIR_USE_SANDBOX_MODE   true → no auth, use public sandbox URL
    FHIR_OAUTH_TOKEN_URL    Token endpoint for oauth2 mode
    FHIR_CLIENT_ID          OAuth2 client_id
    FHIR_CLIENT_SECRET      OAuth2 client_secret

Default sandbox: https://hapi.fhir.org/baseR4  (public, no auth)
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Read config from env at module load time
# ---------------------------------------------------------------------------

_SANDBOX_URL = "https://hapi.fhir.org/baseR4"

FHIR_BASE_URL         = os.getenv("FHIR_BASE_URL", "").rstrip("/")
FHIR_AUTH_TYPE        = os.getenv("FHIR_AUTH_TYPE", "none").lower()
FHIR_TOKEN            = os.getenv("FHIR_TOKEN", "")
FHIR_USERNAME         = os.getenv("FHIR_USERNAME", "")
FHIR_PASSWORD         = os.getenv("FHIR_PASSWORD", "")
FHIR_TIMEOUT_SECONDS  = int(os.getenv("FHIR_TIMEOUT_SECONDS", "10"))
FHIR_USE_SANDBOX_MODE = os.getenv("FHIR_USE_SANDBOX_MODE", "false").lower() == "true"
FHIR_OAUTH_TOKEN_URL  = os.getenv("FHIR_OAUTH_TOKEN_URL", "")
FHIR_CLIENT_ID        = os.getenv("FHIR_CLIENT_ID", "")
FHIR_CLIENT_SECRET    = os.getenv("FHIR_CLIENT_SECRET", "")

# If sandbox mode is enabled and no explicit URL given, use HAPI public server
if FHIR_USE_SANDBOX_MODE and not FHIR_BASE_URL:
    FHIR_BASE_URL = _SANDBOX_URL


class FHIRConnectorError(Exception):
    """Raised when a FHIR query fails after all retries."""


class FHIRConnector:
    """
    Lightweight FHIR R4 read-only client.

    Uses httpx for both sync and async calls.  httpx is a drop-in that
    supports both transports, letting the same class work in Streamlit
    (synchronous) and FastAPI (async) contexts without code duplication.
    """

    def __init__(
        self,
        base_url:       str  = FHIR_BASE_URL,
        auth_type:      str  = FHIR_AUTH_TYPE,
        token:          str  = FHIR_TOKEN,
        username:       str  = FHIR_USERNAME,
        password:       str  = FHIR_PASSWORD,
        timeout:        int  = FHIR_TIMEOUT_SECONDS,
        sandbox_mode:   bool = FHIR_USE_SANDBOX_MODE,
        oauth_token_url:str  = FHIR_OAUTH_TOKEN_URL,
        client_id:      str  = FHIR_CLIENT_ID,
        client_secret:  str  = FHIR_CLIENT_SECRET,
    ) -> None:
        self.base_url      = base_url.rstrip("/")
        self.auth_type     = auth_type if not sandbox_mode else "none"
        self.token         = token
        self.username      = username
        self.password      = password
        self.timeout       = timeout
        self.sandbox_mode  = sandbox_mode
        self._oauth_url    = oauth_token_url
        self._client_id    = client_id
        self._client_secret = client_secret
        self._token_expiry: float = 0.0
        self._lock         = threading.Lock()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def is_enabled(self) -> bool:
        """True when a FHIR base URL is configured."""
        return bool(self.base_url)

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _build_headers(self) -> Dict[str, str]:
        headers = {
            "Accept":       "application/fhir+json",
            "Content-Type": "application/fhir+json",
        }
        if self.auth_type == "bearer" or self.auth_type == "oauth2":
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
        elif self.auth_type == "basic":
            import base64
            creds = base64.b64encode(
                f"{self.username}:{self.password}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {creds}"
        return headers

    def _maybe_refresh_oauth2_token(self) -> None:
        """Fetch/refresh an OAuth2 client-credentials token (synchronous)."""
        if self.auth_type != "oauth2":
            return
        if time.time() < self._token_expiry - 30:
            return  # still valid
        if not (self._oauth_url and self._client_id and self._client_secret):
            logger.warning("[FHIR] oauth2 mode configured but token endpoint / credentials missing")
            return
        try:
            import httpx
            resp = httpx.post(
                self._oauth_url,
                data={
                    "grant_type":    "client_credentials",
                    "client_id":     self._client_id,
                    "client_secret": self._client_secret,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            payload = resp.json()
            self.token         = payload["access_token"]
            self._token_expiry = time.time() + int(payload.get("expires_in", 3600))
            logger.info("[FHIR] OAuth2 token refreshed successfully")
        except Exception as exc:
            logger.warning("[FHIR] OAuth2 token refresh failed: %s", type(exc).__name__)

    # ------------------------------------------------------------------
    # Synchronous interface (Streamlit / intent-router safe)
    # ------------------------------------------------------------------

    def get_resource(
        self, resource_type: str, resource_id: str
    ) -> Optional[Dict[str, Any]]:
        """GET /ResourceType/{id} — returns resource dict or None."""
        if not self.is_enabled():
            return None
        url = f"{self.base_url}/{resource_type}/{resource_id}"
        return self._sync_get(url)

    def search_resource(
        self, resource_type: str, params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """GET /ResourceType?params — returns list of matching resource dicts."""
        if not self.is_enabled():
            return []
        url = f"{self.base_url}/{resource_type}"
        bundle = self._sync_get(url, params=params)
        return _extract_entries(bundle)

    # ------------------------------------------------------------------
    # Async interface (FastAPI / asyncio context)
    # ------------------------------------------------------------------

    async def async_get_resource(
        self, resource_type: str, resource_id: str
    ) -> Optional[Dict[str, Any]]:
        """Async GET /ResourceType/{id}."""
        if not self.is_enabled():
            return None
        url = f"{self.base_url}/{resource_type}/{resource_id}"
        return await self._async_get(url)

    async def async_search_resource(
        self, resource_type: str, params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Async GET /ResourceType?params — returns list of resource dicts."""
        if not self.is_enabled():
            return []
        url = f"{self.base_url}/{resource_type}"
        bundle = await self._async_get(url, params=params)
        return _extract_entries(bundle)

    # ------------------------------------------------------------------
    # Convenience methods (sync)
    # ------------------------------------------------------------------

    def get_patient(self, patient_id: str) -> Optional[Dict[str, Any]]:
        return self.get_resource("Patient", patient_id)

    def search_patients(self, name: str) -> List[Dict[str, Any]]:
        return self.search_resource("Patient", {"name": name, "_count": "20"})

    def get_vitals(self, patient_id: str, limit: int = 30) -> List[Dict[str, Any]]:
        return self.search_resource("Observation", {
            "patient":  patient_id,
            "category": "vital-signs",
            "_sort":    "-date",
            "_count":   str(limit),
        })

    def get_conditions(self, patient_id: str) -> List[Dict[str, Any]]:
        return self.search_resource("Condition", {
            "patient": patient_id,
            "_count":  "50",
        })

    def get_medications(self, patient_id: str) -> List[Dict[str, Any]]:
        return self.search_resource("MedicationRequest", {
            "patient": patient_id,
            "_count":  "50",
        })

    def get_encounters(
        self, patient_id: Optional[str] = None,
        encounter_class: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"_count": "50"}
        if patient_id:
            params["patient"] = patient_id
        if encounter_class:
            params["class"] = encounter_class
        return self.search_resource("Encounter", params)

    def get_devices(self, patient_id: str) -> List[Dict[str, Any]]:
        return self.search_resource("Device", {
            "patient": patient_id,
            "_count":  "20",
        })

    def get_allergies(self, patient_id: str) -> List[Dict[str, Any]]:
        return self.search_resource("AllergyIntolerance", {
            "patient": patient_id,
            "_count":  "20",
        })

    def get_procedures(self, patient_id: str) -> List[Dict[str, Any]]:
        return self.search_resource("Procedure", {
            "patient": patient_id,
            "_sort":   "-date",
            "_count":  "20",
        })

    def get_observations_by_loinc(
        self, patient_id: str, loinc_code: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        return self.search_resource("Observation", {
            "patient": patient_id,
            "code":    f"http://loinc.org|{loinc_code}",
            "_sort":   "-date",
            "_count":  str(limit),
        })

    def search_conditions_by_code(self, code: str, system: str = "") -> List[Dict[str, Any]]:
        param = f"{system}|{code}" if system else code
        return self.search_resource("Condition", {
            "code":   param,
            "_count": "50",
        })

    # ------------------------------------------------------------------
    # Internal sync transport
    # ------------------------------------------------------------------

    def _sync_get(
        self,
        url:    str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            import httpx
        except ImportError:
            logger.error("[FHIR] httpx not installed — run: pip install httpx")
            return None

        with self._lock:
            self._maybe_refresh_oauth2_token()

        try:
            resp = httpx.get(
                url,
                params=params,
                headers=self._build_headers(),
                timeout=self.timeout,
                follow_redirects=True,
            )
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 404:
                logger.debug("[FHIR] 404 Not Found: %s", url)
                return None
            if resp.status_code in (401, 403):
                logger.warning("[FHIR] Auth error %s on %s", resp.status_code, url)
                return None
            logger.warning("[FHIR] Unexpected status %s for %s", resp.status_code, url)
            return None
        except Exception as exc:
            logger.warning("[FHIR] Request failed (%s): %s — falling back to simulator",
                           type(exc).__name__, url)
            return None

    # ------------------------------------------------------------------
    # Internal async transport
    # ------------------------------------------------------------------

    async def _async_get(
        self,
        url:    str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            import httpx
        except ImportError:
            logger.error("[FHIR] httpx not installed — run: pip install httpx")
            return None

        if self.auth_type == "oauth2":
            await self._async_maybe_refresh_oauth2()

        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                resp = await client.get(
                    url,
                    params=params,
                    headers=self._build_headers(),
                    timeout=self.timeout,
                )
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 404:
                return None
            if resp.status_code in (401, 403):
                logger.warning("[FHIR] Auth error %s on %s", resp.status_code, url)
                return None
            logger.warning("[FHIR] Unexpected status %s for %s", resp.status_code, url)
            return None
        except Exception as exc:
            logger.warning("[FHIR] Async request failed (%s): %s", type(exc).__name__, url)
            return None

    async def _async_maybe_refresh_oauth2(self) -> None:
        if time.time() < self._token_expiry - 30:
            return
        if not (self._oauth_url and self._client_id and self._client_secret):
            return
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    self._oauth_url,
                    data={
                        "grant_type":    "client_credentials",
                        "client_id":     self._client_id,
                        "client_secret": self._client_secret,
                    },
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                payload = resp.json()
                self.token         = payload["access_token"]
                self._token_expiry = time.time() + int(payload.get("expires_in", 3600))
                logger.info("[FHIR] OAuth2 token refreshed (async)")
        except Exception as exc:
            logger.warning("[FHIR] Async OAuth2 refresh failed: %s", type(exc).__name__)


# ---------------------------------------------------------------------------
# Bundle entry extractor
# ---------------------------------------------------------------------------

def _extract_entries(bundle: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Pull resource entries from a FHIR Bundle response."""
    if not bundle:
        return []
    if bundle.get("resourceType") != "Bundle":
        # Single resource returned (e.g. Patient read)
        return [bundle]
    return [
        entry["resource"]
        for entry in bundle.get("entry", [])
        if "resource" in entry
    ]


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_connector_instance: Optional[FHIRConnector] = None
_connector_lock = threading.Lock()


def get_fhir_connector() -> FHIRConnector:
    """Return the singleton FHIRConnector (thread-safe, lazy init)."""
    global _connector_instance
    if _connector_instance is None:
        with _connector_lock:
            if _connector_instance is None:
                _connector_instance = FHIRConnector()
                if _connector_instance.is_enabled():
                    logger.info(
                        "[FHIR] Connector initialised — base_url=%s auth=%s sandbox=%s",
                        _connector_instance.base_url,
                        _connector_instance.auth_type,
                        _connector_instance.sandbox_mode,
                    )
                else:
                    logger.info("[FHIR] FHIR_BASE_URL not set — connector disabled, using simulator")
    return _connector_instance
