# Hospital Clinical Intelligence MCP Platform - Technical Design

## Overview

The Hospital Clinical Intelligence MCP Platform is a comprehensive clinical data integration and retrieval system built on the Model Context Protocol (MCP). It ingests healthcare data from multiple sources (HL7 v2, FHIR, DICOM, device telemetry), normalizes and contextualizes it, and provides secure, role-based access through standardized MCP tools.

### Key Design Principles

1. **Modularity**: Separate concerns across ingestion, normalization, context building, and retrieval layers
2. **Scalability**: Horizontal scaling through stateless services and distributed processing
3. **Security**: Defense-in-depth with authentication, authorization, encryption, and audit logging
4. **Reliability**: Graceful degradation, error handling, and data consistency mechanisms
5. **Performance**: Caching, indexing, and optimized query patterns for sub-second response times

## System Architecture

### High-Level System Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Hospital Systems                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │
│  │ EHR/ADT      │  │ Lab System   │  │ Imaging      │  │ Devices  │ │
│  │ (HL7 v2)     │  │ (HL7 v2)     │  │ (DICOM)      │  │ (Telemetry)
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
            ┌───────▼────────┐  ┌──────▼──────────┐
            │ FHIR Server    │  │ Message Queue   │
            │ (REST API)     │  │ (RabbitMQ)      │
            └────────────────┘  └─────────────────┘
                    │                   │
                    └─────────┬─────────┘
                              │
        ┌─────────────────────▼──────────────────────┐
        │   MCP Server (FastAPI + Python MCP SDK)    │
        │                                             │
        │  ┌──────────────────────────────────────┐  │
        │  │ Ingestion Layer                      │  │
        │  │ - HL7 Parser, FHIR Client, DICOM    │  │
        │  │ - Device Telemetry Listener         │  │
        │  └──────────────────────────────────────┘  │
        │                                             │
        │  ┌──────────────────────────────────────┐  │
        │  │ Normalization & Mapping Layer        │  │
        │  │ - ID Mapping, Data Consolidation    │  │
        │  │ - Care Unit Assignment              │  │
        │  └──────────────────────────────────────┘  │
        │                                             │
        │  ┌──────────────────────────────────────┐  │
        │  │ Clinical Context Engine              │  │
        │  │ - Event Classification, Timeline    │  │
        │  │ - Annotation, Confidence Scoring    │  │
        │  └──────────────────────────────────────┘  │
        │                                             │
        │  ┌──────────────────────────────────────┐  │
        │  │ MCP Tool Layer (10 Tools)            │  │
        │  │ - Patient Context, Care Unit Summary│  │
        │  │ - Device Events, Diagnostic Exams   │  │
        │  │ - Specialty-Specific Tools          │  │
        │  └──────────────────────────────────────┘  │
        │                                             │
        │  ┌──────────────────────────────────────┐  │
        │  │ Security & Authorization             │  │
        │  │ - RBAC, Audit Logging, PHI Masking  │  │
        │  └──────────────────────────────────────┘  │
        └─────────────────────┬──────────────────────┘
                              │
        ┌─────────────────────▼──────────────────────┐
        │ Storage Layer                               │
        │ ┌──────────────────────────────────────┐   │
        │ │ PostgreSQL Database                  │   │
        │ │ - Normalized Clinical Data           │   │
        │ │ - Audit Logs, Mappings               │   │
        │ └──────────────────────────────────────┘   │
        │ ┌──────────────────────────────────────┐   │
        │ │ Redis Cache                          │   │
        │ │ - Frequently Accessed Data           │   │
        │ │ - Session Management                 │   │
        │ └──────────────────────────────────────┘   │
        └─────────────────────────────────────────────┘
                              │
        ┌─────────────────────▼──────────────────────┐
        │ MCP Clients (Python)                        │
        │ - Clinician Workstations                    │
        │ - Clinical Decision Support Systems         │
        │ - AI/ML Integration Points                  │
        └─────────────────────────────────────────────┘
```

### Component Architecture

```
MCP Server (FastAPI)
│
├── Ingestion Layer
│   ├── HL7 v2 Listener (TCP/MLLP)
│   │   ├── ADT Message Parser
│   │   ├── ORU Message Parser
│   │   ├── ORM Message Parser
│   │   └── MDM Message Parser
│   ├── FHIR Client (REST)
│   │   ├── Patient Resource Retriever
│   │   ├── Encounter Resource Retriever
│   │   ├── Observation Resource Retriever
│   │   ├── DiagnosticReport Retriever
│   │   ├── ImagingStudy Retriever
│   │   ├── MedicationRequest Retriever
│   │   ├── Procedure Retriever
│   │   └── CarePlan Retriever
│   ├── DICOM Metadata Listener
│   │   ├── DICOM C-STORE Handler
│   │   └── DICOM Metadata Extractor
│   └── Device Telemetry Connector
│       ├── Vital Signs Aggregator
│       ├── Waveform Processor
│       ├── Alarm Event Handler
│       └── Device Status Monitor
│
├── Normalization & Mapping Layer
│   ├── Patient ID Mapper
│   ├── Encounter ID Mapper
│   ├── Device ID Mapper
│   ├── Care Unit Mapper
│   ├── Clinician ID Mapper
│   └── Data Consolidation Engine
│
├── Clinical Context Engine
│   ├── Event Classifier
│   ├── Timeline Builder
│   ├── Annotation Engine
│   ├── Confidence Scorer
│   ├── Diagnosis Context Builder
│   ├── Exam Context Builder
│   ├── Procedure Context Builder
│   └── Alarm Context Builder
│
├── MCP Tool Layer
│   ├── get_patient_clinical_context
│   ├── get_care_unit_summary
│   ├── get_device_events_by_patient
│   ├── get_diagnostic_exam_context
│   ├── get_patient_event_timeline
│   ├── get_alarm_context
│   ├── get_imaging_study_summary
│   ├── get_anesthesia_case_context
│   ├── get_neuro_event_context
│   └── get_cardiology_event_context
│
├── Security & Authorization Layer
│   ├── Authentication Manager (OAuth2/JWT)
│   ├── RBAC Engine
│   ├── Consent Manager
│   ├── PHI Masking Engine
│   └── Audit Logger
│
└── Storage Layer
    ├── PostgreSQL Database
    ├── Redis Cache
    └── Message Queue (RabbitMQ)
```

## Data Flow Diagrams

### HL7 v2 Ingestion Flow

```
HL7 v2 Message (ADT/ORU/ORM/MDM)
        │
        ▼
┌──────────────────────┐
│ HL7 Parser           │
│ - Validate Structure │
│ - Extract Fields     │
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ ID Mapper            │
│ - Patient ID         │
│ - Encounter ID       │
│ - Care Unit          │
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ Data Normalizer      │
│ - Standardize Format │
│ - Validate Values    │
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ Annotation Engine    │
│ - Add Clinical Tags  │
│ - Confidence Scores  │
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ Database Storage     │
│ - Insert/Update      │
│ - Maintain Integrity │
└──────────────────────┘
```

### FHIR Ingestion Flow

```
FHIR Server (REST API)
        │
        ▼
┌──────────────────────┐
│ FHIR Client          │
│ - Query Resources    │
│ - Handle Pagination  │
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ Resource Mapper      │
│ - Patient → Internal │
│ - Encounter → Internal
│ - Observation → Internal
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ Consolidation Engine │
│ - Merge Duplicates   │
│ - Resolve Conflicts  │
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ Database Storage     │
│ - Upsert Operations  │
└──────────────────────┘
```

### Device Telemetry Ingestion Flow

```
Medical Devices (ECG, Ventilator, Pump, etc.)
        │
        ▼
┌──────────────────────┐
│ Device Connector     │
│ - Receive Telemetry  │
│ - Parse Protocol     │
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ Patient Association  │
│ - Map Device to      │
│   Patient/Encounter  │
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ Annotation Engine    │
│ - Detect Abnormal    │
│ - Classify Events    │
│ - Trend Detection    │
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ Time-Series Storage  │
│ - Store Observations │
│ - Index by Time      │
└──────────────────────┘
```

### MCP Tool Query Flow

```
MCP Client Request
        │
        ▼
┌──────────────────────┐
│ Authentication       │
│ - Validate JWT/OAuth │
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ Authorization Check  │
│ - Verify RBAC        │
│ - Check Care Unit    │
│ - Verify Consent     │
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ Input Validation     │
│ - Type Check         │
│ - Range Check        │
│ - ID Validation      │
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ Tool Execution       │
│ - Query Database     │
│ - Build Context      │
│ - Calculate Scores   │
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ Response Formatting  │
│ - JSON Serialization │
│ - PHI Masking        │
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ Audit Logging        │
│ - Log Access         │
│ - Log Data Returned  │
└──────────────────────┘
        │
        ▼
MCP Client Response
```



## MCP Server Design (Python/FastAPI)

### FastAPI Application Structure

```
mcp_server/
├── main.py                          # FastAPI app initialization
├── config.py                        # Configuration management
├── requirements.txt                 # Python dependencies
│
├── routers/
│   ├── __init__.py
│   ├── health.py                    # Health check endpoints
│   ├── mcp_tools.py                 # MCP tool endpoints
│   └── admin.py                     # Admin endpoints
│
├── ingestion/
│   ├── __init__.py
│   ├── hl7_listener.py              # HL7 v2 TCP listener
│   ├── hl7_parser.py                # HL7 message parsing
│   ├── fhir_client.py               # FHIR API client
│   ├── dicom_listener.py            # DICOM metadata listener
│   └── device_connector.py          # Device telemetry connector
│
├── normalization/
│   ├── __init__.py
│   ├── id_mapper.py                 # Patient/Encounter/Device ID mapping
│   ├── care_unit_mapper.py          # Care unit mapping
│   ├── clinician_mapper.py          # Clinician ID mapping
│   ├── data_normalizer.py           # Data normalization
│   └── consolidation.py             # Data consolidation
│
├── context_engine/
│   ├── __init__.py
│   ├── event_classifier.py          # Event classification
│   ├── timeline_builder.py          # Timeline construction
│   ├── annotation_engine.py         # Data annotation
│   ├── confidence_scorer.py         # Confidence scoring
│   ├── diagnosis_context.py         # Diagnosis context
│   ├── exam_context.py              # Exam context
│   ├── procedure_context.py         # Procedure context
│   └── alarm_context.py             # Alarm context
│
├── tools/
│   ├── __init__.py
│   ├── patient_context.py           # get_patient_clinical_context
│   ├── care_unit_summary.py         # get_care_unit_summary
│   ├── device_events.py             # get_device_events_by_patient
│   ├── diagnostic_exam.py           # get_diagnostic_exam_context
│   ├── event_timeline.py            # get_patient_event_timeline
│   ├── alarm_context.py             # get_alarm_context
│   ├── imaging_summary.py           # get_imaging_study_summary
│   ├── anesthesia_context.py        # get_anesthesia_case_context
│   ├── neuro_context.py             # get_neuro_event_context
│   └── cardiology_context.py        # get_cardiology_event_context
│
├── security/
│   ├── __init__.py
│   ├── auth.py                      # Authentication (OAuth2/JWT)
│   ├── rbac.py                      # Role-based access control
│   ├── consent.py                   # Patient consent checking
│   ├── phi_masking.py               # PHI masking/redaction
│   └── audit_logger.py              # Audit logging
│
├── models/
│   ├── __init__.py
│   ├── database.py                  # SQLAlchemy models
│   ├── schemas.py                   # Pydantic schemas
│   └── enums.py                     # Enumerations
│
├── database/
│   ├── __init__.py
│   ├── connection.py                # Database connection
│   ├── cache.py                     # Redis cache
│   └── migrations/                  # Alembic migrations
│
└── utils/
    ├── __init__.py
    ├── logger.py                    # Logging configuration
    ├── validators.py                # Input validators
    └── helpers.py                   # Utility functions
