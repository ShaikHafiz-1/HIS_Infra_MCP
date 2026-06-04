"""
Event Classifier for the Clinical Context Engine.

Classifies clinical events by type and significance, detects abnormal vitals,
and assigns alarm severity levels.
"""

from typing import Any, Dict, List, Optional, Tuple

from mcp_server.utils.logger import get_logger

logger = get_logger(__name__)

# Clinical thresholds for vital signs (adult defaults)
VITAL_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "heart_rate": {"critical_low": 40, "abnormal_low": 50, "abnormal_high": 120, "critical_high": 150},
    "blood_pressure_systolic": {"critical_low": 70, "abnormal_low": 90, "abnormal_high": 160, "critical_high": 180},
    "blood_pressure_diastolic": {"critical_low": 40, "abnormal_low": 60, "abnormal_high": 100, "critical_high": 120},
    "spo2": {"critical_low": 85, "abnormal_low": 90, "abnormal_high": 100, "critical_high": 100},
    "respiratory_rate": {"critical_low": 8, "abnormal_low": 10, "abnormal_high": 24, "critical_high": 30},
    "temperature": {"critical_low": 35.0, "abnormal_low": 36.0, "abnormal_high": 38.5, "critical_high": 40.0},
    "glucose": {"critical_low": 50, "abnormal_low": 70, "abnormal_high": 180, "critical_high": 400},
}

ALARM_SEVERITY_CLINICAL_MAP = {
    "critical": "critical",
    "high": "abnormal_high",
    "medium": "abnormal_low",
    "low": "normal",
    "info": "normal",
}


class EventClassifier:
    """Classifies clinical events by type and significance."""

    EVENT_TYPES = {
        "vital_sign": "observation",
        "alarm": "alarm_event",
        "medication": "medication_event",
        "procedure_start": "procedure_event",
        "procedure_end": "procedure_event",
        "diagnostic_exam": "diagnostic_event",
        "device_status": "device_event",
        "clinician_note": "documentation_event",
        "lab_result": "observation",
        "imaging": "diagnostic_event",
    }

    def classify_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify an event and assign clinical significance.

        Args:
            event_data: Raw event data dict with 'type' key

        Returns:
            Classification dict with event_type, clinical_significance, annotations, confidence_score
        """
        event_type = event_data.get("type", "unknown")

        if event_type in ("vital_sign", "lab_result"):
            return self._classify_vital_sign(event_data)
        elif event_type == "alarm":
            return self._classify_alarm(event_data)
        elif event_type == "medication":
            return self._classify_medication(event_data)
        else:
            return {
                "event_type": event_type,
                "clinical_significance": "normal",
                "annotations": [],
                "confidence_score": 0.80,
            }

    def _classify_vital_sign(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Classify a vital sign observation."""
        vital_type = event_data.get("vital_type", "")
        value = event_data.get("value")

        significance = "normal"
        annotations = []

        if value is not None and vital_type in VITAL_THRESHOLDS:
            thresholds = VITAL_THRESHOLDS[vital_type]
            if value <= thresholds["critical_low"]:
                significance = "critical_low"
                annotations.append(f"CRITICAL: {vital_type} critically low ({value})")
            elif value < thresholds["abnormal_low"]:
                significance = "abnormal_low"
                annotations.append(f"LOW: {vital_type} below normal ({value})")
            elif value >= thresholds["critical_high"]:
                significance = "critical_high"
                annotations.append(f"CRITICAL: {vital_type} critically high ({value})")
            elif value > thresholds["abnormal_high"]:
                significance = "abnormal_high"
                annotations.append(f"HIGH: {vital_type} above normal ({value})")

        return {
            "event_type": "vital_sign",
            "clinical_significance": significance,
            "annotations": annotations,
            "confidence_score": 0.95,
            "is_abnormal": significance != "normal",
        }

    def _classify_alarm(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Classify an alarm event."""
        alarm_type = event_data.get("alarm_type", "unknown")
        severity = event_data.get("severity", "low")

        significance = ALARM_SEVERITY_CLINICAL_MAP.get(severity, "normal")
        annotations = [f"Alarm: {alarm_type} ({severity} severity)"]

        return {
            "event_type": "alarm",
            "clinical_significance": significance,
            "annotations": annotations,
            "confidence_score": 0.98,
            "is_abnormal": severity in ("critical", "high"),
        }

    def _classify_medication(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Classify a medication administration event."""
        medication = event_data.get("medication_name", "unknown")
        return {
            "event_type": "medication",
            "clinical_significance": "normal",
            "annotations": [f"Medication administered: {medication}"],
            "confidence_score": 0.92,
            "is_abnormal": False,
        }

    @staticmethod
    def get_thresholds(vital_type: str) -> Optional[Dict[str, float]]:
        """Return clinical thresholds for a vital type."""
        return VITAL_THRESHOLDS.get(vital_type)

    @staticmethod
    def is_abnormal_vital(vital_type: str, value: float) -> Tuple[bool, str]:
        """
        Check if a vital sign value is abnormal.

        Returns:
            Tuple of (is_abnormal, significance_level)
        """
        thresholds = VITAL_THRESHOLDS.get(vital_type)
        if thresholds is None or value is None:
            return False, "normal"

        if value <= thresholds["critical_low"] or value >= thresholds["critical_high"]:
            return True, "critical"
        if value < thresholds["abnormal_low"] or value > thresholds["abnormal_high"]:
            return True, "abnormal"
        return False, "normal"
