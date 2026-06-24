# Clinical Alarm Management Policy
**Source:** Patient Safety & Quality Committee | Version 2.8 | 2024-01
**References:** AAMI TIR 13:2011, IEC 60601-1-8:2023, ECRI Institute Guidance

## 1. Purpose

Reduce alarm fatigue while ensuring clinically significant alarms receive timely response.
Alarm fatigue = desensitisation from excessive non-actionable alarms; a leading
contributor to patient harm (Joint Commission Sentinel Event Alert 50, 2013).

## 2. Alarm Tier Definitions (IEC 60601-1-8)

| Tier | IEC Name | Signal | Response Time | Meaning |
|------|---------|--------|---------------|---------|
| CRISIS | HIGH | Continuous, rapid | ≤10 seconds | Immediately life-threatening |
| WARNING | MEDIUM | Pulsed, moderate | ≤60 seconds | Potentially harmful if not addressed |
| ADVISORY | LOW | Single tone | ≤5 minutes | Attention needed, not immediately harmful |

## 3. Standard Alarm Thresholds — ICU Adults

| Parameter | CRISIS High | CRISIS Low | WARNING High | WARNING Low |
|-----------|------------|------------|-------------|-------------|
| HR (bpm) | 130 | 40 | 110 | 50 |
| SpO2 (%) | — | 85 | — | 90 |
| SBP (mmHg) | 220 | — | 180 | 90 |
| MAP (mmHg) | — | 50 | — | 60 |
| RR (/min) | 30 | 6 | 25 | 8 |
| Temp (°C) | 40.0 | 35.0 | 38.5 | 35.5 |
| EtCO2 (mmHg) | 60 | 20 | 50 | 25 |

Thresholds may be customised ±20% by the responsible clinician with documented rationale.

## 4. Alarm Response Protocol

**CRISIS alarm:**
1. Acknowledge within 10 seconds at monitor
2. Attend bedside within 30 seconds
3. Assess patient, initiate emergency response if warranted
4. Document response and outcome
5. If alarm non-actionable, escalate for threshold review

**WARNING alarm:**
1. Acknowledge within 60 seconds
2. Assess patient within 2 minutes
3. Determine cause (true vs. artefact)
4. Intervene or adjust threshold with justification

**ADVISORY alarm:**
1. Acknowledge within 5 minutes
2. Address at next scheduled rounding unless clinically urgent
3. Review for trend: 3+ advisories in 1 hour = re-evaluate threshold

## 5. Artefact Identification

Non-actionable alarms are most commonly artefact. Assess:

- **Patient motion**: movement or muscle artefact on ECG, motion on SpO2
- **Poor probe contact**: low perfusion index, probe displacement
- **Lead disconnect**: single-lead artefact vs. true rhythm change
- **Equipment fault**: battery, calibration, cable damage

**Artefact vs. true alarm decision tree:**
1. Is the patient conscious and speaking? (Good baseline assessment)
2. Does clinical exam support the alarm (cyanosis, diaphoresis, distress)?
3. Does the waveform quality indicator show adequate signal?
4. Compare with backup method (manual BP, pulse check, second probe)

## 6. Alarm Customisation Rules

Permitted customisation (documented in care plan):
- HR alarm range: ±20% of standard thresholds
- SpO2: lower limit may be reduced to 85% for COPD patients on physician order
- No CRISIS alarm may be disabled without attending physician authorisation

Prohibited:
- Disabling all alarms on any patient
- Setting alarms outside physiological plausibility ranges
- Silencing CRISIS alarms without attending patient

## 7. Alarm Audit Requirements

Monthly audit of:
- Total alarm count by unit and device type
- Alarm response time (time to acknowledge, time to attend)
- False alarm rate (target <10% of alarms non-actionable)
- Alarm silence rate (target: 0% unacknowledged CRISIS alarms)
- Top 5 most frequent alarm sources (focus reduction effort here)

## 8. Device-Specific Notes

**SpO2 (pulse oximetry)**
Accuracy ±2% for SpO2 78–100%. Inaccurate when:
- SpO2 <70% (probe not calibrated below)
- Carboxyhaemoglobin present (CO poisoning reads falsely normal)
- Methaemoglobinaemia (reads ~85% regardless)
- Severe peripheral vascular disease / hypothermia

**ECG / HR monitoring**
Ensure correct lead placement. Lead II optimal for rhythm assessment.
T-wave over-sensing may cause double-counting → falsely elevated HR alarm.
P-wave amplitude <0.5 mV → automatic gain setting may help.

**NIBP cycling**
Oscillometric NIBP inaccurate in: atrial fibrillation, arterial stiffness >90 years,
aortic regurgitation. Confirm with arterial line or manual auscultation if clinical concern.

## 9. Alarm Fatigue Reduction Strategies

1. Default delay all non-crisis alarms by 15–30 seconds (self-correcting artefacts)
2. Review thresholds every 8-hour shift; adjust to patient's normal range
3. Remove monitoring when no longer clinically indicated
4. Use intelligent alarm systems that suppress repeating alarms after initial notification
5. Assign primary alarm responder per shift; rotate to reduce fatigue
6. 5-Alarm method: if ≥5 alarms in 1 hour from same parameter → review threshold
