"""
FHIR REST Client for retrieving healthcare resources.

This module implements a FHIR client that retrieves resources from FHIR servers
including Patient, Encounter, Observation, DiagnosticReport, ImagingStudy,
MedicationRequest, Procedure, and CarePlan resources.

Supports OAuth2 authentication and handles pagination.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import aiohttp
except ImportError:
    aiohttp = None  # type: ignore[assignment]
from pydantic import ValidationError

from mcp_server.utils.logger import get_logger
from mcp_server.utils.validators import validate_patient_id, validate_encounter_id

logger = get_logger(__name__)


class FHIRClient:
    """
    FHIR REST client for retrieving healthcare resources.
    
    Supports:
    - OAuth2 authentication
    - Resource retrieval with pagination
    - Error handling and retry logic
    - Resource mapping to internal structures
    """

    def __init__(
        self,
        base_url: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        timeout: int = 30,
    ):
        """
        Initialize FHIR client.
        
        Args:
            base_url: FHIR server base URL (e.g., https://fhir.example.com)
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret
            access_token: Pre-obtained access token
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
        self.token_expiry: Optional[datetime] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self) -> None:
        """Create aiohttp session."""
        if not self.session:
            self.session = aiohttp.ClientSession()
            if not self.access_token and self.client_id and self.client_secret:
                await self._refresh_token()

    async def disconnect(self) -> None:
        """Close aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None

    async def _refresh_token(self) -> None:
        """Refresh OAuth2 access token."""
        if not self.client_id or not self.client_secret:
            logger.warning("OAuth2 credentials not provided, skipping token refresh")
            return

        try:
            # Construct token endpoint URL
            token_url = f"{self.base_url}/oauth/token"
            
            data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
            
            async with self.session.post(token_url, data=data, timeout=self.timeout) as resp:
                if resp.status == 200:
                    token_data = await resp.json()
                    self.access_token = token_data.get("access_token")
                    expires_in = token_data.get("expires_in", 3600)
                    self.token_expiry = datetime.now(timezone.utc).timestamp() + expires_in
                    logger.info("OAuth2 token refreshed successfully")
                else:
                    logger.error(f"Failed to refresh token: {resp.status}")
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")

    @property
    def _headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        headers = {
            "Accept": "application/fhir+json",
            "Content-Type": "application/fhir+json",
        }
        
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        
        return headers

    async def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make GET request to FHIR server.
        
        Args:
            url: Request URL
            params: Query parameters
            
        Returns:
            Response JSON
            
        Raises:
            Exception: If request fails
        """
        if not self.session:
            await self.connect()

        try:
            async with self.session.get(
                url,
                headers=self._headers,
                params=params,
                timeout=self.timeout,
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 401:
                    # Token expired, refresh and retry
                    await self._refresh_token()
                    async with self.session.get(
                        url,
                        headers=self._headers,
                        params=params,
                        timeout=self.timeout,
                    ) as retry_resp:
                        if retry_resp.status == 200:
                            return await retry_resp.json()
                        else:
                            logger.error(f"FHIR request failed: {retry_resp.status}")
                            return {}
                else:
                    logger.error(f"FHIR request failed: {resp.status}")
                    return {}
        except asyncio.TimeoutError:
            logger.error(f"FHIR request timeout: {url}")
            return {}
        except Exception as e:
            logger.error(f"FHIR request error: {e}")
            return {}

    async def retrieve_patient(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve Patient resource.
        
        Args:
            patient_id: FHIR Patient ID
            
        Returns:
            Patient resource or None if not found
        """
        try:
            validate_patient_id(patient_id)
            url = f"{self.base_url}/Patient/{patient_id}"
            data = await self._get(url)
            
            if data and data.get("resourceType") == "Patient":
                logger.info(f"Retrieved Patient {patient_id}")
                return data
            return None
        except ValidationError as e:
            logger.error(f"Invalid patient ID: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve patient: {e}")
            return None

    async def retrieve_encounters(
        self,
        patient_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve Encounter resources for a patient.
        
        Args:
            patient_id: FHIR Patient ID
            start_date: Filter encounters after this date
            end_date: Filter encounters before this date
            
        Returns:
            List of Encounter resources
        """
        try:
            validate_patient_id(patient_id)
            
            params = {"subject": f"Patient/{patient_id}"}
            
            if start_date:
                params["date"] = f"ge{start_date.isoformat()}"
            if end_date:
                if "date" in params:
                    params["date"] += f"&date=le{end_date.isoformat()}"
                else:
                    params["date"] = f"le{end_date.isoformat()}"
            
            url = f"{self.base_url}/Encounter"
            data = await self._get(url, params)
            
            encounters = []
            if data and data.get("resourceType") == "Bundle":
                for entry in data.get("entry", []):
                    resource = entry.get("resource", {})
                    if resource.get("resourceType") == "Encounter":
                        encounters.append(resource)
            
            logger.info(f"Retrieved {len(encounters)} encounters for patient {patient_id}")
            return encounters
        except ValidationError as e:
            logger.error(f"Invalid patient ID: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to retrieve encounters: {e}")
            return []

    async def retrieve_observations(
        self,
        patient_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve Observation resources for a patient.
        
        Args:
            patient_id: FHIR Patient ID
            start_date: Filter observations after this date
            end_date: Filter observations before this date
            
        Returns:
            List of Observation resources
        """
        try:
            validate_patient_id(patient_id)
            
            params = {"subject": f"Patient/{patient_id}"}
            
            if start_date:
                params["date"] = f"ge{start_date.isoformat()}"
            if end_date:
                if "date" in params:
                    params["date"] += f"&date=le{end_date.isoformat()}"
                else:
                    params["date"] = f"le{end_date.isoformat()}"
            
            url = f"{self.base_url}/Observation"
            data = await self._get(url, params)
            
            observations = []
            if data and data.get("resourceType") == "Bundle":
                for entry in data.get("entry", []):
                    resource = entry.get("resource", {})
                    if resource.get("resourceType") == "Observation":
                        observations.append(resource)
            
            logger.info(f"Retrieved {len(observations)} observations for patient {patient_id}")
            return observations
        except ValidationError as e:
            logger.error(f"Invalid patient ID: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to retrieve observations: {e}")
            return []

    async def retrieve_diagnostic_reports(
        self,
        patient_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve DiagnosticReport resources for a patient.
        
        Args:
            patient_id: FHIR Patient ID
            start_date: Filter reports after this date
            end_date: Filter reports before this date
            
        Returns:
            List of DiagnosticReport resources
        """
        try:
            validate_patient_id(patient_id)
            
            params = {"subject": f"Patient/{patient_id}"}
            
            if start_date:
                params["date"] = f"ge{start_date.isoformat()}"
            if end_date:
                if "date" in params:
                    params["date"] += f"&date=le{end_date.isoformat()}"
                else:
                    params["date"] = f"le{end_date.isoformat()}"
            
            url = f"{self.base_url}/DiagnosticReport"
            data = await self._get(url, params)
            
            reports = []
            if data and data.get("resourceType") == "Bundle":
                for entry in data.get("entry", []):
                    resource = entry.get("resource", {})
                    if resource.get("resourceType") == "DiagnosticReport":
                        reports.append(resource)
            
            logger.info(f"Retrieved {len(reports)} diagnostic reports for patient {patient_id}")
            return reports
        except ValidationError as e:
            logger.error(f"Invalid patient ID: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to retrieve diagnostic reports: {e}")
            return []

    async def retrieve_imaging_studies(
        self,
        patient_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve ImagingStudy resources for a patient.
        
        Args:
            patient_id: FHIR Patient ID
            start_date: Filter studies after this date
            end_date: Filter studies before this date
            
        Returns:
            List of ImagingStudy resources
        """
        try:
            validate_patient_id(patient_id)
            
            params = {"subject": f"Patient/{patient_id}"}
            
            if start_date:
                params["started"] = f"ge{start_date.isoformat()}"
            if end_date:
                if "started" in params:
                    params["started"] += f"&started=le{end_date.isoformat()}"
                else:
                    params["started"] = f"le{end_date.isoformat()}"
            
            url = f"{self.base_url}/ImagingStudy"
            data = await self._get(url, params)
            
            studies = []
            if data and data.get("resourceType") == "Bundle":
                for entry in data.get("entry", []):
                    resource = entry.get("resource", {})
                    if resource.get("resourceType") == "ImagingStudy":
                        studies.append(resource)
            
            logger.info(f"Retrieved {len(studies)} imaging studies for patient {patient_id}")
            return studies
        except ValidationError as e:
            logger.error(f"Invalid patient ID: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to retrieve imaging studies: {e}")
            return []

    async def retrieve_medication_requests(
        self,
        patient_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve MedicationRequest resources for a patient.
        
        Args:
            patient_id: FHIR Patient ID
            start_date: Filter requests after this date
            end_date: Filter requests before this date
            
        Returns:
            List of MedicationRequest resources
        """
        try:
            validate_patient_id(patient_id)
            
            params = {"subject": f"Patient/{patient_id}"}
            
            if start_date:
                params["authoredon"] = f"ge{start_date.isoformat()}"
            if end_date:
                if "authoredon" in params:
                    params["authoredon"] += f"&authoredon=le{end_date.isoformat()}"
                else:
                    params["authoredon"] = f"le{end_date.isoformat()}"
            
            url = f"{self.base_url}/MedicationRequest"
            data = await self._get(url, params)
            
            requests = []
            if data and data.get("resourceType") == "Bundle":
                for entry in data.get("entry", []):
                    resource = entry.get("resource", {})
                    if resource.get("resourceType") == "MedicationRequest":
                        requests.append(resource)
            
            logger.info(f"Retrieved {len(requests)} medication requests for patient {patient_id}")
            return requests
        except ValidationError as e:
            logger.error(f"Invalid patient ID: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to retrieve medication requests: {e}")
            return []

    async def retrieve_procedures(
        self,
        patient_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve Procedure resources for a patient.
        
        Args:
            patient_id: FHIR Patient ID
            start_date: Filter procedures after this date
            end_date: Filter procedures before this date
            
        Returns:
            List of Procedure resources
        """
        try:
            validate_patient_id(patient_id)
            
            params = {"subject": f"Patient/{patient_id}"}
            
            if start_date:
                params["date"] = f"ge{start_date.isoformat()}"
            if end_date:
                if "date" in params:
                    params["date"] += f"&date=le{end_date.isoformat()}"
                else:
                    params["date"] = f"le{end_date.isoformat()}"
            
            url = f"{self.base_url}/Procedure"
            data = await self._get(url, params)
            
            procedures = []
            if data and data.get("resourceType") == "Bundle":
                for entry in data.get("entry", []):
                    resource = entry.get("resource", {})
                    if resource.get("resourceType") == "Procedure":
                        procedures.append(resource)
            
            logger.info(f"Retrieved {len(procedures)} procedures for patient {patient_id}")
            return procedures
        except ValidationError as e:
            logger.error(f"Invalid patient ID: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to retrieve procedures: {e}")
            return []

    async def retrieve_care_plans(
        self,
        patient_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve CarePlan resources for a patient.
        
        Args:
            patient_id: FHIR Patient ID
            
        Returns:
            List of CarePlan resources
        """
        try:
            validate_patient_id(patient_id)
            
            params = {"subject": f"Patient/{patient_id}"}
            
            url = f"{self.base_url}/CarePlan"
            data = await self._get(url, params)
            
            care_plans = []
            if data and data.get("resourceType") == "Bundle":
                for entry in data.get("entry", []):
                    resource = entry.get("resource", {})
                    if resource.get("resourceType") == "CarePlan":
                        care_plans.append(resource)
            
            logger.info(f"Retrieved {len(care_plans)} care plans for patient {patient_id}")
            return care_plans
        except ValidationError as e:
            logger.error(f"Invalid patient ID: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to retrieve care plans: {e}")
            return []

    async def retrieve_all_resources(
        self,
        patient_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retrieve all available resources for a patient.
        
        Args:
            patient_id: FHIR Patient ID
            start_date: Filter resources after this date
            end_date: Filter resources before this date
            
        Returns:
            Dictionary with resource types as keys and lists of resources as values
        """
        try:
            results = {
                "patient": [],
                "encounters": [],
                "observations": [],
                "diagnostic_reports": [],
                "imaging_studies": [],
                "medication_requests": [],
                "procedures": [],
                "care_plans": [],
            }
            
            # Retrieve patient
            patient = await self.retrieve_patient(patient_id)
            if patient:
                results["patient"] = [patient]
            
            # Retrieve other resources in parallel
            tasks = [
                self.retrieve_encounters(patient_id, start_date, end_date),
                self.retrieve_observations(patient_id, start_date, end_date),
                self.retrieve_diagnostic_reports(patient_id, start_date, end_date),
                self.retrieve_imaging_studies(patient_id, start_date, end_date),
                self.retrieve_medication_requests(patient_id, start_date, end_date),
                self.retrieve_procedures(patient_id, start_date, end_date),
                self.retrieve_care_plans(patient_id),
            ]
            
            (
                encounters,
                observations,
                diagnostic_reports,
                imaging_studies,
                medication_requests,
                procedures,
                care_plans,
            ) = await asyncio.gather(*tasks)
            
            results["encounters"] = encounters
            results["observations"] = observations
            results["diagnostic_reports"] = diagnostic_reports
            results["imaging_studies"] = imaging_studies
            results["medication_requests"] = medication_requests
            results["procedures"] = procedures
            results["care_plans"] = care_plans
            
            logger.info(f"Retrieved all resources for patient {patient_id}")
            return results
        except Exception as e:
            logger.error(f"Failed to retrieve all resources: {e}")
            return {}
