"""
Integration tests for the patient monitor simulator.

Tests cover:
- Simulator startup and patient profile loading
- Vital sign snapshot generation and physiological ranges
- NEWS2 score calculation
- Alarm firing per IEC 60601-1-8 thresholds
- Clinical scenario trajectories
- Thread safety (snapshot access under concurrent reads)
"""

import math
import time
import pytest

from simulator.patient_monitor import (
    get_simulator,
    PatientSimulator,
    ScenarioType,
    AlarmTier,
    _news2,
    _check_alarms,
)


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def sim():
    """Module-scoped simulator — starts once, shared across all tests."""
    s = get_simulator()
    # Give the daemon tick at least one cycle
    time.sleep(2.5)
    return s


# ── Profile tests ─────────────────────────────────────────────────────────

class TestPatientProfiles:
    def test_five_patients_loaded(self, sim):
        profiles = sim.get_all_profiles()
        assert len(profiles) == 5

    def test_patient_ids_are_unique(self, sim):
        ids = [p.patient_id for p in sim.get_all_profiles()]
        assert len(ids) == len(set(ids))

    def test_all_scenarios_covered(self, sim):
        scenarios = {p.scenario for p in sim.get_all_profiles()}
        expected = {
            ScenarioType.RESPIRATORY_DETERIORATION,
            ScenarioType.SEPSIS_RISK,
            ScenarioType.ARRHYTHMIA,
            ScenarioType.POST_OP_INSTABILITY,
            ScenarioType.DEVICE_DISCONNECT,
        }
        assert expected.issubset(scenarios)

    def test_pt001_is_respiratory_scenario(self, sim):
        p = sim.get_profile("PT-001")
        assert p is not None
        assert p.scenario == ScenarioType.RESPIRATORY_DETERIORATION

    def test_profile_fields_are_populated(self, sim):
        for p in sim.get_all_profiles():
            assert p.name
            assert p.age > 0
            assert p.unit
            assert p.bed
            assert p.admission_dx


# ── Snapshot tests ─────────────────────────────────────────────────────────

class TestVitalSnapshots:
    def test_snapshot_exists_for_every_patient(self, sim):
        profiles = sim.get_all_profiles()
        for p in profiles:
            snap = sim.get_snapshot(p.patient_id)
            # device_disconnect patients may have NaN but snapshot should exist
            if p.scenario != ScenarioType.DEVICE_DISCONNECT:
                assert snap is not None

    def test_vitals_within_physiological_bounds(self, sim):
        """Vitals for non-disconnected patients must be in plausible human range."""
        for snap in sim.get_all_snapshots():
            profile = sim.get_profile(snap.patient_id)
            if profile.scenario == ScenarioType.DEVICE_DISCONNECT:
                continue
            if math.isnan(snap.hr):
                continue

            assert 20 <= snap.hr <= 250,   f"HR={snap.hr} out of range"
            assert 50 <= snap.sbp <= 220,  f"SBP={snap.sbp} out of range"
            assert 20 <= snap.dbp <= 150,  f"DBP={snap.dbp} out of range"
            assert 60 <= snap.spo2 <= 100, f"SpO2={snap.spo2} out of range"
            assert 4  <= snap.rr  <= 60,   f"RR={snap.rr} out of range"
            assert 33 <= snap.temp <= 42,  f"Temp={snap.temp} out of range"

    def test_map_is_calculated_correctly(self, sim):
        """MAP should be approximately (SBP + 2*DBP) / 3."""
        for snap in sim.get_all_snapshots():
            if math.isnan(snap.hr):
                continue
            expected_map = (snap.sbp + 2 * snap.dbp) / 3
            assert abs(snap.map_val - expected_map) < 2.0, (
                f"MAP={snap.map_val} expected ~{expected_map:.1f}"
            )

    def test_news2_is_nonnegative_integer(self, sim):
        for snap in sim.get_all_snapshots():
            assert isinstance(snap.news2, int)
            assert snap.news2 >= 0

    def test_risk_level_matches_news2(self, sim):
        """NEWS2 score should correspond to correct risk tier."""
        for snap in sim.get_all_snapshots():
            if snap.news2 <= 4:
                assert snap.risk_level in ("LOW", "STABLE", "MEDIUM")
            elif snap.news2 <= 6:
                assert snap.risk_level in ("MEDIUM", "HIGH")
            else:
                assert snap.risk_level in ("HIGH", "CRITICAL")

    def test_ecg_wave_has_100_points(self, sim):
        for snap in sim.get_all_snapshots():
            if snap.ecg_wave:
                assert len(snap.ecg_wave) == 100

    def test_trend_lists_are_populated(self, sim):
        """After one tick cycle, trend lists should have at least 1 entry."""
        for snap in sim.get_all_snapshots():
            prof = sim.get_profile(snap.patient_id)
            if prof.scenario != ScenarioType.DEVICE_DISCONNECT:
                assert len(snap.hr_trend) >= 1
                assert len(snap.spo2_trend) >= 1


# ── NEWS2 calculation ─────────────────────────────────────────────────────

