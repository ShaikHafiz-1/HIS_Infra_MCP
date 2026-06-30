"""
FHIR R4 → Internal DTO Normalizer.

Maps raw FHIR JSON resources to:
  1. Dicts with the same field names as VitalSnapshot / PatientProfile
     so the existing intent router and UI require zero changes.
  2. FHIRPatient — a wrapper DTO for FHIR-specific extras that have no
     simulator equivalent (conditions, medications, allergies, etc.).

NEWS2 computation follows RCP 2017 spec (same implementation as simulator).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# LOINC vital-sign code → internal field name
# ---------------------------------------------------------------------------

LOINC_VITALS: Dict[str, str] = {
    "8867-4":  "hr",    # Heart rate
    "59408-5": "spo2",  # O2 saturation (pulse oximetry)
    "9279-1":  "rr",    # Respiratory rate
    "8310-5":  "temp",  # Body temperature
    "8480-6":  "sbp",   # Systolic blood pressure
    "8462-4":  "dbp",   # Diastolic blood pressure
    "8478-0":  "map",   # Mean arterial pressure
    "55284-4": "bp",    # Blood pressure panel (component-based)
    "2708-6":  "spo2",  # O2 saturation (alternate code)
    "59576-9": "bmi",   # BMI (informational only)
}

# SNOMED / ICD-10 codes that map to simulator ScenarioTypes (used for condition matching)
ARRHYTHMIA_CODES = {
    # SNOMED CT
    "698247002", "195080001", "164889003", "427084000",
    # ICD-10-CM
    "I49.9", "I48", "I48.0", "I48.1", "I48.91", "I47.1", "I47.2",
}
SEPSIS_CODES = {
    # SNOMED CT
    "91302008", "10001005",
    # ICD-10-CM
    "A41.9", "A41.0", "A41.1", "A41.50",
}
RESPIRATORY_CODES = {
    "267036007", "230145002",
    "J80", "J96.0", "J96.00", "J18.9",
}


# ---------------------------------------------------------------------------
# FHIRPatient DTO  (wraps PatientProfile fields + FHIR-specific extras)
# ---------------------------------------------------------------------------

@dataclass
class FHIRPatient:
    """
    Normalised representation of a FHIR Patient + associated resources.

    Fields that overlap with PatientProfile use the same names so they
    can be consumed by the same intent handlers with no changes.
    """
    # Core (mirrors PatientProfile)
    patient_id:   str           # FHIR resource id
    name:         str
    age:          Optional[int]
    gender:       Optional[str]
    unit:         str = "FHIR"  # ward/location if available
    bed:          str = ""
    admission_dx: str = ""

    # FHIR extras
    fhir_id:      str = ""
    mrn:          Optional[str] = None
    birth_date:   Optional[str] = None

    # Associated resources (normalised dicts)
    conditions:   List[Dict] = field(default_factory=list)
    medications:  List[Dict] = field(default_factory=list)
    encounters:   List[Dict] = field(default_factory=list)
    allergies:    List[Dict] = field(default_factory=list)
    procedures:   List[Dict] = field(default_factory=list)
    devices:      List[Dict] = field(default_factory=list)

    # Latest vitals (mirrors VitalSnapshot fields)
    hr:    Optional[float] = None
    sbp:   Optional[float] = None
    dbp:   Optional[float] = None
    map_val: Optional[float] = None
    spo2:  Optional[float] = None
    rr:    Optional[float] = None
    temp:  Optional[float] = None
    news2: int = 0
    risk_level: str = "UNKNOWN"


# ---------------------------------------------------------------------------
# Patient normalizer
# ---------------------------------------------------------------------------

def norm_patient(fhir_pt: Dict[str, Any]) -> Dict[str, Any]:
    """FHIR Patient → dict with PatientProfile-compatible fields."""
    fhir_id = fhir_pt.get("id", "")

    # Name
    names = fhir_pt.get("name", [])
    full_name = ""
    if names:
        n = names[0]
        given  = " ".join(n.get("given", []))
        family = n.get("family", "")
        full_name = f"{given} {family}".strip()
    if not full_name:
        full_name = fhir_pt.get("text", {}).get("div", "Unknown")[:40]

    # Age from birthDate
    age: Optional[int] = None
    birth_date = fhir_pt.get("birthDate")
    if birth_date:
        try:
            bd = datetime.fromisoformat(birth_date)
            age = int((datetime.now() - bd).days / 365.25)
        except (ValueError, TypeError):
            pass

    # MRN from identifiers
    mrn: Optional[str] = None
    for ident in fhir_pt.get("identifier", []):
        coding = ident.get("type", {}).get("coding", [{}])
        if coding and coding[0].get("code") == "MR":
            mrn = ident.get("value")
            break
    if mrn is None:
        for ident in fhir_pt.get("identifier", []):
            if ident.get("value"):
                mrn = ident["value"]
                break

    return {
        "patient_id":   fhir_id,
        "fhir_id":      fhir_id,
        "name":         full_name,
        "age":          age,
        "gender":       fhir_pt.get("gender"),
        "birth_date":   birth_date,
        "mrn":          mrn,
        "unit":         "FHIR",
        "bed":          "",
        "admission_dx": "",
    }


# ---------------------------------------------------------------------------
# Observation / vital sign normalizer
# ---------------------------------------------------------------------------

def norm_observations_to_vitals(observations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate a list of FHIR Observations into a flat vitals dict.

    Returns dict with keys: hr, sbp, dbp, map_val, spo2, rr, temp, news2, risk_level.
    Missing values are None.
    """
    vitals: Dict[str, Optional[float]] = {
        "hr": None, "sbp": None, "dbp": None, "map_val": None,
        "spo2": None, "rr": None, "temp": None,
    }

    # Process most-recent first (observations should be sorted -date)
    for obs in observations:
        _apply_observation(obs, vitals)

    # Derive MAP if not directly present
    if vitals["map_val"] is None and vitals["sbp"] and vitals["dbp"]:
        vitals["map_val"] = round(
            (vitals["sbp"] + 2 * vitals["dbp"]) / 3, 1
        )

    news2 = compute_news2(vitals)
    risk  = _news2_to_risk(news2)

    return {**vitals, "news2": news2, "risk_level": risk}