```

### MCP Protocol Implementation

The MCP server implements the Model Context Protocol using the Python MCP SDK:

```python
# main.py
from fastapi import FastAPI
from mcp.server.fastapi import MCPServer
from mcp.types import Tool, TextContent

app = FastAPI()
mcp_server = MCPServer(app)

# Define MCP tools
tools = [
    Tool(
        name="get_patient_clinical_context",
        description="Retrieve comprehensive clinical context for a patient",
        inputSchema={
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
                "include_timeline": {"type": "boolean", "default": False}
            },
            "required": ["patient_id"]
        }
    ),
    # ... additional tools
]

@mcp_server.call_tool
async def handle_tool_call(name: str, arguments: dict):
    if name == "get_patient_clinical_context":
        return await patient_context.get_context(arguments["patient_id"])
    # ... handle other tools
```

### Tool Definitions with Input/Output Schemas

Each MCP tool has standardized input and output schemas:

```python
# Tool: get_patient_clinical_context
INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "patient_id": {
            "type": "string",
            "description": "Internal patient identifier"
        },
        "include_timeline": {
            "type": "boolean",
            "description": "Include event timeline",
            "default": False
        },
        "include_devices": {
            "type": "boolean",
            "description": "Include active devices",
            "default": True
        }
    },
    "required": ["patient_id"]
}

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "patient": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "mrn": {"type": "string"},
                "name": {"type": "string"},
                "dob": {"type": "string"},
                "age": {"type": "integer"}
            }
        },
        "encounter": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "care_unit": {"type": "string"},
                "admission_time": {"type": "string"},
                "clinicians": {"type": "array"}
            }
        },
        "diagnoses": {"type": "array"},
        "medications": {"type": "array"},
        "devices": {"type": "array"},
        "recent_events": {"type": "array"},
        "confidence_score": {"type": "number"},
        "source_references": {"type": "array"}
    }
}
```

### Request/Response Handling and Error Management

```python
# Error handling middleware
@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={
            "error": "Validation Error",
            "details": str(exc),
            "request_id": request.headers.get("X-Request-ID")
        }
    )

@app.exception_handler(AuthorizationError)
async def authorization_exception_handler(request, exc):
    audit_logger.log_denied_access(request)
    return JSONResponse(
        status_code=403,
        content={"error": "Access Denied"}
    )

@app.exception_handler(DatabaseError)
async def database_exception_handler(request, exc):
    logger.error(f"Database error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error"}
    )
```

### Concurrent Request Handling

```python
# Connection management with asyncio
from concurrent.futures import ThreadPoolExecutor

class ConnectionPool:
    def __init__(self, max_connections=100):
        self.executor = ThreadPoolExecutor(max_workers=max_connections)
        self.active_connections = 0
        self.max_connections = max_connections
    
    async def execute(self, coro):
        if self.active_connections >= self.max_connections:
            raise ConnectionLimitError("Max connections reached")
        
        self.active_connections += 1
        try:
            return await coro
        finally:
            self.active_connections -= 1
```



## Data Ingestion Architecture

### HL7 v2 Listener

```python
# ingestion/hl7_listener.py
import socket
from hl7.util import parse_message

