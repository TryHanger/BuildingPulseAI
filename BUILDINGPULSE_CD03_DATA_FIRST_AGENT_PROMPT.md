# BuildingPulse AI — CD-03 Data-First Parallel Feasibility Sprint

**Purpose:** leave CD-02 frozen and obtain usable *physical evidence*, or prove unavailability in the inspected sources. This is not a rerun of Stage 8C, CD-01 or CD-02, not a new production model, and not a mandate to produce positive results.

## Mandatory inputs

Read the current independent audit `BUILDINGPULSE_CD02_INDEPENDENT_AUDIT.md`, the CD-02 ZIP (`DECISION_MATRIX.md`, `CLAIM_TO_EVIDENCE.md`, `results/Q_*`, `results/D_*`, `results/R_*`, `code/rescore.py`, `inputs/local_header_inventory.json`), original search2 C07 and search4 C03/C06 scientific reports, and the exposed-test register. Establish immutable source/dataset IDs and state what is already test-exposed.

## Track 0 — Close CD-02 reporting defect, not the old experiments

In a new versioned report only, **do not edit old results**, distinguish:
- `normal_valid_given_fan_on` vs `normal_fan_on_and_valid_over_all_clean`;
- `fault_valid_given_fan_on` vs `fault_fan_on_and_valid_over_all_fault_window`;
- per-event raw ticks, fan-on ticks, score-valid ticks and alarm-eligible ticks;
- uncovered event fraction and OOD fraction by season.

Regression anchors on frozen Nesbitt R: normal 3603 total / 3154 fan-on / 3141 valid-and-fan-on; fault 1009 total / 834 fan-on / 834 valid-and-fan-on. Scenarios 2018-07-10: 35/123; 2018-07-18: 50/120. Do not silently change FAR or thresholds. Make the exact definitions machine-readable and testable. Use STOP if counts disagree with the frozen artifacts until discrepancy is explained.

## Track 1 — Independent-source dataset procurement (parallel with Track 2)

Search *official* datasets and primary articles/documentation relevant to AHU feedback-hidden actuator and sensor faults. Check first: full original CSIRO experiment/BMS documentation, LBNL SD-AHU/related original datasets, Drexel RBC-Nesbitt original 540-column maps, RBC-ASHRAE1312, NIST/ASHRAE reference fault sets, and any genuine real AHU/BAS dataset with a physical actuator command/position pair. These are search candidates, **not assumed suitable or accessible**.

For every candidate, create a machine-readable table: official DOI/URL/license, original physical equipment and control strategy, raw file names/IDs, SHA-256, fault on/off windows, whether ground truth is mechanical/independently measured vs BAS override/setpoint injection, actual sensor location, units and sampling, pre/post proxy path, and whether command, actual position, coil-local water flow/power, independent SAT reference are simultaneously recorded.

Prove signal independence with evidence from tag dictionary and, where possible, sample timing/crosschecks. A label containing `feedback` is not enough; exact equality `MAT==SAT` is not an independent sensor. Never conflate override, command and independent actuator achieved position. Explicitly label unverified mappings. Only new physically distinct, non-leaky signals may qualify.

**Do not impose an unnecessarily universal all-sensors requirement.** Predeclare the minimal channel set for **each narrow fault pair**. E.g. valve-effectiveness vs SAT sensor bias may require an independently calibrated SAT reference OR coil branch flow in addition to commanded valve and controlled SAT, depending on the identifiability calculation. If a specific pair is identifiable with less instrumentation, justify it by a rank/uncertainty derivation. If independent measurement is missing, mark that specific test `NOT_EVALUABLE`.

Deliver `DATASET_FEASIBILITY_MATRIX.csv` and `SOURCE_VERIFICATION_LEDGER.md`; classify each dataset `ELIGIBLE_REAL`, `ELIGIBLE_SIMULATION_ONLY`, `INSUFFICIENT_SEMANTICS`, `DATA_UNAVAILABLE`. Include negative candidate reviews. Do not claim field validation based on simulated, overridden, or reused output.

## Track 2 — Two micro-experiment specifications (no coding if Gate fails)

**CD03-P (Physical fault discrimination):** source idea from line differential protection/conservation (search2 C07) and hydraulic balance (search4 C06). Hypothesis: at fixed false-alarm episode budget, an independent actuator/coil-flow or reference-temperature residual separates at least one weak actuator fault from sensor bias better than SAT tracking alone. Minimal baselines: tracking temperature, command-only, physically constrained residual, and the best existing simple reference. Negative controls: duplicate SAT, unknown inlet humidity/load, coil storage, flow-sensor bias and an injected BAS override leak. If actual flow or thermodynamic power unavailable, *do not* label an estimated flow as measured. Need time-aligned clean and fault events before implementing.

**CD03-I (Identifiability / measurement value):** source idea from search4 and NLID-LV-01. Use pairwise fault signatures after nuisance projection and noise scaling; rank increase alone is insufficient. Specify held-out evaluation of fault-pair discrimination/top-1 isolation and risk-vs-coverage at equal sensor cost. Compare fixed expert choice and random eligible measurement. Include failure cases for zero sensitivity, common-mode drift and correlated measurement error. A deterministic toy may validate formulas but not justify product integration.

**ARX stays a baseline, not a third ML development track.** 60-min early detection 2/7 vs 0/7 after excluding the BAS setpoint case, exact paired p=.5, 0.94 vs 0.37 false episodes/8h, and 2018 low fan-on coverage are frozen negative/limited evidence. Do not tune ARX further on the same eight disclosed scenarios.

## Gate for any data-driven pilot

Before reading a new dataset's fault residuals or fitting thresholds, write `PRE_ACCESS_PROTOCOL.md` with SHA-256 and external timestamp evidence if available, split by entire physical events/dates, expected sensor semantics, allowable calibration on normal-only periods, the acceptable time-to-detect, FAR <=5% and <=2 false episodes per eight hours, and explicit `coverage` requirements for both normal and fault windows. Reserve genuinely unexposed events and identify development-known ones. A file written after test access is not proof of pre-access freeze. Abstention/OOD always requires reported coverage; zero-coverage FAR must be `null`.

Pilot only if the appropriate feasibility gate passes. Small pilot should be falsifiable and cheap: one fault-pair, one independent sensor comparison, one negative control. No new N4SID/Kalman/active probing, no neural networks, no production/UI changes. Otherwise stop cleanly with `NOT_EVALUABLE` and exact missing physical signals, not a surrogate positive result.

## Audit deliverables

Create `BUILDINGPULSE_AUDIT_CD03_DATA_FIRST.zip` with source of all scripts; signed/official file manifests and raw non-proprietary inputs or bounded samples with download scripts/checksums; physical channel lineage and injection-status map; split/freeze record; baseline and candidate code if executed; per-point, per-event and eligibility masks; explicit denominators; failed tests and negative controls; valid environment lock or dependency versions; full test stdout/stderr; `git status` and diff if Git exists, otherwise state its absence; `REPRODUCE.md`; SHA-256 index; `CLAIM_TO_EVIDENCE.md`; `STOP_GO.md`. Re-extract into clean temporary directory and rerun every claimed autonomous test. Any missing raw data or dependency must be identified precisely, not represented as a PASS.

**Hard constraints:** no commit/push/merge/deploy; no change to Stages 1–7.1 or previous archives; no external LLM sub-agents; no live BAS/control interventions. Stop after submitting outcomes and the ZIP. User approval required before enlarging scope.
