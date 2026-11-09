# SCIENTIFIC CORRIGENDUM — Stage 8C Protocol & Pre-Registration Rectification

- **Target Document:** `research/protocols/CSIRO_AHU10_VALIDATION_PROTOCOL.md` (Stage 8C)
- **Status:** `SUPERSEDED_AND_RECTIFIED`
- **Date of Corrigendum:** 2026-11-05
- **Governing Reference:** Forensic Code Reanalysis (`scripts/evaluate_csiro_ahu10_validation.py`, Manifest `research/runs/csiro_ahu10_validation_manifest.json`)

---

## 1. Context and Purpose of this Corrigendum

The historical protocol document `CSIRO_AHU10_VALIDATION_PROTOCOL.md` was drafted as a prospective study plan for evaluating AHU-10 of the CSIRO Energy Centre. Subsequent independent audit (`BUILDINGPULSE_STAGE_8C_INDEPENDENT_AUDIT.md`) established multiple discrepancies between prospective protocol assertions and physical/code reality.

In accordance with strict scientific integrity principles:
1. The historical protocol `CSIRO_AHU10_VALIDATION_PROTOCOL.md` is preserved intact without retroactive rewriting.
2. This Corrigendum explicitly enumerates all `SUPERSEDED` claims, replacing them with verifiable physical and algorithmic ground truth.

---

## 2. Superseded Protocol Claims vs Physical Ground Truth

### Item 1: Protocol Status — Pre-Registered Blind Holdout vs Test-Exposed Reanalysis
- **Superseded Protocol Claim:** Sections 1 and 2 claim that AHU-10 represents an "independent blind external validation holdout" with cryptographic pre-registration.
- **Ground Truth & Rectification:** **`TEST_EXPOSED_FORENSIC_REANALYSIS`**. AHU-10 and its test dates (e.g., 2013-11-07 and 2013-11-11) were already inspected and modeled during Stages 8A and 8B. A markdown file in the project workspace does not establish blind pre-registration. All results are strictly reported as forensic reanalysis on a development-exposed facility.

### Item 2: Threshold Calibration — Percentile vs Fixed Exploratory Thresholds
- **Superseded Protocol Claim:** Section 4 claims that thresholds $\tau=3.00$ and $\tau=4.00$ were chosen via empirical percentile calibration (p99.0 and p99.5) on healthy training residuals.
- **Ground Truth & Rectification:** **`FIXED_EXPLORATORY_THRESHOLDS`**. The implementation uses hardcoded constant thresholds $\tau=3.00$ and $\tau=4.00$. Diagnostic percentile evaluation on the clean training partition (N=873 points) shows:
  - Thermal Model (M1): $\text{p99.0} = 4.668$, $\text{p99.5} = 5.419$.
  - Control Inversion Model (M2): $\text{p99.0} = 3.974$, $\text{p99.5} = 4.073$.
  Thus, $\tau=3.00$ and $\tau=4.00$ are conservative heuristic thresholds, not empirical percentile cutoffs.

### Item 3: Residual Standardization Formula
- **Superseded Protocol Claim:** Residuals were described as standardized $Z$-scores under standard Gaussian assumptions ($3\sigma / 4\sigma$).
- **Ground Truth & Rectification:** The standardization scale is computed as:
  $$\sigma = \text{std}(|\text{residual}|) = \text{std}(|y - \hat{y}|)$$
  This scales residuals by the standard deviation of their absolute values rather than the standard deviation of signed residuals. Hence, $z = |y - \hat{y}| / \sigma$ is not a standard Gaussian z-score and must be interpreted as a scaled absolute error metric.

### Item 4: Zero-Shot Transferability — RBC-Nesbitt to CSIRO
- **Superseded Protocol Claim:** The protocol proposed evaluating Zero-Shot transfer from the RBC-Nesbitt model to CSIRO AHU-10.
- **Ground Truth & Rectification:** **`NOT_COMPARABLE` (INVALID_SEMANTIC_CONTROL)**.
  1. **Target Mismatch:** RBC-Nesbitt M2 predicts $CCV\_FBK$ (actuator potentiometer stem feedback, 0–100%). CSIRO BMS records only $CCV\_CMD$ (controller command signal). These are physically distinct control loop signals.
  2. **Feature Substitution:** In RBC-Nesbitt, $MA\_TEMP$ was mixed air temperature. On CSIRO AHU-10, $MA\_TEMP$ in BMS telemetrically duplicates $SA\_TEMP$.
  Therefore, comparisons between $CCV\_CMD$ and predictions of $CCV\_FBK$ lack semantic validity and are retained solely as negative diagnostic controls.

### Item 5: Event Classification and Left Censoring
- **Superseded Protocol Claim:** All 10 fault experiments were treated as evaluating fault onset detection.
- **Ground Truth & Rectification:** **`LEFT_CENSORED_FAULT_ONSET` vs `OBSERVABLE_ONSET`**.
  - Three experiments (**ID 176, ID 194, ID 322**) physically started at **08:30–08:31**, whereas CSIRO BMS archive recording starts at **09:00**.
  - Alarms occurring after 09:00 cannot be classified as detecting the inception of the fault, but rather capture an already established anomaly during fan startup.
  - The primary detection metric is strictly defined on the **7 events with observable onset (`new_onset_observable_7`)**:
    - M1 Thermal Local $\tau=3$: **4/7** (57.1%)
    - M2 Control Local $\tau=4$: **2/7** (28.6%)
    - M3 Linear Fusion $\tau=3$: **4/7** (57.1%)

### Item 6: False Alarm Rate Evaluation
- **Superseded Protocol Claim:** Prospective expectation of controlled false alarm rates ($\text{FAR} \le 5\%$) under local empirical calibration.
- **Ground Truth & Rectification:** **`FAILED_FAR_BUDGET`**.
  - On the clean, unified operational baseline ($N=1861$ points), local models exhibit unacceptably high false alarm rates:
    - M2 Control Local $\tau=4.00$: **750/1861 (40.30%)**; Summer baseline: **220/485 (45.36%)**.
    - M1 Thermal Local $\tau=3.00$: **979/1861 (52.61%)**; Summer baseline: **480/485 (98.97%)**.
  - Severe seasonal distribution shift renders empirical models trained on shoulder season (September) ineffective during peak summer cooling.

### Item 7: BMS Telemetry Identity vs Physical Instrumentation
- **Superseded Protocol Claim:** Stating that AHU-10 lacks a physical mixed air temperature sensor based on $MA\_TEMP == SA\_TEMP$.
- **Ground Truth & Rectification:** The equality $MA\_TEMP == SA\_TEMP$ on all 422,169 records is a **telemetry export stream identity** in the BMS database, not definitive proof of physical hardware absence. Without commissioning mechanical drawings, this is documented strictly as telemetric signal redundancy.
