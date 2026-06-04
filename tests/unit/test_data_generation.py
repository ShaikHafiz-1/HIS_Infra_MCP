"""
Unit tests for test data generation module.

Tests cover:
- Patient data generation
- Encounter data generation
- Device data generation
- HL7 message generation
- Device telemetry simulation
"""

import pytest
from datetime import datetime, timedelta
from mcp_server.ingestion.test_data_generator import (
    PatientDataGenerator,
    EncounterDataGenerator,
    DeviceDataGenerator,
    HL7MessageGenerator,
    DeviceTelemetrySimulator,
)


class TestPatientDataGenerator:
    """Test patient data generation."""

    def test_generate_single_patient(self):
        """Test generating a single patient record."""
        patient = PatientDataGenerator.generate_patient()
        
        # Verify required fields
        assert "id" in patient
        assert "first_name" in patient
        assert "last_name" in patient
        assert "mrn" in patient
        assert "date_of_birth" in patient
        assert "gender" in patient
        
        # Verify field types
        assert isinstance(patient["id"], str)
        assert isinstance(patient["first_name"], str)
        assert isinstance(patient["last_name"], str)
        assert isinstance(patient["mrn"], str)
        assert isinstance(patient["gender"], str)
        
        # Verify field values
        assert len(patient["id"]) > 0
        assert len(patient["first_name"]) > 0
        assert len(patient["last_name"]) > 0
        assert patient["mrn"].startswith("MRN")
        assert patient["gender"] in ["M", "F", "Other"]
        assert patient["is_active"] is True
        assert patient["is_deleted"] is False

    def test_generate_multiple_patients(self):
        """Test generating multiple patient records."""
        count = 10
        patients = PatientDataGenerator.generate_patients(count)
        
        assert len(patients) == count
        
        # Verify all patients have unique IDs and MRNs
        ids = [p["id"] for p in patients]
        mrns = [p["mrn"] for p in patients]
        
        assert len(set(ids)) == count
        assert len(set(mrns)) == count

    def test_patient_data_consistency(self):
        """Test that patient data is consistent and realistic."""
        patient = PatientDataGenerator.generate_patient()
        
        # Verify email format
        assert "@" in patient["email"]
        
        # Verify phone format
        assert len(patient["phone"]) > 0
        
        # Verify address exists
        assert len(patient["address"]) > 0


class TestEncounterDataGenerator:
    """Test encounter data generation."""

    def test_generate_single_encounter(self):
        """Test generating a single encounter record."""
        patient_id = "PAT-123"
        care_unit_id = "UNIT-456"
        
        encounter = EncounterDataGenerator.generate_encounter(patient_id, care_unit_id)
        
        # Verify required fields
        assert "id" in encounter
        assert "patient_id" in encounter
        assert "care_unit_id" in encounter
        assert "encounter_type" in encounter
        assert "admission_time" in encounter
        assert "is_active" in encounter
        
        # Verify field values
        assert encounter["patient_id"] == patient_id
        assert encounter["care_unit_id"] == care_unit_id
        assert encounter["encounter_type"] in EncounterDataGenerator.ENCOUNTER_TYPES
        assert isinstance(encounter["admission_time"], datetime)
        assert isinstance(encounter["is_active"], bool)

    def test_encounter_discharge_time_logic(self):
        """Test that discharge time is only set when encounter is inactive."""
        patient_id = "PAT-123"
        care_unit_id = "UNIT-456"
        
        # Generate multiple encounters and check discharge logic
        for _ in range(10):
            encounter = EncounterDataGenerator.generate_encounter(patient_id, care_unit_id)
            
            if encounter["is_active"]:
                assert encounter["discharge_time"] is None
            else:
                assert encounter["discharge_time"] is not None
                assert encounter["discharge_time"] > encounter["admission_time"]

    def test_generate_multiple_encounters(self):
        """Test generating multiple encounter records."""
        patient_ids = ["PAT-1", "PAT-2", "PAT-3"]
        care_unit_ids = ["UNIT-1", "UNIT-2"]
        count = 20
        
        encounters = EncounterDataGenerator.generate_encounters(
            patient_ids, care_unit_ids, count
        )
        
        assert len(encounters) == count
        
        # Verify all encounters have unique IDs
        ids = [e["id"] for e in encounters]
        assert len(set(ids)) == count
        
        # Verify encounters reference valid patients and care units
        for encounter in encounters:
            assert encounter["patient_id"] in patient_ids
            assert encounter["care_unit_id"] in care_unit_ids


