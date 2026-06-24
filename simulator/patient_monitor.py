"""
Patient Monitor Simulator — Hospital Clinical Intelligence Platform.

Streams physiologically realistic vital signs for 5 patients across 5 clinical
scenarios. Usable as an imported module (Streamlit) or as a standalone FastAPI
service on port 8001.

Clinical scenarios
------------------
1. respiratory_deterioration  SpO2 ↓, RR ↑, HR ↑  → CRISIS alarm
2. sepsis_risk                Temp ↑, HR ↑, MAP ↓  → sepsis criteria met
3. arrhythmia                 HR irregular + PVC bursts → WARNING alarm
4. post_op_instability        MAP ↓ after surgery   → trending down
5. device_disconnect          Vital gaps + artifact  → device offline

NEWS2 scoring per RCP 2017. IEC 60601-1-8 alarm tiers.
"""

from __future__ import annotations

import math
import random
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Enums & constants
# ---------------------------------------------------------------------------

class ScenarioType(str, Enum):
    RESPIRATORY_DETERIORATION = "respiratory_deterioration"
    SEPSIS_RISK               = "sepsis_risk"
    ARRHYTHMIA                = "arrhythmia"
    POST_OP_INSTABILITY       = "post_op_instability"
    DEVICE_DISCONNECT         = "device_disconnect"
    STABLE                    = "stable"


class AlarmTier(str, Enum):
    CRISIS   = "CRISIS"    # IEC 60601-1-8 HIGH
    WARNING  = "WARNING"   # IEC 60601-1-8 MEDIUM
    ADVISORY = "ADVISORY"  # IEC 60601-1-8 LOW


# Alarm thresholds (AAMI / IEC 60601-1-8)
HR_CRISIS_HIGH, HR_CRISIS_LOW   = 130, 40
HR_WARN_HIGH,   HR_WARN_LOW     = 110, 50
SPO2_CRISIS,    SPO2_WARN       = 85.0, 90.0
RR_CRISIS_HIGH, RR_CRISIS_LOW   = 30,   6
RR_WARN_HIGH,   RR_WARN_LOW     = 25,   8
MAP_CRISIS_LOW, MAP_WARN_LOW    = 50.0, 60.0
TEMP_CRISIS_HIGH, TEMP_WARN_HIGH = 40.0, 38.5


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AlarmEvent:
    alarm_id:   str
    patient_id: str
    tier:       AlarmTier
    parameter:  str         # "HR", "SpO2", "RR", "MAP", "Temp"
    value:      float
    threshold:  float
    message:    str
    fired_at:   float       # Unix epoch
    acknowledged: bool = False


@dataclass
class VitalSnapshot:
    """Full vital sign snapshot at one moment in time."""
    patient_id:   str
    timestamp:    float
    hr:           float
    sbp:          float
    dbp:          float
    map_val:      float
    spo2:         float
    rr:           float
    temp:         float
    etco2:        Optional[float]
    # Derived
    news2:        int
    risk_level:   str          # STABLE / LOW / MEDIUM / HIGH / CRITICAL
    active_alarms: List[AlarmEvent]
    # Trends (last 12 readings, ~1-minute history at 5-s poll)
    hr_trend:    List[float]
    spo2_trend:  List[float]
    rr_trend:    List[float]
    map_trend:   List[float]
    # ECG waveform (120 points ≈ one complex at ~150 bpm)
    ecg_wave:    List[float]
    # Device status
    devices_online:  List[str]
    devices_offline: List[str]


@dataclass
class PatientProfile:
    patient_id: str
    name:       str
    age:        int
    gender:     str
    unit:       str
    bed:        str
    scenario:   ScenarioType
    admission_dx: str
    # Baseline vitals (healthy resting)
    base_hr:    float
    base_sbp:   float
    base_dbp:   float
    base_spo2:  float
    base_rr:    float
    base_temp:  float
    # Attached devices
    devices:    List[str]


