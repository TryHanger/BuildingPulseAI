# BuildingPulse AI · Independent G4.1 / G5 data gate review

**Date:** 2026-11-07  
**Reviewed:** `BUILDINGPULSE_G4_1_G5_DATA_GATE_REVIEW.zip` (SHA-256 `beaba01bcf4350065ea2cf0d70bc865c7a2c49d71a32c333fffa698f4e0aeab3`)  
**Auditor's decision:** `G4.1_ACCEPT_WITH_P1_CLARIFICATION` · `G5_SOURCE_GATE_ACCEPTED` · `FAULT_METRICS_NOT_AUTHORIZED` · `NEXT: G5.1_CONTROLLED_INTERVENTION_LABEL_GATE`.

## 1. Evidence actually rechecked

- The 2,966,169-byte ZIP passes CRC; all 72 entries in `SHA256SUMS.txt` match, with the manifest itself intentionally excluded from that list.
- Recomputed SHA-256 for all 15 local LBNL CSV files from the **original RC2 full ZIP**, matching `outputs/G5_SOURCE_AUDIT.json`. Recomputed the full nominal `AHU_annual.csv` SHA-256: `13a61e5b3e62dcf214b387dc57632073a8044c794eb8102d90d074aa80702d8b`.
- Independently recomputed split boundaries, uninterrupted fan-on duration and common quality mask using a separate streaming CSV implementation (see `verify_g5_handoff.py`). Counts exactly match:

  | Partition | Calendar rows | Fan on | Five-minute hold & valid common panel |
  |---|---:|---:|---:|
  | Train | 172,740 | 91,927 | 91,427 |
  | Calibration | 87,840 | 48,007 | 47,747 |
  | Retrospective test | 264,960 | 138,748 | 137,993 |
  | **Total** | **525,540** | **278,682** | **277,167** |

  This is **52.74% coverage of all logged minutes**. There are no duplicated source timestamps or non-minute steps in the nominal CSV. The nominal SAT setpoint is constant `55.184006 °F` in the full source.
- Verified SHA-256 of original CSIRO Parquet bytes in RC2 against the Git LFS pointers **included in the G5 handoff**: AHU9 `d43028…`, AHU10 `f789b7…`, intervention table `b7ebad…`. This validates byte identity relative to supplied pointers, not by itself the scientific meaning of every event label.
- Recomputed canonical JSON `run_sha256` for five exported G4.1 reports. Results: 10/10 violating samples but 0 confirmed episodes; 11/11 violating samples and 1 confirmed episode; missing MAT 32/32 not evaluable; demo 1 confirmed episode; LBNL sample zero.
- Ran `overlay/tests/test_g5_source_roles.py` in a minimal isolated package using the RC2 signal registry: **8 passed**. No training or F1/AUC claims were made. The submitted `evidence/pytest.log` reports **291 passed, 67 warnings**; a complete project test run in an identical environment was **not reproduced** here. Similarly, frontend/Playwright/Docker pass claims are supported by logs, not independently rerun in this review.
- OpenAPI document parses as 3.1.0, contract version `1.0.0-rc.6`, seven path templates.

## 2. G4.1 findings

**Pass:** temporal confirmation and separate counter for violating, not yet confirmed samples; chart renamed to **«Температуры смешения»**; technical details moved into collapsible sections; distinct REAL SIMULATION vs DEMO provenance. `run_sha256` is an integrity check for the *serialized report*, not a trusted digital signature attesting to the physical source.

**P1 remaining — ambiguous top-level semantics:** In the 10-sample report, `coverage.violated=10`, `unconfirmed_violated_samples=10`, `events=[]`, but top-level `status=NO_SYMPTOMS_ON_EVALUATED_WINDOWS` and `evidence_status=NOT_DETECTED`. The UI does display the 10 unconfirmed violations, and says there are no *confirmed* symptoms, so this is not false event confirmation. However a compact consumer of `evidence_status` can mistake “not yet confirmed” for “nothing violated.” **Fix:** add an orthogonal `confirmation_state=PENDING` or other versioned explicit status, or ensure every client/report renders “10 violating minutes; confirmation pending.” Preserve the confirmed-episode gate and backwards compatibility.

**P1:** Unconfirmed violations in a window may belong to an episode that later becomes confirmed; distinguish `unconfirmed_as_of_window_end` from `permanently_unconfirmed`. The window report cannot infer ultimate final state without future data. Keep source time, version, right-censoring and source SHA explicit.

## 3. G5 data science assessment

### Accepted

