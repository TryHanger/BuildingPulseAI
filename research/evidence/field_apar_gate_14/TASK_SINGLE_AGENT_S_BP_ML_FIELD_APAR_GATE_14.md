# SINGLE AGENT S — BP-ML-FIELD-APAR-GATE-14

## Mandate / why now

Stage13 accepted `ACCEPT_EXPLORATORY_DESCRIPTIVE`: six real AHU 120-min windows have negative median SAT changes, but *so do some no-scheduled-intervention windows*, and all events lie on two days at one site. We need to advance from repeated after-the-fact inspection of temperature to an **explicit, prequalified physical-rule baseline** drawn from published APAR literature, with honest abstention and negative controls. **One agent S only**, on the current BuildingPulse working copy. No second project, no production alert or operational FDD changes.

**GitHub amendment (2026-11-09):** The user has subsequently authorized committing and pushing to `TryHanger/BuildingPulseAI` in the designated review branch. This supersedes the earlier `no commit/no push` rule **only for that repository and the workflow below**. Do not deploy, force-push, merge without approval, or modify `main` after baseline bootstrap. See `GITHUB_HANDOFF_STAGE14.md`.

The central question is not whether six intervention windows show a temperature fall (already known) but whether a **documented regime-aware APAR-like rule**, using available genuine BMS channels with defensible roles, would distinguish an actionable operating anomaly from common benign/misclassified temperature variations *better than a naive SAT-drop flag*. This is a **research-only feasibility and small exploratory baseline**; it cannot establish FDD population-level accuracy or physical cause.

## Inputs and non-negotiable science contract

- Source publication: Nehasil et al. (2021), *Versatile AHU fault detection – Design, field validation and practical application*, DOI `10.1016/j.enbuild.2021.110781`, preferably open accepted manuscript from CTU repository `https://dspace.cvut.cz/entities/publication/35d10945-7123-4cdc-8367-50bfdb4c1052`.
- Source data: Mendeley Data Version 1, DOI `10.17632/jkw85sm4v4.1`, originals pinned in Stage13 `evidence/SOURCE_PROVENANCE_11.json` (six AHU workbooks, schedule workbook, place-tag diagram). Independently SHA-256 check all eight source bytes before proceeding; do not interpolate 300s data or substitute missing sensors.
- Stage12/13 fixed manifests/trace baselines are immutable; preserve original timestamps (timezone unknown). DO NOT treat a controller request as actual valve/pump position, and do not use publisher fault labels as real-time features.
- Stage13 event windows were *previously examined*, so any subsequent evaluation on them is **exploratory and not a blind confirmatory validation**. Stage13 `PRE [−30,0)`, `WINDOW [0,120m)`, `POST [end,end+30m)` remain immutable for the existing six main events; short row29 remains separate. The first POST tick can still carry the publisher intervention label.

## Work sequence and gates

### Gate A — Recover the actual published method

1. Read the original paper/accepted manuscript, especially sensing/semantics, operating-mode rules, Table of induced faults and evaluation definitions. Produce `PAPER_APAR_TRACEABILITY_14.md`: exact rule or conditional family, source page/figure/table, required channels, expected directions, dwell/threshold if *actually specified*, and difference between the **author's results (94 of 105)** and this project. Do not invent author rule parameters or claim to have reproduced their complete rule system.
2. Source-qualify only **one** candidate rule for heating-valve/pump or another physically coherent AHU symptom; prefer a direct input-available published rule over speculative combinations. Make an explicit `PHYSICAL_INPUT_CONTRACT_14.csv` with source tag, `real_value`/`required_value`, unit, air/liquid placement, controller mode and unknown independence. Confirm no *required* channel is missing or only a modeled/oracle state. If original article's precise rule is not sufficiently documented, label an independently defined rule `APAR_INSPIRED_NOT_PAPER_REPLICATION`, with physical rationale and no assertion of 94/105 equivalence.
3. Predeclare whether source really allows the needed regime conditioning and independently measured effect. If not: emit `STOP_RULE_INPUTS_UNQUALIFIED` or `STOP_METHOD_NOT_REPRODUCIBLE` and stop before fault scoring. A baseline rule may detect *observed state mismatch* without establishing physical cause; annotate it as such.

### Gate B — Freeze design and comparison windows BEFORE any new scoring

