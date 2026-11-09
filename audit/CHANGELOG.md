# CHANGELOG — Stage 8C Forensic Release Candidate

All notable technical and scientific changes for Stage 8C forensic integrity repair and release candidate preparation are documented in this file.

---

## [Stage 8C Release Candidate] — 2026-11-05

### 1. Delivery & Reproducibility
- **Added:** Raw telemetry `data/raw/csiro_ahu10.parquet` (7,884,660 bytes, 422,169 rows, 17 columns, SHA-256: `f789b7efc5a0ec9857d5126137f727b94ad0895b63ff9b2170dd5651b26d3610`).
- **Added:** Raw experiments registry `data/raw/csiro_fault_experiments.parquet` (28,276 bytes, 391 rows, 103 on AHU-10, SHA-256: `b7ebad8a25baa8da7740186eb52a1eb62d0602c82dcc394ed0527ea5c6fd65f2`).
- **Added:** Complete historical Stage 8B dependencies (`research/runs/rbc_nesbitt_reconciled_manifest.json`, `research/reports/STAGE8B_R2_EVIDENCE_REPORT.md`, all 23 Nesbitt raw CSVs) to resolve all external test dependencies.
- **Added:** Standalone orchestration entrypoint `run_csiro_validation.py` with zero external dependencies, verified clean `python -m py_compile` and exit code 0.
- **Added:** Pinned environment specifications in `requirements.txt`.

### 2. Temporal Grid & Global Masking
- **Fixed:** Unified 5-minute temporal grid constructed across 33 selected days (9 train, 9 experiment, 15 baseline) yielding exactly 3,199 points, 0 duplicate timestamps, and 0 NaT values.
- **Fixed:** Global fault mask constructed across all 103 registered experiments of AHU-10 with 30-minute washout.
- **Resolved:** Multi-experiment day 2013-10-31 (experiments 224, 225, 226): continuous fault block from 09:35 to 12:30, followed by washout to 13:00, resolving 97 duplicate records and 24 conflicting normal/fault labels from earlier iterations.
- **Verified:** Baseline point counts: 873 clean operational training points, 1861 normal evaluation points (485 winter + 485 summer + 485 spring + 406 experiment-day normal sections).

### 3. Scientific Event-Level Classification & Left Censoring
- **Added:** Explicit separation of primary detection metric `new_onset_observable_7` (7 events with observable physical onset in telemetry) from secondary metric `post_observation_alarm_all_10` (all 10 events).
- **Added:** Classification of experiments ID 176, ID 194, ID 322 as `LEFT_CENSORED_FAULT_ONSET` (physical start at ~08:30 vs telemetry recording start at 09:00).
- **Fixed:** Primary detection results:
  - M1 Thermal Local $\tau=3.00$: **4/7 (57.1%)** [18.4%, 90.1%]
  - M2 Control Local $\tau=4.00$: **2/7 (28.6%)** [3.7%, 71.0%]
  - M3 Linear Fusion Local $\tau=3.00$: **4/7 (57.1%)** [18.4%, 90.1%]
  - M6 Direct Damper $\tau=3.00$: **0/7 (0.0%)** [0.0%, 41.0%]

### 4. False Alarm Rate Rectification
- **Corrected:** Pointwise FAR updated to exact data values:
  - M2 Control Local $\tau=4.00$: **750/1861 (40.30%)** total FAR; Summer: **220/485 (45.36%)**; Winter: **181/485 (37.32%)**; Spring: **75/485 (15.46%)**; Exp-day normal: **183/406 (45.07%)**.
  - M1 Thermal Local $\tau=3.00$: **979/1861 (52.61%)** total FAR; Summer: **480/485 (98.97%)**; Winter: **161/485 (33.20%)**.
- **Removed:** All legacy textual artifacts citing 29.24% or 35.88% FAR.
- **Revoked:** All claims asserting that local empirical calibration achieves a controlled false alarm rate ($\le 5.0\%$).
- **Added:** Pre-fault embargo sensitivity check (30-minute embargo removes 72 points, FAR becomes 729/1789 = 40.75%).

### 5. Semantic Compatibility & Transferability
- **Reclassified:** RBC-Nesbitt Zero-Shot transfer reclassified strictly as `NOT_COMPARABLE` (`INVALID_SEMANTIC_CONTROL`).
- **Documented:** Physical target mismatch ($CCV\_FBK$ stem potentiometer feedback in Nesbitt vs $CCV\_CMD$ controller output command in CSIRO) and input channel substitution ($MA\_TEMP \to SA\_TEMP$ due to BMS telemetric redundancy).
- **Removed:** Misleading claim that Zero-Shot transfer exhibits "FAR > 70%". Formally low FAR (0.91% at $\tau=4.00$) disclosed alongside low recall (2/7) and semantic invalidity.

### 6. Threshold Lineage & Standardization
- **Clarified:** Thresholds $\tau=3.00$ and $\tau=4.00$ documented as fixed exploratory constants.
- **Reported:** Training residual percentiles reported as distribution diagnostics (Thermal: p99.0 = 4.668, p99.5 = 5.419; Control: p99.0 = 3.974, p99.5 = 4.073).
- **Documented:** Standardization formula recorded as $\sigma = \text{std}(|y - \hat{y}|)$.
- **Added:** Scientific Corrigendum `research/protocols/SCIENTIFIC_CORRIGENDUM.md`.

### 7. Automated Parity & Regression Suite
- **Updated:** `scripts/evaluate_csiro_ahu10_validation.py` with single canonical evaluation function guaranteeing 100% data/manifest/report parity.
- **Expanded:** `tests/test_csiro_ahu10_validation.py` to 10 comprehensive algorithmic tests. Full suite now contains 43 tests (100% PASS).
