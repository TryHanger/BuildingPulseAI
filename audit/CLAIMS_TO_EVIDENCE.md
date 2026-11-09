# CLAIMS TO EVIDENCE MAPPING — Stage 8C Release Candidate

This document provides a strict, verifiable mapping between every scientific claim in the Stage 8C forensic release and its supporting data, mathematical formulation, code implementation, and artifacts.

---

## 1. Study Status and Provenance Claims

### Claim 1.1: The evaluation is test-exposed forensic reanalysis, not a blind independent validation
- **Scientific Statement:** The evaluation on CSIRO AHU-10 is classified as `TEST_EXPOSED_FORENSIC_REANALYSIS`. It is not an independent blind holdout and does not provide prospective cryptographic proof of transferability.
- **Evidence:**
  - Facility AHU-10 and its test dates (e.g. 2013-11-07, 2013-11-11) were already inspected and used for modeling in Stage 8A (`research/reports/STAGE8A_CONTROL_EFFORT_REPORT.md`) and Stage 8B.
  - Machine Manifest: `research/runs/csiro_ahu10_validation_manifest.json` specifies `"protocol_status": "TEST_EXPOSED_FORENSIC_REANALYSIS"`.
  - Corrigendum: `research/protocols/SCIENTIFIC_CORRIGENDUM.md` supersedes prospective claims in `CSIRO_AHU10_VALIDATION_PROTOCOL.md`.

### Claim 1.2: BMS Telemetry Identity (MA_TEMP == SA_TEMP) is a database property, not physical hardware proof
- **Scientific Statement:** The equality $MA\_TEMP == SA\_TEMP$ across all 422,169 records of `data/raw/csiro_ahu10.parquet` reflects identical values exported by the TAC Vista BMS database, not hardware proof that no physical mixed air sensor exists.
- **Evidence:**
  - `(df["AHU10ahuMaTemp"] == df["AHU10ahuSaTemp"]).all() == True` with maximum absolute difference of `0.0`.
  - Manifest records `"telemetry_ma_sa_identity": true`.

---

## 2. Event-Level Fault Detection Claims

### Claim 2.1: Rigorous separation of 7 observable events from 3 left-censored events
- **Scientific Statement:** Three fault experiments (IDs 176, 194, 322) physically began at 08:30–08:31, before BMS telemetry begins recording at 09:00. Alarms occurring after 09:00 represent post-observation detections on an already active fault, not detection of fault inception. The primary metric is `new_onset_observable_7`.
- **Evidence:**
  - `data/raw/csiro_fault_experiments.parquet`:
    - ID 176: Start `2013-10-23 08:30:48`, telemetry begins `2013-10-23 09:00:00`
    - ID 194: Start `2013-10-25 08:31:06`, telemetry begins `2013-10-25 09:00:00`
    - ID 322: Start `2013-11-11 08:30:31`, telemetry begins `2013-11-11 09:00:00`
  - 7 Observable events: IDs 141, 264, 116, 224, 226, 161, 215.
  - Manifest per-event record `is_left_censored` and status `DETECTED_POST_OBSERVATION_LEFT_CENSORED`.

### Claim 2.2: Primary Detection Performance (Observable N=7)
- **Scientific Statement:**
  - M1 Thermal Local $\tau=3.00$: **4/7 (57.1%)**, 95% CI [18.4%, 90.1%]
  - M2 Control Local $\tau=4.00$: **2/7 (28.6%)**, 95% CI [3.7%, 71.0%]
  - M3 Linear Fusion Local $\tau=3.00$: **4/7 (57.1%)**, 95% CI [18.4%, 90.1%]
  - M6 Direct Damper $\tau=3.00$: **0/7 (0.0%)**, 95% CI [0.0%, 41.0%]
- **Evidence:**
  - `research/runs/csiro_ahu10_validation_manifest.json` under `event_detection_outcomes[<model>]["new_onset_observable_7"]`.
  - Fully verified in `tests/test_csiro_ahu10_validation.py::test_4_left_censored_events_excluded_from_observable_7`.

### Claim 2.3: Qualified Secondary Detection Performance (Post-Observation N=10)
- **Scientific Statement:**
  - M1 Thermal Local $\tau=3.00$: **5/10 (50.0%)**, 95% CI [18.7%, 81.3%]
  - M2 Control Local $\tau=4.00$: **3/10 (30.0%)**, 95% CI [6.7%, 65.2%]
  - M3 Linear Fusion Local $\tau=3.00$: **5/10 (50.0%)**, 95% CI [18.7%, 81.3%]