# ---------------------------------------------------------------------------
# NEWS2 scorer (RCP 2017)
# ---------------------------------------------------------------------------

def _news2(hr: float, sbp: float, rr: float, spo2: float,
           temp: float, on_o2: bool = False, avpu: str = "A") -> int:
    score = 0

    # RR
    if rr <= 8 or rr >= 25:  score += 3
    elif rr >= 21:            score += 2
    elif rr >= 9:             score += 0
    else:                     score += 1   # shouldn't reach

    # SpO2 (scale 1 — no COPD)
    if spo2 <= 91:            score += 3
    elif spo2 <= 93:          score += 2
    elif spo2 <= 95:          score += 1

    # On supplemental O2
    if on_o2:                 score += 2

    # Systolic BP
    if sbp <= 90 or sbp >= 220: score += 3
    elif sbp <= 100:            score += 2
    elif sbp <= 110:            score += 1

    # HR
    if hr <= 40 or hr >= 131:  score += 3
    elif hr >= 111:             score += 2
    elif hr >= 91:              score += 1
    elif hr >= 51:              score += 0
    else:                       score += 1   # 41-50

    # Temperature
    if temp <= 35.0:           score += 3
    elif temp <= 36.0:         score += 1
    elif temp <= 38.0:         score += 0
    elif temp <= 39.0:         score += 1
    else:                      score += 2

    # AVPU
    if avpu != "A":            score += 3

    return score


def _risk_level(news2: int) -> str:
    if news2 >= 7:   return "CRITICAL"
    if news2 >= 5:   return "HIGH"
    if news2 >= 3:   return "MEDIUM"
    if news2 >= 1:   return "LOW"
    return "STABLE"


# ---------------------------------------------------------------------------
# ECG waveform generator
# ---------------------------------------------------------------------------

def _ecg_segment(rng: random.Random, hr: float, pvcs: bool = False,
                 artifact: bool = False) -> List[float]:
    """Generate one ~1-second ECG segment (100 points) at given HR."""
    if artifact:
        return [rng.uniform(-0.5, 0.5) for _ in range(100)]

    points: List[float] = []
    cycle   = 60.0 / hr          # seconds per beat
    samples = 100
    dt      = 1.0 / samples

    t = 0.0
    while len(points) < samples:
        phase = (t % cycle) / cycle  # 0..1 within beat
        v = 0.0

        if 0.0 <= phase < 0.20:   # P wave
            v = 0.15 * math.sin(phase / 0.20 * math.pi)
        elif 0.20 <= phase < 0.24: # PQ segment
            v = 0.0
        elif 0.24 <= phase < 0.25: # Q dip
            v = -0.1
        elif 0.25 <= phase < 0.26: # R spike
            if pvcs and rng.random() < 0.20:
                v = 1.8 * math.sin((phase - 0.25) / 0.01 * math.pi)
            else:
                v = 1.2 * math.sin((phase - 0.25) / 0.01 * math.pi)
        elif 0.26 <= phase < 0.28: # S dip
            v = -0.15 * math.sin((phase - 0.26) / 0.02 * math.pi)
        elif 0.28 <= phase < 0.40: # ST segment
            v = 0.0
        elif 0.40 <= phase < 0.65: # T wave
            v = 0.3 * math.sin((phase - 0.40) / 0.25 * math.pi)
        else:
            v = 0.0

        v += rng.gauss(0, 0.01)   # baseline noise
        points.append(round(v, 4))
        t += dt

    return points[:samples]


# ---------------------------------------------------------------------------
# Scenario dynamics: compute vital deltas at elapsed seconds
# ---------------------------------------------------------------------------

