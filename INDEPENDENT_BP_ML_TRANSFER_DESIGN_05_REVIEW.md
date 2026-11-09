# Independent review — BuildingPulse BP-ML-TRANSFER-DESIGN-05

**Verdict:** `ACCEPT_PRE_SCORE_DESIGN`. After this independent review, **only** `GO_TARGET_NORMAL_ONLY` is permitted under frozen experiment parameters. **No fault inference; no fault-score; no target fitting or recalibration; no FDD or product deployment.** Target-normal success is a technical gate, not authorization for fault evaluation.

## Basis and independent verification

Submitted: `BUILDINGPULSE_BP_ML_TRANSFER_DESIGN_05_REVIEW.zip` (53 members, including checksums); `sha256sum -c SHA256SUMS.txt` — **52/52 PASS**. All 9 files in additive `BP_ML_TRANSFER_DESIGN_05.patch` reproduced exactly from patch. No modifications of historical FDD/production files in the additive patch. Previous archive SHA checks independently passed for REPRO-02, REPRO-03, VALIDATION-04. The source dataset was extracted **independently** from the accepted `BUILDINGPULSE_G0_G1_AUDIT.zip`, target records from accepted `G5_3_G36_1WK_SOURCE_BYTES.zip` and `G5_2_G36_SOURCE_BYTES.zip`; all raw member hashes match the frozen protocol.

- Source `AHU_annual.csv` SHA-256: `13a61e5b3e62dcf214b387dc57632073a8044c794eb8102d90d074aa80702d8b` (525,540 records).
- Target healthy `BaselineSystem.csv`: `624e3c4e823e265e98d7c982f8498718b263ab1aff4d3fb4f2eb5ff787d370b3` (10,081 records; final right-boundary row excluded).
- Target probe `CooCoiValStuck_0.csv`: `46c3e2833a5baddc7159d4424ad0d9e072d1cda06c10c1a96dfcba12c5f94a59` (metadata validated only; **no inference run**).
- Frozen `TRANSFER_05_PROTOCOL.json` SHA-256: `7efbb52918b8ffb004318bf538fbe58774600aeefebe93cdaebc7ab72fee0fd0`.
- Source fit receipt SHA-256: `1187a8aa96ff7c64ef4e4c0613bee91e8acf5d3bbc794c7d314889ee451fff84`.
- Native reduced LightGBM SHA-256: `643f08b6f50edef8487783f41ea7067e9860181df4eda152d5751625`.
- Ridge reduced JSON SHA-256: `a0e122b112ad2ae6b914635bf161d8977b5a11283b75260b620504dfd317f7de`.

Re-ran the actual **model-free** `preflight.py` on independently reconstructed raw source and both G36 CSVs: **full resulting JSON matches `PREFLIGHT.json` exactly**. Source warm/running 116,272 mins; G36 normal 5,425 mins over seven 775-minute blocks; G36 probe (preflight only) 8,386 mins. `INPUT_SUPPORT_AUDIT.json` shows all 5,425 healthy G36 eligible minutes fit **individual source train min/max**; this establishes input availability, **not** joint distribution similarity or predictive performance. Pre-support common minutes of target normal and probe: 5,423, not a causal paired comparator. Directly ran 20/20 new tests — PASS (current audit environment has different pinned sklearn/pandas/numpy versions; this does not establish byte-reproducible retraining).

Independently loaded the **delivered saved** native booster and Ridge scaler/coefficients and recomputed per-day absolute-error summaries on original **LBNL source-only** data. **186/186** comparisons (62 eligible days × three methods) matched archived `SOURCE_NORMAL_DAILY.csv` within 1.1e−16 °F. Distinct training 70,842 source minutes; 53 evaluable source calibration days; only 9 evaluable source-normal exploratory days out of 73 calendar days, each reported without alarms. This does not establish cross-simulator success. Did not call `Booster.predict()` on either G36 source.

The manuscript and protocol forbid using SAT as model X, G36 simulated oracle labels/true positions/coil heat flows, guessed calendar dates, target fit, and matching two runs as a natural controlled pair. Main X = `MA_TEMP`, `OA_TEMP`, `RA_TEMP`. `SF_SPD_DM` in LBNL correctly differentiated from speed command `SF_CS`. Mode/time/missing-data checks exist. Agent's evidence of pre-freeze/source-fit order is consistent but log timestamps do not independently prove a historical sequence.

## Important scientific and engineering qualifications

1. **Controller shift is decisive:** source uses near-fixed SAT regulation, target G36 uses Trim & Respond. A virtual SAT based solely on MAT/OA/RA may flag legitimate normal control operation. A target-normal false-alarm stop is a **valuable negative result**, not a reason to tune thresholds to G36.
2. Train support bounds are univariate min/max only. **5,425/5,425 inside limits does not prove in-distribution** in feature combinations, conditional SAT behavior, or occupancy/control regimes. Joint drift may be reported only descriptively; do not invent a post-hoc gate or adjust input mask after seeing target outcomes.
3. Seven nominal 1-week blocks share controller, simulated plant, season and forcing. They are **not seven independent physical buildings**; zero alarm blocks would not establish zero deployment FPR or real-world generalization.
4. Source-normal exploratory held-out **9 days** is small and within the same generator; no source fault scores were run in Stage 05. A positive healthy gate does **not** validate fault sensitivity or attribution.
5. **Code/status defect to address before any future fault evaluation:** helper `healthy_gate` currently returns literal `GO_FAULT_EVAL_DESCRIPTIVE` upon a technical healthy pass, whereas the frozen protocol requires a **separate independent owner approval**. Next stage must map technical PASS to `PASS_TARGET_NORMAL_AWAITING_FAULT_APPROVAL` and never automatically trigger the fault branch. Do not mutate the frozen protocol JSON to fix this; correct stage-specific execution semantics instead.
6. Source-only fit weights were independently tested by re-scoring but not retrained in an exactly matching dependency environment. Agent's byte-repeat log is supplied; this audit does not assert independent byte-identical model retraining.
7. Historical 16-physical-feature native SAT model remains `BLOCKED_EXTERNAL_VALIDATION`. New reduced model cannot inherit its high LBNL AUC, its 37/59 result, its multi-target ranking, or its publisher alias identity. The new source-normal nine-day outcome is not a substitute for sensitivity validation.

## Explicit authorization and next gate

I authorize **`GO_TARGET_NORMAL_ONLY`**, limited to the **single frozen `BaselineSystem.csv` file** and the source-trained immutable LightGBM/Ridge/physical SAT−SP baseline. Confirm all listed protocol/model/dataset SHA before scoring. Apply the **same minute mask** to all methods, no target adaptation, no threshold changes (`z > 3`, source healthy calibration). Retain all seven predeclared model-day blocks, including abstentions, and the right boundary exclusion. Report full per-minute score trace and per-block status, mode strata, reasons for abstain, and evidence of contamination controls. Frozen healthy gate: ≥3 eligible blocks, ≥80% eligible warm/running minutes, zero LightGBM normal alarm blocks, complete fan/OAT observability. **If any condition fails: STOP_OOD_HEALTHY and no fault-run inference.** If passes: **PASS_TARGET_NORMAL_AWAITING_FAULT_APPROVAL** and request review before any G36 fault score.

Next task file: `TASK_SINGLE_AGENT_S_BP_ML_TRANSFER_NORMAL_06.md`. No Git commit, push, deploy, modification of original datasets or old models.