def _apply_observation(obs: Dict[str, Any], vitals: Dict[str, Optional[float]]) -> None:
    """Extract value from one Observation and write into vitals dict."""
    # Find LOINC code
    loinc_code: Optional[str] = None
    for coding in obs.get("code", {}).get("coding", []):
        sys = coding.get("system", "")
        if "loinc.org" in sys or not sys:
            loinc_code = coding.get("code")
            break

    # Blood pressure panel — values in component[]
    if loinc_code == "55284-4" or loinc_code == "85354-9":
        for comp in obs.get("component", []):
            for comp_coding in comp.get("code", {}).get("coding", []):
                comp_code = comp_coding.get("code")
                field_name = LOINC_VITALS.get(comp_code)
                if field_name in ("sbp", "dbp") and vitals[field_name] is None:
                    v = _extract_quantity(comp)
                    if v is not None:
                        vitals[field_name] = v
        return

    field_name = LOINC_VITALS.get(loinc_code) if loinc_code else None
    if field_name is None or field_name not in vitals:
        return

    v = _extract_quantity(obs)
    if v is not None and vitals[field_name] is None:
        # Handle unit conversion (Fahrenheit → Celsius for temp)
        if field_name == "temp":
            unit_str = (
                obs.get("valueQuantity", {}).get("unit", "")
                or obs.get("valueQuantity", {}).get("code", "")
            )
            if unit_str in ("[degF]", "°F", "F"):
                v = round((v - 32) * 5 / 9, 1)
        vitals[field_name] = v