def _apply_scenario(profile: PatientProfile, elapsed: float, rng: random.Random
                    ) -> Tuple[float, float, float, float, float, float, Optional[float]]:
    """
    Return (hr, sbp, dbp, spo2, rr, temp, etco2) after applying scenario
    dynamics to the patient's baselines.
    elapsed: seconds since simulation start
    """
    hr   = profile.base_hr
    sbp  = profile.base_sbp
    dbp  = profile.base_dbp
    spo2 = profile.base_spo2
    rr   = profile.base_rr
    temp = profile.base_temp
    etco2: Optional[float] = None

    s = profile.scenario

    if s == ScenarioType.RESPIRATORY_DETERIORATION:
        # SpO2 drops 1%/90s, RR rises 1/60s, HR compensates
        drop_spo2 = min(15.0, elapsed / 90.0)
        rise_rr   = min(16.0, elapsed / 60.0)
        rise_hr   = min(40.0, elapsed / 45.0)
        spo2 = max(82.0, profile.base_spo2 - drop_spo2)
        rr   = min(32.0, profile.base_rr   + rise_rr)
        hr   = min(135.0, profile.base_hr  + rise_hr)
        etco2 = max(18.0, 38.0 - elapsed / 90.0)

    elif s == ScenarioType.SEPSIS_RISK:
        # Temp rises 0.1°C/60s, HR rises 0.5/30s, MAP drops 0.3/45s
        rise_temp = min(2.5, elapsed / 600.0)
        rise_hr   = min(35.0, elapsed * 0.5 / 30.0)
        drop_map  = min(20.0, elapsed * 0.3 / 45.0)
        drop_sbp  = drop_map * 1.5
        drop_dbp  = drop_map * 0.7
        temp = min(40.2, profile.base_temp + rise_temp)
        hr   = min(130.0, profile.base_hr  + rise_hr)
        sbp  = max(80.0, profile.base_sbp  - drop_sbp)
        dbp  = max(40.0, profile.base_dbp  - drop_dbp)

    elif s == ScenarioType.ARRHYTHMIA:
        # HR oscillates ±15 bpm with 3-minute PVC burst cycle
        burst = (math.sin(elapsed / 180.0 * math.pi) > 0.6)
        if burst:
            hr = profile.base_hr + rng.uniform(15, 30)
        else:
            hr = profile.base_hr + rng.gauss(0, 5)

    elif s == ScenarioType.POST_OP_INSTABILITY:
        # MAP dips in first 10 min, partial recovery, second dip at 20 min
        if elapsed < 600:
            drop = elapsed / 600.0 * 25.0
        elif elapsed < 1200:
            drop = 25.0 - (elapsed - 600) / 600.0 * 15.0
        else:
            drop = 10.0 + (elapsed - 1200) / 600.0 * 15.0
        drop = min(30.0, max(0.0, drop))
        sbp = max(78.0, profile.base_sbp - drop * 1.5)
        dbp = max(42.0, profile.base_dbp - drop * 0.7)

    elif s == ScenarioType.DEVICE_DISCONNECT:
        # After 5 minutes device goes offline, vitals show artifact
        if elapsed > 300:
            return (hr, sbp, dbp, float("nan"), float("nan"), temp, None)

    # Add physiological noise
    hr   += rng.gauss(0, 1.5)
    sbp  += rng.gauss(0, 2.0)
    dbp  += rng.gauss(0, 1.5)
    spo2 += rng.gauss(0, 0.3)
    rr   += rng.gauss(0, 0.5)
    temp += rng.gauss(0, 0.05)

    # Clamp to physiological limits
    hr   = max(30.0,  min(180.0, hr))
    sbp  = max(60.0,  min(240.0, sbp))
    dbp  = max(30.0,  min(140.0, dbp))
    spo2 = max(70.0,  min(100.0, spo2))
    rr   = max(4.0,   min(40.0,  rr))
    temp = max(33.0,  min(42.0,  temp))

    return (hr, sbp, dbp, spo2, rr, temp, etco2)


# ---------------------------------------------------------------------------
# Alarm checker
# ---------------------------------------------------------------------------

