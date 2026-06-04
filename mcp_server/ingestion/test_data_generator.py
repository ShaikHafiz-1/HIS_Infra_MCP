"""
Test data generator for Hospital Clinical Intelligence MCP Platform.

This module provides generators for realistic test data including:
- Patient demographics
- Encounter records
- Medical devices
- HL7 v2 messages
- Device telemetry data
"""

import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import faker

# Initialize faker for realistic data generation
fake = faker.Faker()


class PatientDataGenerator:
    """Generate realistic patient demographic data."""

    GENDERS = ["M", "F", "Other"]
    BLOOD_TYPES = ["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"]

    @staticmethod
    def generate_patient() -> Dict:
        """Generate a single patient record."""
        patient_id = str(uuid.uuid4())
        mrn = f"MRN{random.randint(100000, 999999)}"
        
        return {
            "id": patient_id,
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "mrn": mrn,
            "date_of_birth": fake.date_of_birth(minimum_age=18, maximum_age=95),
            "gender": random.choice(PatientDataGenerator.GENDERS),
            "phone": fake.phone_number(),
            "email": fake.email(),
            "address": fake.address(),
            "is_active": True,
            "is_deleted": False,
        }

    @staticmethod
    def generate_patients(count: int = 50) -> List[Dict]:
        """Generate multiple patient records."""
        return [PatientDataGenerator.generate_patient() for _ in range(count)]


class EncounterDataGenerator:
    """Generate realistic encounter records."""

    ENCOUNTER_TYPES = ["admission", "transfer", "discharge", "observation"]
    CHIEF_COMPLAINTS = [
        "Chest pain",
        "Shortness of breath",
        "Fever",
        "Abdominal pain",
        "Headache",
        "Dizziness",
        "Nausea",
        "Cough",
    ]
    DIAGNOSES = [
        "Hypertension",
        "Diabetes",
        "Pneumonia",
        "Acute coronary syndrome",
        "Sepsis",
        "Acute kidney injury",
        "Congestive heart failure",
        "Atrial fibrillation",
    ]

    @staticmethod
    def generate_encounter(patient_id: str, care_unit_id: str) -> Dict:
        """Generate a single encounter record."""
        admission_time = datetime.now(timezone.utc) - timedelta(days=random.randint(0, 30))
        discharge_time = None
        is_active = random.choice([True, False])
        
        if not is_active:
            discharge_time = admission_time + timedelta(
                hours=random.randint(1, 168)
            )
        
        return {
            "id": str(uuid.uuid4()),
            "patient_id": patient_id,
            "care_unit_id": care_unit_id,
            "encounter_type": random.choice(EncounterDataGenerator.ENCOUNTER_TYPES),
            "admission_time": admission_time,
            "discharge_time": discharge_time,
            "is_active": is_active,
            "chief_complaint": random.choice(EncounterDataGenerator.CHIEF_COMPLAINTS),
            "admission_diagnosis": random.choice(EncounterDataGenerator.DIAGNOSES),
            "discharge_diagnosis": random.choice(EncounterDataGenerator.DIAGNOSES)
            if discharge_time
            else None,
            "is_deleted": False,
        }

    @staticmethod
    def generate_encounters(
        patient_ids: List[str], care_unit_ids: List[str], count: int = 150
    ) -> List[Dict]:
        """Generate multiple encounter records."""
        encounters = []
        for _ in range(count):
            patient_id = random.choice(patient_ids)
            care_unit_id = random.choice(care_unit_ids)
            encounters.append(
                EncounterDataGenerator.generate_encounter(patient_id, care_unit_id)
            )
        return encounters


class DeviceDataGenerator:
    """Generate realistic medical device records."""

    DEVICE_TYPES = [
        "ECG Monitor",
        "Ventilator",
        "Infusion Pump",
        "Pulse Oximeter",
        "Blood Pressure Monitor",
        "Dialysis Machine",
        "Defibrillator",
        "Ultrasound Machine",
    ]
    MANUFACTURERS = [
        "Philips",
        "GE Healthcare",
        "Siemens",
        "Medtronic",
        "Abbott",
        "Baxter",
    ]
    CALIBRATION_STATUSES = ["calibrated", "needs_calibration", "out_of_service"]

    @staticmethod
    def generate_device(encounter_id: Optional[str] = None) -> Dict:
        """Generate a single device record."""
        device_type = random.choice(DeviceDataGenerator.DEVICE_TYPES)
        
        return {
            "id": str(uuid.uuid4()),
            "encounter_id": encounter_id,
            "device_type": device_type,
            "device_name": f"{device_type} #{random.randint(1, 100)}",
            "serial_number": f"SN{random.randint(100000, 999999)}",
            "manufacturer": random.choice(DeviceDataGenerator.MANUFACTURERS),
            "model": f"Model-{random.randint(1000, 9999)}",
            "location": f"Room {random.randint(101, 599)}",
            "is_online": random.choice([True, False]),
            "battery_level": random.uniform(20, 100) if random.choice([True, False]) else None,
            "calibration_status": random.choice(
                DeviceDataGenerator.CALIBRATION_STATUSES
            ),
            "is_active": True,
            "is_deleted": False,
        }

    @staticmethod
    def generate_devices(encounter_ids: List[str], count: int = 250) -> List[Dict]:
        """Generate multiple device records."""
        devices = []
        for _ in range(count):
            encounter_id = random.choice(encounter_ids) if encounter_ids else None
            devices.append(DeviceDataGenerator.generate_device(encounter_id))
        return devices