def _extract_quantity(obs: Dict[str, Any]) -> Optional[float]:
    """Pull numeric value from valueQuantity, component valueQuantity, or valueInteger."""
    vq = obs.get("valueQuantity")
    if vq and vq.get("value") is not None:
        try:
            return float(vq["value"])
        except (TypeError, ValueError):
            pass
    vi = obs.get("valueInteger")
    if vi is not None:
        return float(vi)
    return None


# ---------------------------------------------------------------------------
# NEWS2 scorer (RCP 2017) — mirrors patient_monitor.py implementation
# ---------------------------------------------------------------------------

def compute_news2(vitals: Dict[str, Any]) -> int:
    """
    Compute NEWS2 score from a vitals dict.
    Returns 0 if data is insufficient (< 3 parameters present).
    """
    score = 0
    present = 0

    rr   = vitals.get("rr")
    spo2 = vitals.get("spo2")
    sbp  = vitals.get("sbp")
    hr   = vitals.get("hr")
    temp = vitals.get("temp")

    if rr is not None and not math.isnan(rr):
        present += 1
        if rr <= 8 or rr >= 25:   score += 3
        elif rr >= 21:             score += 2
        elif rr >= 12:             score += 0
        elif rr >= 9:              score += 1

    if spo2 is not None and not math.isnan(spo2):
        present += 1
        if spo2 <= 91:   score += 3
        elif spo2 <= 93: score += 2
        elif spo2 <= 95: score += 1

    if sbp is not None and not math.isnan(sbp):
        present += 1
        if sbp <= 90 or sbp >= 220:  score += 3
        elif sbp <= 100:             score += 2
        elif sbp <= 110:             score += 1

    if hr is not None and not math.isnan(hr):
        present += 1
        if hr <= 40 or hr >= 131:   score += 3
        elif hr >= 111:              score += 2
        elif hr >= 91 or hr <= 50:   score += 1

    if temp is not None and not math.isnan(temp):
        present += 1
        if temp <= 35.0:             score += 3
        elif temp >= 39.1:           score += 2
        elif temp <= 36.0 or temp >= 38.1: score += 1

    return score if present >= 3 else 0


def _news2_to_risk(score: int) -> str:
    if score >= 7:   return "CRITICAL"
    if score >= 5:   return "HIGH"
    if score >= 3:   return "MEDIUM"
    if score >= 1:   return "LOW"
    return "STABLE"


# ---------------------------------------------------------------------------
# Other resource normalizers
# ---------------------------------------------------------------------------

def norm_condition(c: Dict[str, Any]) -> Dict[str, Any]:
    """FHIR Condition → minimal display dict."""
    coding = c.get("code", {}).get("coding", [{}])[0]
    return {
        "code":        coding.get("code", ""),
        "system":      coding.get("system", ""),
        "display":     coding.get("display") or c.get("code", {}).get("text", "Unknown"),
        "status":      c.get("clinicalStatus", {}).get("coding", [{}])[0].get("code", ""),
        "onset":       c.get("onsetDateTime", c.get("onsetString", "")),
        "patient_ref": _ref_id(c.get("subject", {}).get("reference", "")),
    }


def norm_medication(m: Dict[str, Any]) -> Dict[str, Any]:
    """FHIR MedicationRequest → minimal display dict."""
    med_ref  = m.get("medicationReference", {})
    med_cc   = m.get("medicationCodeableConcept", {})
    med_name = (
        med_ref.get("display")
        or med_cc.get("text")
        or (med_cc.get("coding") or [{}])[0].get("display")
        or "Unknown"
    )
    dosage = ""
    if m.get("dosageInstruction"):
        dosage = m["dosageInstruction"][0].get("text", "")
    return {
        "name":       med_name,
        "status":     m.get("status", ""),
        "intent":     m.get("intent", ""),
        "dosage":     dosage,
        "authored":   m.get("authoredOn", ""),
        "patient_ref": _ref_id(m.get("subject", {}).get("reference", "")),
    }