def _check_alarms(patient_id: str, hr: float, spo2: float,
                  rr: float, map_val: float, temp: float) -> List[AlarmEvent]:
    alarms: List[AlarmEvent] = []
    now = time.time()

    def _alarm(tier: AlarmTier, param: str, val: float, thresh: float, msg: str):
        alarms.append(AlarmEvent(
            alarm_id   = f"ALM-{uuid.uuid4().hex[:8].upper()}",
            patient_id = patient_id,
            tier       = tier,
            parameter  = param,
            value      = round(val, 1),
            threshold  = thresh,
            message    = msg,
            fired_at   = now,
        ))

    if math.isnan(hr):
        return alarms  # device offline — no alarms

    if hr >= HR_CRISIS_HIGH:
        _alarm(AlarmTier.CRISIS, "HR", hr, HR_CRISIS_HIGH,
               f"HR {hr:.0f} bpm ≥ {HR_CRISIS_HIGH} — tachycardia crisis")
    elif hr >= HR_WARN_HIGH:
        _alarm(AlarmTier.WARNING, "HR", hr, HR_WARN_HIGH,
               f"HR {hr:.0f} bpm ≥ {HR_WARN_HIGH} — tachycardia warning")

    if hr <= HR_CRISIS_LOW:
        _alarm(AlarmTier.CRISIS, "HR", hr, HR_CRISIS_LOW,
               f"HR {hr:.0f} bpm ≤ {HR_CRISIS_LOW} — bradycardia crisis")
    elif hr <= HR_WARN_LOW:
        _alarm(AlarmTier.WARNING, "HR", hr, HR_WARN_LOW,
               f"HR {hr:.0f} bpm ≤ {HR_WARN_LOW} — bradycardia warning")

    if spo2 <= SPO2_CRISIS:
        _alarm(AlarmTier.CRISIS, "SpO2", spo2, SPO2_CRISIS,
               f"SpO2 {spo2:.1f}% ≤ {SPO2_CRISIS}% — critical hypoxaemia")
    elif spo2 <= SPO2_WARN:
        _alarm(AlarmTier.WARNING, "SpO2", spo2, SPO2_WARN,
               f"SpO2 {spo2:.1f}% ≤ {SPO2_WARN}% — desaturation")
    elif spo2 <= 93.0:
        _alarm(AlarmTier.ADVISORY, "SpO2", spo2, 93.0,
               f"SpO2 {spo2:.1f}% ≤ 93% — supplemental O2 advised")

    if rr >= RR_CRISIS_HIGH:
        _alarm(AlarmTier.CRISIS, "RR", rr, RR_CRISIS_HIGH,
               f"RR {rr:.0f}/min ≥ {RR_CRISIS_HIGH} — tachypnoea crisis")
    elif rr >= RR_WARN_HIGH:
        _alarm(AlarmTier.WARNING, "RR", rr, RR_WARN_HIGH,
               f"RR {rr:.0f}/min ≥ {RR_WARN_HIGH} — tachypnoea warning")

    if map_val <= MAP_CRISIS_LOW:
        _alarm(AlarmTier.CRISIS, "MAP", map_val, MAP_CRISIS_LOW,
               f"MAP {map_val:.0f} mmHg ≤ {MAP_CRISIS_LOW} — hypotension crisis")
    elif map_val <= MAP_WARN_LOW:
        _alarm(AlarmTier.WARNING, "MAP", map_val, MAP_WARN_LOW,
               f"MAP {map_val:.0f} mmHg ≤ {MAP_WARN_LOW} — hypotension warning")

    if temp >= TEMP_CRISIS_HIGH:
        _alarm(AlarmTier.CRISIS, "Temp", temp, TEMP_CRISIS_HIGH,
               f"Temp {temp:.1f}°C ≥ {TEMP_CRISIS_HIGH}°C — hyperpyrexia")
    elif temp >= TEMP_WARN_HIGH:
        _alarm(AlarmTier.WARNING, "Temp", temp, TEMP_WARN_HIGH,
               f"Temp {temp:.1f}°C ≥ {TEMP_WARN_HIGH}°C — fever")

    return alarms


