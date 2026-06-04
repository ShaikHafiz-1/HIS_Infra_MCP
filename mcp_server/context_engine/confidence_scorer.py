"""
Confidence Scorer for the Clinical Context Engine.

Calculates confidence scores for observations and aggregated clinical context
based on source reliability, data age, and device calibration status.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from mcp_server.utils.logger import get_logger

logger = get_logger(__name__)

SOURCE_RELIABILITY: Dict[str, float] = {
    "hl7": 0.95,
    "fhir": 0.95,
    "dicom": 0.90,
    "device_telemetry": 0.88,
    "manual_entry": 0.80,
    "internal_database": 0.99,
    "device_connector": 0.88,
    "unknown": 0.70,
}


class ConfidenceScorer:
    """Calculates confidence scores for clinical data."""

    def score_observation(self, observation: Dict[str, Any]) -> float:
        """
        Calculate confidence score for a single observation.

        Factors:
        - Source system reliability
        - Data age (older = lower confidence)
        - Device calibration status (if applicable)

        Returns float in [0.0, 1.0].
        """
        score = 1.0

        source = observation.get("source_system", observation.get("source", "unknown"))
        score *= SOURCE_RELIABILITY.get(source, 0.70)

        timestamp = observation.get("timestamp")
        if timestamp:
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except ValueError:
                    timestamp = None
            if timestamp:
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                age_minutes = (datetime.now(timezone.utc) - timestamp).total_seconds() / 60
                if age_minutes > 1440:  # > 24 hours
                    score *= 0.70
                elif age_minutes > 60:  # > 1 hour
                    score *= 0.90

        calibration = observation.get("calibration_status")
        if calibration and calibration != "calibrated":
            score *= 0.80

        return max(0.0, min(1.0, round(score, 3)))

    def score_aggregated_context(self, context: Dict[str, Any]) -> float:
        """
        Calculate an aggregate confidence score for a complete clinical context.

        Returns float in [0.0, 1.0].
        """
        scores: List[float] = []

        if context.get("patient"):
            scores.append(0.99)  # demographic data is highly reliable

        if context.get("encounter"):
            scores.append(0.97)

        observations = context.get("recent_observations", context.get("observations", []))
        if observations:
            obs_scores = [self.score_observation(o) for o in observations]
            scores.append(sum(obs_scores) / len(obs_scores))

        if context.get("medications"):
            scores.append(0.95)

        if context.get("devices"):
            scores.append(0.90)

        if context.get("diagnoses"):
            scores.append(0.92)

        if not scores:
            return 0.50

        return round(sum(scores) / len(scores), 3)

    @staticmethod
    def get_source_reliability(source: str) -> float:
        """Return reliability factor for a given data source."""
        return SOURCE_RELIABILITY.get(source, 0.70)