class HL7MessageGenerator:
    """Generate sample HL7 v2 messages for testing."""

    @staticmethod
    def generate_adt_message(
        patient_id: str, mrn: str, care_unit: str, event_type: str = "A01"
    ) -> str:
        """Generate HL7 ADT (Admission/Discharge/Transfer) message."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        message_id = str(uuid.uuid4())[:8]
        
        hl7_message = (
            f"MSH|^~\\&|EHR|HOSPITAL|MCP|RECEIVER|{timestamp}||ADT^{event_type}|{message_id}|P|2.5\r"
            f"EVN|{event_type}|{timestamp}\r"
            f"PID|1||{mrn}^^^HOSPITAL||{fake.last_name()}^{fake.first_name()}||"
            f"{fake.date_of_birth(minimum_age=18, maximum_age=95).strftime('%Y%m%d')}|"
            f"{random.choice(['M', 'F'])}|||{fake.address()}\r"
            f"PV1|1|I|{care_unit}^{random.randint(1, 10)}^1|H|||{random.randint(1000, 9999)}|"
            f"ADMIT|A|{timestamp}\r"
        )
        
        return hl7_message

    @staticmethod
    def generate_oru_message(
        patient_id: str, mrn: str, test_name: str = "Glucose"
    ) -> str:
        """Generate HL7 ORU (Observation Result) message."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        message_id = str(uuid.uuid4())[:8]
        
        hl7_message = (
            f"MSH|^~\\&|LAB|HOSPITAL|MCP|RECEIVER|{timestamp}||ORU^R01|{message_id}|P|2.5\r"
            f"PID|1||{mrn}^^^HOSPITAL||{fake.last_name()}^{fake.first_name()}||"
            f"{fake.date_of_birth(minimum_age=18, maximum_age=95).strftime('%Y%m%d')}|"
            f"{random.choice(['M', 'F'])}\r"
            f"OBR|1|{random.randint(100000, 999999)}|{random.randint(100000, 999999)}|"
            f"2345-7^{test_name}^LN\r"
            f"OBX|1|NM|2345-7^{test_name}^LN||{random.randint(70, 150)}|mg/dL|70-100|"
            f"{'H' if random.choice([True, False]) else 'N'}|||F\r"
        )
        
        return hl7_message

    @staticmethod
    def generate_orm_message(
        patient_id: str, mrn: str, medication: str = "Aspirin"
    ) -> str:
        """Generate HL7 ORM (Order) message."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        message_id = str(uuid.uuid4())[:8]
        
        hl7_message = (
            f"MSH|^~\\&|PHARMACY|HOSPITAL|MCP|RECEIVER|{timestamp}||ORM^O01|{message_id}|P|2.5\r"
            f"PID|1||{mrn}^^^HOSPITAL||{fake.last_name()}^{fake.first_name()}||"
            f"{fake.date_of_birth(minimum_age=18, maximum_age=95).strftime('%Y%m%d')}|"
            f"{random.choice(['M', 'F'])}\r"
            f"ORC|NW|{random.randint(100000, 999999)}|{random.randint(100000, 999999)}|"
            f"IP|CM|||||{timestamp}\r"
            f"RXO|{medication}^{medication}^NDC||500|mg|PO|BID\r"
        )
        
        return hl7_message

    @staticmethod
    def generate_mdm_message(
        patient_id: str, mrn: str, note_type: str = "Discharge Summary"
    ) -> str:
        """Generate HL7 MDM (Medical Document Management) message."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        message_id = str(uuid.uuid4())[:8]
        
        hl7_message = (
            f"MSH|^~\\&|EHR|HOSPITAL|MCP|RECEIVER|{timestamp}||MDM^T02|{message_id}|P|2.5\r"
            f"EVN|T02|{timestamp}\r"
            f"PID|1||{mrn}^^^HOSPITAL||{fake.last_name()}^{fake.first_name()}||"
            f"{fake.date_of_birth(minimum_age=18, maximum_age=95).strftime('%Y%m%d')}|"
            f"{random.choice(['M', 'F'])}\r"
            f"TXA|1|{note_type}|PA|{timestamp}|{timestamp}|{timestamp}|"
            f"AU|{random.randint(1000, 9999)}|{note_type}\r"
        )
        
        return hl7_message

    @staticmethod
    def generate_hl7_messages(
        patient_ids: List[str], mrns: List[str], count: int = 100
    ) -> List[str]:
        """Generate multiple HL7 messages."""
        messages = []
        message_types = [
            ("ADT", HL7MessageGenerator.generate_adt_message),
            ("ORU", HL7MessageGenerator.generate_oru_message),
            ("ORM", HL7MessageGenerator.generate_orm_message),
            ("MDM", HL7MessageGenerator.generate_mdm_message),
        ]
        
        for _ in range(count):
            msg_type, generator = random.choice(message_types)
            patient_id = random.choice(patient_ids)
            mrn = random.choice(mrns)
            
            if msg_type == "ADT":
                msg = generator(patient_id, mrn, f"UNIT-{random.randint(1, 8)}")
            else:
                msg = generator(patient_id, mrn)
            
            messages.append(msg)
        
        return messages