# ---------------------------------------------------------------------------
# Patient profiles
# ---------------------------------------------------------------------------

PATIENT_PROFILES: List[PatientProfile] = [
    PatientProfile(
        patient_id  = "PT-001",
        name        = "Carol Williams",
        age         = 74,
        gender      = "F",
        unit        = "ICU",
        bed         = "ICU-1C",
        scenario    = ScenarioType.RESPIRATORY_DETERIORATION,
        admission_dx = "Post-extubation respiratory insufficiency",
        base_hr     = 88,
        base_sbp    = 118,
        base_dbp    = 72,
        base_spo2   = 96.5,
        base_rr     = 16,
        base_temp   = 37.1,
        devices     = ["Masimo SpO2 Root", "Philips IntelliVue MX800",
                       "Draeger V500 Ventilator", "Edwards EV1000 CO"],
    ),
    PatientProfile(
        patient_id  = "PT-002",
        name        = "Alice Johnson",
        age         = 61,
        gender      = "F",
        unit        = "ICU",
        bed         = "ICU-3A",
        scenario    = ScenarioType.SEPSIS_RISK,
        admission_dx = "Pneumonia with SIRS criteria",
        base_hr     = 92,
        base_sbp    = 122,
        base_dbp    = 74,
        base_spo2   = 95.0,
        base_rr     = 18,
        base_temp   = 37.9,
        devices     = ["Nihon Kohden BSM-3562", "Masimo SpO2", "Philips CX50 Echo"],
    ),
    PatientProfile(
        patient_id  = "PT-003",
        name        = "Eleanor Thompson",
        age         = 83,
        gender      = "F",
        unit        = "ED",
        bed         = "ED-8",
        scenario    = ScenarioType.ARRHYTHMIA,
        admission_dx = "Paroxysmal atrial fibrillation",
        base_hr     = 78,
        base_sbp    = 138,
        base_dbp    = 82,
        base_spo2   = 97.0,
        base_rr     = 14,
        base_temp   = 36.8,
        devices     = ["GE Dash 4000", "Zoll AED Plus"],
    ),
    PatientProfile(
        patient_id  = "PT-004",
        name        = "Bob Martinez",
        age         = 48,
        gender      = "M",
        unit        = "CARD",
        bed         = "CARD-7B",
        scenario    = ScenarioType.POST_OP_INSTABILITY,
        admission_dx = "Post-CABG day 1",
        base_hr     = 72,
        base_sbp    = 126,
        base_dbp    = 78,
        base_spo2   = 98.0,
        base_rr     = 14,
        base_temp   = 37.2,
        devices     = ["Philips IntelliVue MX700", "Terumo CVP Monitor",
                       "Abbott i-STAT", "Fresenius Kabi Agilia Pump"],
    ),
    PatientProfile(
        patient_id  = "PT-005",
        name        = "David Chen",
        age         = 36,
        gender      = "M",
        unit        = "NEURO",
        bed         = "NEURO-2",
        scenario    = ScenarioType.DEVICE_DISCONNECT,
        admission_dx = "TBI — mild concussion, observation",
        base_hr     = 66,
        base_sbp    = 112,
        base_dbp    = 68,
        base_spo2   = 98.5,
        base_rr     = 13,
        base_temp   = 36.6,
        devices     = ["Natus Neurology EEG", "Masimo Radical-7"],
    ),
]


# ---------------------------------------------------------------------------
# Trend ring-buffer helper
# ---------------------------------------------------------------------------