class TestDeviceDataGenerator:
    """Test device data generation."""

    def test_generate_single_device(self):
        """Test generating a single device record."""
        device = DeviceDataGenerator.generate_device()
        
        # Verify required fields
        assert "id" in device
        assert "device_type" in device
        assert "device_name" in device
        assert "manufacturer" in device
        assert "is_online" in device
        assert "calibration_status" in device
        
        # Verify field values
        assert device["device_type"] in DeviceDataGenerator.DEVICE_TYPES
        assert device["manufacturer"] in DeviceDataGenerator.MANUFACTURERS
        assert device["calibration_status"] in DeviceDataGenerator.CALIBRATION_STATUSES
        assert isinstance(device["is_online"], bool)

    def test_generate_device_with_encounter(self):
        """Test generating a device associated with an encounter."""
        encounter_id = "ENC-123"
        device = DeviceDataGenerator.generate_device(encounter_id)
        
        assert device["encounter_id"] == encounter_id

    def test_generate_multiple_devices(self):
        """Test generating multiple device records."""
        encounter_ids = ["ENC-1", "ENC-2", "ENC-3"]
        count = 30
        
        devices = DeviceDataGenerator.generate_devices(encounter_ids, count)
        
        assert len(devices) == count
        
        # Verify all devices have unique IDs
        ids = [d["id"] for d in devices]
        assert len(set(ids)) == count

    def test_device_battery_level_logic(self):
        """Test that battery level is only set for certain devices."""
        # Generate multiple devices and check battery logic
        for _ in range(10):
            device = DeviceDataGenerator.generate_device()
            
            if device["battery_level"] is not None:
                assert 0 <= device["battery_level"] <= 100


class TestHL7MessageGenerator:
    """Test HL7 message generation."""

    def test_generate_adt_message(self):
        """Test generating an ADT message."""
        patient_id = "PAT-123"
        mrn = "MRN123456"
        care_unit = "CARDIO"
        
        message = HL7MessageGenerator.generate_adt_message(
            patient_id, mrn, care_unit
        )
        
        # Verify message structure
        assert isinstance(message, str)
        assert message.startswith("MSH|")
        assert "ADT" in message
        assert mrn in message
        assert care_unit in message
        
        # Verify HL7 segments
        segments = message.split("\r")
        assert any(seg.startswith("MSH") for seg in segments)
        assert any(seg.startswith("EVN") for seg in segments)
        assert any(seg.startswith("PID") for seg in segments)
        assert any(seg.startswith("PV1") for seg in segments)

    def test_generate_oru_message(self):
        """Test generating an ORU message."""
        patient_id = "PAT-123"
        mrn = "MRN123456"
        test_name = "Glucose"
        
        message = HL7MessageGenerator.generate_oru_message(
            patient_id, mrn, test_name
        )
        
        # Verify message structure
        assert isinstance(message, str)
        assert message.startswith("MSH|")
        assert "ORU" in message
        assert mrn in message
        assert test_name in message
        
        # Verify HL7 segments
        segments = message.split("\r")
        assert any(seg.startswith("MSH") for seg in segments)
        assert any(seg.startswith("PID") for seg in segments)
        assert any(seg.startswith("OBR") for seg in segments)
        assert any(seg.startswith("OBX") for seg in segments)

    def test_generate_orm_message(self):
        """Test generating an ORM message."""
        patient_id = "PAT-123"
        mrn = "MRN123456"
        medication = "Aspirin"
        
        message = HL7MessageGenerator.generate_orm_message(
            patient_id, mrn, medication
        )
        
        # Verify message structure
        assert isinstance(message, str)
        assert message.startswith("MSH|")
        assert "ORM" in message
        assert mrn in message
        assert medication in message

    def test_generate_mdm_message(self):
        """Test generating an MDM message."""
        patient_id = "PAT-123"
        mrn = "MRN123456"
        note_type = "Discharge Summary"
        
        message = HL7MessageGenerator.generate_mdm_message(
            patient_id, mrn, note_type
        )
        
        # Verify message structure
        assert isinstance(message, str)
        assert message.startswith("MSH|")
        assert "MDM" in message
        assert mrn in message
        assert note_type in message

    def test_generate_multiple_hl7_messages(self):
        """Test generating multiple HL7 messages."""
        patient_ids = ["PAT-1", "PAT-2", "PAT-3"]
        mrns = ["MRN1", "MRN2", "MRN3"]
        count = 20
        
        messages = HL7MessageGenerator.generate_hl7_messages(
            patient_ids, mrns, count
        )
        
        assert len(messages) == count
        
        # Verify all messages are valid HL7
        for message in messages:
            assert isinstance(message, str)
            assert message.startswith("MSH|")
            assert "\r" in message


