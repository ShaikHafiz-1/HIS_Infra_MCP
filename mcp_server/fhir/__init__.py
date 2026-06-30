"""FHIR R4 connector layer — real-time query interface for MCP tools."""

from mcp_server.fhir.connector import FHIRConnector, get_fhir_connector, FHIRConnectorError
from mcp_server.fhir.normalizer import FHIRPatient, normalizer

__all__ = ["FHIRConnector", "get_fhir_connector", "FHIRConnectorError", "FHIRPatient", "normalizer"]
