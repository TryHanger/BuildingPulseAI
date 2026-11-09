# BuildingPulse AI — CD-02 Fast Evidence: independent technical/scientific audit

**Date:** 2026-11-05. **Object:** `BUILDINGPULSE_AUDIT_CD02_FAST_EVIDENCE.zip`. The claims below are based on the exact files supplied in this archive and independent executions, not just on the author's DECISION_MATRIX.

## 1. Integrity and repeatability

- Exact ZIP SHA-256: `9e04bdd225ce2b109e8f24d138b3848a2a869731b7d8e1c517476b5e5388f029`.
- Archive contains 168 entries: 167 entries with external SHA-256 records plus `audit/SHA256SUMS.txt`. ZIP CRC check PASS; 167/167 checksums PASS.
- Ran `PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python verify_package.py --replay` **on a clean extraction**. Exit code 0. Seven targeted Python unittest tests PASS; the prior independent counterexample also runs. Replays Q, D, R from bundled CD01 artifacts.
- The machine comparison checked 397,026 values, with 79 tiny float changes (max abs difference `5.551115123125783e-17`) and 0 material mismatches. Categorical flags, integers, timestamps and grouping match archived outputs.
- Local independent environment Python 3.13.5, pandas 2.2.3, NumPy 2.3.5, SciPy 1.17.0; `pyarrow` absent and not required for this replay. This replays CD02 from archived CSV, NPZ and CD01 frozen predictions, **not** upstream raw Parquet-to-trained-model fit or a fresh blind experiment.

## 2. Results and decision

| Package | What was actually checked | Verdict |
|---|---|---|
| CD02-Q | Headers of 23 Nesbitt CSVs, 15 local LBNL samples, extracted full CSIRO SAT/MAT vectors, channel provenance tables | NEED_NEW_DATA for the proposed command/independent-feedback/flow/reference experiment; applies to inspected local files and supplied provenance, not proof that suitable data do not exist elsewhere |
| CD02-D | Numerical nuisance projection of hard-coded static linearized PI toy; independent rank recreation | ANALYTICAL_TOY_ONLY. Rank 0 for SAT+command or duplicate SAT; 1 when either ideal independent flow or SAT reference is added; 2 when both are added. No measured fault isolation, no uncertainty interval, no source-domain transfer validated |
| CD02-R | Time-aware forensic re-score of **already exposed** Nesbitt M1 and ARX frozen predictions | No confirmatory superiority. Interesting individual alarms, but tiny independent-event count, changed alarm-episode burden and no new test site |

### CD02-R, independently recomputed

| Measure | M1 | ARX |
|---|---:|---:|
| Unrestricted event-level new alarms | 1/8 | 4/8 |
| Alarm within 60 minutes (all eight events) | 0/8 | 3/8 |
| Alarm within 60 minutes **excluding BAS setpoint adjustment** | 0/7 | 2/7 |
| Normal false-positive points | 54/3154 = 1.712% | 47/3154 = 1.490% |
| False alarm episodes/8 equivalent operating hours | 12×96/3154 = 0.365 | 31×96/3154 = 0.944 |

ARX detected: `2017-01-03` at +5 min (damper), `2017-08-11` at +5 min (cooling valve), `2018-07-09` at +0 min (BAS setpoint-demand adjustment, not verified physical SAT sensor drift) and `2017-07-18` at +605 min, **65 minutes after the official intervention end**. Independent event re-score of original `inputs/cd01/results/lanes/B/pointwise.csv` confirms 3/8 at <=60 minutes, 2/7 excluding setpoint. M1's sole alarm was at +670 min.

Exact paired McNemar p = .25 for three extra timely ARX alarms vs M1 on eight events; p = .50 when the BAS setpoint intervention is excluded (2 discordant benefits). These are descriptive, underpowered tests, and all events are TEST-EXPOSED. Shifted same-season clean-day negative control: ARX starts 1/8 false event windows at <=60 minutes; mode-crossing negative control: 0/7. They are not independent random experiments.

### Prior CD01 alarm-onset bug

- The original evaluator incorrectly vetoed *all* future starts when the alarm was already active at the fault boundary.
- The corrected scorer distinguishes `strict_clean_start_onset` (clean boundary required) and `any_new_onset_after_fault` (a later new start after an **observed** quiet five-minute tick). These metrics are not automatically causal fault attribution.
- CD01-A conditional alarm FAR is still 1214/1785 = 68.01%; the stricter prior 7/14 and new temporal 10/14 do **not** make this method viable.