class TestDeviceTelemetrySimulator:
    """Test device telemetry simulation."""

    def test_generate_vital_signs(self):
        """Test generating a single set of vital signs."""
        vitals = DeviceTelemetrySimulator.generate_vital_signs()
        
        # Verify all vital signs are present
        for vital_name in DeviceTelemetrySimulator.VITAL_SIGNS.keys():
            assert vital_name in vitals
        
        # Verify vital sign values are within expected ranges
        for vital_name, config in DeviceTelemetrySimulator.VITAL_SIGNS.items():
            value = vitals[vital_name]
            assert config["min"] <= value <= config["max"]

    def test_generate_vital_signs_series(self):
        """Test generating a series of vital signs."""
        count = 50
        series = DeviceTelemetrySimulator.generate_vital_signs_series(count)
        
        assert len(series) == count
        
        # Verify timestamps are in descending order
        for i in range(len(series) - 1):
            assert series[i]["timestamp"] >= series[i + 1]["timestamp"]
        
        # Verify all vital signs are present in each entry
        for entry in series:
            assert "timestamp" in entry
            for vital_name in DeviceTelemetrySimulator.VITAL_SIGNS.keys():
                assert vital_name in entry

    def test_generate_alarm_event(self):
        """Test generating a single alarm event."""
        device_id = "DEV-123"
        patient_id = "PAT-456"
        
        alarm = DeviceTelemetrySimulator.generate_alarm_event(device_id, patient_id)
        
        # Verify required fields
        assert "id" in alarm
        assert "device_id" in alarm
        assert "patient_id" in alarm
        assert "alarm_type" in alarm
        assert "severity" in alarm
        assert "timestamp" in alarm
        
        # Verify field values
        assert alarm["device_id"] == device_id
        assert alarm["patient_id"] == patient_id
        assert alarm["alarm_type"] in DeviceTelemetrySimulator.ALARM_TYPES
        assert alarm["severity"] in ["critical", "high", "medium", "low"]
        assert isinstance(alarm["timestamp"], datetime)

    def test_generate_multiple_alarm_events(self):
        """Test generating multiple alarm events."""
        device_ids = ["DEV-1", "DEV-2", "DEV-3"]
        patient_ids = ["PAT-1", "PAT-2", "PAT-3"]
        count = 25
        
        alarms = DeviceTelemetrySimulator.generate_alarm_events(
            device_ids, patient_ids, count
        )
        
        assert len(alarms) == count
        
        # Verify all alarms have unique IDs
        ids = [a["id"] for a in alarms]
        assert len(set(ids)) == count
        
        # Verify alarms reference valid devices and patients
        for alarm in alarms:
            assert alarm["device_id"] in device_ids
            assert alarm["patient_id"] in patient_ids


class TestDataGenerationIntegration:
    """Integration tests for data generation."""

    def test_generate_complete_dataset(self):
        """Test generating a complete dataset."""
        # Generate patients
        patients = PatientDataGenerator.generate_patients(10)
        patient_ids = [p["id"] for p in patients]
        
        # Generate care units
        care_units = [
            {"id": "UNIT-1", "name": "Cardiology"},
            {"id": "UNIT-2", "name": "ICU"},
        ]
        care_unit_ids = [u["id"] for u in care_units]
        
        # Generate encounters
        encounters = EncounterDataGenerator.generate_encounters(
            patient_ids, care_unit_ids, 20
        )
        encounter_ids = [e["id"] for e in encounters]
        
        # Generate devices
        devices = DeviceDataGenerator.generate_devices(encounter_ids, 30)
        device_ids = [d["id"] for d in devices]
        
        # Generate HL7 messages
        mrns = [p["mrn"] for p in patients]
        hl7_messages = HL7MessageGenerator.generate_hl7_messages(
            patient_ids, mrns, 20
        )
        
        # Generate telemetry
        alarms = DeviceTelemetrySimulator.generate_alarm_events(
            device_ids, patient_ids, 15
        )
        
        # Verify dataset completeness
        assert len(patients) == 10
        assert len(encounters) == 20
        assert len(devices) == 30
        assert len(hl7_messages) == 20
        assert len(alarms) == 15

    def test_data_consistency_across_generators(self):
        """Test that data is consistent across different generators."""
        # Generate patients
        patients = PatientDataGenerator.generate_patients(5)
        patient_ids = [p["id"] for p in patients]
        
        # Generate encounters for these patients
        care_unit_ids = ["UNIT-1", "UNIT-2"]
        encounters = EncounterDataGenerator.generate_encounters(
            patient_ids, care_unit_ids, 10
        )
        
        # Verify all encounters reference valid patients
        for encounter in encounters:
            assert encounter["patient_id"] in patient_ids
            assert encounter["care_unit_id"] in care_unit_ids