class DeviceTelemetrySimulator:
    """Generate realistic device telemetry data."""

    VITAL_SIGNS = {
        "heart_rate": {"min": 40, "max": 150, "unit": "bpm"},
        "systolic_bp": {"min": 80, "max": 200, "unit": "mmHg"},
        "diastolic_bp": {"min": 40, "max": 120, "unit": "mmHg"},
        "spo2": {"min": 85, "max": 100, "unit": "%"},
        "respiratory_rate": {"min": 8, "max": 40, "unit": "breaths/min"},
        "temperature": {"min": 35.0, "max": 40.0, "unit": "°C"},
    }

    ALARM_TYPES = [
        "low_spo2",
        "high_heart_rate",
        "low_heart_rate",
        "high_bp",
        "low_bp",
        "high_temperature",
        "low_temperature",
        "apnea",
    ]

    @staticmethod
    def generate_vital_signs() -> Dict:
        """Generate a single set of vital signs."""
        vitals = {}
        for vital_name, config in DeviceTelemetrySimulator.VITAL_SIGNS.items():
            vitals[vital_name] = random.uniform(config["min"], config["max"])
        return vitals

    @staticmethod
    def generate_vital_signs_series(
        count: int = 100, interval_seconds: int = 60
    ) -> List[Dict]:
        """Generate a series of vital signs over time (newest to oldest)."""
        series = []
        base_time = datetime.now(timezone.utc)
        
        for i in range(count):
            # Generate timestamps in descending order (newest first)
            timestamp = base_time - timedelta(seconds=interval_seconds * i)
            vitals = DeviceTelemetrySimulator.generate_vital_signs()
            vitals["timestamp"] = timestamp
            series.append(vitals)
        
        return series

    @staticmethod
    def generate_alarm_event(device_id: str, patient_id: str) -> Dict:
        """Generate a single alarm event."""
        alarm_type = random.choice(DeviceTelemetrySimulator.ALARM_TYPES)
        severity_map = {
            "low_spo2": "critical",
            "high_heart_rate": "high",
            "low_heart_rate": "high",
            "high_bp": "medium",
            "low_bp": "high",
            "high_temperature": "medium",
            "low_temperature": "medium",
            "apnea": "critical",
        }
        
        return {
            "id": str(uuid.uuid4()),
            "device_id": device_id,
            "patient_id": patient_id,
            "alarm_type": alarm_type,
            "severity": severity_map.get(alarm_type, "medium"),
            "threshold": random.uniform(50, 150),
            "timestamp": datetime.now(timezone.utc),
            "acknowledged": random.choice([True, False]),
        }

    @staticmethod
    def generate_alarm_events(
        device_ids: List[str], patient_ids: List[str], count: int = 50
    ) -> List[Dict]:
        """Generate multiple alarm events."""
        alarms = []
        for _ in range(count):
            device_id = random.choice(device_ids)
            patient_id = random.choice(patient_ids)
            alarms.append(
                DeviceTelemetrySimulator.generate_alarm_event(device_id, patient_id)
            )
        return alarms