class _TrendBuffer:
    def __init__(self, maxlen: int = 12):
        self._buf: List[float] = []
        self._maxlen = maxlen

    def push(self, v: float) -> List[float]:
        self._buf.append(round(v, 1))
        if len(self._buf) > self._maxlen:
            self._buf = self._buf[-self._maxlen:]
        return list(self._buf)


# ---------------------------------------------------------------------------
# PatientSimulator — the core engine
# ---------------------------------------------------------------------------

class PatientSimulator:
    """
    Thread-safe simulator. Call get_snapshot(patient_id) or get_all_snapshots()
    from any thread. Internally advances state every tick_interval seconds.
    """

    def __init__(self, tick_interval: float = 2.0):
        self._tick        = tick_interval
        self._start_time  = time.time()
        self._lock        = threading.Lock()
        self._snapshots:  Dict[str, VitalSnapshot] = {}
        self._alarm_history: List[AlarmEvent]       = []
        self._rngs:       Dict[str, random.Random]  = {}
        self._trends:     Dict[str, Dict[str, _TrendBuffer]] = {}

        for p in PATIENT_PROFILES:
            seed = int(uuid.UUID(p.patient_id.replace("PT-", "0000000" + p.patient_id[-3:]).zfill(32).replace("-","")) % (2**32)) if False else hash(p.patient_id) % (2**31)
            self._rngs[p.patient_id] = random.Random(seed)
            self._trends[p.patient_id] = {
                "hr":  _TrendBuffer(), "spo2": _TrendBuffer(),
                "rr":  _TrendBuffer(), "map":  _TrendBuffer(),
            }
            self._tick_patient(p, 0.0)   # initial snapshot

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    def _run(self):
        while True:
            elapsed = time.time() - self._start_time
            for profile in PATIENT_PROFILES:
                self._tick_patient(profile, elapsed)
            time.sleep(self._tick)

    # ------------------------------------------------------------------
    def _tick_patient(self, profile: PatientProfile, elapsed: float):
        rng = self._rngs[profile.patient_id]
        hr, sbp, dbp, spo2, rr, temp, etco2 = _apply_scenario(profile, elapsed, rng)

        # Handle device-offline NaN values
        offline = math.isnan(hr) if not math.isfinite(hr) else False
        if offline:
            hr = sbp = dbp = spo2 = rr = float("nan")

        map_val = (sbp + 2 * dbp) / 3.0 if not offline else float("nan")

        # Trends
        tb = self._trends[profile.patient_id]
        hr_t   = tb["hr"].push(hr   if not math.isnan(hr)   else 0)
        spo2_t = tb["spo2"].push(spo2 if not math.isnan(spo2) else 0)
        rr_t   = tb["rr"].push(rr   if not math.isnan(rr)   else 0)
        map_t  = tb["map"].push(map_val if not math.isnan(map_val) else 0)

        # NEWS2
        n2 = 0 if offline else _news2(hr, sbp, rr, spo2, temp,
                                       on_o2=(profile.scenario == ScenarioType.RESPIRATORY_DETERIORATION))
        risk = _risk_level(n2) if not offline else "UNKNOWN"

        # Alarms
        alarms = [] if offline else _check_alarms(
            profile.patient_id, hr, spo2, rr,
            map_val if not math.isnan(map_val) else 0.0, temp)

        # ECG
        pvcs    = (profile.scenario == ScenarioType.ARRHYTHMIA)
        ecg_pts = _ecg_segment(rng, hr if not offline else 80.0,
                                pvcs=pvcs, artifact=offline)

        # Device status
        if offline:
            online_devs  = []
            offline_devs = profile.devices[:]
        elif profile.scenario == ScenarioType.RESPIRATORY_DETERIORATION and elapsed > 60:
            # Draeger V500 goes offline at 60s in respiratory scenario
            online_devs  = [d for d in profile.devices if "Draeger" not in d]
            offline_devs = [d for d in profile.devices if "Draeger" in d]
        else:
            online_devs  = profile.devices[:]
            offline_devs = []

        snap = VitalSnapshot(
            patient_id   = profile.patient_id,
            timestamp    = time.time(),
            hr           = round(hr, 1)    if not offline else float("nan"),
            sbp          = round(sbp, 1)   if not offline else float("nan"),
            dbp          = round(dbp, 1)   if not offline else float("nan"),
            map_val      = round(map_val, 1) if not offline else float("nan"),
            spo2         = round(spo2, 2)  if not offline else float("nan"),
            rr           = round(rr, 1)    if not offline else float("nan"),
            temp         = round(temp, 1)  if not offline else float("nan"),
            etco2        = round(etco2, 1) if etco2 is not None else None,
            news2        = n2,
            risk_level   = risk,
            active_alarms = alarms,
            hr_trend     = hr_t,
            spo2_trend   = spo2_t,
            rr_trend     = rr_t,
            map_trend    = map_t,
            ecg_wave     = ecg_pts,
            devices_online  = online_devs,
            devices_offline = offline_devs,
        )

        with self._lock:
            self._snapshots[profile.patient_id] = snap
            for a in alarms:
                # Deduplicate: only keep latest alarm per parameter per patient
                self._alarm_history = [
                    h for h in self._alarm_history
                    if not (h.patient_id == a.patient_id and h.parameter == a.parameter)
                ]
                self._alarm_history.append(a)
                # Cap history
                if len(self._alarm_history) > 500:
                    self._alarm_history = self._alarm_history[-500:]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_snapshot(self, patient_id: str) -> Optional[VitalSnapshot]:
        with self._lock:
            return self._snapshots.get(patient_id)

    def get_all_snapshots(self) -> List[VitalSnapshot]:
        with self._lock:
            return list(self._snapshots.values())

    def get_profile(self, patient_id: str) -> Optional[PatientProfile]:
        return next((p for p in PATIENT_PROFILES if p.patient_id == patient_id), None)

    def get_all_profiles(self) -> List[PatientProfile]:
        return PATIENT_PROFILES

    def get_active_alarms(self) -> List[AlarmEvent]:
        with self._lock:
            # Return highest-priority alarm per patient
            seen: Dict[str, AlarmEvent] = {}
            for a in reversed(self._alarm_history):
                if a.patient_id not in seen:
                    seen[a.patient_id] = a
            all_alarms = list(self._alarm_history[-50:])
        return sorted(all_alarms, key=lambda a: (
            {"CRISIS": 0, "WARNING": 1, "ADVISORY": 2}[a.tier], a.fired_at
        ))

    def get_alarm_history(self, patient_id: Optional[str] = None,
                          limit: int = 100) -> List[AlarmEvent]:
        with self._lock:
            history = self._alarm_history[-limit:]
        if patient_id:
            history = [a for a in history if a.patient_id == patient_id]
        return list(reversed(history))

    def snapshot_as_dict(self, snap: VitalSnapshot) -> dict:
        """Serialise VitalSnapshot for JSON / Streamlit display."""
        return {
            "patient_id":   snap.patient_id,
            "timestamp":    snap.timestamp,
            "ts_iso":       datetime.fromtimestamp(snap.timestamp, tz=timezone.utc).isoformat(),
            "hr":           snap.hr,
            "sbp":          snap.sbp,
            "dbp":          snap.dbp,
            "map":          snap.map_val,
            "spo2":         snap.spo2,
            "rr":           snap.rr,
            "temp":         snap.temp,
            "etco2":        snap.etco2,
            "news2":        snap.news2,
            "risk_level":   snap.risk_level,
            "hr_trend":     snap.hr_trend,
            "spo2_trend":   snap.spo2_trend,
            "rr_trend":     snap.rr_trend,
            "map_trend":    snap.map_trend,
            "ecg_wave":     snap.ecg_wave,
            "devices_online":  snap.devices_online,
            "devices_offline": snap.devices_offline,
            "alarms": [
                {
                    "alarm_id":  a.alarm_id,
                    "tier":      a.tier,
                    "parameter": a.parameter,
                    "value":     a.value,
                    "threshold": a.threshold,
                    "message":   a.message,
                    "fired_at":  a.fired_at,
                }
                for a in snap.active_alarms
            ],
        }

    def elapsed_seconds(self) -> float:
        return time.time() - self._start_time


