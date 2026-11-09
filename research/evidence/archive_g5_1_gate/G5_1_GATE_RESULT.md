# BuildingPulse AI · G5.1 gate result

**Decision** `STOP_NO_QUALIFIED_INTERVENTION_FAMILY`  
**Product closeout** PASS · OpenAPI `1.0.0-rc.7`  
**Scope** CSIRO published BMS interventions, one operational building, retrospective only · 7 November 2026

## Qualification result

Every published intervention row was inventoried. AHU9 has 198, AHU10 has 103 and AHU15 has 90. The release has telemetry for AHU9 and AHU10. A row may represent a proxy command, a sensor-input override or a more ambiguous treatment. It does not constitute an independent experiment. Source counts below include all published rows, including rows without matched telemetry.

| Check | Result | Evidence |
|---|---|---|
| Publisher bytes, taxonomy and interval join | PASS | All three Parquet SHA-256 match the G5 LFS receipts. A separate in-memory SQL count agreed with indexed half-open slicing for every valid publisher row. `EVENT_LABEL_LEDGER.csv` and `qualification.json`. |
| Source clock for interval alignment | PASS for native interval membership | Time columns are offset-free. Both telemetry sources are sorted and unique with modal 30-second cadence. The publisher rounds telemetry to one second. The gate uses a 30-second boundary tolerance and rejects steps off the nominal grid, including breaks between pre/event/post windows. |
| Clock or physical onset for delay | UNKNOWN | The declared interval comes from the publisher's intervention log. UTC offset, controller clock synchronization and actual activation time lack separate verification. Delay is undefined. |
| Independent eligible event volume | FAIL | Across supported AHUs, 23 rows in 17 building-day blocks pass structural checks after excluding known reviewed dates. No family exceeds **6** such blocks against a predeclared minimum of **35**. Even before removing reviewed dates, the best family reaches **7**. These are upper bounds from structure, before channel and excitation qualification. |
| Treatment isolation | FAIL for many rows | 152 rows overlap a same-AHU interval. 290 overlap another AHU without evidence clearing shared influence. 132 have a neighboring nonoverlap interval within the washout. Counts can overlap. Row IDs and exact reasons are in the ledger. |
| Physical plausibility | PASS for a documented BMS override taxonomy | The source describes controlled intervention through proxies. A named proxy family does not establish the actual feedback signal or independently measured physical effect. |
| Deployment observability, excitation and independent feedback | UNKNOWN | Recorded valve and damper points cannot be bound to distinct pre-override demand and independently measured travel. Fan speed has unresolved proxy provenance. The published MAT vector duplicates SAT exactly for both AHUs. A temperature column or controller value cannot substitute for independent travel. `SOURCE_POINT_LINEAGE.csv`. |
| Label identifiability | PASS for the scope of a documented interval, UNKNOWN for mechanism | `CONTROLLED_BMS_INTERVENTION_PRESENT` is a publisher interval label. Ambiguous rows are marked separately. Exact native proxy tag, physical effect and mechanical fault are unverified. |
| Verified reference and blind test | FAIL | Zero verified reference blocks. Outside a documented interval is `UNKNOWN_UNANNOTATED`. At least 33 building dates from Stage 8C were already exposed. No qualified experiment partition or blind holdout exists. |

The 30-minute pre/post rule and cross-AHU isolation are conservative screening choices fixed before the sweep. They do not assert cross-AHU influence for every overlap. A nominally zero or missing magnitude is flagged as ambiguous without a verified map from native magnitude to treatment. The minimum of 35 blocks is a feasibility floor with 20 reserved for retrospective test, not a guarantee of statistical power. `ELIGIBILITY_MATRIX.csv` reports each family and AHU and the combined available telemetry with shared calendar blocks deduplicated. No comparator, Ridge challenger, model fit, detection score or production FAR was computed. The G5 LBNL nominal pilot remains separate.

## Product semantics

A live 10-observation window gives `violated=10`, `unconfirmed_violated_samples=10`, zero episodes and `confirmation_state=PENDING`. The UI shows «Нарушение продолжается на границе окна» and explains that later observations can change confirmation. The 11th observation confirms the episode at the existing 600-second threshold. A short violation already ended within the window gives `UNCONFIRMED`. Legacy status values and routes remain compatible. The G5.1 state is additive and describes only the observed window.

## Specific acquisition

Request an **IBAL AHU1 chilled-water valve intervention campaign**, from the NIST IBAL Experiments export or the IBAL database contact listed on the page. Identify AHU1 valve V12 explicitly. The V2 example in the dictionary is a different path. Ask for raw synchronized `v12_pos_c` demand and `v12_pos_fb` feedback, `ahu1_f_cc`, `ahu1_cc_out_rtd`, verified cooling enable, and an independent calibrated SAT reference at the same measurement plane as the controller SAT. Ask for point mapping, independent verification of achieved travel, clock offset and synchronization, and a signed run log with planned and actual start/end, release, washout, safety aborts, stable-load controls and independently verified nominal runs. Request distinct repeated whole-day blocks and separate custody of test runs.

The two previously reviewed sample runs are ice-storage charging runs, with no corresponding intervention labels. If no suitable past AHU1 run exists, request a separately approved instrumented trial of a documented limited-travel intervention on V12 with control runs. State whether intervention is simulated in the controller or physically imposed. Do not start the modeling gate until the owner and independent reviewer accept the source. [NIST IBAL database and contact](https://www.nist.gov/el/beed/intelligent-buildings-agents-project/data/database), [point dictionary](https://www.nist.gov/el/beed/intelligent-buildings-agents-project/data/data-dictionary), [published thermal-storage sample](https://www.nist.gov/el/beed/intelligent-buildings-agents-project/data/sample-experimental-thermal-storage-data)

## Verification

297 pytest passed, strict TypeScript/Vite built, generated types and live HTTP report schema checked, and Playwright G0–G3 and G5.1 regression passed. The two pending UI screenshots are 1440×900 and 390×844 viewport captures. Docker read-only scratch smoke passed. Full Compose was outside this narrow regression. SHA-256 for original and restored raw, processed and SQLite matched before and after. The accepted G5 overlay was reverified by hash before editing the isolated copy.

[Protocol frozen before sweep](PROTOCOL_G5_1_v1.md) · [Source and reproduction](G5_1_REPRODUCE.md)
