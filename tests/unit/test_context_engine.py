"""
Unit tests for the Clinical Context Engine components.

Tests event classifier, timeline builder, annotation engine,
and confidence scorer.
"""

import pytest
from datetime import datetime, timezone, timedelta

from mcp_server.context_engine.event_classifier import EventClassifier, VITAL_THRESHOLDS
from mcp_server.context_engine.confidence_scorer import ConfidenceScorer
from mcp_server.context_engine.annotation_engine import AnnotationEngine
from mcp_server.context_engine.timeline_builder import TimelineBuilder


# ---------------------------------------------------------------------------
# EventClassifier tests
# ---------------------------------------------------------------------------

class TestEventClassifier:
    """Tests for EventClassifier."""

    def setup_method(self):
        self.clf = EventClassifier()

    def test_classify_normal_heart_rate(self):
        result = self.clf.classify_event({"type": "vital_sign", "vital_type": "heart_rate", "value": 75})
        assert result["clinical_significance"] == "normal"
        assert result["is_abnormal"] is False

    def test_classify_critical_low_heart_rate(self):
        result = self.clf.classify_event({"type": "vital_sign", "vital_type": "heart_rate", "value": 35})
        assert result["clinical_significance"] == "critical_low"
        assert result["is_abnormal"] is True

    def test_classify_critical_high_heart_rate(self):
        result = self.clf.classify_event({"type": "vital_sign", "vital_type": "heart_rate", "value": 155})
        assert result["clinical_significance"] == "critical_high"
        assert result["is_abnormal"] is True

    def test_classify_abnormal_low_heart_rate(self):
        result = self.clf.classify_event({"type": "vital_sign", "vital_type": "heart_rate", "value": 45})
        assert result["clinical_significance"] == "abnormal_low"
        assert result["is_abnormal"] is True

    def test_classify_abnormal_high_spo2(self):
        result = self.clf.classify_event({"type": "vital_sign", "vital_type": "spo2", "value": 88})
        assert result["clinical_significance"] == "abnormal_low"

    def test_classify_critical_alarm(self):
        result = self.clf.classify_event({
            "type": "alarm", "alarm_type": "cardiac_arrest", "severity": "critical"
        })
        assert result["clinical_significance"] == "critical"
        assert result["is_abnormal"] is True

    def test_classify_low_severity_alarm(self):
        result = self.clf.classify_event({
            "type": "alarm", "alarm_type": "low_battery", "severity": "low"
        })
        assert result["clinical_significance"] == "normal"
        assert result["is_abnormal"] is False

    def test_classify_medication_event(self):
        result = self.clf.classify_event({
            "type": "medication", "medication_name": "Aspirin"
        })
        assert result["event_type"] == "medication"
        assert result["is_abnormal"] is False

    def test_classify_unknown_event_type(self):
        result = self.clf.classify_event({"type": "custom_event"})
        assert result["clinical_significance"] == "normal"
        assert "confidence_score" in result

    def test_is_abnormal_vital(self):
        is_abn, level = EventClassifier.is_abnormal_vital("heart_rate", 35)
        assert is_abn is True
        assert level == "critical"

    def test_is_normal_vital(self):
        is_abn, level = EventClassifier.is_abnormal_vital("heart_rate", 80)
        assert is_abn is False
        assert level == "normal"

    def test_get_thresholds_known_type(self):
        thresholds = EventClassifier.get_thresholds("heart_rate")
        assert thresholds is not None
        assert "critical_low" in thresholds
        assert "critical_high" in thresholds

    def test_get_thresholds_unknown_type(self):
        thresholds = EventClassifier.get_thresholds("unknown_vital")
        assert thresholds is None

    def test_classification_is_deterministic(self):
        """Property: same input always produces same output."""
        event = {"type": "vital_sign", "vital_type": "spo2", "value": 88}
        result1 = self.clf.classify_event(event)
        result2 = self.clf.classify_event(event)
        assert result1["clinical_significance"] == result2["clinical_significance"]
        assert result1["is_abnormal"] == result2["is_abnormal"]
        assert result1["confidence_score"] == result2["confidence_score"]


# ---------------------------------------------------------------------------
# ConfidenceScorer tests
# ---------------------------------------------------------------------------