# ---------------------------------------------------------------------------
# Module-level singleton (created on first import)
# ---------------------------------------------------------------------------

_simulator: Optional[PatientSimulator] = None
_sim_lock = threading.Lock()


def get_simulator() -> PatientSimulator:
    global _simulator
    if _simulator is None:
        with _sim_lock:
            if _simulator is None:
                _simulator = PatientSimulator(tick_interval=2.0)
    return _simulator


# ---------------------------------------------------------------------------
# Optional: standalone FastAPI app on port 8001
# ---------------------------------------------------------------------------

def _build_fastapi_app():
    try:
        from fastapi import FastAPI, WebSocket, WebSocketDisconnect
        from fastapi.middleware.cors import CORSMiddleware
        import asyncio, json
    except ImportError:
        return None

    api = FastAPI(title="Patient Monitor Simulator API", version="1.0.0")
    api.add_middleware(CORSMiddleware, allow_origins=["*"],
                       allow_methods=["*"], allow_headers=["*"])
    sim = get_simulator()

    @api.get("/api/patients")
    async def list_patients():
        snaps = sim.get_all_snapshots()
        profs = {p.patient_id: p for p in sim.get_all_profiles()}
        return [
            {**sim.snapshot_as_dict(s),
             "name": profs[s.patient_id].name,
             "unit": profs[s.patient_id].unit,
             "bed":  profs[s.patient_id].bed,
             "scenario": profs[s.patient_id].scenario,
             "admission_dx": profs[s.patient_id].admission_dx}
            for s in snaps
        ]

    @api.get("/api/patients/{patient_id}")
    async def get_patient(patient_id: str):
        snap = sim.get_snapshot(patient_id)
        prof = sim.get_profile(patient_id)
        if snap is None or prof is None:
            from fastapi import HTTPException
            raise HTTPException(404, "Patient not found")
        return {**sim.snapshot_as_dict(snap), "name": prof.name,
                "unit": prof.unit, "bed": prof.bed,
                "scenario": prof.scenario, "admission_dx": prof.admission_dx}

    @api.get("/api/alarms")
    async def get_alarms():
        alarms = sim.get_active_alarms()
        profs  = {p.patient_id: p for p in sim.get_all_profiles()}
        return [
            {**a.__dict__,
             "patient_name": profs.get(a.patient_id, PatientProfile.__new__(PatientProfile)).name
             if a.patient_id in profs else "Unknown"}
            for a in alarms
        ]

    @api.websocket("/ws/vitals")
    async def vitals_ws(websocket: WebSocket):
        await websocket.accept()
        try:
            while True:
                snaps = sim.get_all_snapshots()
                profs = {p.patient_id: p for p in sim.get_all_profiles()}
                payload = [
                    {**sim.snapshot_as_dict(s),
                     "name": profs[s.patient_id].name,
                     "unit": profs[s.patient_id].unit}
                    for s in snaps
                ]
                await websocket.send_text(json.dumps(payload, default=str))
                await asyncio.sleep(2.0)
        except WebSocketDisconnect:
            pass

    @api.get("/api/health")
    async def health():
        return {"status": "ok", "elapsed_s": sim.elapsed_seconds(),
                "patients": len(PATIENT_PROFILES)}

    return api


# Allow: uvicorn simulator.patient_monitor:app --port 8001
try:
    app = _build_fastapi_app()
except Exception:
    app = None


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("simulator.patient_monitor:app", host="0.0.0.0",
                port=8001, log_level="info")