def norm_encounter(e: Dict[str, Any]) -> Dict[str, Any]:
    """FHIR Encounter → minimal display dict."""
    enc_class = e.get("class", {})
    if isinstance(enc_class, dict):
        class_code = enc_class.get("code", "")
    else:
        class_code = ""
    period = e.get("period", {})
    return {
        "encounter_id": e.get("id", ""),
        "class":        class_code,
        "status":       e.get("status", ""),
        "start":        period.get("start", ""),
        "end":          period.get("end", ""),
        "reason":       (e.get("reasonCode") or [{}])[0].get("text", ""),
        "patient_ref":  _ref_id(e.get("subject", {}).get("reference", "")),
    }


def norm_device(d: Dict[str, Any]) -> Dict[str, Any]:
    """FHIR Device → minimal display dict."""
    dtype = d.get("type", {})
    type_display = (
        dtype.get("text")
        or (dtype.get("coding") or [{}])[0].get("display")
        or "Unknown device"
    )
    return {
        "device_id":    d.get("id", ""),
        "type":         type_display,
        "status":       d.get("status", ""),
        "manufacturer": d.get("manufacturer", ""),
        "model":        d.get("modelNumber", d.get("model", "")),
        "patient_ref":  _ref_id(d.get("patient", {}).get("reference", "")),
    }


def norm_allergy(a: Dict[str, Any]) -> Dict[str, Any]:
    """FHIR AllergyIntolerance → minimal display dict."""
    substance = a.get("code", {})
    name = (
        substance.get("text")
        or (substance.get("coding") or [{}])[0].get("display")
        or "Unknown"
    )
    return {
        "substance":    name,
        "type":         a.get("type", ""),
        "criticality":  a.get("criticality", ""),
        "status":       a.get("clinicalStatus", {}).get("coding", [{}])[0].get("code", ""),
        "patient_ref":  _ref_id(a.get("patient", {}).get("reference", "")),
    }


def norm_procedure(p: Dict[str, Any]) -> Dict[str, Any]:
    """FHIR Procedure → minimal display dict."""
    coding = p.get("code", {}).get("coding", [{}])[0]
    return {
        "procedure":   coding.get("display") or p.get("code", {}).get("text", "Unknown"),
        "code":        coding.get("code", ""),
        "status":      p.get("status", ""),
        "performed":   p.get("performedDateTime", p.get("performedString", "")),
        "patient_ref": _ref_id(p.get("subject", {}).get("reference", "")),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ref_id(ref: str) -> str:
    """Extract resource ID from a FHIR reference string like 'Patient/123'."""
    return ref.split("/")[-1] if "/" in ref else ref


def condition_matches_category(cond: Dict[str, Any], category: str) -> bool:
    """
    Return True if a normalised condition dict is in a given clinical category.
    category: 'arrhythmia' | 'sepsis' | 'respiratory'
    """
    code = cond.get("code", "").strip()
    if category == "arrhythmia":
        return code in ARRHYTHMIA_CODES
    if category == "sepsis":
        return code in SEPSIS_CODES
    if category == "respiratory":
        return code in RESPIRATORY_CODES
    return False


# ---------------------------------------------------------------------------
# Module-level singleton normalizer (stateless, but convenient)
# ---------------------------------------------------------------------------

class _Normalizer:
    norm_patient               = staticmethod(norm_patient)
    norm_observations_to_vitals = staticmethod(norm_observations_to_vitals)
    norm_condition             = staticmethod(norm_condition)
    norm_medication            = staticmethod(norm_medication)
    norm_encounter             = staticmethod(norm_encounter)
    norm_device                = staticmethod(norm_device)
    norm_allergy               = staticmethod(norm_allergy)
    norm_procedure             = staticmethod(norm_procedure)
    compute_news2              = staticmethod(compute_news2)


normalizer = _Normalizer()