## 3. A material reporting defect remains: operation-mask coverage

**P1 — `code/rescore.py` lines 42–52, particularly line 51.** The displayed `fault_coverage` denominator is `f = eval & active & fault`; the numerator is `f & observed`. This is **conditional sensor-score coverage after restricting to fan-on rows**, not coverage of the entire registered physical fault interval. Consequently `fault_coverage = 100%` is essentially tautological when every fan-on fault row has a finite score.

Recomputed from the frozen R source CSV without changing a model:

| Population | All labelled 5-minute rows | Fan-on rows | Fan-on and finite |
|---|---:|---:|---:|
| Normal, evaluation | 3603 | 3154 (87.5%) | 3141 (87.2%) |
| Fault, evaluation | 1009 | 834 (**82.7%**) | 834 (**82.7%**) |

Three low-coverage fault days: 2018-07-09, 104/121 scored; 2018-07-10, **35/123**; 2018-07-18, **50/120**. Thus event count 2/7 should always appear alongside eligible-time fraction per event. Do **not** reinterpret fan-off readings as mandatory fault detections; the point is to disclose two denominators, `conditional_finite_coverage` and `physical_window_fan_on_coverage`, and how many cases have insufficient exposure to be scored fairly. Using the same mask for M1 and ARX preserves the paired comparison but does not validate an unqualified claim of 100% fault coverage.

**P1 — OOD external validation limitation.** In the `R_metrics.json`, the independent winter and spring normal cohorts each have `ood_normal = 1.0` relative to the frozen training domain; combined OOD fraction of operating normal is 45.24%. An acceptable observed FAR on an extrapolated mode does not establish valid physical fault-detection sensitivity in that mode. No OOD-abstention policy was enabled; make that explicit.

## 4. Other limitations

1. **Provenance:** bundle includes original-source names/hashes, snapshots of headers and two-channel SAT/MAT arrays. It does not contain all original full upstream CSIRO/LBNL/Nesbitt raw datasets, so equality to each publisher's complete sources is *not* independently proven. The local snapshot is sufficient to replay this CD02 forensic scorer but not to reconstruct the entire data capture chain.
2. **Freeze:** `FROZEN_PROTOCOL_INITIAL.md` and `INITIAL_FREEZE.json` are included and the later added official-schedule sensitivity is labelled post hoc. However timestamps and pre-access status cannot be independently attested from an archive assembled after the fact; all these events are explicitly DEVELOPMENT-EXPLORATORY anyway.
3. **Physics:** coincident `MA_TEMP == SA_TEMP` in supplied CSIRO measurements demonstrates duplicate logged values, not that a physical MAT sensor was absent. The Q signal map avoids falsely treating the duplicate as a second independent channel.
4. **Toy:** nuisance-projected ranks are algebraically sound for the hard-coded sensitivities, but fault sensitivity calibration, independent noise, and label provenance are missing. No field diagnosis result follows from rank alone.
5. **Production immutability:** the archive is an isolated research package, with no independently verified upstream Git baseline to prove unchanged production/UI. No evidence in this archive of production deployment.

## 5. Acceptance

- **Engineering and research-sprint reproducibility: PASS** (with the R coverage-reporting limitation).
- **The three scientific decisions Q/D/R: ACCEPT as scoped triage**: Q and D require independent physical data; R does not warrant promotion beyond a simple reference ARX baseline.
- **Any scientific claim of improved deployment-ready detector: NO GO.** No fresh blind fault set, no independent validation across equipment, no measured independent position/flow/reference combination, no statistically convincing event-level gain.
- **Do not run another rescue loop to tune ARX on these eight exposed scenarios.** Correct the two coverage labels in the next provenance/reporting update without retroactively changing CD02 model metrics.

## 6. Next narrowly defined action

Run a **data-first independent measurement discovery sprint**: check primary-source channel dictionaries and raw samples for a genuine paired pre-override command and independently measured actuator position/coil flow/reference sensor, with temporally matched and trustworthy fault interventions. A small set of independently instrumented, labelled fault events beats more regressions on already explored CSVs. If no eligible dataset, provide `NOT_EVALUABLE` and an exact measurement acquisition plan; do not invent a synthetic field victory. Keep mandatory complete ZIP, source, logs, checksums and negative findings.