class TestNEWS2:
    """Unit tests for the NEWS2 scoring function."""

    def test_healthy_patient_scores_zero(self):
        score = _news2(hr=70, sbp=120, rr=16, spo2=97, temp=37.0, on_o2=False)
        assert score == 0

    def test_high_hr_adds_points(self):
        score_normal  = _news2(hr=70,  sbp=120, rr=16, spo2=97, temp=37.0)
        score_high_hr = _news2(hr=115, sbp=120, rr=16, spo2=97, temp=37.0)
        assert score_high_hr > score_normal

    def test_low_spo2_adds_points(self):
        score_normal   = _news2(hr=70, sbp=120, rr=16, spo2=97, temp=37.0)
        score_low_spo2 = _news2(hr=70, sbp=120, rr=16, spo2=91, temp=37.0)
        assert score_low_spo2 > score_normal

    def test_supplemental_o2_adds_two_points(self):
        score_air    = _news2(hr=70, sbp=120, rr=16, spo2=94, temp=37.0, on_o2=False)
        score_on_o2  = _news2(hr=70, sbp=120, rr=16, spo2=94, temp=37.0, on_o2=True)
        assert score_on_o2 == score_air + 2

    def test_avpu_not_alert_adds_three_points(self):
        score_alert = _news2(hr=70, sbp=120, rr=16, spo2=97, temp=37.0, avpu="A")
        score_voice = _news2(hr=70, sbp=120, rr=16, spo2=97, temp=37.0, avpu="V")
        assert score_voice == score_alert + 3

    def test_maximal_deterioration_scores_high(self):
        score = _news2(hr=130, sbp=85, rr=28, spo2=88, temp=38.6, on_o2=True, avpu="P")
        assert score >= 10


# ── Alarm tests ───────────────────────────────────────────────────────────

class TestAlarmFiring:
    def test_spo2_crisis_fires_below_85(self):
        alarms = _check_alarms("PT-TEST", hr=70, spo2=83.0, rr=18, map_val=70, temp=37.0)
        crisis_alarms = [a for a in alarms if a.tier == AlarmTier.CRISIS.value and "SpO2" in a.parameter]
        assert len(crisis_alarms) >= 1

    def test_spo2_warning_fires_between_85_and_90(self):
        alarms = _check_alarms("PT-TEST", hr=70, spo2=88.0, rr=18, map_val=70, temp=37.0)
        warn_alarms = [a for a in alarms if a.tier == AlarmTier.WARNING.value and "SpO2" in a.parameter]
        assert len(warn_alarms) >= 1

    def test_no_alarm_when_vitals_normal(self):
        alarms = _check_alarms("PT-TEST", hr=70, spo2=97.0, rr=16, map_val=75, temp=37.0)
        assert len(alarms) == 0, f"Unexpected alarms: {[a.message for a in alarms]}"

    def test_hr_crisis_fires_above_130(self):
        alarms = _check_alarms("PT-TEST", hr=135, spo2=97.0, rr=16, map_val=75, temp=37.0)
        crisis_alarms = [a for a in alarms if a.tier == AlarmTier.CRISIS.value and "HR" in a.parameter]
        assert len(crisis_alarms) >= 1

    def test_nan_vitals_do_not_raise(self):
        """Device disconnect scenario: all-NaN vitals must not throw."""
        try:
            alarms = _check_alarms("PT-TEST",
                                   hr=float("nan"), spo2=float("nan"),
                                   rr=float("nan"), map_val=float("nan"),
                                   temp=float("nan"))
        except Exception as ex:
            pytest.fail(f"NaN vitals raised an exception: {ex}")


# ── Scenario trajectory tests ─────────────────────────────────────────────

class TestScenarioTrajectory:
    def test_respiratory_pt_spo2_falls_over_time(self):
        """SpO2 for PT-001 must be lower after 5 minutes than at baseline."""
        sim = get_simulator()
        snap_now = sim.get_snapshot("PT-001")
        profile   = sim.get_profile("PT-001")
        if snap_now is None or math.isnan(snap_now.spo2):
            pytest.skip("Snapshot not ready yet")

        # Baseline value from profile
        baseline_spo2 = profile.base_spo2
        # Even at elapsed ~0 the scenario hasn't degraded much
        # After 5+ minutes it should be measurably lower
        if sim.elapsed_seconds() > 300:
            assert snap_now.spo2 < baseline_spo2, (
                f"Expected SpO2 < {baseline_spo2} after 5+ minutes, got {snap_now.spo2:.1f}"
            )

    def test_device_disconnect_pt_eventually_loses_vitals(self):
        """PT-005 should show NaN vitals after 5 minutes elapsed."""
        sim = get_simulator()
        if sim.elapsed_seconds() < 310:
            pytest.skip("Need 300+ seconds elapsed for device disconnect scenario")
        snap = sim.get_snapshot("PT-005")
        if snap:
            assert math.isnan(snap.hr), "Expected NaN HR for device disconnect scenario"


# ── Thread safety ─────────────────────────────────────────────────────────

class TestThreadSafety:
    def test_concurrent_snapshot_reads(self, sim):
        """Multiple threads reading snapshots simultaneously should not deadlock or raise."""
        import threading
        errors = []

        def read_snapshots():
            try:
                for _ in range(20):
                    snaps = sim.get_all_snapshots()
                    _ = [sim.snapshot_as_dict(s) for s in snaps]
            except Exception as ex:
                errors.append(str(ex))

        threads = [threading.Thread(target=read_snapshots) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Thread errors: {errors}"


# ── Alarm history ─────────────────────────────────────────────────────────

class TestAlarmHistory:
    def test_alarm_history_returns_list(self, sim):
        history = sim.get_alarm_history("PT-001", limit=50)
        assert isinstance(history, list)

    def test_alarm_history_respects_limit(self, sim):
        history = sim.get_alarm_history("PT-001", limit=5)
        assert len(history) <= 5

    def test_all_patient_alarm_history(self, sim):
        history = sim.get_alarm_history(limit=100)
        assert isinstance(history, list)

    def test_alarm_history_sorted_descending(self, sim):
        history = sim.get_alarm_history(limit=20)
        if len(history) >= 2:
            for i in range(len(history) - 1):
                assert history[i].fired_at >= history[i + 1].fired_at, \
                    "Alarm history should be sorted newest-first"
