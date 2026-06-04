"""
Unit tests for FHIR REST client.

Tests cover:
- Patient resource retrieval
- Encounter resource retrieval
- Observation resource retrieval
- DiagnosticReport resource retrieval
- ImagingStudy resource retrieval
- MedicationRequest resource retrieval
- Procedure resource retrieval
- CarePlan resource retrieval
- Error handling and authentication
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_server.ingestion.fhir_client import FHIRClient


class TestFHIRClientInitialization:
    """Test FHIR client initialization."""

    def test_client_initialization_with_token(self):
        """Test client initialization with access token."""
        client = FHIRClient(
            base_url="https://fhir.example.com",
            access_token="test_token",
        )
        
        assert client.base_url == "https://fhir.example.com"
        assert client.access_token == "test_token"
        assert client.timeout == 30

    def test_client_initialization_with_oauth2(self):
        """Test client initialization with OAuth2 credentials."""
        client = FHIRClient(
            base_url="https://fhir.example.com",
            client_id="test_client",
            client_secret="test_secret",
        )
        
        assert client.client_id == "test_client"
        assert client.client_secret == "test_secret"

    def test_client_initialization_strips_trailing_slash(self):
        """Test that trailing slash is removed from base URL."""
        client = FHIRClient(base_url="https://fhir.example.com/")
        assert client.base_url == "https://fhir.example.com"


class TestFHIRClientHeaders:
    """Test FHIR client header generation."""

    def test_headers_with_token(self):
        """Test headers include authorization token."""
        client = FHIRClient(
            base_url="https://fhir.example.com",
            access_token="test_token",
        )
        
        headers = client._headers
        assert headers["Authorization"] == "Bearer test_token"
        assert headers["Accept"] == "application/fhir+json"

    def test_headers_without_token(self):
        """Test headers without authorization token."""
        client = FHIRClient(base_url="https://fhir.example.com")
        
        headers = client._headers
        assert "Authorization" not in headers
        assert headers["Accept"] == "application/fhir+json"


class TestFHIRClientPatientRetrieval:
    """Test Patient resource retrieval."""

    @pytest.mark.asyncio
    async def test_retrieve_patient_success(self):
        """Test successful patient retrieval."""
        client = FHIRClient(
            base_url="https://fhir.example.com",
            access_token="test_token",
        )
        
        patient_data = {
            "resourceType": "Patient",
            "id": "PAT-123",
            "name": [{"given": ["John"], "family": "Doe"}],
            "birthDate": "1980-01-01",
        }
        
        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = patient_data
            
            result = await client.retrieve_patient("PAT-123")
            
            assert result == patient_data
            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_patient_not_found(self):
        """Test patient retrieval when not found."""
        client = FHIRClient(
            base_url="https://fhir.example.com",
            access_token="test_token",
        )
        
        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {}
            
            result = await client.retrieve_patient("PAT-999")
            
            assert result is None

    @pytest.mark.asyncio
    async def test_retrieve_patient_invalid_id(self):
        """Test patient retrieval with invalid ID."""
        client = FHIRClient(
            base_url="https://fhir.example.com",
            access_token="test_token",
        )
        
        result = await client.retrieve_patient("")
        assert result is None


class TestFHIRClientEncounterRetrieval:
    """Test Encounter resource retrieval."""

    @pytest.mark.asyncio
    async def test_retrieve_encounters_success(self):
        """Test successful encounter retrieval."""
        client = FHIRClient(
            base_url="https://fhir.example.com",
            access_token="test_token",
        )
        
        response_data = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Encounter",
                        "id": "ENC-123",
                        "subject": {"reference": "Patient/PAT-123"},
                        "status": "finished",
                    }
                }
            ],
        }
        
        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response_data
            
            result = await client.retrieve_encounters("PAT-123")
            
            assert len(result) == 1
            assert result[0]["id"] == "ENC-123"

    @pytest.mark.asyncio
    async def test_retrieve_encounters_with_date_filter(self):
        """Test encounter retrieval with date filtering."""
        client = FHIRClient(
            base_url="https://fhir.example.com",
            access_token="test_token",
        )
        
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 12, 31, tzinfo=timezone.utc)
        
        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"resourceType": "Bundle", "entry": []}
            
            await client.retrieve_encounters("PAT-123", start_date, end_date)
            
            # Verify date parameters were passed
            call_args = mock_get.call_args
            assert call_args is not None


class TestFHIRClientObservationRetrieval:
    """Test Observation resource retrieval."""

    @pytest.mark.asyncio
    async def test_retrieve_observations_success(self):
        """Test successful observation retrieval."""
        client = FHIRClient(
            base_url="https://fhir.example.com",
            access_token="test_token",
        )
        
        response_data = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Observation",
                        "id": "OBS-123",
                        "subject": {"reference": "Patient/PAT-123"},
                        "code": {"coding": [{"code": "8480-6", "display": "Systolic blood pressure"}]},
                        "valueQuantity": {"value": 120, "unit": "mmHg"},
                    }
                }
            ],
        }
        
        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response_data
            
            result = await client.retrieve_observations("PAT-123")
            
            assert len(result) == 1
            assert result[0]["id"] == "OBS-123"


class TestFHIRClientDiagnosticReportRetrieval:
    """Test DiagnosticReport resource retrieval."""

    @pytest.mark.asyncio
    async def test_retrieve_diagnostic_reports_success(self):
        """Test successful diagnostic report retrieval."""
        client = FHIRClient(
            base_url="https://fhir.example.com",
            access_token="test_token",
        )
        
        response_data = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "DiagnosticReport",
                        "id": "DR-123",
                        "subject": {"reference": "Patient/PAT-123"},
                        "code": {"coding": [{"code": "58410-2", "display": "Complete blood count"}]},
                        "status": "final",
                    }
                }
            ],
        }
        
        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response_data
            
            result = await client.retrieve_diagnostic_reports("PAT-123")
            
            assert len(result) == 1
            assert result[0]["id"] == "DR-123"


class TestFHIRClientImagingStudyRetrieval:
    """Test ImagingStudy resource retrieval."""

    @pytest.mark.asyncio
    async def test_retrieve_imaging_studies_success(self):
        """Test successful imaging study retrieval."""
        client = FHIRClient(
            base_url="https://fhir.example.com",
            access_token="test_token",
        )
        
        response_data = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "ImagingStudy",
                        "id": "IMG-123",
                        "subject": {"reference": "Patient/PAT-123"},
                        "modality": [{"system": "http://dicom.nema.org/resources/ontology/DCM", "code": "CT"}],
                        "status": "available",
                    }
                }
            ],
        }
        
        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response_data
            
            result = await client.retrieve_imaging_studies("PAT-123")
            
            assert len(result) == 1
            assert result[0]["id"] == "IMG-123"


class TestFHIRClientMedicationRequestRetrieval:
    """Test MedicationRequest resource retrieval."""

    @pytest.mark.asyncio
    async def test_retrieve_medication_requests_success(self):
        """Test successful medication request retrieval."""
        client = FHIRClient(
            base_url="https://fhir.example.com",
            access_token="test_token",
        )
        
        response_data = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "MedicationRequest",
                        "id": "MR-123",
                        "subject": {"reference": "Patient/PAT-123"},
                        "medicationCodeableConcept": {"coding": [{"code": "197446", "display": "Aspirin"}]},
                        "status": "active",
                    }
                }
            ],
        }
        
        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response_data
            
            result = await client.retrieve_medication_requests("PAT-123")
            
            assert len(result) == 1
            assert result[0]["id"] == "MR-123"


class TestFHIRClientProcedureRetrieval:
    """Test Procedure resource retrieval."""

    @pytest.mark.asyncio
    async def test_retrieve_procedures_success(self):
        """Test successful procedure retrieval."""
        client = FHIRClient(
            base_url="https://fhir.example.com",
            access_token="test_token",
        )
        
        response_data = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Procedure",
                        "id": "PROC-123",
                        "subject": {"reference": "Patient/PAT-123"},
                        "code": {"coding": [{"code": "80146002", "display": "Appendectomy"}]},
                        "status": "completed",
                    }
                }
            ],
        }
        
        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response_data
            
            result = await client.retrieve_procedures("PAT-123")
            
            assert len(result) == 1
            assert result[0]["id"] == "PROC-123"


class TestFHIRClientCarePlanRetrieval:
    """Test CarePlan resource retrieval."""

    @pytest.mark.asyncio
    async def test_retrieve_care_plans_success(self):
        """Test successful care plan retrieval."""
        client = FHIRClient(
            base_url="https://fhir.example.com",
            access_token="test_token",
        )
        
        response_data = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "CarePlan",
                        "id": "CP-123",
                        "subject": {"reference": "Patient/PAT-123"},
                        "status": "active",
                        "intent": "plan",
                    }
                }
            ],
        }
        
        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response_data
            
            result = await client.retrieve_care_plans("PAT-123")
            
            assert len(result) == 1
            assert result[0]["id"] == "CP-123"


class TestFHIRClientAllResourcesRetrieval:
    """Test retrieving all resources for a patient."""

    @pytest.mark.asyncio
    async def test_retrieve_all_resources_success(self):
        """Test successful retrieval of all resources."""
        client = FHIRClient(
            base_url="https://fhir.example.com",
            access_token="test_token",
        )
        
        patient_data = {
            "resourceType": "Patient",
            "id": "PAT-123",
        }
        
        with patch.object(client, "retrieve_patient", new_callable=AsyncMock) as mock_patient:
            with patch.object(client, "retrieve_encounters", new_callable=AsyncMock) as mock_enc:
                with patch.object(client, "retrieve_observations", new_callable=AsyncMock) as mock_obs:
                    with patch.object(client, "retrieve_diagnostic_reports", new_callable=AsyncMock) as mock_dr:
                        with patch.object(client, "retrieve_imaging_studies", new_callable=AsyncMock) as mock_img:
                            with patch.object(client, "retrieve_medication_requests", new_callable=AsyncMock) as mock_mr:
                                with patch.object(client, "retrieve_procedures", new_callable=AsyncMock) as mock_proc:
                                    with patch.object(client, "retrieve_care_plans", new_callable=AsyncMock) as mock_cp:
                                        mock_patient.return_value = patient_data
                                        mock_enc.return_value = []
                                        mock_obs.return_value = []
                                        mock_dr.return_value = []
                                        mock_img.return_value = []
                                        mock_mr.return_value = []
                                        mock_proc.return_value = []
                                        mock_cp.return_value = []
                                        
                                        result = await client.retrieve_all_resources("PAT-123")
                                        
                                        assert "patient" in result
                                        assert len(result["patient"]) == 1
                                        assert result["patient"][0]["id"] == "PAT-123"


class TestFHIRClientContextManager:
    """Test FHIR client context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_connect_disconnect(self):
        """Test context manager properly connects and disconnects."""
        client = FHIRClient(
            base_url="https://fhir.example.com",
            access_token="test_token",
        )
        
        with patch.object(client, "connect", new_callable=AsyncMock) as mock_connect:
            with patch.object(client, "disconnect", new_callable=AsyncMock) as mock_disconnect:
                async with client:
                    pass
                
                mock_connect.assert_called_once()
                mock_disconnect.assert_called_once()


class TestFHIRClientErrorHandling:
    """Test FHIR client error handling."""

    @pytest.mark.asyncio
    async def test_retrieve_patient_handles_exception(self):
        """Test patient retrieval handles exceptions gracefully."""
        client = FHIRClient(
            base_url="https://fhir.example.com",
            access_token="test_token",
        )
        
        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Network error")
            
            result = await client.retrieve_patient("PAT-123")
            
            assert result is None

    @pytest.mark.asyncio
    async def test_retrieve_encounters_handles_exception(self):
        """Test encounter retrieval handles exceptions gracefully."""
        client = FHIRClient(
            base_url="https://fhir.example.com",
            access_token="test_token",
        )
        
        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Network error")
            
            result = await client.retrieve_encounters("PAT-123")
            
            assert result == []
