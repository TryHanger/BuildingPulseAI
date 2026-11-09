# BuildingPulse AI — Independent Audit of Stage 8B-R.4 Corrected

**Date:** 2026-11-04  
**Artifact:** `BUILDINGPULSE_AUDIT_STAGE_8B_R_4_CORRECTED.zip`  
**Archive SHA-256 (independently calculated):** `12b8a96d614496844a59c0d6301f96c13160b1ad1327293761cdf0b4244adf7e`  
**Scope:** reproducibility, report/data parity, event-onset semantics, FAR and eligibility denominators, model provenance, product-code comparison. This is a technical audit, **not** a new blinded validation.

## 1. Reproduced evidence

- ZIP CRC check (`ZipFile.testzip`) succeeded; ZIP contains 259 entries. `SHA256SUMS.txt` lists 257 files; all 257 match their independent SHA-256. The two unlisted entries are `SHA256SUMS.txt` and `audit/SHA256SUMS.txt` themselves (self-reference exclusion, not 2 missing experiment files).
- From the extracted archive: `python -m pytest tests -q` = **33 passed in 3.41 s**.
- Independent copy of the archive: `python run_independent_validation.py` returned 0 and generated 3,744 pointwise predictions. After removing the execution timestamp, the machine result manifests are exactly equal to the supplied version. The executed code in `scripts/...` and the copies under `code/scripts/...` have identical SHA-256. The same holds for `ml/diagnostics/time_aware_fdd.py` and `code/ml/diagnostics/time_aware_fdd.py`.
- Comparing the current archive to `BUILDINGPULSE_AUDIT_NEXT_EXTERNAL_VALIDATION.zip`, all shared **31 `code/backend/app/` files** and **13 `code/frontend/src/` files** are byte-identical. This establishes no changes *between the supplied archives* in those paths. It does not independently prove full Git working-tree status, deploy status, or the historical v0.7.1 release integrity.
- The actual source reconstructs locally-fitted `Ridge(alpha=10.0)` models from two 2016 baseline days on every run (`scripts/evaluate_rbc_nesbitt_independent_validation.py`, lines 563–565). The coefficients remain reproducible. Thus the correct statement is “no change in fitted model parameters relative to this protocol,” not “models are never re-fitted at execution.”

## 2. Replicated primary matrix: five TEST-EXPOSED fault days

| Detector | Any overlap | New onset within *official* fault interval | Pointwise FAR | False alarm episodes/8 h |
|---|---:|---:|---:|---:|
| M1 thermal, τ=2.75 | 2/5 | 2/5 | 133/3124 = 4.26% | 0.37 |
| M2 feedback, validation τ=3.0 | 2/5 | **0/5** | 675/3124 = 21.61% | 2.70 |
| M2 feedback, exploratory τ=3.5 | 2/5 | 1/5 | 403/3124 = 12.90% | 1.26 |
| M2 feedback, exploratory τ=4.0 | 2/5 | **1/5** | 80/3124 = 2.56% | 0.68 |
| M3 fusion, exploratory τ=4.0 | 2/5 | 1/5 | 165/3124 = 5.28% | 0.89 |
| M6 direct BAS override rule | 4/5 | 2/5 | 948/3124 = 30.35% | 3.56 |
| M2 with DomainGuard, τ=3.5 | 0/5 | 0/5 | 0/1224 = 0%, **conditional only** | 0.00 |

The two thresholds 3.5 and 4.0 were previously exposed to test events and are **not independent validation results**. The model selected from development validation (M2 τ=3.0) has high FAR and no post-official-fault new event onsets. No model passes a convincing all-season, previously blinded confirmation of improved FDD.

### Seasonal FAR matters

- M2 τ=4.0: combined FAR 2.56%, **winter FAR 6.59%**, so season-specific threshold compliance fails.
- M6: **winter FAR 66.27%** despite detecting some directly observable BAS overrides in summer.
- M1: 133 false-alarm points across normal sections of fault days, while **0/2304** baseline-day normal points alarm. Accordingly, FAR on fault-day nominal sections alone is **133/820 = 16.22%**, even though aggregate FAR is 4.26%; the distinction could arise from operational regimes, transitional/washout states, or incomplete normal labels. No causal attribution follows from these counts alone.
- M2 τ=4.0: baseline-day FAR is **26/2304 = 1.13%**, while fault-day nominal sections are **54/820 = 6.59%**. The aggregated score obscures the operational shift.

## 3. Important unresolved event-boundary sensitivity: 2016-12-01

**Location in code:** `HOLDOUT_FAULT_SPECS` at the top of `scripts/evaluate_rbc_nesbitt_independent_validation.py`; `evaluate_holdout_slice` around lines 260–352.

The agent's own registered metadata gives:

- `official_start_hhmm = 1000` (10:00)
- `physical_override_start_hhmm = 955` (09:55)
- Raw BAS `RELIEF_DAMPER`: **45.6% at 09:50 → 90.0% at 09:55**.
- Alarm `M2_Control_Mat400`: **False at 09:50 → True at 09:55** (a new onset). It remains True at 10:00.