class TestConfidenceScorer:
    """Tests for ConfidenceScorer."""

    def setup_method(self):
        self.scorer = ConfidenceScorer()

    def test_score_reliable_source(self):
        obs = {"source_system": "internal_database", "timestamp": datetime.now(timezone.utc).isoformat()}
        score = self.scorer.score_observation(obs)
        assert 0.90 <= score <= 1.0

    def test_score_unreliable_source(self):
        obs = {"source_system": "unknown"}
        score = self.scorer.score_observation(obs)
        assert score < 0.80

    def test_score_old_data_reduces_score(self):
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        recent_ts = datetime.now(timezone.utc).isoformat()
        old_score = self.scorer.score_observation({"source_system": "hl7", "timestamp": old_ts})
        new_score = self.scorer.score_observation({"source_system": "hl7", "timestamp": recent_ts})
        assert old_score < new_score

    def test_score_uncalibrated_device_reduces_score(self):
        calibrated = {"source_system": "device_telemetry", "calibration_status": "calibrated"}
        uncalibrated = {"source_system": "device_telemetry", "calibration_status": "needs_calibration"}
        cal_score = self.scorer.score_observation(calibrated)
        uncal_score = self.scorer.score_observation(uncalibrated)
        assert cal_score > uncal_score

    def test_score_range_always_0_to_1(self):
        """Property: confidence score is always in [0, 1]."""
        test_cases = [
            {"source_system": "unknown"},
            {"source_system": "internal_database", "calibration_status": "needs_calibration"},
            {},
        ]
        for obs in test_cases:
            score = self.scorer.score_observation(obs)
            assert 0.0 <= score <= 1.0

    def test_aggregate_context_score(self):
        context = {
            "patient": {"id": "p1"},
            "encounter": {"id": "e1"},
            "medications": [{"name": "Aspirin"}],
        }
        score = self.scorer.score_aggregated_context(context)
        assert 0.0 <= score <= 1.0

    def test_empty_context_returns_0_5(self):
        score = self.scorer.score_aggregated_context({})
        assert score == 0.50

    def test_get_source_reliability_known(self):
        r = ConfidenceScorer.get_source_reliability("fhir")
        assert r == 0.95

    def test_get_source_reliability_unknown(self):
        r = ConfidenceScorer.get_source_reliability("alien_system")
        assert r == 0.70


# ---------------------------------------------------------------------------
# AnnotationEngine tests
# ---------------------------------------------------------------------------

class TestAnnotationEngine:
    """Tests for AnnotationEngine."""

    def setup_method(self):
        self.engine = AnnotationEngine()

    def test_annotate_normal_observation_no_annotations(self):
        obs = {"vital_type": "heart_rate", "value": 75, "observation_type": "heart_rate"}
        annotations = self.engine.annotate_observation(obs)
        assert annotations == []

    def test_annotate_abnormal_observation(self):
        obs = {"vital_type": "heart_rate", "value": 35, "observation_type": "heart_rate"}
        annotations = self.engine.annotate_observation(obs)
        assert len(annotations) >= 1
        types = [a["type"] for a in annotations]
        assert "abnormal_value" in types

    def test_annotate_rising_trend(self):
        obs = {"vital_type": "heart_rate", "value": 80, "observation_type": "heart_rate", "trend": "increasing"}
        annotations = self.engine.annotate_observation(obs)
        types = [a["type"] for a in annotations]
        assert "trend" in types

    def test_annotate_alarm_critical(self):
        alarm = {"alarm_type": "cardiac_arrest", "severity": "critical"}
        annotations = self.engine.annotate_alarm(alarm)
        assert len(annotations) >= 2
        types = [a["type"] for a in annotations]
        assert "alarm_severity" in types
        assert "clinical_significance" in types

    def test_annotate_alarm_low_severity(self):
        alarm = {"alarm_type": "low_battery", "severity": "low"}
        annotations = self.engine.annotate_alarm(alarm)
        types = [a["type"] for a in annotations]
        assert "alarm_severity" in types
        # Only one annotation for low severity
        assert "clinical_significance" not in types

    def test_annotate_medication(self):
        med = {"medication_name": "Aspirin", "indication": "Pain relief"}
        annotations = self.engine.annotate_medication(med)
        assert len(annotations) == 2
        types = [a["type"] for a in annotations]
        assert "medication_administration" in types
        assert "indication" in types

    def test_detect_trend_increasing(self):
        values = [70, 72, 74, 76, 78, 80, 82, 84]
        trend = self.engine.detect_trend(values)
        assert trend == "increasing"

    def test_detect_trend_decreasing(self):
        values = [90, 88, 86, 84, 82, 80, 78, 76]
        trend = self.engine.detect_trend(values)
        assert trend == "decreasing"

    def test_detect_trend_stable(self):
        values = [75, 76, 74, 75, 76, 75, 74, 75]
        trend = self.engine.detect_trend(values)
        assert trend == "stable"

    def test_detect_trend_single_value(self):
        trend = self.engine.detect_trend([75])
        assert trend == "stable"


