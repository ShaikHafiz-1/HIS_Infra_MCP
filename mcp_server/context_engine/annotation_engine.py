"""
Annotation Engine for the Clinical Context Engine.

Adds clinically-relevant labels to raw data: abnormal values, trends,
clinical context (pre/post procedure), and alarm significance.
"""

from typing import Any, Dict, List, Optional

from mcp_server.context_engine.event_classifier import EventClassifier, VITAL_THRESHOLDS
from mcp_server.utils.logger import get_logger

logger = get_logger(__name__)

_classifier = EventClassifier()


class AnnotationEngine:
    """Annotates clinical data with clinically-relevant labels."""

    def annotate_observation(self, observation: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Add clinical annotations to a single observation.

        Returns:
            List of annotation dicts with 'type', 'severity', 'description'.
        """
        annotations: List[Dict[str, Any]] = []

        vital_type = observation.get("observation_type", observation.get("vital_type"))
        value = observation.get("value")

        if vital_type and value is not None:
            is_abnormal, significance = EventClassifier.is_abnormal_vital(vital_type, value)
            if is_abnormal:
                annotations.append({
                    "type": "abnormal_value",
                    "severity": significance,
                    "description": f"Abnormal {vital_type}: {value} ({significance})",
                })

        trend = observation.get("trend")
        if trend and trend != "stable":
            annotations.append({
                "type": "trend",
                "direction": trend,
                "description": f"{vital_type or 'Value'} trend: {trend}",
            })

        clinical_context = observation.get("clinical_context")
        if clinical_context:
            annotations.append({
                "type": "clinical_context",
                "context": clinical_context,
                "description": f"Observation during: {clinical_context}",
            })

        return annotations

    def annotate_alarm(self, alarm: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Annotate an alarm event with severity and clinical significance."""
        severity = alarm.get("severity", "low")
        alarm_type = alarm.get("alarm_type", "unknown")

        annotations = [{
            "type": "alarm_severity",
            "severity": severity,
            "description": f"Alarm: {alarm_type} with {severity} severity",
        }]

        if severity in ("critical", "high"):
            annotations.append({
                "type": "clinical_significance",
                "severity": "high",
                "description": "Requires immediate clinical attention",
            })

        return annotations

    def annotate_medication(self, medication: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Annotate a medication event."""
        name = medication.get("medication_name", "unknown")
        indication = medication.get("indication")

        annotations = [{
            "type": "medication_administration",
            "description": f"Medication: {name}",
        }]
        if indication:
            annotations.append({
                "type": "indication",
                "description": f"Indication: {indication}",
            })
        return annotations

    def detect_trend(self, values: List[float]) -> str:
        """
        Detect trend direction from a list of sequential values.

        Returns:
            'increasing', 'decreasing', or 'stable'
        """
        if len(values) < 2:
            return "stable"

        first_half = values[:len(values) // 2]
        second_half = values[len(values) // 2:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)

        delta = avg_second - avg_first
        # Use 5% threshold relative to the average to determine trend
        threshold = abs(avg_first) * 0.05 if avg_first != 0 else 1.0

        if delta > threshold:
            return "increasing"
        elif delta < -threshold:
            return "decreasing"
        return "stable"