4. Produce `METHOD_PREREG_14.md` and machine-readable JSON plus their SHA-256. Define rule predicate, applicability, missing-data and mode handling, optional dwell, output statuses (`APPLICABLE`, `NOT_APPLICABLE`, `INSUFFICIENT_DATA`, `UNVERIFIED_SEMANTICS`, `RESEARCH_SIGNAL_ONLY`), and the selected **naive** baseline (`sign(median SAT_window - median SAT_pre)` is previously observed, so mark as retrospective baseline). Include explicit threshold provenance: publisher-stated, engineer-fixed ex ante, or independently calibrated on disjoint source *normal-like* periods. No parameter, sensor, threshold, window or date may be tuned after examining Stage13 fault labels/results. If no justified threshold exists, use non-decision numerical evidence without binary score.
5. Build a new **all-eligible comparator ledger** on native 300-second grid for same AHU/clock/duration and mode, first screening with timestamps/availability/commands only. Exclude site scheduled-intervention days ±1 and overlapping interventions. Rank dates deterministically and seal selection *before any reading of outcome magnitudes*. Retain **every** qualifying non-scheduled comparator, not just nearest. Show which comparator windows share the same calendar day or overlapping samples; group evidence by date/site, do NOT count all as independent negatives. `no fault` publisher label remains an annotation, not certified healthy ground truth.
6. Record site-level unobserved co-variation and other concurrent interventions; do not claim physical cause isolation or make p-values from correlated 5-minute ticks. If controls have inadequate distinct dates, outcome must be `STOP_UNDERPOWERED_COMPARATORS` for *claim of differentiation* regardless how large intervention SAT falls are. Report data coverage and abstentions, rather than quietly removing difficult AHUs.

### Gate C — ONE exploratory prototype if A and B pass

7. Implement only `research/ml_field_apar_gate_14/` (or analogous isolated research namespace) with a small deterministic offline runner, tests, and concise CSV/JSON outputs. No new ML, no LightGBM retuning, no production rule activation; do not write to old `diagnostics_service.py`, model weights or production incidents. Preserve existing Stage10/Stage12/Stage13 research views and hashes; optional research-only graph can be prepared **after** numeric reconciliation, not before.
8. Evaluate precisely the original six main event windows + **all** eligible comparator windows; short row29 reported separately. Present per-episode observed signals, inapplicability reasons, binary outputs *only if an a priori threshold is justified*, false alert counts labelled **on non-scheduled windows** (never 'specificity'), and case-based differences from naive SAT-drop. Report every failure, no censoring. Preserve raw evidence; do not infer physical valve or pump state from command tags. If scoring is impossible, deliver Gate A/B audit and STOP without implementing a dummy classifier.
9. Internal quality: unit tests for opposite sign, missing sensor, wrong unit, fan OFF, contradictory commands, invalid clock/cadence, unrealistically sparse data, corrupted source, duplicate events, label-in-feature leakage, overlap in comparator times, and edge boundary POST label. Independent replay and exact SHA 8 original source files; no full-original ZIP in delivery. If full integrated app unavailable, clearly say so. Test the isolated research code without changing baseline product files.

## Decisions / forbidden conclusions

- `GO_RESEARCH_APAR_BASELINE_ONLY`: inputs and thresholds qualified, all original source files/ledger verified, negative comparisons included, research-only outputs reproducible. This is *not* a field diagnosis or validated method.
- `STOP_RULE_INPUTS_UNQUALIFIED`: required physical channel semantics or measurement absent.
- `STOP_METHOD_NOT_REPRODUCIBLE`: original rule cannot be reconstructed exactly; if an adapted method is reasonable, explicitly mark it as a different research hypothesis and require prereg before its own exploratory run.
- `STOP_UNDERPOWERED_COMPARATORS`: few independent site-dates/healthy cases to support differentiation; preserve descriptive evidence, do not score sensitivity/specificity as field performance.
- Never assert `CAUSAL_EFFECT_IDENTIFIED`, `FIELD_FDD_ACCURACY_ESTABLISHED`, `REPRODUCED_94_OF_105`, or `CROSS_BUILDING_VALIDATED` based on this dataset. Stage11 causal gate remains STOP.

## Required delivery via GitHub (updated transport)

The original task requested a compact ZIP. The owner has **replaced that handoff mechanism with GitHub**. Commit all necessary changed source files, tests, protocols, manifests, compact evidence and negative cases to branch `research/field-apar-gate-14`; open/update a **Draft PR against `main`**. Do not commit the eight original large workbooks, large raw CSVs, model weights, SQLite or secrets. Include SHA-256 plus download/reproduction instructions. The PR must contain an exact base/head commit SHA, test commands/logs, source role audit, immutable prereg, comparator ledger, decisions, unchanged protected-file hashes, and an honest `CLAIM / NOT CLAIM / STOP` index. Do not merge or proceed to Stage15 before independent review.

A documented STOP is a legitimate final result; do not fabricate an alternative method to force a GO.