The algorithm defines event recall **only inside the official 10:00–20:45 interval**, so it labels this episode `ALARM_STARTED_BEFORE_FAULT`, with no new onset. This is **correct under the published official-window definition**, but not equivalent to saying the model never reacted near physical actuation. The report also must not imply the 08:40 alarm was continuous until fault start: there were intervening alarm-offs and a new onset at 09:55.

Independent sensitivity calculation on the *same stored alarm traces* (no model or threshold changes):

| Method | New onsets in official windows | New onsets in agent-specified physical override windows |
|---|---:|---:|
| M2 τ=3.0 | 0/5 | 0/5 |
| M2 τ=3.5 | 1/5 | 1/5 |
| **M2 τ=4.0** | **1/5** | **2/5** |
| **M3 τ=4.0** | **1/5** | **2/5** |
| M6 | 2/5 | 2/5 |

**Interpretation:** This is **not** a reason to promote M2 to success. On this winter date, the model had numerous earlier false alarm onsets due to severe seasonal mismatch, so the onset at 09:55 cannot be attributed uniquely to the new physical override. However, official versus physical intervention windows should both be reported, and the factual claim “no new onset for this scenario” must always specify the official 10:00 boundary. Independent experimenter records for the exact physical start should govern any future primary metric; the agent's manually specified `physical_override_start_hhmm` does not by itself prove provenance.

## 4. Zero-denominator scientific bug (P1)

In `evaluate_holdout_slice` near lines 453–465:

```python
far = round(float(tot_fa / tot_norm_eff) if tot_norm_eff > 0 else 0.0, 4)
...
pt_recall = round(float(total_det_rows / total_fault_rows_eligible) if total_fault_rows_eligible > 0 else 0.0, 4)
```

Winter DomainGuard retains **0/1183 normal points** and **0 fault points**. Conditional winter FAR is **undefined (0/0)**, not an observed 0%. The proper machine value is `null` plus `NOT_EVALUABLE_ZERO_COVERAGE`; separate, operational episode recall is **0/2** because the detector abstained on both events. Similarly, conditional pointwise fault recall at zero eligible points is undefined. The report currently says 0.00% for the winter conditional FAR even though it also discloses 0.0% coverage; this should be corrected before academic publication. For the full 13-day slice, `0/1224 = 0%` is a defined **conditional** FAR at only 39.2% normal coverage and about 0.2% fault coverage.

## 5. Scientific limits to preserve

1. **Model type:** M2 predicts **CCV_FBK actuator feedback**, not controller command. It is not zero-shot transfer of a trained CSIRO model.
2. **M6 signal:** reads `RELIEF_DAMPER` and `RETURN_DAMPER`, both potentially expose BAS intervention. It is a direct BAS rule, not independent proof of fault physics.
3. **OOD abstention:** full holdout normal coverage **39.2%**, fault coverage **0.2%**; no deployment advantage can be inferred from conditional 0% FAR.
4. **Test exposure:** all five fault days have been repeatedly examined. There is no prospective/cryptographically blinded holdout proof of model superiority.
5. **Causal inference:** the circular-shift control's high FAR only indicates sensitivity to temporal alignment, not proof/disproof of causal identification of faults.
6. **Selection:** the summer/winter “all operational points” counts include 5-minute records across the entire day (all passed `SF_SPD ≥ 10` in this sample); false alarm episodes/8h are normalized by eligible observed hours, not by literal staffed business shifts.

## 6. Acceptance decision

- **Archive integrity:** PASS.
- **Standalone 33/33 tests:** PASS.
- **Numerical reproducibility and primary generated report/machine matrix parity:** PASS for checked measures.
- **Correction of prior continuous pre-fault alarm inflation:** PASS for the **official** window definition.
- **Physical override/onset timing:** **P1 UNRESOLVED SEMANTICS**; the 09:55/10:00 sensitivity should be published, not silently discarded.
- **Conditional FAR at zero coverage:** **P1 SCIENTIFIC BUG**; undefined must not be serialized as 0%.
- **Scientific superiority / cross-building generalization / production readiness:** **NOT DEMONSTRATED**.

**Verdict:** accept Stage 8B-R.4 Corrected as reproducible **post-hoc forensic accounting** of a negative/limited research result, **not** as successful independent validation of a universal FDD detector. Do not initiate another metric-optimization cycle on these five fault days. Fix zero-denominator reporting and preserve a separate official-vs-physical timing sensitivity when this work is published or cited. Future scientific progress requires genuinely unseen data, stronger channel lineage, and pre-access versioned preregistration.

## Reproduction commands

```bash
sha256sum BUILDINGPULSE_AUDIT_STAGE_8B_R_4_CORRECTED.zip
unzip BUILDINGPULSE_AUDIT_STAGE_8B_R_4_CORRECTED.zip -d audit_r4_corrected
cd audit_r4_corrected
sha256sum -c SHA256SUMS.txt
python -m pytest tests -q
python run_independent_validation.py
```

**Note:** the published ZIP does not prove any Git commit/push/deployment absence. Checksums prove only the contents of this artifact; byte comparison with the earlier supplied ZIP supports that common backend and frontend source files remained unchanged between these two supplied artifacts.