# ---------------------------------------------------------------------------
# TimelineBuilder tests
# ---------------------------------------------------------------------------

class TestTimelineBuilder:
    """Tests for TimelineBuilder."""

    def setup_method(self):
        self.builder = TimelineBuilder()
        self.now = datetime.now(timezone.utc)

    def _ts(self, hours_offset: float) -> str:
        return (self.now + timedelta(hours=hours_offset)).isoformat()

    def test_empty_timeline(self):
        result = self.builder.build_timeline()
        assert result == []

    def test_timeline_sorted_chronologically(self):
        obs = [
            {"vital_type": "heart_rate", "observation_type": "heart_rate",
             "value": 75, "timestamp": self._ts(-2)},
            {"vital_type": "spo2", "observation_type": "spo2",
             "value": 97, "timestamp": self._ts(-5)},
        ]
        timeline = self.builder.build_timeline(observations=obs)
        assert len(timeline) == 2
        t0 = timeline[0]["timestamp"]
        t1 = timeline[1]["timestamp"]
        assert t0 < t1

    def test_timeline_mixed_event_types(self):
        obs = [{"vital_type": "heart_rate", "observation_type": "heart_rate", "value": 80,
                "timestamp": self._ts(-3)}]
        alarms = [{"alarm_type": "low_spo2", "severity": "high", "timestamp": self._ts(-1)}]
        meds = [{"medication_name": "Aspirin", "administration_time": self._ts(-2)}]

        timeline = self.builder.build_timeline(observations=obs, alarm_events=alarms, medication_events=meds)
        assert len(timeline) == 3
        types = [e["event_type"] for e in timeline]
        assert "vital_sign" in types
        assert "alarm" in types
        assert "medication" in types

    def test_timeline_filters_by_time_window(self):
        obs = [
            {"vital_type": "heart_rate", "observation_type": "heart_rate", "value": 75,
             "timestamp": self._ts(-10)},
            {"vital_type": "heart_rate", "observation_type": "heart_rate", "value": 80,
             "timestamp": self._ts(-2)},
        ]
        start = self.now - timedelta(hours=5)
        end = self.now
        timeline = self.builder.build_timeline(observations=obs, start_time=start, end_time=end)
        assert len(timeline) == 1

    def test_timeline_entries_have_required_fields(self):
        obs = [{"vital_type": "heart_rate", "observation_type": "heart_rate",
                "value": 80, "timestamp": self._ts(-1)}]
        timeline = self.builder.build_timeline(observations=obs)
        assert len(timeline) == 1
        entry = timeline[0]
        assert "timestamp" in entry
        assert "event_type" in entry
        assert "event" in entry
        assert "clinical_significance" in entry
        assert "annotations" in entry
        assert "confidence_score" in entry

    def test_abnormal_vital_classified_correctly(self):
        obs = [{"vital_type": "heart_rate", "observation_type": "heart_rate",
                "value": 35, "timestamp": self._ts(-1)}]
        timeline = self.builder.build_timeline(observations=obs)
        assert timeline[0]["clinical_significance"] == "critical_low"

    def test_alarm_classification_in_timeline(self):
        alarms = [{"alarm_type": "cardiac_arrest", "severity": "critical",
                   "timestamp": self._ts(-1)}]
        timeline = self.builder.build_timeline(alarm_events=alarms)
        assert timeline[0]["event_type"] == "alarm"
        assert timeline[0]["clinical_significance"] == "critical"