class HL7Listener:
    def __init__(self, host='0.0.0.0', port=2575):
        self.host = host
        self.port = port
        self.socket = None
    
    async def start(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((self.host, self.port))
        self.socket.listen(5)
        
        while True:
            conn, addr = self.socket.accept()
            asyncio.create_task(self.handle_connection(conn))
    
    async def handle_connection(self, conn):
        try:
            while True:
                # MLLP framing: <VT> message <FS><CR>
                data = conn.recv(4096)
                if not data:
                    break
                
                message = self.extract_mllp_message(data)
                await self.process_hl7_message(message)
                
                # Send ACK
                ack = self.generate_ack(message)
                conn.send(ack)
        finally:
            conn.close()
    
    def extract_mllp_message(self, data):
        # Remove MLLP framing characters
        return data[1:-2].decode('utf-8')
    
    async def process_hl7_message(self, message):
        try:
            parsed = parse_message(message)
            msg_type = parsed[0][0][0]  # MSH-9 Message Type
            
            if msg_type == 'ADT':
                await self.process_adt(parsed)
            elif msg_type == 'ORU':
                await self.process_oru(parsed)
            elif msg_type == 'ORM':
                await self.process_orm(parsed)
            elif msg_type == 'MDM':
                await self.process_mdm(parsed)
        except Exception as e:
            logger.error(f"HL7 parsing error: {e}")
            await audit_logger.log_ingestion_error(message, str(e))
```

### FHIR Client

```python
# ingestion/fhir_client.py
import aiohttp
from fhirclient.models import patient, encounter, observation

class FHIRClient:
    def __init__(self, base_url, auth_token):
        self.base_url = base_url
        self.auth_token = auth_token
        self.session = None
    
    async def retrieve_patient(self, patient_id):
        url = f"{self.base_url}/Patient/{patient_id}"
        async with self.session.get(url, headers=self.auth_headers) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                logger.error(f"Failed to retrieve patient: {resp.status}")
    
    async def retrieve_observations(self, patient_id, start_date, end_date):
        url = f"{self.base_url}/Observation"
        params = {
            "subject": f"Patient/{patient_id}",
            "date": f"ge{start_date}&date=le{end_date}"
        }
        observations = []
        
        async with self.session.get(url, params=params, headers=self.auth_headers) as resp:
            data = await resp.json()
            for entry in data.get('entry', []):
                observations.append(entry['resource'])
        
        return observations
    
    @property
    def auth_headers(self):
        return {
            "Authorization": f"Bearer {self.auth_token}",
            "Accept": "application/fhir+json"
        }
```

### DICOM Metadata Listener

```python
# ingestion/dicom_listener.py
from pydicom.dataset import Dataset
from pynetdicom import AE, evt

class DICOMListener:
    def __init__(self, port=11112):
        self.port = port
        self.ae = AE()
        self.ae.add_supported_context('1.2.840.10008.5.1.4.1.1.2')  # CT Image Storage
        self.ae.add_supported_context('1.2.840.10008.5.1.4.1.1.2.1')  # Enhanced CT
        # ... add other supported contexts
    
    async def start(self):
        handlers = [(evt.EVT_C_STORE, self.handle_c_store)]
        self.ae.start_server(('0.0.0.0', self.port), evt_handlers=handlers)
    
    async def handle_c_store(self, event):
        ds = event.dataset
        
        # Extract metadata
        metadata = {
            'patient_id': ds.PatientID,
            'study_id': ds.StudyInstanceUID,
            'series_id': ds.SeriesInstanceUID,
            'modality': ds.Modality,
            'timestamp': ds.StudyDate + ds.StudyTime,
            'description': ds.StudyDescription,
            'sop_class': ds.file_meta.MediaStorageSOPClassUID
        }
        
        await self.store_dicom_metadata(metadata)
        
        # Return success
        return 0x0000
    
    async def store_dicom_metadata(self, metadata):
        # Normalize patient ID and store
        internal_patient_id = await id_mapper.get_internal_patient_id(
            metadata['patient_id']
        )
        metadata['internal_patient_id'] = internal_patient_id
        
        # Store in database
        await db.store_imaging_study(metadata)
```

### Device Telemetry Connector

```python
# ingestion/device_connector.py
import asyncio
from typing import Dict, List

class DeviceTelemetryConnector:
    def __init__(self):
        self.device_handlers = {}
        self.patient_device_map = {}
    
    async def connect_device(self, device_id, device_type, connection_params):
        if device_type == 'philips_monitor':
            handler = PhilipsMonitorHandler(device_id, connection_params)
        elif device_type == 'ventilator':
            handler = VentilatorHandler(device_id, connection_params)
        # ... other device types
        
        self.device_handlers[device_id] = handler
        asyncio.create_task(handler.start())
    
    async def process_vital_signs(self, device_id, vitals):
        # vitals: {'hr': 85, 'spo2': 98, 'bp_sys': 120, 'bp_dia': 80}
        
        patient_id = await self.get_patient_for_device(device_id)
        encounter_id = await self.get_encounter_for_patient(patient_id)
        
        # Annotate vitals
        annotations = await self.annotate_vitals(vitals)
        
        # Store observations
        for vital_name, vital_value in vitals.items():
            observation = {
                'patient_id': patient_id,
                'encounter_id': encounter_id,
                'device_id': device_id,
                'observation_type': vital_name,
                'value': vital_value,
                'timestamp': datetime.now(),
                'annotations': annotations.get(vital_name, [])
            }
            await db.store_observation(observation)
    
    async def process_alarm_event(self, device_id, alarm):
        # alarm: {'type': 'low_spo2', 'severity': 'high', 'threshold': 90}
        
        patient_id = await self.get_patient_for_device(device_id)
        
        alarm_event = {
            'patient_id': patient_id,
            'device_id': device_id,
            'alarm_type': alarm['type'],
            'severity': alarm['severity'],
            'threshold': alarm['threshold'],
            'timestamp': datetime.now()
        }
        
        await db.store_alarm_event(alarm_event)
        await self.notify_clinicians(patient_id, alarm_event)
```



## Normalization and Mapping Layer

### Patient ID Mapping

```python
# normalization/id_mapper.py
class PatientIDMapper:
    def __init__(self, db):
        self.db = db
        self.cache = {}
    
    async def get_internal_patient_id(self, external_id, source_system):
        """
        Get internal patient ID from external identifier.
        Handles multiple external IDs for same patient.
        """
        cache_key = f"{source_system}:{external_id}"
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Query mapping table
        mapping = await self.db.query(
            "SELECT internal_id FROM patient_id_mapping "
            "WHERE external_id = %s AND source_system = %s",
            (external_id, source_system)
        )
        
        if mapping:
            internal_id = mapping[0]['internal_id']
            self.cache[cache_key] = internal_id
            return internal_id
        
        # Create new mapping
        internal_id = await self.create_patient_mapping(external_id, source_system)
        self.cache[cache_key] = internal_id
        return internal_id
    
    async def create_patient_mapping(self, external_id, source_system):
        """Create new patient mapping and check for duplicates."""
        
        # Check for potential duplicates using fuzzy matching
        potential_duplicates = await self.find_potential_duplicates(
            external_id, source_system
        )
        
        if potential_duplicates:
            # Log for manual reconciliation
            await audit_logger.log_potential_duplicate(
                external_id, source_system, potential_duplicates
            )
        
        # Create new internal ID
        internal_id = f"PAT-{uuid.uuid4()}"
        
        await self.db.execute(
            "INSERT INTO patient_id_mapping "
            "(internal_id, external_id, source_system, created_at) "
            "VALUES (%s, %s, %s, NOW())",
            (internal_id, external_id, source_system)
        )
        
        return internal_id
    
    async def find_potential_duplicates(self, external_id, source_system):
        """Find potential duplicate patients using fuzzy matching."""
        # Implementation uses Levenshtein distance or similar
        pass
```

### Encounter ID Mapping

```python
# normalization/id_mapper.py (continued)
class EncounterIDMapper:
    async def get_internal_encounter_id(self, external_id, source_system, patient_id):
        """Map external encounter ID to internal ID."""
        
        mapping = await self.db.query(
            "SELECT internal_id FROM encounter_id_mapping "
            "WHERE external_id = %s AND source_system = %s AND patient_id = %s",
            (external_id, source_system, patient_id)
        )
        
        if mapping:
            return mapping[0]['internal_id']
        
        # Create new mapping
        internal_id = f"ENC-{uuid.uuid4()}"
        
        await self.db.execute(
            "INSERT INTO encounter_id_mapping "
            "(internal_id, external_id, source_system, patient_id, created_at) "
            "VALUES (%s, %s, %s, %s, NOW())",
            (internal_id, external_id, source_system, patient_id)
        )
        
        return internal_id
```

### Care Unit Mapping

```python
# normalization/care_unit_mapper.py
class CareUnitMapper:
    CARE_UNIT_MAPPING = {
        'CARDIO': 'cardiology',
        'ED': 'emergency_department',
        'NEURO': 'neurology',
        'SURG': 'surgical_ward',
        'OR': 'operating_room',
        'ICU': 'intensive_care',
        'RAD': 'radiology',
        'GEN': 'general_ward'
    }
    
    async def get_internal_care_unit(self, external_code):
        """Map external care unit code to internal identifier."""
        
        if external_code in self.CARE_UNIT_MAPPING:
            return self.CARE_UNIT_MAPPING[external_code]
        
        # Query custom mappings
        mapping = await self.db.query(
            "SELECT internal_code FROM care_unit_mapping "
            "WHERE external_code = %s",
            (external_code,)
        )
        
        if mapping:
            return mapping[0]['internal_code']
        
        # Log unmapped care unit
        logger.warning(f"Unmapped care unit code: {external_code}")
        return None
```

### Data Consolidation Engine

```python
# normalization/consolidation.py
class DataConsolidationEngine:
    async def consolidate_patient_data(self, patient_id):
        """
        Consolidate data from multiple sources for a patient.
        Handles conflicts and merges duplicate records.
        """
        
        # Get all data sources for patient
        sources = await self.db.query(
            "SELECT DISTINCT source_system FROM data_source_tracking "
            "WHERE patient_id = %s",
            (patient_id,)
        )
        
        consolidated = {
            'patient_id': patient_id,
            'demographics': {},
            'encounters': [],
            'observations': [],
            'medications': [],
            'diagnoses': [],
            'conflicts': []
        }
        
        # Merge demographics from all sources
        demographics = await self.merge_demographics(patient_id, sources)
        consolidated['demographics'] = demographics
        
        # Consolidate encounters
        encounters = await self.consolidate_encounters(patient_id)
        consolidated['encounters'] = encounters
        
        # Consolidate observations
        observations = await self.consolidate_observations(patient_id)
        consolidated['observations'] = observations
        
        return consolidated
    
    async def merge_demographics(self, patient_id, sources):
        """Merge patient demographics from multiple sources."""
        
        demographics = {}
        conflicts = []
        
        for source in sources:
            demo = await self.db.query(
                "SELECT * FROM patient_demographics "
                "WHERE patient_id = %s AND source_system = %s",
                (patient_id, source['source_system'])
            )
            
            if demo:
                for key, value in demo[0].items():
                    if key not in demographics:
                        demographics[key] = value
                    elif demographics[key] != value:
                        conflicts.append({
                            'field': key,
                            'source1': demographics[key],
                            'source2': value,
                            'source_system': source['source_system']
                        })
        
        return demographics, conflicts
```



## Clinical Context Engine

### Event Classification

```python
# context_engine/event_classifier.py
class EventClassifier:
    EVENT_TYPES = {
        'vital_sign_change': 'observation',
        'alarm': 'alarm_event',
        'medication_administration': 'medication_event',
        'procedure_start': 'procedure_event',
        'procedure_end': 'procedure_event',
        'diagnostic_exam': 'diagnostic_event',
        'device_status_change': 'device_event',
        'clinician_note': 'documentation_event'
    }
    
    async def classify_event(self, event_data):
        """Classify incoming event and assign clinical significance."""
        
        event_type = event_data.get('type')
        classification = {
            'event_type': event_type,
            'clinical_significance': 'normal',
            'annotations': [],
            'confidence_score': 1.0
        }
        
        if event_type == 'vital_sign_change':
            classification = await self.classify_vital_sign(event_data)
        elif event_type == 'alarm':
            classification = await self.classify_alarm(event_data)
        elif event_type == 'medication_administration':
            classification = await self.classify_medication(event_data)
        
        return classification
    
    async def classify_vital_sign(self, vital_data):
        """Classify vital sign observation."""
        
        vital_type = vital_data['vital_type']
        value = vital_data['value']
        
        # Get clinical thresholds
        thresholds = await self.get_clinical_thresholds(vital_type)
        
        significance = 'normal'
        if value < thresholds['critical_low']:
            significance = 'critical_low'
        elif value < thresholds['abnormal_low']:
            significance = 'abnormal_low'
        elif value > thresholds['critical_high']:
            significance = 'critical_high'
        elif value > thresholds['abnormal_high']:
            significance = 'abnormal_high'
        
        return {
            'event_type': 'vital_sign_change',
            'clinical_significance': significance,
            'annotations': [f"{vital_type} {significance}"],
            'confidence_score': 0.95
        }
    
    async def classify_alarm(self, alarm_data):
        """Classify alarm event."""
        
        alarm_type = alarm_data['alarm_type']
        severity = alarm_data['severity']
        
        # Map severity to clinical significance
        significance_map = {
            'critical': 'critical',
            'high': 'abnormal_high',
            'medium': 'abnormal_low',
            'low': 'normal'
        }
        
        return {
            'event_type': 'alarm',
            'clinical_significance': significance_map.get(severity, 'normal'),
            'annotations': [f"Alarm: {alarm_type} ({severity})"],
            'confidence_score': 0.98
        }
```

### Timeline Builder

```python
# context_engine/timeline_builder.py
class TimelineBuilder:
    async def build_patient_timeline(self, patient_id, start_time, end_time):
        """Build chronological timeline of clinical events."""
        
        events = []
        
        # Retrieve all event types
        observations = await self.db.query(
            "SELECT * FROM observations "
            "WHERE patient_id = %s AND timestamp BETWEEN %s AND %s "
            "ORDER BY timestamp ASC",
            (patient_id, start_time, end_time)
        )
        
        alarms = await self.db.query(
            "SELECT * FROM alarm_events "
            "WHERE patient_id = %s AND timestamp BETWEEN %s AND %s "
            "ORDER BY timestamp ASC",
            (patient_id, start_time, end_time)
        )
        
        medications = await self.db.query(
            "SELECT * FROM medication_events "
            "WHERE patient_id = %s AND timestamp BETWEEN %s AND %s "
            "ORDER BY timestamp ASC",
            (patient_id, start_time, end_time)
        )
        
        procedures = await self.db.query(
            "SELECT * FROM procedures "
            "WHERE patient_id = %s AND start_time BETWEEN %s AND %s "
            "ORDER BY start_time ASC",
            (patient_id, start_time, end_time)
        )
        
        # Merge and sort all events
        all_events = []
        all_events.extend([('observation', e) for e in observations])
        all_events.extend([('alarm', e) for e in alarms])
        all_events.extend([('medication', e) for e in medications])
        all_events.extend([('procedure', e) for e in procedures])
        
        # Sort by timestamp
        all_events.sort(key=lambda x: x[1]['timestamp'])
        
        # Build timeline with context
        timeline = []
        for event_type, event in all_events:
            timeline_entry = {
                'timestamp': event['timestamp'],
                'event_type': event_type,
                'event': event,
                'context': await self.build_event_context(event_type, event)
            }
            timeline.append(timeline_entry)
        
        return timeline
    
    async def build_event_context(self, event_type, event):
        """Build contextual information for an event."""
        
        context = {
            'preceding_events': [],
            'concurrent_events': [],
            'related_diagnoses': []
        }
        
        # Get preceding events (last 5 minutes)
        preceding_time = event['timestamp'] - timedelta(minutes=5)
        preceding = await self.db.query(
            "SELECT * FROM events "
            "WHERE patient_id = %s AND timestamp BETWEEN %s AND %s "
            "ORDER BY timestamp DESC LIMIT 5",
            (event['patient_id'], preceding_time, event['timestamp'])
        )
        context['preceding_events'] = preceding
        
        return context
```

### Annotation Engine

```python
# context_engine/annotation_engine.py
class AnnotationEngine:
    async def annotate_observation(self, observation):
        """Add clinical annotations to observation."""
        
        annotations = []
        
        # Check for abnormal values
        if observation['is_abnormal']:
            annotations.append({
                'type': 'abnormal_value',
                'severity': observation['abnormality_level'],
                'description': f"Abnormal {observation['observation_type']}"
            })
        
        # Check for trends
        trend = await self.detect_trend(observation)
        if trend:
            annotations.append({
                'type': 'trend',
                'direction': trend['direction'],
                'description': f"{trend['direction']} trend detected"
            })
        
        # Check for clinical context
        context = await self.get_clinical_context(observation)
        if context:
            annotations.append({
                'type': 'clinical_context',
                'context': context,
                'description': f"During {context}"
            })
        
        return annotations
    
    async def detect_trend(self, observation):
        """Detect trends in vital signs."""
        
        # Get previous observations of same type
        previous = await self.db.query(
            "SELECT value, timestamp FROM observations "
            "WHERE patient_id = %s AND observation_type = %s "
            "AND timestamp < %s "
            "ORDER BY timestamp DESC LIMIT 10",
            (observation['patient_id'], observation['observation_type'], 
             observation['timestamp'])
        )
        
        if len(previous) < 3:
            return None
        
        # Calculate trend
        values = [p['value'] for p in previous]
        
        # Simple linear regression
        if values[0] > values[-1]:
            direction = 'decreasing'
        elif values[0] < values[-1]:
            direction = 'increasing'
        else:
            direction = 'stable'
        
        return {'direction': direction, 'values': values}
```

### Confidence Scoring

```python
# context_engine/confidence_scorer.py
class ConfidenceScorer:
    async def score_observation(self, observation):
        """Calculate confidence score for observation."""
        
        score = 1.0
        
        # Reduce score based on data source reliability
        source_reliability = await self.get_source_reliability(
            observation['source_system']
        )
        score *= source_reliability
        
        # Reduce score if data is old
        age_minutes = (datetime.now() - observation['timestamp']).total_seconds() / 60
        if age_minutes > 60:
            score *= 0.9
        elif age_minutes > 1440:  # 24 hours
            score *= 0.7
        
        # Reduce score if device is not calibrated
        if observation.get('device_id'):
            device = await self.db.query(
                "SELECT calibration_status FROM devices WHERE id = %s",
                (observation['device_id'],)
            )
            if device and device[0]['calibration_status'] != 'calibrated':
                score *= 0.8
        
        return max(0.0, min(1.0, score))
    
    async def score_aggregated_context(self, context):
        """Calculate confidence score for aggregated clinical context."""
        
        scores = []
        
        # Score each component
        if context.get('patient'):
            scores.append(await self.score_observation(context['patient']))
        
        if context.get('observations'):
            obs_scores = [
                await self.score_observation(obs) 
                for obs in context['observations']
            ]
            scores.append(sum(obs_scores) / len(obs_scores) if obs_scores else 1.0)
        
        if context.get('medications'):
            scores.append(0.95)  # Medications typically high confidence
        
        # Average all scores
        overall_score = sum(scores) / len(scores) if scores else 0.5
        
        return overall_score
```



## Storage Layer Design

### Database Schema

```sql
-- Core Patient Data
CREATE TABLE patients (
    id UUID PRIMARY KEY,
    mrn VARCHAR(50) UNIQUE NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    date_of_birth DATE,
    gender VARCHAR(10),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE patient_id_mapping (
    id UUID PRIMARY KEY,
    internal_id UUID REFERENCES patients(id),
    external_id VARCHAR(100) NOT NULL,
    source_system VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(external_id, source_system)
);

-- Encounter Data
CREATE TABLE encounters (
    id UUID PRIMARY KEY,
    patient_id UUID REFERENCES patients(id),
    care_unit_id UUID REFERENCES care_units(id),
    admission_time TIMESTAMP NOT NULL,
    discharge_time TIMESTAMP,
    status VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE encounter_id_mapping (
    id UUID PRIMARY KEY,
    internal_id UUID REFERENCES encounters(id),
    external_id VARCHAR(100) NOT NULL,
    source_system VARCHAR(50) NOT NULL,
    patient_id UUID REFERENCES patients(id),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(external_id, source_system, patient_id)
);

-- Care Units
CREATE TABLE care_units (
    id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    unit_type VARCHAR(50),
    location VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Clinicians
CREATE TABLE clinicians (
    id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    role VARCHAR(50),
    specialty VARCHAR(100),
    contact_info VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE clinician_id_mapping (
    id UUID PRIMARY KEY,
    internal_id UUID REFERENCES clinicians(id),
    external_id VARCHAR(100) NOT NULL,
    source_system VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(external_id, source_system)
);

-- Devices
CREATE TABLE devices (
    id UUID PRIMARY KEY,
    device_type VARCHAR(50),
    model VARCHAR(100),
    serial_number VARCHAR(100),
    location VARCHAR(100),
    status VARCHAR(20),
    calibration_status VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE device_id_mapping (
    id UUID PRIMARY KEY,
    internal_id UUID REFERENCES devices(id),
    external_id VARCHAR(100) NOT NULL,
    source_system VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(external_id, source_system)
);

-- Observations (Vital Signs, Lab Results)
CREATE TABLE observations (
    id UUID PRIMARY KEY,
    patient_id UUID REFERENCES patients(id),
    encounter_id UUID REFERENCES encounters(id),
    device_id UUID REFERENCES devices(id),
    observation_type VARCHAR(50),
    value NUMERIC,
    unit VARCHAR(20),
    timestamp TIMESTAMP NOT NULL,
    is_abnormal BOOLEAN,
    abnormality_level VARCHAR(20),
    source_system VARCHAR(50),
    confidence_score NUMERIC(3,2),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_observations_patient_time ON observations(patient_id, timestamp DESC);
CREATE INDEX idx_observations_encounter_time ON observations(encounter_id, timestamp DESC);

-- Alarm Events
CREATE TABLE alarm_events (
    id UUID PRIMARY KEY,
    patient_id UUID REFERENCES patients(id),
    device_id UUID REFERENCES devices(id),
    alarm_type VARCHAR(100),
    severity VARCHAR(20),
    threshold NUMERIC,
    timestamp TIMESTAMP NOT NULL,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by UUID REFERENCES clinicians(id),
    acknowledged_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_alarms_patient_time ON alarm_events(patient_id, timestamp DESC);

-- Diagnostic Exams
CREATE TABLE diagnostic_exams (
    id UUID PRIMARY KEY,
    patient_id UUID REFERENCES patients(id),
    encounter_id UUID REFERENCES encounters(id),
    exam_type VARCHAR(50),
    indication VARCHAR(500),
    timestamp TIMESTAMP NOT NULL,
    result_status VARCHAR(20),
    findings TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Imaging Studies
CREATE TABLE imaging_studies (
    id UUID PRIMARY KEY,
    patient_id UUID REFERENCES patients(id),
    encounter_id UUID REFERENCES encounters(id),
    study_id VARCHAR(100),
    modality VARCHAR(50),
    timestamp TIMESTAMP NOT NULL,
    description TEXT,
    findings TEXT,
    report_status VARCHAR(20),
    radiologist_id UUID REFERENCES clinicians(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Procedures
CREATE TABLE procedures (
    id UUID PRIMARY KEY,
    patient_id UUID REFERENCES patients(id),
    encounter_id UUID REFERENCES encounters(id),
    procedure_type VARCHAR(100),
    indication VARCHAR(500),
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    status VARCHAR(20),
    outcome VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Medications
CREATE TABLE medication_events (
    id UUID PRIMARY KEY,
    patient_id UUID REFERENCES patients(id),
    encounter_id UUID REFERENCES encounters(id),
    medication_name VARCHAR(200),
    dosage VARCHAR(100),
    route VARCHAR(50),
    indication VARCHAR(500),
    administration_time TIMESTAMP,
    administered_by UUID REFERENCES clinicians(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Audit Logs
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY,
    clinician_id UUID REFERENCES clinicians(id),
    tool_name VARCHAR(100),
    patient_id UUID REFERENCES patients(id),
    action VARCHAR(50),
    parameters JSONB,
    result_summary VARCHAR(500),
    timestamp TIMESTAMP DEFAULT NOW(),
    ip_address VARCHAR(50)
);

CREATE INDEX idx_audit_logs_clinician_time ON audit_logs(clinician_id, timestamp DESC);
CREATE INDEX idx_audit_logs_patient_time ON audit_logs(patient_id, timestamp DESC);
```

### Indexing Strategy

```sql
-- Performance indexes for common queries
CREATE INDEX idx_patients_mrn ON patients(mrn);
CREATE INDEX idx_encounters_patient_active ON encounters(patient_id, discharge_time) 
    WHERE discharge_time IS NULL;
CREATE INDEX idx_observations_type_time ON observations(observation_type, timestamp DESC);
CREATE INDEX idx_alarm_events_severity ON alarm_events(severity, timestamp DESC);
CREATE INDEX idx_imaging_studies_modality ON imaging_studies(modality, timestamp DESC);

-- Composite indexes for common query patterns
CREATE INDEX idx_patient_encounter_time ON observations(patient_id, encounter_id, timestamp DESC);
CREATE INDEX idx_device_patient_time ON observations(device_id, patient_id, timestamp DESC);
```

### Caching Layer Design

```python
# database/cache.py
import redis
import json
from typing import Any, Optional

class CacheLayer:
    def __init__(self, redis_url='redis://localhost:6379'):
        self.redis = redis.from_url(redis_url)
        self.ttl = {
            'patient_context': 300,      # 5 minutes
            'care_unit_summary': 60,     # 1 minute
            'device_events': 120,        # 2 minutes
            'clinical_thresholds': 3600  # 1 hour
        }
    
    async def get_patient_context(self, patient_id: str) -> Optional[dict]:
        """Retrieve cached patient context."""
        key = f"patient_context:{patient_id}"
        cached = self.redis.get(key)
        return json.loads(cached) if cached else None
    
    async def set_patient_context(self, patient_id: str, context: dict):
        """Cache patient context."""
        key = f"patient_context:{patient_id}"
        self.redis.setex(
            key,
            self.ttl['patient_context'],
            json.dumps(context)
        )
    
    async def invalidate_patient_cache(self, patient_id: str):
        """Invalidate patient cache on data update."""
        keys = self.redis.keys(f"patient_context:{patient_id}*")
        if keys:
            self.redis.delete(*keys)
    
    async def get_clinical_thresholds(self, vital_type: str) -> Optional[dict]:
        """Retrieve cached clinical thresholds."""
        key = f"thresholds:{vital_type}"
        cached = self.redis.get(key)
        return json.loads(cached) if cached else None
    
    async def set_clinical_thresholds(self, vital_type: str, thresholds: dict):
        """Cache clinical thresholds."""
        key = f"thresholds:{vital_type}"
        self.redis.setex(
            key,
            self.ttl['clinical_thresholds'],
            json.dumps(thresholds)
        )
```

### Partitioning Strategy

```python
# database/partitioning.py
class PartitioningStrategy:
    """
    Partition observations table by time for better performance.
    Observations are partitioned monthly.
    """
    
    async def create_monthly_partition(self, year: int, month: int):
        """Create monthly partition for observations."""
        
        partition_name = f"observations_{year}_{month:02d}"
        start_date = f"{year}-{month:02d}-01"
        
        if month == 12:
            end_date = f"{year+1}-01-01"
        else:
            end_date = f"{year}-{month+1:02d}-01"
        
        sql = f"""
        CREATE TABLE {partition_name} PARTITION OF observations
        FOR VALUES FROM ('{start_date}') TO ('{end_date}');
        """
        
        await self.db.execute(sql)
    
    async def archive_old_data(self, months_old: int = 24):
        """Archive observations older than specified months."""
        
        cutoff_date = datetime.now() - timedelta(days=30*months_old)
        
        # Export to archive storage
        sql = f"""
        SELECT * FROM observations 
        WHERE timestamp < '{cutoff_date}'
        """
        
        data = await self.db.query(sql)
        await self.export_to_archive(data)
        
        # Delete from main table
        await self.db.execute(
            f"DELETE FROM observations WHERE timestamp < '{cutoff_date}'"
        )
```



## MCP Tool Implementations

### Tool 1: get_patient_clinical_context

```python
# tools/patient_context.py
async def get_patient_clinical_context(patient_id: str, include_timeline: bool = False):
    """
    Retrieve comprehensive clinical context for a patient.
    
    Returns:
    - Patient demographics
    - Current encounter and care unit
    - Active diagnoses and medications
    - Assigned clinicians
    - Active devices
    - Recent abnormal observations
    - Recent clinical events
    - Confidence score
    """
    
    # Check authorization
    await auth.check_patient_access(current_user, patient_id)
    
    # Check consent
    if not await consent.check_consent(patient_id, current_user):
        raise ConsentDeniedError()
    
    # Try cache first
    cached = await cache.get_patient_context(patient_id)
    if cached:
        return cached
    
    # Build context
    context = {
        'patient': await get_patient_demographics(patient_id),
        'encounter': await get_current_encounter(patient_id),
        'diagnoses': await get_active_diagnoses(patient_id),
        'medications': await get_current_medications(patient_id),
        'clinicians': await get_assigned_clinicians(patient_id),
        'devices': await get_active_devices(patient_id),
        'recent_observations': await get_recent_abnormal_observations(patient_id),
        'recent_events': await get_recent_clinical_events(patient_id),
        'source_references': []
    }
    
    if include_timeline:
        context['timeline'] = await timeline_builder.build_patient_timeline(
            patient_id, 
            datetime.now() - timedelta(hours=24),
            datetime.now()
        )
    
    # Calculate confidence score
    context['confidence_score'] = await confidence_scorer.score_aggregated_context(context)
    
    # Cache result
    await cache.set_patient_context(patient_id, context)
    
    # Audit log
    await audit_logger.log_tool_call(
        'get_patient_clinical_context',
        current_user,
        patient_id,
        context
    )
    
    return context
```

### Tool 2: get_care_unit_summary

```python
# tools/care_unit_summary.py
async def get_care_unit_summary(care_unit_id: str):
    """
    Retrieve summary of all patients in a care unit.
    
    Returns:
    - List of active patients
    - Critical patients (flagged)
    - Abnormal vital trends
    - Active alarms
    - Recent procedures
    - Clinician assignments
    """
    
    # Check authorization
    await auth.check_care_unit_access(current_user, care_unit_id)
    
    # Get all active patients in care unit
    patients = await db.query(
        "SELECT DISTINCT p.id FROM patients p "
        "JOIN encounters e ON p.id = e.patient_id "
        "WHERE e.care_unit_id = %s AND e.discharge_time IS NULL",
        (care_unit_id,)
    )
    
    summary = {
        'care_unit_id': care_unit_id,
        'total_patients': len(patients),
        'critical_patients': [],
        'patients': [],
        'clinician_assignments': [],
        'recent_procedures': [],
        'active_alarms': []
    }
    
    # Build summary for each patient
    for patient in patients:
        patient_id = patient['id']
        
        # Get patient context
        context = await get_patient_clinical_context(patient_id)
        
        # Check if critical
        is_critical = await is_patient_critical(patient_id)
        
        patient_summary = {
            'patient_id': patient_id,
            'mrn': context['patient']['mrn'],
            'name': context['patient']['name'],
            'is_critical': is_critical,
            'recent_observations': context['recent_observations'],
            'active_alarms': await get_patient_alarms(patient_id),
            'assigned_clinicians': context['clinicians']
        }
        
        summary['patients'].append(patient_summary)
        
        if is_critical:
            summary['critical_patients'].append(patient_summary)
    
    # Get recent procedures
    summary['recent_procedures'] = await db.query(
        "SELECT * FROM procedures "
        "WHERE encounter_id IN (SELECT id FROM encounters WHERE care_unit_id = %s) "
        "AND start_time > NOW() - INTERVAL '24 hours' "
        "ORDER BY start_time DESC",
        (care_unit_id,)
    )
    
    # Get clinician assignments
    summary['clinician_assignments'] = await get_care_unit_clinician_assignments(care_unit_id)
    
    # Audit log
    await audit_logger.log_tool_call(
        'get_care_unit_summary',
        current_user,
        care_unit_id,
        summary
    )
    
    return summary
```

### Tool 3: get_device_events_by_patient

```python
# tools/device_events.py
async def get_device_events_by_patient(
    patient_id: str,
    start_time: datetime,
    end_time: datetime,
    device_type: Optional[str] = None
):
    """
    Retrieve device events and alarms for a patient.
    
    Returns:
    - Alarm events with severity
    - Device status changes
    - Waveform events
    - Device setting changes
    - Vital sign trends
    - Correlation with clinical observations
    """
    
    # Check authorization
    await auth.check_patient_access(current_user, patient_id)
    
    # Get device events
    query = """
    SELECT ae.*, d.device_type, d.model
    FROM alarm_events ae
    JOIN devices d ON ae.device_id = d.id
    WHERE ae.patient_id = %s 
    AND ae.timestamp BETWEEN %s AND %s
    """
    
    params = [patient_id, start_time, end_time]
    
    if device_type:
        query += " AND d.device_type = %s"
        params.append(device_type)
    
    query += " ORDER BY ae.timestamp DESC"
    
    alarms = await db.query(query, params)
    
    # Get vital sign observations from devices
    observations = await db.query(
        "SELECT * FROM observations "
        "WHERE patient_id = %s AND device_id IS NOT NULL "
        "AND timestamp BETWEEN %s AND %s "
        "ORDER BY timestamp DESC",
        (patient_id, start_time, end_time)
    )
    
    # Detect trends
    trends = await detect_vital_trends(observations)
    
    # Correlate with clinical events
    clinical_events = await db.query(
        "SELECT * FROM clinical_events "
        "WHERE patient_id = %s AND timestamp BETWEEN %s AND %s",
        (patient_id, start_time, end_time)
    )
    
    result = {
        'patient_id': patient_id,
        'time_window': {'start': start_time, 'end': end_time},
        'alarm_events': alarms,
        'vital_observations': observations,
        'trends': trends,
        'correlated_events': clinical_events,
        'source_references': []
    }
    
    # Audit log
    await audit_logger.log_tool_call(
        'get_device_events_by_patient',
        current_user,
        patient_id,
        result
    )
    
    return result
```

### Tool 4: get_diagnostic_exam_context

```python
# tools/diagnostic_exam.py
async def get_diagnostic_exam_context(
    exam_id: Optional[str] = None,
    patient_id: Optional[str] = None
):
    """
    Retrieve diagnostic exam context including imaging and lab results.
    
    Returns:
    - DICOM metadata for imaging studies
    - Imaging findings and impressions
    - Lab results with reference ranges
    - Contemporaneous vital signs
    - Clinical indication
    - Related clinical events
    """
    
    if exam_id:
        exam = await db.query(
            "SELECT * FROM diagnostic_exams WHERE id = %s",
            (exam_id,)
        )
        if not exam:
            raise ExamNotFoundError()
        patient_id = exam[0]['patient_id']
    
    # Check authorization
    await auth.check_patient_access(current_user, patient_id)
    
    # Get exam details
    exam = await db.query(
        "SELECT * FROM diagnostic_exams WHERE patient_id = %s ORDER BY timestamp DESC LIMIT 1",
        (patient_id,)
    )
    
    if not exam:
        raise ExamNotFoundError()
    
    exam_data = exam[0]
    exam_time = exam_data['timestamp']
    
    # Get imaging studies
    imaging = await db.query(
        "SELECT * FROM imaging_studies WHERE patient_id = %s AND timestamp = %s",
        (patient_id, exam_time)
    )
    
    # Get contemporaneous vital signs (±30 minutes)
    vitals = await db.query(
        "SELECT * FROM observations "
        "WHERE patient_id = %s AND timestamp BETWEEN %s AND %s "
        "ORDER BY timestamp ASC",
        (patient_id, exam_time - timedelta(minutes=30), exam_time + timedelta(minutes=30))
    )
    
    # Get related clinical events
    related_events = await db.query(
        "SELECT * FROM clinical_events "
        "WHERE patient_id = %s AND timestamp BETWEEN %s AND %s",
        (patient_id, exam_time - timedelta(hours=1), exam_time + timedelta(hours=1))
    )
    
    result = {
        'exam': exam_data,
        'imaging_studies': imaging,
        'vital_signs': vitals,
        'related_events': related_events,
        'indication': exam_data['indication'],
        'findings': exam_data['findings'],
        'source_references': []
    }
    
    # Audit log
    await audit_logger.log_tool_call(
        'get_diagnostic_exam_context',
        current_user,
        patient_id,
        result
    )
    
    return result
```



## Security and Authorization Design

### Authentication Mechanism

```python
# security/auth.py
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
import jwt
from datetime import datetime, timedelta

class AuthenticationManager:
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
    
    async def authenticate_clinician(self, username: str, password: str):
        """Authenticate clinician against hospital identity provider."""
        
        # Query hospital identity provider (LDAP, OAuth2, etc.)
        clinician = await self.query_identity_provider(username, password)
        
        if not clinician:
            await audit_logger.log_failed_auth(username)
            raise AuthenticationError("Invalid credentials")
        
        # Create JWT token
        token = self.create_access_token(clinician)
        
        await audit_logger.log_successful_auth(clinician['id'])
        
        return token
    
    def create_access_token(self, clinician: dict, expires_delta: timedelta = None):
        """Create JWT access token."""
        
        if expires_delta is None:
            expires_delta = timedelta(hours=8)
        
        expire = datetime.utcnow() + expires_delta
        
        to_encode = {
            'sub': clinician['id'],
            'name': clinician['name'],
            'role': clinician['role'],
            'care_units': clinician['care_units'],
            'exp': expire
        }
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    async def verify_token(self, token: str = Depends(oauth2_scheme)):
        """Verify JWT token."""
        
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            clinician_id = payload.get("sub")
            
            if clinician_id is None:
                raise HTTPException(status_code=401, detail="Invalid token")
            
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
    
    async def query_identity_provider(self, username: str, password: str):
        """Query hospital identity provider (LDAP, OAuth2, etc.)."""
        # Implementation depends on hospital's identity provider
        pass
```

### Role-Based Access Control (RBAC)

```python
# security/rbac.py
class RBACEngine:
    ROLE_PERMISSIONS = {
        'physician': {
            'get_patient_clinical_context': True,
            'get_care_unit_summary': True,
            'get_device_events_by_patient': True,
            'get_diagnostic_exam_context': True,
            'get_patient_event_timeline': True,
            'get_alarm_context': True,
            'get_imaging_study_summary': True,
            'get_anesthesia_case_context': True,
            'get_neuro_event_context': True,
            'get_cardiology_event_context': True
        },
        'nurse': {
            'get_patient_clinical_context': True,
            'get_care_unit_summary': True,
            'get_device_events_by_patient': True,
            'get_alarm_context': True,
            'get_patient_event_timeline': True
        },
        'technician': {
            'get_patient_clinical_context': False,
            'get_device_events_by_patient': True,
            'get_alarm_context': True
        },
        'administrator': {
            'get_patient_clinical_context': True,
            'get_care_unit_summary': True,
            'get_device_events_by_patient': True,
            'get_diagnostic_exam_context': True,
            'get_patient_event_timeline': True,
            'get_alarm_context': True,
            'get_imaging_study_summary': True,
            'get_anesthesia_case_context': True,
            'get_neuro_event_context': True,
            'get_cardiology_event_context': True
        }
    }
    
    async def check_tool_permission(self, clinician: dict, tool_name: str):
        """Check if clinician has permission to use tool."""
        
        role = clinician.get('role')
        permissions = self.ROLE_PERMISSIONS.get(role, {})
        
        if not permissions.get(tool_name, False):
            await audit_logger.log_denied_access(clinician['id'], tool_name)
            raise PermissionDeniedError(f"Role {role} cannot access {tool_name}")
    
    async def check_care_unit_access(self, clinician: dict, care_unit_id: str):
        """Check if clinician has access to care unit."""
        
        assigned_units = clinician.get('care_units', [])
        
        if care_unit_id not in assigned_units:
            await audit_logger.log_denied_access(clinician['id'], f"care_unit:{care_unit_id}")
            raise PermissionDeniedError(f"Not assigned to care unit {care_unit_id}")
```

### Patient Consent Checking

```python
# security/consent.py
class ConsentManager:
    async def check_consent(self, patient_id: str, clinician_id: str):
        """Check if patient has consented to data access."""
        
        consent = await db.query(
            "SELECT * FROM patient_consent WHERE patient_id = %s",
            (patient_id,)
        )
        
        if not consent:
            # No consent record - deny access
            return False
        
        consent_data = consent[0]
        
        # Check if consent is active
        if consent_data['status'] != 'active':
            return False
        
        # Check if consent has expired
        if consent_data['expiration_date'] < datetime.now():
            return False
        
        # Check granular consent (e.g., specific care units)
        if consent_data['scope'] == 'specific_care_units':
            clinician = await db.query(
                "SELECT care_units FROM clinicians WHERE id = %s",
                (clinician_id,)
            )
            allowed_units = consent_data['allowed_care_units']
            clinician_units = clinician[0]['care_units']
            
            if not any(unit in allowed_units for unit in clinician_units):
                return False
        
        return True
```

### PHI Masking and Redaction

```python
# security/phi_masking.py
class PHIMaskingEngine:
    async def mask_response(self, response: dict, clinician_role: str):
        """Mask PHI in response based on clinician role."""
        
        if clinician_role == 'administrator':
            # Administrators see full data
            return response
        
        # Mask patient name (show only initials)
        if 'patient' in response and 'name' in response['patient']:
            name = response['patient']['name']
            response['patient']['name'] = self.mask_name(name)
        
        # Mask MRN (show only last 4 digits)
        if 'patient' in response and 'mrn' in response['patient']:
            mrn = response['patient']['mrn']
            response['patient']['mrn'] = f"***{mrn[-4:]}"
        
        # Mask medication names in error messages
        if 'error' in response:
            response['error'] = self.mask_medications(response['error'])
        
        return response
    
    def mask_name(self, name: str) -> str:
        """Mask patient name to initials."""
        parts = name.split()
        return '.'.join([p[0] for p in parts]) + '.'
    
    def mask_medications(self, text: str) -> str:
        """Mask medication names in text."""
        # Replace specific medication names with generic terms
        medications = {
            'Warfarin': 'anticoagulant',
            'Metformin': 'antidiabetic',
            'Lisinopril': 'antihypertensive'
        }
        
        for med, generic in medications.items():
            text = text.replace(med, generic)
        
        return text
```

### Audit Logging Architecture

```python
# security/audit_logger.py
class AuditLogger:
    async def log_tool_call(self, tool_name: str, clinician_id: str, patient_id: str, result: dict):
        """Log MCP tool invocation."""
        
        log_entry = {
            'id': str(uuid.uuid4()),
            'timestamp': datetime.now(),
            'clinician_id': clinician_id,
            'tool_name': tool_name,
            'patient_id': patient_id,
            'action': 'tool_call',
            'parameters': {
                'patient_id': patient_id,
                'tool': tool_name
            },
            'result_summary': f"Retrieved {len(result)} records",
            'ip_address': get_client_ip()
        }
        
        # Store in database
        await db.execute(
            "INSERT INTO audit_logs (id, timestamp, clinician_id, tool_name, patient_id, action, parameters, result_summary, ip_address) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (log_entry['id'], log_entry['timestamp'], log_entry['clinician_id'], 
             log_entry['tool_name'], log_entry['patient_id'], log_entry['action'],
             json.dumps(log_entry['parameters']), log_entry['result_summary'], 
             log_entry['ip_address'])
        )
        
        # Encrypt sensitive fields
        await self.encrypt_audit_log(log_entry['id'])
    
    async def log_denied_access(self, clinician_id: str, resource: str):
        """Log denied access attempt."""
        
        log_entry = {
            'timestamp': datetime.now(),
            'clinician_id': clinician_id,
            'action': 'denied_access',
            'resource': resource,
            'ip_address': get_client_ip()
        }
        
        await db.execute(
            "INSERT INTO audit_logs (timestamp, clinician_id, action, parameters, ip_address) "
            "VALUES (%s, %s, %s, %s, %s)",
            (log_entry['timestamp'], log_entry['clinician_id'], log_entry['action'],
             json.dumps({'resource': resource}), log_entry['ip_address'])
        )
    
    async def encrypt_audit_log(self, log_id: str):
        """Encrypt sensitive audit log fields."""
        
        # Use hospital's encryption key
        encryption_key = os.getenv('AUDIT_LOG_ENCRYPTION_KEY')
        
        # Encrypt patient_id and clinician_id fields
        await db.execute(
            "UPDATE audit_logs SET patient_id = pgp_sym_encrypt(patient_id, %s) "
            "WHERE id = %s",
            (encryption_key, log_id)
        )
```



## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: MCP Protocol Compliance

*For any* MCP tool invocation, the server response SHALL conform to the MCP protocol specification with valid tool definitions and structured JSON responses.

**Validates: Requirements 1.1, 1.2, 1.6**

### Property 2: Client Authentication on Connection

*For any* MCP client connection, the server SHALL authenticate the client identity before allowing tool invocation, rejecting unauthenticated clients.

**Validates: Requirements 1.3, 19.1, 19.2**

### Property 3: Concurrent Request Handling

*For any* set of N concurrent MCP tool requests (where N ≤ 100), the server SHALL process all requests without dropping or corrupting any request.

**Validates: Requirements 1.5, 25.3**

### Property 4: Input Parameter Validation

*For any* MCP tool invocation with invalid parameters (wrong type, out of range, invalid ID), the server SHALL reject the request and return a descriptive error message.

**Validates: Requirements 1.7, 1.8, 23.1, 23.2, 23.3, 23.4**

### Property 5: HL7 Message Parsing Round Trip

*For any* valid HL7 v2 message (ADT, ORU, ORM, MDM), parsing and then re-serializing SHALL produce an equivalent message structure.

**Validates: Requirements 2.5, 2.7**

### Property 6: HL7 Message Rejection on Malformation

*For any* malformed HL7 v2 message, the server SHALL reject the message, log the error, and NOT store corrupted data.

**Validates: Requirements 2.6**

### Property 7: Patient ID Normalization Consistency

*For any* patient referenced by multiple external IDs from different source systems, all references SHALL map to the same internal patient ID.

**Validates: Requirements 2.8, 6.1, 6.6**

### Property 8: FHIR Resource Normalization

*For any* FHIR resource retrieved from a FHIR server, the resource SHALL be normalized to internal data structures and maintain all clinically relevant fields.

**Validates: Requirements 3.9, 3.10**

### Property 9: DICOM Metadata Extraction Completeness

*For any* DICOM study received, the server SHALL extract and store patient ID, study ID, modality, timestamp, and description without loss.

**Validates: Requirements 4.2, 4.4**

### Property 10: Device Data Patient Association

*For any* device telemetry received, the server SHALL correctly associate it with the patient and encounter currently assigned to that device.

**Validates: Requirements 5.6**

### Property 11: Device Data Timestamping

*For any* device telemetry received, the server SHALL add a server-side timestamp, ensuring all observations have consistent, monotonically increasing timestamps.

**Validates: Requirements 5.7**

### Property 12: Abnormal Vital Sign Annotation

*For any* vital sign observation with value outside clinical thresholds, the server SHALL annotate it as abnormal with appropriate severity level.

**Validates: Requirements 7.1, 7.8**

### Property 13: Alarm Event Severity Classification

*For any* alarm event, the server SHALL classify it with a severity level (critical, high, medium, low) based on alarm type and threshold.

**Validates: Requirements 7.2**

### Property 14: Clinical Timeline Chronological Ordering

*For any* patient timeline built from multiple event types, all events SHALL be ordered chronologically by timestamp with no gaps or duplicates.

**Validates: Requirements 8.4**

### Property 15: Patient Clinical Context Completeness

*For any* patient with active encounters, the get_patient_clinical_context tool SHALL return demographics, encounter info, diagnoses, medications, clinicians, devices, and recent events.

**Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 9.9, 9.10**

### Property 16: Care Unit Summary Patient Inclusion

*For any* care unit, the get_care_unit_summary tool SHALL return all active patients in that unit with no omissions.

**Validates: Requirements 10.1**

### Property 17: Critical Patient Identification

*For any* patient with critical alarms or abnormal vitals, the get_care_unit_summary tool SHALL flag that patient as critical.

**Validates: Requirements 10.2**

### Property 18: Role-Based Tool Access Control

*For any* clinician with role R attempting to invoke tool T, the server SHALL allow invocation only if role R has permission for tool T.

**Validates: Requirements 19.5, 19.7**

### Property 19: Care Unit Access Restriction

*For any* clinician attempting to access patient data, the server SHALL deny access if the patient's care unit is not in the clinician's assigned care units.

**Validates: Requirements 19.6**

### Property 20: Unauthorized Access Denial and Logging

*For any* unauthorized access attempt, the server SHALL deny the request and log the attempt with clinician ID, resource, and timestamp.

**Validates: Requirements 19.8, 21.5**

### Property 21: Patient Consent Enforcement

*For any* patient without active consent, the server SHALL deny all data access requests for that patient.

**Validates: Requirements 20.2, 20.3**

### Property 22: Granular Consent Enforcement

*For any* patient with granular consent (e.g., specific care units), the server SHALL enforce the consent scope and deny access outside the scope.

**Validates: Requirements 20.4**

### Property 23: Audit Log Completeness

*For any* MCP tool invocation, the server SHALL create an audit log entry with timestamp, clinician ID, tool name, patient ID, and parameters.

**Validates: Requirements 21.1, 21.2, 21.4, 21.6**

### Property 24: PHI Masking in Logs

*For any* audit log entry, the server SHALL NOT contain full patient names, full MRNs, or full medication names in plaintext.

**Validates: Requirements 22.1, 22.2, 22.3, 22.4**

### Property 25: PHI Masking in Error Messages

*For any* error message returned to a client, the server SHALL mask or redact PHI (patient names, MRNs, medication names).

**Validates: Requirements 22.5**

### Property 26: Audit Log Encryption

*For any* audit log entry stored in the database, sensitive fields (patient_id, clinician_id) SHALL be encrypted at rest.

**Validates: Requirements 22.6**

### Property 27: Database Connection Failure Handling

*For any* database connection failure, the server SHALL handle the error gracefully, return an appropriate HTTP status code, and log the error.

**Validates: Requirements 23.5, 23.7, 23.8**

### Property 28: Referential Integrity Maintenance

*For any* patient record, all associated encounters, observations, and devices SHALL have valid foreign key references to the patient.

**Validates: Requirements 24.1**

### Property 29: Data Consistency Across Sources

*For any* patient data from multiple sources, conflicting values SHALL be detected, logged, and flagged for reconciliation.

**Validates: Requirements 24.2, 24.3**

### Property 30: Query Performance - Patient Context

*For any* patient context query on typical datasets (< 1000 observations), the server SHALL respond within 500ms.

**Validates: Requirements 25.1**

### Property 31: Query Performance - Care Unit Summary

*For any* care unit summary query for units with 50+ patients, the server SHALL respond within 1000ms.

**Validates: Requirements 25.2**

### Property 32: Caching Effectiveness

*For any* frequently accessed patient context, the second and subsequent requests SHALL be served from cache with response time < 50ms.

**Validates: Requirements 25.5**

### Property 33: Database Indexing Effectiveness

*For any* query on indexed columns (patient_id, timestamp, observation_type), the query execution plan SHALL use the index.

**Validates: Requirements 25.6**

### Property 34: Slow Query Logging

*For any* query exceeding 1000ms execution time, the server SHALL log the query with execution time and parameters.

**Validates: Requirements 25.7**

### Property 35: Data Retention Policy

*For any* audit log entry, the server SHALL retain it for a minimum of 7 years from creation date.

**Validates: Requirements 21.9, 26.1**



## Error Handling and Resilience

### Error Classification

```python
# Error types and handling strategies
class MCPError(Exception):
    """Base MCP error"""
    pass

class AuthenticationError(MCPError):
    """Authentication failed"""
    status_code = 401

class AuthorizationError(MCPError):
    """Authorization failed"""
    status_code = 403

class ValidationError(MCPError):
    """Input validation failed"""
    status_code = 400

class ConsentDeniedError(MCPError):
    """Patient consent not provided"""
    status_code = 403

class PatientNotFoundError(MCPError):
    """Patient not found"""
    status_code = 404

class DatabaseError(MCPError):
    """Database operation failed"""
    status_code = 500

class ExternalServiceError(MCPError):
    """External service (FHIR, DICOM) failed"""
    status_code = 503
```

### Retry Logic for Transient Failures

```python
# Retry decorator for transient failures
import asyncio
from functools import wraps

def retry_on_transient_error(max_retries=3, backoff_factor=2):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except (ConnectionError, TimeoutError) as e:
                    if attempt == max_retries - 1:
                        raise
                    
                    wait_time = backoff_factor ** attempt
                    logger.warning(f"Attempt {attempt + 1} failed, retrying in {wait_time}s")
                    await asyncio.sleep(wait_time)
        
        return wrapper
    return decorator

@retry_on_transient_error(max_retries=3)
async def query_fhir_server(resource_type, patient_id):
    # FHIR query with automatic retry
    pass
```

### Circuit Breaker Pattern

```python
# Circuit breaker for external service failures
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half-open
    
    async def call(self, func, *args, **kwargs):
        if self.state == 'open':
            if (datetime.now() - self.last_failure_time).total_seconds() > self.timeout:
                self.state = 'half-open'
            else:
                raise CircuitBreakerOpenError("Circuit breaker is open")
        
        try:
            result = await func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise
    
    def on_success(self):
        self.failure_count = 0
        self.state = 'closed'
    
    def on_failure(self):
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'open'
            logger.error("Circuit breaker opened due to repeated failures")

# Usage
fhir_breaker = CircuitBreaker(failure_threshold=5)

async def get_fhir_patient(patient_id):
    return await fhir_breaker.call(fhir_client.get_patient, patient_id)
```

### Graceful Degradation

```python
# Graceful degradation when services fail
async def get_patient_clinical_context_with_degradation(patient_id):
    context = {
        'patient': None,
        'encounter': None,
        'diagnoses': [],
        'medications': [],
        'devices': [],
        'degraded_services': []
    }
    
    # Try to get patient demographics
    try:
        context['patient'] = await get_patient_demographics(patient_id)
    except Exception as e:
        logger.error(f"Failed to get patient demographics: {e}")
        context['degraded_services'].append('patient_demographics')
    
    # Try to get encounter info
    try:
        context['encounter'] = await get_current_encounter(patient_id)
    except Exception as e:
        logger.error(f"Failed to get encounter: {e}")
        context['degraded_services'].append('encounter')
    
    # Try to get diagnoses
    try:
        context['diagnoses'] = await get_active_diagnoses(patient_id)
    except Exception as e:
        logger.error(f"Failed to get diagnoses: {e}")
        context['degraded_services'].append('diagnoses')
    
    # Return partial context even if some services failed
    return context
```

### Health Check Endpoints

```python
# Health check endpoints for monitoring
@app.get("/health")
async def health_check():
    """Basic health check"""
    return {"status": "healthy"}

@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with component status"""
    
    health = {
        'status': 'healthy',
        'components': {}
    }
    
    # Check database
    try:
        await db.query("SELECT 1")
        health['components']['database'] = 'healthy'
    except Exception as e:
        health['components']['database'] = f'unhealthy: {str(e)}'
        health['status'] = 'degraded'
    
    # Check cache
    try:
        cache.ping()
        health['components']['cache'] = 'healthy'
    except Exception as e:
        health['components']['cache'] = f'unhealthy: {str(e)}'
        health['status'] = 'degraded'
    
    # Check FHIR server
    try:
        await fhir_client.health_check()
        health['components']['fhir_server'] = 'healthy'
    except Exception as e:
        health['components']['fhir_server'] = f'unhealthy: {str(e)}'
        health['status'] = 'degraded'
    
    return health
```

## Testing Strategy

### Unit Testing Approach

Unit tests verify specific examples, edge cases, and error conditions:

```python
# tests/test_patient_context.py
import pytest
from tools.patient_context import get_patient_clinical_context

@pytest.mark.asyncio
async def test_patient_context_returns_demographics():
    """Test that patient context includes demographics"""
    patient_id = "PAT-123"
    context = await get_patient_clinical_context(patient_id)
    
    assert context['patient'] is not None
    assert 'mrn' in context['patient']
    assert 'name' in context['patient']

@pytest.mark.asyncio
async def test_patient_context_with_invalid_patient_id():
    """Test that invalid patient ID raises error"""
    with pytest.raises(PatientNotFoundError):
        await get_patient_clinical_context("INVALID-ID")

@pytest.mark.asyncio
async def test_patient_context_respects_care_unit_access():
    """Test that clinician can only access assigned care units"""
    clinician = {'id': 'CLIN-1', 'care_units': ['cardiology']}
    patient_id = "PAT-123"  # Patient in neurology
    
    with pytest.raises(AuthorizationError):
        await get_patient_clinical_context(patient_id, clinician)
```

### Property-Based Testing Approach

Property tests verify universal properties across all inputs using hypothesis:

```python
# tests/test_properties.py
from hypothesis import given, strategies as st
import pytest

# Property 1: MCP Protocol Compliance
@given(
    tool_name=st.sampled_from([
        'get_patient_clinical_context',
        'get_care_unit_summary',
        'get_device_events_by_patient'
    ]),
    patient_id=st.text(min_size=1, max_size=50)
)
@pytest.mark.asyncio
async def test_mcp_protocol_compliance(tool_name, patient_id):
    """
    Feature: hospital-clinical-mcp, Property 1: MCP Protocol Compliance
    For any MCP tool invocation, the server response SHALL conform to MCP protocol
    """
    response = await invoke_mcp_tool(tool_name, {'patient_id': patient_id})
    
    # Verify response is valid JSON
    assert isinstance(response, dict)
    
    # Verify response has required fields
    assert 'status' in response or 'error' in response

# Property 4: Input Parameter Validation
@given(
    patient_id=st.one_of(
        st.none(),
        st.integers(),
        st.text(max_size=0),
        st.text(min_size=1000)
    )
)
@pytest.mark.asyncio
async def test_input_parameter_validation(patient_id):
    """
    Feature: hospital-clinical-mcp, Property 4: Input Parameter Validation
    For any MCP tool invocation with invalid parameters, the server SHALL reject
    """
    with pytest.raises((ValidationError, TypeError)):
        await get_patient_clinical_context(patient_id)

# Property 7: Patient ID Normalization Consistency
@given(
    external_ids=st.lists(
        st.tuples(st.text(min_size=1), st.text(min_size=1)),
        min_size=2,
        max_size=5
    )
)
@pytest.mark.asyncio
async def test_patient_id_normalization_consistency(external_ids):
    """
    Feature: hospital-clinical-mcp, Property 7: Patient ID Normalization Consistency
    For any patient referenced by multiple external IDs, all references SHALL map
    to the same internal patient ID
    """
    internal_ids = []
    
    for external_id, source_system in external_ids:
        internal_id = await id_mapper.get_internal_patient_id(external_id, source_system)
        internal_ids.append(internal_id)
    
    # All internal IDs should be the same
    assert len(set(internal_ids)) == 1

# Property 14: Clinical Timeline Chronological Ordering
@given(
    events=st.lists(
        st.fixed_dictionaries({
            'timestamp': st.datetimes(),
            'event_type': st.sampled_from(['observation', 'alarm', 'medication']),
            'value': st.integers()
        }),
        min_size=1,
        max_size=100
    )
)
@pytest.mark.asyncio
async def test_clinical_timeline_chronological_ordering(events):
    """
    Feature: hospital-clinical-mcp, Property 14: Clinical Timeline Chronological Ordering
    For any patient timeline, all events SHALL be ordered chronologically
    """
    patient_id = "PAT-TEST"
    
    # Store events
    for event in events:
        await store_event(patient_id, event)
    
    # Retrieve timeline
    timeline = await timeline_builder.build_patient_timeline(
        patient_id,
        datetime.min,
        datetime.max
    )
    
    # Verify chronological ordering
    timestamps = [e['timestamp'] for e in timeline]
    assert timestamps == sorted(timestamps)

# Property 30: Query Performance - Patient Context
@given(
    num_observations=st.integers(min_value=1, max_value=1000)
)
@pytest.mark.asyncio
async def test_query_performance_patient_context(num_observations):
    """
    Feature: hospital-clinical-mcp, Property 30: Query Performance - Patient Context
    For any patient context query on typical datasets, the server SHALL respond
    within 500ms
    """
    patient_id = "PAT-PERF-TEST"
    
    # Create test data
    for i in range(num_observations):
        await create_observation(patient_id, {
            'type': 'vital_sign',
            'value': 100 + i
        })
    
    # Measure query time
    start_time = time.time()
    context = await get_patient_clinical_context(patient_id)
    elapsed_time = (time.time() - start_time) * 1000  # Convert to ms
    
    # Verify performance
    assert elapsed_time < 500, f"Query took {elapsed_time}ms, expected < 500ms"
```

### Integration Testing

Integration tests verify data ingestion and retrieval workflows:

```python
# tests/test_integration.py
@pytest.mark.asyncio
async def test_hl7_ingestion_to_retrieval():
    """Test complete HL7 ingestion and retrieval workflow"""
    
    # Create HL7 ADT message
    hl7_message = create_hl7_adt_message(
        patient_id="12345",
        patient_name="John Doe",
        care_unit="Cardiology"
    )
    
    # Send to HL7 listener
    await hl7_listener.process_message(hl7_message)
    
    # Retrieve patient context
    context = await get_patient_clinical_context("PAT-12345")
    
    # Verify data was ingested and normalized
    assert context['patient']['name'] == "John Doe"
    assert context['encounter']['care_unit'] == "cardiology"

@pytest.mark.asyncio
async def test_fhir_ingestion_to_retrieval():
    """Test complete FHIR ingestion and retrieval workflow"""
    
    # Mock FHIR server response
    fhir_patient = {
        'resourceType': 'Patient',
        'id': 'fhir-123',
        'name': [{'given': ['Jane'], 'family': 'Smith'}]
    }
    
    # Retrieve from FHIR
    await fhir_client.retrieve_patient("fhir-123")
    
    # Verify data was normalized
    patient = await db.query("SELECT * FROM patients WHERE mrn = %s", ("fhir-123",))
    assert patient[0]['first_name'] == "Jane"
```

### End-to-End Testing

End-to-end tests verify complete MCP tool workflows:

```python
# tests/test_e2e.py
@pytest.mark.asyncio
async def test_e2e_patient_context_workflow():
    """Test complete patient context retrieval workflow"""
    
    # Setup: Create test patient with data
    patient_id = await create_test_patient("John Doe")
    encounter_id = await create_test_encounter(patient_id, "Cardiology")
    await create_test_observations(patient_id, encounter_id, 10)
    await create_test_medications(patient_id, encounter_id, 3)
    
    # Execute: Retrieve patient context
    context = await get_patient_clinical_context(patient_id)
    
    # Verify: All expected data is present
    assert context['patient']['id'] == patient_id
    assert len(context['observations']) == 10
    assert len(context['medications']) == 3
    assert context['confidence_score'] > 0.8
```



## Deployment Architecture

### Docker Containerization

```dockerfile
# Dockerfile for MCP Server
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Kubernetes Deployment

```yaml
# kubernetes/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-server
  namespace: clinical-intelligence
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mcp-server
  template:
    metadata:
      labels:
        app: mcp-server
    spec:
      containers:
      - name: mcp-server
        image: hospital/mcp-server:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: mcp-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: mcp-secrets
              key: redis-url
        - name: FHIR_SERVER_URL
          valueFrom:
            configMapKeyRef:
              name: mcp-config
              key: fhir-server-url
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health/detailed
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10

---
apiVersion: v1
kind: Service
metadata:
  name: mcp-server-service
  namespace: clinical-intelligence
spec:
  selector:
    app: mcp-server
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: mcp-server-hpa
  namespace: clinical-intelligence
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: mcp-server
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Database Deployment

```yaml
# kubernetes/postgres-deployment.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-pvc
  namespace: clinical-intelligence
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 500Gi

---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: clinical-intelligence
spec:
  serviceName: postgres
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15-alpine
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_DB
          value: clinical_intelligence
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-secrets
              key: password
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
      volumes:
      - name: postgres-storage
        persistentVolumeClaim:
          claimName: postgres-pvc
```

### Message Queue Deployment

```yaml
# kubernetes/rabbitmq-deployment.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: rabbitmq
  namespace: clinical-intelligence
spec:
  serviceName: rabbitmq
  replicas: 3
  selector:
    matchLabels:
      app: rabbitmq
  template:
    metadata:
      labels:
        app: rabbitmq
    spec:
      containers:
      - name: rabbitmq
        image: rabbitmq:3.12-management-alpine
        ports:
        - containerPort: 5672
        - containerPort: 15672
        env:
        - name: RABBITMQ_DEFAULT_USER
          valueFrom:
            secretKeyRef:
              name: rabbitmq-secrets
              key: username
        - name: RABBITMQ_DEFAULT_PASS
          valueFrom:
            secretKeyRef:
              name: rabbitmq-secrets
              key: password
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
```

### Monitoring and Logging Infrastructure

```yaml
# kubernetes/monitoring.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
  namespace: clinical-intelligence
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
    scrape_configs:
    - job_name: 'mcp-server'
      static_configs:
      - targets: ['mcp-server-service:8000']

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prometheus
  namespace: clinical-intelligence
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prometheus
  template:
    metadata:
      labels:
        app: prometheus
    spec:
      containers:
      - name: prometheus
        image: prom/prometheus:latest
        ports:
        - containerPort: 9090
        volumeMounts:
        - name: config
          mountPath: /etc/prometheus
      volumes:
      - name: config
        configMap:
          name: prometheus-config

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: grafana
  namespace: clinical-intelligence
spec:
  replicas: 1
  selector:
    matchLabels:
      app: grafana
  template:
    metadata:
      labels:
        app: grafana
    spec:
      containers:
      - name: grafana
        image: grafana/grafana:latest
        ports:
        - containerPort: 3000
        env:
        - name: GF_SECURITY_ADMIN_PASSWORD
          valueFrom:
            secretKeyRef:
              name: grafana-secrets
              key: admin-password
```

## Implementation Roadmap

### Phase 1: MCP Server Skeleton and Basic Tools (Weeks 1-4)

**Deliverables:**
- FastAPI application with MCP protocol implementation
- Basic authentication and authorization framework
- 3 core MCP tools: get_patient_clinical_context, get_care_unit_summary, get_device_events_by_patient
- Test data generation and simulation
- Unit test framework

**Tasks:**
- Set up FastAPI project structure
- Implement MCP protocol handlers
- Create basic tool definitions and schemas
- Implement JWT authentication
- Create test data generators
- Write unit tests for core functionality

### Phase 2: Data Ingestion and Persistent Storage (Weeks 5-8)

**Deliverables:**
- HL7 v2 listener and parser
- FHIR client for resource retrieval
- DICOM metadata listener
- Device telemetry connector
- PostgreSQL database with schema
- Data normalization and mapping layer
- Message queue for asynchronous processing

**Tasks:**
- Implement HL7 v2 TCP listener with MLLP framing
- Implement FHIR client with pagination and error handling
- Implement DICOM C-STORE handler
- Implement device telemetry connectors
- Create database schema and migrations
- Implement ID mapping and consolidation
- Set up RabbitMQ for message queuing
- Write integration tests

### Phase 3: Clinical Context Engine and Remaining Tools (Weeks 9-12)

**Deliverables:**
- Clinical context engine with event classification and timeline building
- Annotation engine with confidence scoring
- Remaining 7 MCP tools
- Redis caching layer
- Performance optimization

**Tasks:**
- Implement event classifier
- Implement timeline builder
- Implement annotation engine
- Implement confidence scorer
- Implement remaining tools (diagnostic exam, timeline, alarm, imaging, anesthesia, neuro, cardiology)
- Implement Redis caching
- Optimize database queries and indexes
- Write property-based tests

### Phase 4: Production Security, RBAC, and Hospital Integration (Weeks 13-16)

**Deliverables:**
- Production authentication (OAuth2/LDAP integration)
- Role-based access control (RBAC)
- Patient consent management
- Comprehensive audit logging
- PHI masking and encryption
- Kubernetes deployment configuration
- Monitoring and alerting
- Documentation and training materials

**Tasks:**
- Integrate with hospital identity provider
- Implement RBAC engine
- Implement consent checking
- Implement audit logging with encryption
- Implement PHI masking
- Create Kubernetes deployment manifests
- Set up Prometheus and Grafana monitoring
- Write end-to-end tests
- Create API documentation
- Create deployment and operations guides

## Folder Structure

```
hospital-clinical-mcp/
├── README.md
├── requirements.txt
├── setup.py
├── docker-compose.yml
│
├── src/
│   ├── main.py                          # FastAPI app entry point
│   ├── config.py                        # Configuration management
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health.py                    # Health check endpoints
│   │   ├── mcp_tools.py                 # MCP tool endpoints
│   │   └── admin.py                     # Admin endpoints
│   │
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── hl7_listener.py              # HL7 v2 TCP listener
│   │   ├── hl7_parser.py                # HL7 message parsing
│   │   ├── fhir_client.py               # FHIR API client
│   │   ├── dicom_listener.py            # DICOM metadata listener
│   │   └── device_connector.py          # Device telemetry connector
│   │
│   ├── normalization/
│   │   ├── __init__.py
│   │   ├── id_mapper.py                 # ID mapping
│   │   ├── care_unit_mapper.py          # Care unit mapping
│   │   ├── clinician_mapper.py          # Clinician mapping
│   │   ├── data_normalizer.py           # Data normalization
│   │   └── consolidation.py             # Data consolidation
│   │
│   ├── context_engine/
│   │   ├── __init__.py
│   │   ├── event_classifier.py          # Event classification
│   │   ├── timeline_builder.py          # Timeline construction
│   │   ├── annotation_engine.py         # Data annotation
│   │   ├── confidence_scorer.py         # Confidence scoring
│   │   ├── diagnosis_context.py         # Diagnosis context
│   │   ├── exam_context.py              # Exam context
│   │   ├── procedure_context.py         # Procedure context
│   │   └── alarm_context.py             # Alarm context
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── patient_context.py           # get_patient_clinical_context
│   │   ├── care_unit_summary.py         # get_care_unit_summary
│   │   ├── device_events.py             # get_device_events_by_patient
│   │   ├── diagnostic_exam.py           # get_diagnostic_exam_context
│   │   ├── event_timeline.py            # get_patient_event_timeline
│   │   ├── alarm_context.py             # get_alarm_context
│   │   ├── imaging_summary.py           # get_imaging_study_summary
│   │   ├── anesthesia_context.py        # get_anesthesia_case_context
│   │   ├── neuro_context.py             # get_neuro_event_context
│   │   └── cardiology_context.py        # get_cardiology_event_context
│   │
│   ├── security/
│   │   ├── __init__.py
│   │   ├── auth.py                      # Authentication
│   │   ├── rbac.py                      # Role-based access control
│   │   ├── consent.py                   # Patient consent
│   │   ├── phi_masking.py               # PHI masking
│   │   └── audit_logger.py              # Audit logging
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py                  # SQLAlchemy models
│   │   ├── schemas.py                   # Pydantic schemas
│   │   └── enums.py                     # Enumerations
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py                # Database connection
│   │   ├── cache.py                     # Redis cache
│   │   └── migrations/                  # Alembic migrations
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logger.py                    # Logging configuration
│       ├── validators.py                # Input validators
│       └── helpers.py                   # Utility functions
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                      # Pytest configuration
│   ├── test_unit/
│   │   ├── test_auth.py
│   │   ├── test_patient_context.py
│   │   ├── test_care_unit_summary.py
│   │   └── ...
│   ├── test_integration/
│   │   ├── test_hl7_ingestion.py
│   │   ├── test_fhir_ingestion.py
│   │   └── ...
│   ├── test_properties/
│   │   ├── test_protocol_compliance.py
│   │   ├── test_data_normalization.py
│   │   ├── test_performance.py
│   │   └── ...
│   └── test_e2e/
│       ├── test_patient_workflow.py
│       └── ...
│
├── database/
│   ├── migrations/
│   │   ├── versions/
│   │   │   ├── 001_initial_schema.py
│   │   │   ├── 002_add_audit_logs.py
│   │   │   └── ...
│   │   └── env.py
│   └── schema.sql
│
├── kubernetes/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── postgres-deployment.yaml
│   ├── rabbitmq-deployment.yaml
│   ├── monitoring.yaml
│   └── secrets.yaml
│
├── docs/
│   ├── API.md                           # API documentation
│   ├── DEPLOYMENT.md                    # Deployment guide
│   ├── OPERATIONS.md                    # Operations guide
│   ├── SECURITY.md                      # Security documentation
│   ├── ARCHITECTURE.md                  # Architecture documentation
│   └── TROUBLESHOOTING.md               # Troubleshooting guide
│
└── .github/
    └── workflows/
        ├── test.yml                     # Test workflow
        ├── build.yml                    # Build workflow
        └── deploy.yml                   # Deploy workflow
```

## Summary

This comprehensive technical design provides a complete blueprint for implementing the Hospital Clinical Intelligence MCP Platform. The system is designed to:

1. **Ingest** clinical data from multiple sources (HL7, FHIR, DICOM, devices)
2. **Normalize** data across different source systems and identifiers
3. **Contextualize** clinical information through event classification and timeline building
4. **Retrieve** data securely through 10 specialized MCP tools
5. **Protect** patient privacy through authentication, authorization, consent checking, and audit logging
6. **Perform** efficiently with caching, indexing, and optimized queries
7. **Scale** horizontally through containerization and Kubernetes orchestration

The design emphasizes security, reliability, and performance while maintaining clinical accuracy and data integrity. The 35 correctness properties provide comprehensive coverage of functional and non-functional requirements, enabling property-based testing to verify system behavior across diverse inputs and scenarios.

