# Patient Monitor Device Troubleshooting Guide
**Source:** Clinical Engineering & Biomedical Technology | Version 5.0 | 2024-02

## 1. General Troubleshooting Approach

Before escalating to Clinical Engineering:
1. Check power (AC connected? Battery level?)
2. Check all cable connections (patient ↔ device ↔ network)
3. Confirm correct sensor placement on patient
4. Restart monitoring module (not whole monitor) if available
5. Check patient comfort and cooperation (interference from movement)
6. Verify alarm thresholds appropriate for this patient

## 2. SpO2 / Pulse Oximetry

### Low or No Reading
- **Cause A**: Poor perfusion (cold, vasoconstriction, shock)
  - Action: Apply finger probe to earlobe or forehead reflectance probe
  - Check capillary refill time; if >3s, report to nurse immediately

- **Cause B**: Probe displacement or incorrect placement
  - Action: Reapply probe; ensure finger nail not varnished; clean sensor
  - For paediatric: use appropriate paediatric probe size

- **Cause C**: External light interference (fluorescent/surgical lights)
  - Action: Cover probe with light shield or dark cloth

- **Cause D**: Motion artefact
  - Action: Switch to motion-tolerant mode; use different digit

### Falsely Normal Reading
- Carboxyhaemoglobin (CO poisoning): co-oximetry required
- Methaemoglobinaemia: SpO2 reads ~85% regardless of true O2 saturation
- Severe anaemia: SpO2 may read normal despite poor O2 delivery (low Hb)

### SpO2 Waveform Quality
- Good signal: clean pulsatile waveform, perfusion index >0.5
- Poor signal: noisy, flat, irregular waveform — suspect artefact
- Disconnect the probe, apply to new site, and recheck

## 3. ECG / Cardiac Monitor

### Flat-Line or No Waveform
1. Check all leads connected (RA, LA, LL, V leads)
2. Check lead wires for damage (kinks, fraying, connector corrosion)
3. Check skin preparation: clean, dry; abrade lightly with gauze
4. Replace electrodes if >24 hours old or visibly dry
5. Select different lead if one lead noisy
6. If all leads flat: check patient, call code team if unresponsive

### Noisy / Artefactual ECG
- 50/60 Hz interference: ensure good skin-electrode contact; remove nearby electrical devices
- Baseline wander: poor electrode contact; re-prep skin; restrain if moving
- Muscle artefact: patient shivering or restless; electromyographic noise
- Lead reversal: check wiring; P in lead I negative → LA/RA swap

### Falsely High HR
- T-wave over-sensing: reduce gain or switch lead
- Pacemaker spike counting: enable pacemaker mode; check pacemaker type
- Artefact from patient movement: use beat-to-beat averaging

## 4. Non-Invasive Blood Pressure (NIBP)

### Measurement Error
- Cuff too small → falsely high reading (use larger cuff for arm circumference >32cm)
- Cuff too large → falsely low reading
- Cuff over clothing → inaccurate; apply to bare skin
- Patient arm not at heart level → +/- 8 mmHg per 10 cm deviation

### Repeated Measurement Failure
1. Check cuff tubing not kinked
2. Check cuff not too tight (should admit 2 fingers under cuff)
3. Clean connector port with dry cloth
4. If arrhythmia (AF): NIBP oscillometric method unreliable — use manual auscultation
5. After 5 failed attempts → request arterial line or manual BP

### NIBP Calibration
Verify monthly against calibrated aneroid manometer. Deviation >5 mmHg → remove from service.

## 5. Invasive Arterial Line (ABP)

### Dampened Waveform
- Cause: air bubble in transducer line, partial catheter occlusion, kinked line
- Action: Fast-flush test; if waveform square wave not sharp → troubleshoot
- Flush line with 1–2 mL normal saline (hospital protocol)
- Reposition wrist/arm; check catheter not against vessel wall

### No Waveform
1. Confirm stopcock positions all correct
2. Check cable connection to module
3. Check transducer levelled at phlebostatic axis (right atrium — 4th ICS, MAL)
4. Zero transducer (stopcock to air, press zero button, close)

### MAP Reading Discrepant
- Zero monthly and after any position change
- Re-level transducer if patient repositioned >30°

## 6. Mechanical Ventilator (Draeger / Hamilton / Puritan Bennett)

### Ventilator Offline / No Data to Monitor
1. Check power supply and UPS battery backup
2. Check RS-232 / HL7 / Ventilator Gateway cable to monitoring system
3. Restart integration gateway (typically standalone box at bed)
4. If ventilator itself alarming: check patient first, then troubleshoot equipment
5. CRITICAL: never leave ventilated patient unmonitored; manual hand-ventilation until resolved

### High Airway Pressure Alarm
- Patient coughing or biting tube (biting protection or sedation consideration)
- Circuit kinked or occluded
- Patient-ventilator dyssynchrony
- Pneumothorax (sudden onset, desaturation, absent breath sounds unilateral)
- Bronchospasm / mucus plug

### Low Minute Volume Alarm
- Disconnect in circuit (check all connections)
- Large leak in cuff (deflated cuff or cuff rupture)
- Low tidal volume set incorrectly

## 7. Infusion Pump

### Occlusion Alarm
- Check IV line from bag to patient: kink, clamp not open, infiltration
- Check cannula patency (flush with saline)
- Replace administration set if >72h old

### No Drug Delivery (silent pump)
- Check drug/rate programming (keypad error)
- Check cartridge or syringe loaded correctly
- Check battery if portable pump

## 8. When to Call Clinical Engineering

Call immediately:
- Device display failure (black screen, frozen)
- Electrical sparking, burning smell, patient shock sensation
- Device failed after drop or liquid exposure
- Device failing self-test on startup
- NIBP calibration drift >10 mmHg

Tag device "OUT OF SERVICE — DO NOT USE" and remove from bedside.
Log incident in clinical engineering management system.

## 9. Device Incident Reporting

Any device-related adverse event or near-miss must be reported:
1. Complete incident report (electronic reporting system)
2. Retain device and all accessories in same state
3. Notify Clinical Engineering within 4 hours
4. FDA MedWatch report if serious injury or death (US) / MHRA Yellow Card (UK)
