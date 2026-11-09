# BuildingPulse AI — Independent Review: BP-ML-REPRO-02

**Date:** 2026-11-08  
**Decision:** `ACCEPT_RESEARCH_ONLY_PILOT / HOLD_FDD_PROMOTION`  
**Source:** user-provided `BUILDINGPULSE_BP_ML_REPRO_02_REVIEW.zip`, ZIP SHA-256 `d9b3187756ab98d001305c92dbf04c2fc82393896d1d64faaa016cb48c85faf7`.

## Scope and verified material

- ZIP integrity/CRC passed; `SHA256SUMS.txt` validated **81/81** component hashes.
- Current package manifest links to G6.0 (`6cf3f518...`) and BP-ML-REPRO-01 (`04c41595...`): SHA-256 of both actual local base ZIP files matched.
- All **18** `overlay/` modified-file hashes, the patch SHA, and the research registry manifest SHA matched `MANIFEST.json`.
- Registry has **8** SHA-verified LightGBM model text files and **2** SHA-verified archive Parquet windows. Independently loaded the native **SA_TEMP** LightGBM booster (v4.6.0); its **19** named features exactly match the manifest; SA_TEMP itself and simulated-only `SYS_CTL`/`CHWC_VLV` are not input features of that model.
- Independently verified all **10,981** rows of `SAT_OFFLINE_WINDOW.csv` for the residual `abs(actual-predicted)` and mean-z daily aggregation; maximum observed floating point discrepancies were below `1e-10`. The 14 archived case/calendar days include **12 with eligible minutes and two with zero eligible minutes**. This verifies the offline saved data, *not* independent HTTP inference or original model training.
- Inspected code (`virtual_sensor_research.py`, `build_registry.py`, `controls.py`, React page), Playwright screenshot, and logs. Journal states `339 passed`, TypeScript, HTTP, OpenAPI and Docker backend smoke succeeded; **full pytest / HTTP / Playwright / full model retrain not independently rerun in this audit**. Full Docker Compose was explicitly `NOT_RUN` by the agent.

## Independently recalculated research figures

From the **saved REPRO-01 59-day tables**, with a fixed cutoff `z > 3`, evaluated on the intersection of calendar days:

| Study arm | Signal | TP / fault days | FP / healthy days | Day AUC |
|---|---|---:|---:|---:|
| BASIC with commands | eight-target maximum | 37/59 | 0/59 | 0.9520253 |
| BASIC with commands | **SA_TEMP-specific virtual model** | **37/59** | **0/59** | **0.9810399** |
| BASIC without commands | eight-target maximum | 27/59 | 0/59 | 0.8724504 |
| BASIC without commands | **SA_TEMP-specific virtual model** | **23/59** | **0/59** | **0.8474576** |

Against the simple SAT-versus-setpoint comparator (33/59, 0/59), **four extra detection days** appear in BASIC with commands: 2018-10-20, 2018-11-04, 2018-11-29 and 2018-12-14. All four are also detected by the *SA_TEMP-specific* model, not solely by other targets. The 37/59 result is therefore not a false attribution for this particular scenario.

**However, this coincidence does not generalize to other scenarios.** On BASIC with commands, `Damper stuck 25%` registers **58/59** on the eight-target maximum and only **43/59** on SA_TEMP. On BASIC without commands, `SA +2 °C` registers **27/59** on the eight-target maximum and **23/59** on SA_TEMP; `Valve leak` registers 1/59 versus 0/59. The displayed comparison must name the detector target/aggregation, not use the generic label 'LightGBM'.

The 0/59 healthy alert count applies only to this *same-simulator test cohort*, not to a representative field deployment. The 59 days are correlated samples from one underlying simulation and do not constitute 59 independent trials.

## Issues and gates

### P0 (scientific) — the score used to authorize a model is not a complete validation of the exported model

`p1-gate.json` uses **previously saved REPRO-01 `daily.csv` results** to approve the research pilot. `build_registry.py` then **refits** and serializes the eight native models. REPRO-02 verifies parity on the first **seven archive dates** for each of two scenarios, not for the **entire 59-day cohort of the precise exported `.lightgbm.txt` model**.

This is not a reason to reject the read-only archive demo. It is a reason to **withhold claims** that the deployed research artifact itself achieved 37/59 until the precise pinned booster is evaluated across all 59 days under identical masks and reported separately from the historical REPRO-01 scorer. Retraining may be numerically close, but full-cohort parity has not been established by the delivered receipt.

### P1 — alert policy with inadequate daily coverage

`infer` only abstains for **zero** eligible minutes or an unavailable input/calibration scale. There is no lower bound on minimum scored minutes/day. In principle a one-minute day could produce a `MODEL_ANOMALY` via a single high z, which would be presented as a daily result. The existing two windows have 715–956 eligible minutes when nonempty; there is no evidence of a one-minute case in the supplied windows. Add and predeclare a coverage/sufficiency policy and negative controls **before scoring additional fault days**; preserve the previous outputs as historical versioned evidence.

### P1 — hypothesis labeling, post-hoc experiments and selection bias

- `coi_bias_±2/±4` to official `sa_bias_±2/±4` remains **`UNVERIFIED_PUBLISHER_ALIAS`**. Never describe this as fully publisher-confirmed physical SAT-sensor-fault ground truth.
- The same 59-day evaluation cohort informed selection of the pilot (`37 vs 33`). It is therefore not a fresh blinded confirmatory validation of the chosen method.
- Bagging frequency `subsample_freq=1` raises reported results substantially but was explored **post hoc**. It cannot be selected as a superior production configuration without an independent predeclared evaluation on fresh data. The gate correctly leaves the original model unchanged.

### P1 — research UI comparison semantics

The top chart is **SAT-specific** and the tables currently use **system max of eight targets**, which is clearly disclosed in text but easy to overlook. Add explicit labels to each measure and SAT-only comparator rows; avoid implying the research page's SAT alarm is a full multi-target FDD detector. Consider plotting the time course of the SAT residual, not just the selected-minute numerical residual.

### P2 — isolated research interface and limited transfer

The research page only supports two fixed seven-day simulation windows. Do not imply a live stream or operation on field equipment. Research alerts remain separate from FDD incidents. `RESEARCH_ONLY`, simulated provenance, input order, model SHA and missing data abstention are implemented responsibly. Full Compose and field transfer are not verified here. One year and one simulator do not establish generalization.

## Acceptance

**ACCEPT:** archive-only virtual SAT research pilot, validated package/model hashes, reproducible saved result arithmetic, explicit SIMULATED/RESEARCH_ONLY UX, separation from FDD.

**HOLD:** promotion into operational fault classification, claims of 99–100% field reliability, causal localization, extrapolation of all eight-target AUC to single SAT, claim of full-cohort parity of a retrained registry model.

**Next:** execute one narrowly scoped `BP-ML-REPRO-03`: verify frozen native SAT model on the full original cohort; stratify SAT-only vs multi-target and controller-command ablation; introduce predeclared low-coverage abstention tests, without training a new candidate or changing thresholds. No separate frontend agent.

## Reproducibility of this audit

Run `python verify_repro02_independent.py <unzipped BP-ML-REPRO-02 directory>`; inspect `INDEPENDENT_RECALC.json`. This independent calculation uses only the Python standard library and the exported data. It **does not** re-run model fitting, load the Parquet windows, or substitute for an identical-environment pytest run.
