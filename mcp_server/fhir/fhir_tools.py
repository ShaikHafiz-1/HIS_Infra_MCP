"""
FHIR MCP Tool Business Logic.

Each function in this module corresponds to one MCP tool.  They call the
FHIRConnector, normalise the response, and return structured dicts suitable
for returning from an MCP tool handler.

Fallback contract: when the connector is disabled or returns nothing, every
function returns an empty/stub result (never raises).  The caller decides
whether to fall through to simulator data.

All functions are synchronous — safe to call from Streamlit (intent router)
or from async MCP tool handlers via asyncio.to_thread().
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from mcp_server.fhir.connector import get_fhir_connector
from mcp_server.fhir.normalizer import (
    FHIRPatient,
    norm_patient,
    norm_observations_to_vitals,
    norm_condition,
    norm_medication,
    norm_encounter,
    norm_device,
    norm_allergy,
    norm_procedure,
    compute_news2,
    _news2_to_risk,
    condition_matches_category,
    ARRHYTHMIA_CODES,
    LOINC_VITALS,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: build a FHIRPatient from raw resources
# ---------------------------------------------------------------------------

def _build_fhir_patient(
    pt_resource: Dict[str, Any],
    vitals_raw:  Optional[List[Dict]] = None,
    conditions:  Optional[List[Dict]] = None,
    medications: Optional[List[Dict]] = None,
    encounters:  Optional[List[Dict]] = None,
    devices:     Optional[List[Dict]] = None,
    allergies:   Optional[List[Dict]] = None,
    procedures:  Optional[List[Dict]] = None,
) -> FHIRPatient:
    base = norm_patient(pt_resource)
    vitals = norm_observations_to_vitals(vitals_raw or [])

    # Location / unit from most-recent encounter
    enc_list = [norm_encounter(e) for e in (encounters or [])]
    unit = "FHIR"
    if enc_list:
        unit = enc_list[0].get("class", "FHIR") or "FHIR"

    # Primary admission diagnosis from conditions
    cond_list = [norm_condition(c) for c in (conditions or [])]
    dx = cond_list[0]["display"] if cond_list else ""

    return FHIRPatient(
        patient_id   = base["patient_id"],
        fhir_id      = base["fhir_id"],
        name         = base["name"],
        age          = base["age"],
        gender       = base["gender"],
        birth_date   = base.get("birth_date"),
        mrn          = base.get("mrn"),
        unit         = unit,
        bed          = "",
        admission_dx = dx,
        conditions   = cond_list,
        medications  = [norm_medication(m) for m in (medications or [])],
        encounters   = enc_list,
        allergies    = [norm_allergy(a) for a in (allergies or [])],
        procedures   = [norm_procedure(p) for p in (procedures or [])],
        devices      = [norm_device(d) for d in (devices or [])],
        hr           = vitals.get("hr"),
        sbp          = vitals.get("sbp"),
        dbp          = vitals.get("dbp"),
        map_val      = vitals.get("map_val"),
        spo2         = vitals.get("spo2"),
        rr           = vitals.get("rr"),
        temp         = vitals.get("temp"),
        news2        = vitals.get("news2", 0),
        risk_level   = vitals.get("risk_level", "UNKNOWN"),
    )


# ---------------------------------------------------------------------------
# Tool 1 — fhir_get_patient
# ---------------------------------------------------------------------------

def get_patient_by_id(fhir_patient_id: str) -> Dict[str, Any]:
    """
    Retrieve demographics and current vitals for a single FHIR patient.
    GET /Patient/{id}  +  GET /Observation?patient={id}&category=vital-signs
    """
    conn = get_fhir_connector()
    if not conn.is_enabled():
        return {"source": "simulator", "fhir_enabled": False}

    pt = conn.get_patient(fhir_patient_id)
    if not pt:
        return {"error": f"Patient {fhir_patient_id} not found", "fhir_enabled": True}

    vitals_raw  = conn.get_vitals(fhir_patient_id)
    conditions  = conn.get_conditions(fhir_patient_id)
    medications = conn.get_medications(fhir_patient_id)
    encounters  = conn.get_encounters(patient_id=fhir_patient_id)
    devices     = conn.get_devices(fhir_patient_id)
    allergies   = conn.get_allergies(fhir_patient_id)
    procedures  = conn.get_procedures(fhir_patient_id)

    patient = _build_fhir_patient(
        pt, vitals_raw, conditions, medications, encounters, devices, allergies, procedures
    )

    return {
        "source":       "fhir",
        "fhir_enabled": True,
        "patient_id":   patient.patient_id,
        "name":         patient.name,
        "age":          patient.age,
        "gender":       patient.gender,
        "mrn":          patient.mrn,
        "unit":         patient.unit,
        "admission_dx": patient.admission_dx,
        "vitals": {
            "hr":      patient.hr,
            "sbp":     patient.sbp,
            "dbp":     patient.dbp,
            "map_val": patient.map_val,
            "spo2":    patient.spo2,
            "rr":      patient.rr,
            "temp":    patient.temp,
        },
        "news2":        patient.news2,
        "risk_level":   patient.risk_level,
        "conditions":   patient.conditions[:5],
        "medications":  patient.medications[:5],
        "encounters":   patient.encounters[:3],
        "devices":      patient.devices[:5],
        "allergies":    patient.allergies[:5],
        "procedures":   patient.procedures[:5],
    }


# ---------------------------------------------------------------------------
# Tool 2 — fhir_search_patients
# ---------------------------------------------------------------------------

def search_patients(name: str) -> Dict[str, Any]:
    """
    Search patients by name.
    GET /Patient?name={name}
    """
    conn = get_fhir_connector()
    if not conn.is_enabled():
        return {"source": "simulator", "fhir_enabled": False, "patients": []}

    raw_patients = conn.search_patients(name)
    patients = [norm_patient(p) for p in raw_patients]

    return {
        "source":       "fhir",
        "fhir_enabled": True,
        "query":        name,
        "count":        len(patients),
        "patients":     patients[:20],
    }


# ---------------------------------------------------------------------------
# Tool 3 — fhir_get_patient_vitals
# ---------------------------------------------------------------------------

def get_patient_vitals(fhir_patient_id: str, limit: int = 20) -> Dict[str, Any]:
    """
    Retrieve latest vital signs for a patient.
    GET /Observation?patient={id}&category=vital-signs&_sort=-date
    """
    conn = get_fhir_connector()
    if not conn.is_enabled():
        return {"source": "simulator", "fhir_enabled": False}

    raw = conn.get_vitals(fhir_patient_id, limit=limit)
    vitals = norm_observations_to_vitals(raw)

    return {
        "source":       "fhir",
        "fhir_enabled": True,
        "patient_id":   fhir_patient_id,
        "observation_count": len(raw),
        **vitals,
    }


# ---------------------------------------------------------------------------
# Tool 4 — fhir_get_patient_conditions
# ---------------------------------------------------------------------------

def get_patient_conditions(fhir_patient_id: str) -> Dict[str, Any]:
    """
    Retrieve active conditions/diagnoses.
    GET /Condition?patient={id}
    """
    conn = get_fhir_connector()
    if not conn.is_enabled():
        return {"source": "simulator", "fhir_enabled": False, "conditions": []}

    raw = conn.get_conditions(fhir_patient_id)
    conditions = [norm_condition(c) for c in raw]

    return {
        "source":       "fhir",
        "fhir_enabled": True,
        "patient_id":   fhir_patient_id,
        "count":        len(conditions),
        "conditions":   conditions,
    }


# ---------------------------------------------------------------------------
# Tool 5 — fhir_get_patient_medications
# ---------------------------------------------------------------------------

def get_patient_medications(fhir_patient_id: str) -> Dict[str, Any]:
    """
    Retrieve active medication requests.
    GET /MedicationRequest?patient={id}
    """
    conn = get_fhir_connector()
    if not conn.is_enabled():
        return {"source": "simulator", "fhir_enabled": False, "medications": []}

    raw = conn.get_medications(fhir_patient_id)
    medications = [norm_medication(m) for m in raw]

    return {
        "source":       "fhir",
        "fhir_enabled": True,
        "patient_id":   fhir_patient_id,
        "count":        len(medications),
        "medications":  medications,
    }


# ---------------------------------------------------------------------------
# Tool 6 — fhir_get_patient_encounters
# ---------------------------------------------------------------------------

def get_patient_encounters(fhir_patient_id: str) -> Dict[str, Any]:
    """
    Retrieve encounter history.
    GET /Encounter?patient={id}
    """
    conn = get_fhir_connector()
    if not conn.is_enabled():
        return {"source": "simulator", "fhir_enabled": False, "encounters": []}

    raw = conn.get_encounters(patient_id=fhir_patient_id)
    encounters = [norm_encounter(e) for e in raw]

    return {
        "source":       "fhir",
        "fhir_enabled": True,
        "patient_id":   fhir_patient_id,
        "count":        len(encounters),
        "encounters":   encounters,
    }


# ---------------------------------------------------------------------------
# Tool 7 — fhir_get_icu_patients
# ---------------------------------------------------------------------------

def get_icu_patients() -> Dict[str, Any]:
    """
    Retrieve all inpatient (IMP class) encounters as a census.
    GET /Encounter?class=http://terminology.hl7.org/CodeSystem/v3-ActCode|IMP
    """
    conn = get_fhir_connector()
    if not conn.is_enabled():
        return {"source": "simulator", "fhir_enabled": False, "patients": []}

    # HAPI FHIR public server uses coded class
    raw = conn.get_encounters(
        encounter_class="http://terminology.hl7.org/CodeSystem/v3-ActCode|IMP"
    )
    # Also try short code variant
    if not raw:
        raw = conn.get_encounters(encounter_class="IMP")

    patients = []
    for enc in raw[:30]:
        ne = norm_encounter(enc)
        if ne["status"] in ("in-progress", "arrived", "triaged", ""):
            pt_ref = ne.get("patient_ref", "")
            if pt_ref:
                pt = conn.get_patient(pt_ref)
                if pt:
                    p = norm_patient(pt)
                    patients.append({
                        **p,
                        "encounter_class": ne["class"],
                        "encounter_status": ne["status"],
                        "encounter_start":  ne["start"],
                        "reason":           ne["reason"],
                    })

    return {
        "source":       "fhir",
        "fhir_enabled": True,
        "unit":         "ICU/Inpatient",
        "count":        len(patients),
        "patients":     patients,
    }


# ---------------------------------------------------------------------------
# Tool 8 — fhir_get_patients_with_low_spo2
# ---------------------------------------------------------------------------

def get_patients_with_low_spo2(threshold: float = 90.0) -> Dict[str, Any]:
    """
    Find patients with SpO2 below threshold.
    GET /Observation?code=http://loinc.org|59408-5&value-quantity=lt{threshold}
    """
    conn = get_fhir_connector()
    if not conn.is_enabled():
        return {"source": "simulator", "fhir_enabled": False, "patients": []}

    raw = conn.search_resource("Observation", {
        "code":           "http://loinc.org|59408-5",
        "value-quantity": f"lt{threshold}",
        "_sort":          "-date",
        "_count":         "50",
    })

    # Deduplicate by patient (keep most recent)
    seen: Dict[str, Dict] = {}
    for obs in raw:
        pt_ref = obs.get("subject", {}).get("reference", "")
        pt_id  = pt_ref.split("/")[-1] if "/" in pt_ref else pt_ref
        if pt_id and pt_id not in seen:
            vq  = obs.get("valueQuantity", {})
            val = vq.get("value")
            seen[pt_id] = {
                "patient_id": pt_id,
                "spo2":       val,
                "time":       obs.get("effectiveDateTime", ""),
            }

    return {
        "source":       "fhir",
        "fhir_enabled": True,
        "threshold":    threshold,
        "count":        len(seen),
        "patients":     list(seen.values()),
    }


# ---------------------------------------------------------------------------
# Tool 9 — fhir_get_patients_with_high_news2
# ---------------------------------------------------------------------------

def get_patients_with_high_news2(threshold: int = 5) -> Dict[str, Any]:
    """
    Find patients with NEWS2 score at or above threshold.
    Requires: search inpatient encounters, pull vitals, compute NEWS2.
    """
    conn = get_fhir_connector()
    if not conn.is_enabled():
        return {"source": "simulator", "fhir_enabled": False, "patients": []}

    # Get inpatient encounters
    encs = conn.get_encounters(encounter_class="IMP")
    if not encs:
        encs = conn.get_encounters(
            encounter_class="http://terminology.hl7.org/CodeSystem/v3-ActCode|IMP"
        )

    high_news2_patients = []
    for enc in encs[:20]:
        ne     = norm_encounter(enc)
        pt_ref = ne.get("patient_ref", "")
        if not pt_ref:
            continue
        vitals_raw = conn.get_vitals(pt_ref, limit=15)
        vitals     = norm_observations_to_vitals(vitals_raw)
        score      = vitals.get("news2", 0)
        if score >= threshold:
            pt = conn.get_patient(pt_ref)
            pt_info = norm_patient(pt) if pt else {"patient_id": pt_ref, "name": "Unknown"}
            high_news2_patients.append({
                **pt_info,
                "news2":      score,
                "risk_level": vitals.get("risk_level", "UNKNOWN"),
                "spo2":       vitals.get("spo2"),
                "hr":         vitals.get("hr"),
                "rr":         vitals.get("rr"),
                "sbp":        vitals.get("sbp"),
                "temp":       vitals.get("temp"),
            })

    high_news2_patients.sort(key=lambda p: p["news2"], reverse=True)

    return {
        "source":       "fhir",
        "fhir_enabled": True,
        "threshold":    threshold,
        "count":        len(high_news2_patients),
        "patients":     high_news2_patients,
    }


# ---------------------------------------------------------------------------
# Tool 10 — fhir_get_patients_with_arrhythmia
# ---------------------------------------------------------------------------

def get_patients_with_arrhythmia() -> Dict[str, Any]:
    """
    Find patients with arrhythmia conditions.
    GET /Condition?code={arrhythmia_codes}
    """
    conn = get_fhir_connector()
    if not conn.is_enabled():
        return {"source": "simulator", "fhir_enabled": False, "patients": []}

    matched = []
    seen_patients: set = set()

    # Try each primary arrhythmia code
    for code in ("698247002", "I49.9", "I48"):
        raw_conds = conn.search_resource("Condition", {
            "code":   code,
            "_count": "20",
        })
        for cond in raw_conds:
            pt_ref = cond.get("subject", {}).get("reference", "")
            pt_id  = pt_ref.split("/")[-1] if "/" in pt_ref else pt_ref
            if not pt_id or pt_id in seen_patients:
                continue
            seen_patients.add(pt_id)
            nc = norm_condition(cond)
            pt = conn.get_patient(pt_id)
            pt_info = norm_patient(pt) if pt else {"patient_id": pt_id, "name": "Unknown"}
            matched.append({**pt_info, "condition": nc["display"], "condition_code": nc["code"]})

        if matched:
            break  # stop at first code that returns results

    return {
        "source":       "fhir",
        "fhir_enabled": True,
        "count":        len(matched),
        "patients":     matched,
    }


# ---------------------------------------------------------------------------
# Tool 11 — fhir_get_connected_devices
# ---------------------------------------------------------------------------

def get_connected_devices(fhir_patient_id: str) -> Dict[str, Any]:
    """
    Retrieve devices associated with a patient.
    GET /Device?patient={id}
    """
    conn = get_fhir_connector()
    if not conn.is_enabled():
        return {"source": "simulator", "fhir_enabled": False, "devices": []}

    raw     = conn.get_devices(fhir_patient_id)
    devices = [norm_device(d) for d in raw]
    online  = [d for d in devices if d.get("status") == "active"]
    offline = [d for d in devices if d.get("status") != "active"]

    return {
        "source":        "fhir",
        "fhir_enabled":  True,
        "patient_id":    fhir_patient_id,
        "total":         len(devices),
        "online_count":  len(online),
        "offline_count": len(offline),
        "devices":       devices,
    }


# ---------------------------------------------------------------------------
# Tool 12 — fhir_get_patient_timeline
# ---------------------------------------------------------------------------

def get_patient_timeline(fhir_patient_id: str) -> Dict[str, Any]:
    """
    Build a chronological event timeline from encounters, observations, and procedures.
    """
    conn = get_fhir_connector()
    if not conn.is_enabled():
        return {"source": "simulator", "fhir_enabled": False, "events": []}

    # Gather events from three resource types
    events: List[Dict[str, Any]] = []

    for enc in conn.get_encounters(patient_id=fhir_patient_id)[:10]:
        ne = norm_encounter(enc)
        events.append({
            "type": "encounter", "time": ne["start"] or ne["end"],
            "description": f"Encounter ({ne['class']}) — {ne['status']}",
            "detail": ne,
        })

    for obs in conn.get_vitals(fhir_patient_id, limit=10):
        ts = obs.get("effectiveDateTime", "")
        vq = obs.get("valueQuantity", {})
        code_display = (
            obs.get("code", {}).get("coding", [{}])[0].get("display", "Observation")
        )
        value_str = f"{vq.get('value', '?')} {vq.get('unit', '')}" if vq else ""
        events.append({
            "type": "observation", "time": ts,
            "description": f"{code_display}: {value_str}",
            "detail": {"code": code_display, "value": vq.get("value"), "unit": vq.get("unit")},
        })

    for proc in conn.get_procedures(fhir_patient_id)[:10]:
        np = norm_procedure(proc)
        events.append({
            "type": "procedure", "time": np["performed"],
            "description": f"Procedure: {np['procedure']} ({np['status']})",
            "detail": np,
        })

    events.sort(key=lambda e: e.get("time") or "", reverse=True)

    return {
        "source":       "fhir",
        "fhir_enabled": True,
        "patient_id":   fhir_patient_id,
        "count":        len(events),
        "events":       events[:30],
    }


# ---------------------------------------------------------------------------
# Tool 13 — fhir_summarize_patient_status
# ---------------------------------------------------------------------------

def summarize_patient_status(fhir_patient_id: str) -> Dict[str, Any]:
    """
    Full clinical status summary: demographics + vitals + conditions +
    medications + devices + risk assessment.
    """
    conn = get_fhir_connector()
    if not conn.is_enabled():
        return {"source": "simulator", "fhir_enabled": False}

    pt = conn.get_patient(fhir_patient_id)
    if not pt:
        return {"error": f"Patient {fhir_patient_id} not found", "fhir_enabled": True}

    vitals_raw  = conn.get_vitals(fhir_patient_id, limit=15)
    conditions  = conn.get_conditions(fhir_patient_id)
    medications = conn.get_medications(fhir_patient_id)
    devices     = conn.get_devices(fhir_patient_id)
    allergies   = conn.get_allergies(fhir_patient_id)

    patient = _build_fhir_patient(
        pt, vitals_raw, conditions, medications, devices=devices, allergies=allergies
    )

    # Build concise summary text
    cond_str = ", ".join(c["display"] for c in patient.conditions[:3]) or "None documented"
    med_str  = ", ".join(m["name"] for m in patient.medications[:3]) or "None documented"
    allergy_str = ", ".join(a["substance"] for a in patient.allergies[:3]) or "NKDA"

    vitals_parts = []
    if patient.hr:   vitals_parts.append(f"HR {patient.hr:.0f} bpm")
    if patient.spo2: vitals_parts.append(f"SpO2 {patient.spo2:.0f}%")
    if patient.rr:   vitals_parts.append(f"RR {patient.rr:.0f}/min")
    if patient.sbp:  vitals_parts.append(f"BP {patient.sbp:.0f}/{patient.dbp or '?':.0f} mmHg")
    if patient.temp: vitals_parts.append(f"Temp {patient.temp:.1f}°C")
    vitals_str = "  |  ".join(vitals_parts) or "No vital data"

    summary = (
        f"**{patient.name}** | {patient.age or '?'} y/o {patient.gender or ''} | "
        f"MRN: {patient.mrn or 'N/A'}\n"
        f"**Conditions:** {cond_str}\n"
        f"**Medications:** {med_str}\n"
        f"**Allergies:** {allergy_str}\n"
        f"**Vitals:** {vitals_str}\n"
        f"**NEWS2:** {patient.news2} — **Risk:** {patient.risk_level}\n"
        f"**Devices:** {len(patient.devices)} linked\n"
        f"\n> Source: FHIR ({conn.base_url})"
    )

    return {
        "source":       "fhir",
        "fhir_enabled": True,
        "patient_id":   patient.patient_id,
        "name":         patient.name,
        "age":          patient.age,
        "gender":       patient.gender,
        "mrn":          patient.mrn,
        "news2":        patient.news2,
        "risk_level":   patient.risk_level,
        "conditions":   patient.conditions[:5],
        "medications":  patient.medications[:5],
        "allergies":    patient.allergies[:5],
        "devices":      patient.devices[:5],
        "vitals": {
            "hr": patient.hr, "spo2": patient.spo2, "rr": patient.rr,
            "sbp": patient.sbp, "dbp": patient.dbp, "temp": patient.temp,
        },
        "summary_text": summary,
    }