- Distinct data layers: publishing source, raw bytes, local slices, scenario labels, method inputs and physical independent measurements.
- `coi_bias` / `sa_bias` crosswalk remains UNKNOWN. Duplicate-severity payload groups are excluded; full source output remains an agent-reported finding until independently rereading the publisher's full 607 MB ZIP. The LBNL web dataset page describes 20 CSVs whereas its published PDF inventory contains 21 rows: this source inconsistency is acknowledged rather than silently reconciled.
- BASIC command vs measurement vs `EXTRA_SIMULATED` is retained; neither `SYS_CTL` nor native fault labels nor physical valve feedback absent from BASIC are used as model inputs.
- Nominal one-campaign time holdout avoids minute-level random shuffle; train-only normalization and calibration are specified. The protocol explicitly forbids F1/recall/delay/field claims from nominal residuals.
- CSIRO was correctly rejected as **independent physical valve-travel evidence**: BMS proxy override interval != measured stem travel.

### Known methodological traps, before any model is trained

1. **Single simulation campaign and temporal regime shift.** Train = winter/spring, calibration = late spring/early summer, retrospective test = summer/autumn/winter. Test OOD may be severe; no independent fault or blind normal campaigns. Even a better MAE or lower alarm count is descriptive, not FDD validation.
2. **Same-time controller command.** `CHWC_VLV_DM` is downstream of measured, controlled SAT and may improve fitting by absorbing a simulated fault's effect. It belongs in an explicit **separate** post-treatment/shortcut ablation only. Main diagnostic model must not use privileged or outcome-derived features; clock and causal ordering must be documented for live inference.
3. **Setpoint is not a physical SAT predictor in all modes.** The nominal `SA_TEMPSPT` is constant and economizer/locked-out cooling permits departures. `abs(SAT−SP)` is an engineering comparison, not an equivalent residual learner or physical fault rule on every window. Include a simple train-only constant/MA-only baseline if/when nominal regression is authorized.
4. **Nominal alarm calibration != guaranteed false alarm control.** A 95th percentile of dependent calibration residuals with 600 s confirmation is a fixed exploratory policy. It does not prove a 5% false-alarm rate on held-out seasons or deployed equipment. Do not choose thresholds, model, features or OOD exclusions after viewing retrospective test outcomes.
5. **No fault labels in A.** Low residual MAE, PCA/LightGBM gains and simulated SAT compensation do not establish detection, isolation, or causality. Do not add PCR/MinCovDet/LightGBM merely to generate a leaderboard.
6. **CSIRO event labels have narrower but potentially useful meaning.** Official repository says fault periods were injected through BMS proxies that override commands or sensor values. Those intervals may qualify for **controlled BMS intervention detection**, after label-to-signal alignment, overlap checks and data sampling checks. They do not establish physical mechanical failure, true healthy negatives, independent actuator travel, or field transfer.

## 4. Recommended research direction

**NEXT G5.1: qualify exactly one already available, logged CSIRO intervention family** as an event-detection benchmark before looking for exotic methods or waiting indefinitely for NIST instrumentation. Audit all intervention records by AHU, type, target, duration, overlap, available signals and role/lineage; choose a family only if enough independent event episodes and genuinely usable pre/post intervals exist. Use source timestamps and keep intervention labels outside model inputs. If qualified, freeze an explicit retrospective event-level evaluation and authorize one simple baseline before considering Ridge/LightGBM. If no family qualifies, STOP with a compact decision table and either request truly instrumented NIST data or run nominal LBNL regression only as a separately labeled **descriptive engineering exercise**, never as evidence of physical fault detection.

**No model training is authorized by this review**, because label alignment and clean negative support for the proposed new CSIRO task have not yet been independently qualified. This is a bounded next gate, not permission to cycle through arbitrary datasets.

## 5. Source references

- LBNL dataset page: https://faultdetection.lbl.gov/dataset/simulated-sd-ahu/
- LBNL SD-AHU official point and scenario inventory, tables 2–4: https://fdddata.lbl.gov/data/Simulated_LBNL_FDD_Data_Sets_SDAHU/LBNL_FDD_Data_Sets_SDAHU.pdf
- CSIRO official repository, BMS proxy overrides, intervention log and ground-truth join description: https://github.com/csiro-energy-systems/ahu-fault-detection-dataset
- NIST IBAL data dictionary: https://www.nist.gov/el/beed/intelligent-buildings-agents-project/data/data-dictionary

## 6. Gate ledger

| Gate | Decision | Qualification |
|---|---|---|
| G4.1 UI / report closeout | **ACCEPT with P1** | Show pending violations separately from no violations |
| G5 source and contract inventory | **ACCEPT** | Verified 15 local hashes / 3 CSIRO payload hashes and nominal mask; full publisher ZIP evidence agent-provided |
| G5 nominal residual protocol | **ACCEPT as preregistered proposal** | One campaign, retrospective, descriptive only |
| G5 physical fault evaluation | **STOP** | No qualified independent physical ground truth for selected mechanism |
| G5.1 CSIRO controlled-intervention benchmark | **RESEARCH-GATE AUTHORIZED** | Audit documented injections before coding/training |
| New ML training / F1 / deployment | **NOT AUTHORIZED** | Requires a task-matched label gate and fixed test protocol |