- **Evidence:**
  - Manifest under `event_detection_outcomes[<model>]["post_observation_alarm_all_10"]`.

---

## 3. False Alarm Rate (FAR) and Operational Feasibility Claims

### Claim 3.1: Local models severely fail the project engineering FAR budget ($\le 5.0\%$)
- **Scientific Statement:** The claim of "controlled false alarm rates under local calibration" is refuted by empirical data. Local models trigger catastrophic false alarm rates on healthy operational baseline days.
- **Evidence:**
  - Unified operational normal baseline: $N = 1861$ 5-minute points (485 winter + 485 summer + 485 spring + 406 experiment-day normal sections).
  - M2 Control Local $\tau=4.00$: **750/1861 (40.30% FAR)**, 32 false alarm episodes, 1.65 episodes/8h.
  - M1 Thermal Local $\tau=3.00$: **979/1861 (52.61% FAR)**, 32 false alarm episodes, 1.65 episodes/8h.
  - Manifest under `false_alarm_slices["all_operational_norm_combined"]`.

### Claim 3.2: Severe seasonal degradation during Summer cooling
- **Scientific Statement:** Models trained on September data experience severe cross-seasonal distribution shift during peak summer operations (January 2014).
- **Evidence:**
  - Summer baseline slice (Jan 3, 6-9, 2014, $N = 485$ points):
    - M2 Control Local $\tau=4.00$: **220/485 (45.36% FAR)**.
    - M1 Thermal Local $\tau=3.00$: **480/485 (98.97% FAR)**.
  - Manifest under `false_alarm_slices["summer_baseline_only"]`.

### Claim 3.3: Pre-fault embargo does not alter the negative conclusion
- **Scientific Statement:** Excluding a 30-minute pre-fault embargo before each experiment removes 72 borderline points, but leaves the overall FAR essentially unchanged ($40.30\% \to 40.75\%$).
- **Evidence:**
  - Manifest under `false_alarm_slices["pre_fault_embargo_sensitivity"]["M2_Control_Local_Tau400"]`:
    - Standard: 750 / 1861 (40.30%)
    - With Embargo: 729 / 1789 (40.75%)

---

## 4. Semantic Compatibility Claims

### Claim 4.1: RBC-Nesbitt Zero-Shot Transfer is scientifically NOT_COMPARABLE
- **Scientific Statement:** The RBC-Nesbitt model cannot serve as a valid physical Zero-Shot transfer to CSIRO AHU-10 because:
  1. Target variable in Nesbitt was $CCV\_FBK$ (actuator stem position potentiometer feedback). CSIRO records only $CCV\_CMD$ (controller command output).
  2. Input feature $MA\_TEMP$ was substituted with $SA\_TEMP$.
  Formally low FAR (17/1861 = 0.91%) at $\tau=4.00$ reflects target incompatibility and weak sensitivity (Recall 2/7), not successful physical generalization.
- **Evidence:**
  - Manifest marks category `"INVALID_SEMANTIC_CONTROL"` and name `"M2_Control_ZeroShot_Tau400_NOT_COMPARABLE"`.
  - Protocol corrigendum: `research/protocols/SCIENTIFIC_CORRIGENDUM.md`, Section 2, Item 4.

---

## 5. Model Lineage and Threshold Claims

### Claim 5.1: Thresholds $\tau=3.00$ and $\tau=4.00$ are fixed exploratory heuristics
- **Scientific Statement:** Thresholds $\tau=3.00$ and $\tau=4.00$ are fixed constants chosen during preliminary exploration. They are not derived from empirical 99.0% or 99.5% percentile calibration on the training distribution.
- **Evidence:**
  - Training residual diagnostics (N=873 clean operational points):
    - Thermal: p99.0 = 4.668, p99.5 = 5.419
    - Control: p99.0 = 3.974, p99.5 = 4.073
  - Manifest under `training_metadata["fixed_research_thresholds"]` and `training_metadata["thermal_model"]` / `control_model`.

### Claim 5.2: Scaling parameter uses absolute residual deviation
- **Scientific Statement:** Residual scaling is computed as $\sigma = \text{std}(|y - \hat{y}|)$, measuring the dispersion of absolute errors rather than standard signed residual variance.
- **Evidence:**
  - Implemented in `scripts/evaluate_csiro_ahu10_validation.py` lines 312-314 and 322-324:
    `res_train = np.abs(y_train - model.predict(X_train)); sigma = float(np.std(res_train))`.
  - Documented in manifest: `"standardization_formula": "sigma = float(np.std(np.abs(residual)))"`.
