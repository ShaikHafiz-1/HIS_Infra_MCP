"""
Timeline Builder for the Clinical Context Engine.

Constructs chronological event timelines for patients, merging observations,
alarms, medications, procedures, and documentation events.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from mcp_server.context_engine.event_classifier import EventClassifier
from mcp_server.context_engine.annotation_engine import AnnotationEngine
from mcp_server.utils.logger import get_logger

logger = get_logger(__name__)

_classifier = EventClassifier()
_annotator = AnnotationEngine()


def _parse_timestamp(ts: Any) -> Optional[datetime]:
    """Parse a timestamp from various formats."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts
    if isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return None
    return None


class TimelineBuilder:
    """Builds chronological clinical event timelines."""

    def build_timeline(
        self,
        observations: List[Dict[str, Any]] = None,
        alarm_events: List[Dict[str, Any]] = None,
        medication_events: List[Dict[str, Any]] = None,
        procedures: List[Dict[str, Any]] = None,
        notes: List[Dict[str, Any]] = None,
        device_changes: List[Dict[str, Any]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Build a chronological timeline from heterogeneous clinical event lists.

        Each timeline entry has:
          - timestamp: ISO string
          - event_type: category
          - event: original event dict
          - clinical_significance: normal/abnormal_low/abnormal_high/critical_low/critical_high
          - annotations: list of annotation dicts
          - confidence_score: float

        Returns list sorted ascending by timestamp.
        """
        raw_events: List[tuple] = []

        for obs in (observations or []):
            ts = _parse_timestamp(obs.get("timestamp"))
            raw_events.append(("vital_sign", ts, obs))

        for alarm in (alarm_events or []):
            ts = _parse_timestamp(alarm.get("timestamp"))
            raw_events.append(("alarm", ts, alarm))

        for med in (medication_events or []):
            ts = _parse_timestamp(med.get("administration_time") or med.get("timestamp"))
            raw_events.append(("medication", ts, med))

        for proc in (procedures or []):
            ts = _parse_timestamp(proc.get("start_time") or proc.get("timestamp"))
            raw_events.append(("procedure", ts, proc))

        for note in (notes or []):
            ts = _parse_timestamp(note.get("timestamp") or note.get("authored_time"))
            raw_events.append(("clinician_note", ts, note))

        for change in (device_changes or []):
            ts = _parse_timestamp(change.get("timestamp"))
            raw_events.append(("device_setting_change", ts, change))

        # Filter by time window
        if start_time or end_time:
            filtered = []
            for (etype, ts, evt) in raw_events:
                if ts is None:
                    continue
                if start_time and ts < start_time:
                    continue
                if end_time and ts > end_time:
                    continue
                filtered.append((etype, ts, evt))
            raw_events = filtered

        # Sort by timestamp, None timestamps go last
        raw_events.sort(key=lambda x: x[1] or datetime.max.replace(tzinfo=timezone.utc))

        timeline = []
        for (etype, ts, evt) in raw_events:
            classification = _classifier.classify_event({"type": etype, **evt})
            annotations = self._annotate_event(etype, evt)

            entry = {
                "timestamp": ts.isoformat() if ts else None,
                "event_type": etype,
                "event": evt,
                "clinical_significance": classification.get("clinical_significance", "normal"),
                "annotations": annotations,
                "confidence_score": classification.get("confidence_score", 0.80),
            }
            timeline.append(entry)

        return timeline

    def _annotate_event(self, event_type: str, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Dispatch annotation to the appropriate method."""
        if event_type in ("vital_sign", "lab_result"):
            return _annotator.annotate_observation(event)
        elif event_type == "alarm":
            return _annotator.annotate_alarm(event)
        elif event_type == "medication":
            return _annotator.annotate_medication(event)
        return []
