# BuildingPulse AI — independent audit: BP-ML-DOMAIN-SHIFT-07

**Date:** 2026-11-08  
**Status:** `ACCEPT_NEGATIVE_TRANSFER_RESULT` for Stage 07, **not** permission to score faulted G36 or deploy model.

## 1. Evidence and scope

- Archive: `BUILDINGPULSE_BP_ML_DOMAIN_SHIFT_07_REVIEW.zip`; ZIP CRC PASS, **40/40 SHA256SUMS entries PASS**.
- Source frozen archives (SHA-256 verified by independent tool):
  - Design 05: `2febd05cdfe42efb9dbe65c39a5b0f1c42a22c07fba657f691e33bcde2113b7b`
  - Normal 06: `64ce1a8c46e163ae346df4d3bfec82d486d3a0052fc5da47a4cd2112a45e6bcf`
  - Independent prior task ZIP: `b66be9f2b491256f3df8f5f53d5426a0843c2e42c4d830409459066ae904732a`
- Original LBNL `AHU_annual.csv`: SHA `13a61e5b3e62dcf214b387dc57632073a8044c794eb8102d90d074aa80702d8b`.
- Applied supplied patch in an isolated scratch tree with original Stage 06 router version. `git apply --check` and `git apply` PASS; **12/12 resulting files match the provided overlay byte-for-byte**.
- Independently reran `verify_no_model_07` over original LBNL CSV and frozen Stage 05/06 archives. `PASS` and `STOP_OOD_HEALTHY` reproduced. Generated JSON matches supplied register at **all fields except one 1-ULP numerical rounding difference**: `OA_TEMP/RA_TEMP` correlation of frozen G36 trace `-0.4387365046202244` vs supplied `-0.4387365046202245`; absolute delta ~1.11e-16. Thus JSON *semantic/numeric* parity, **not byte-identical** on current runtime. No decision changes.
- Independent arithmetic of preserved trace: 10,080 rows; 5,425 eligible minutes; 6 eligible minutes with `PLANT_MODE=4`; 7 daily blocks; pooled MAE LightGBM 1.886578433218974 °F, Ridge 1.8670114161803837 °F, SAT−SP 0.18064253312211975 °F. All historical 7/7 alarm decisions preserved.
- Independently stress-tested *service-only* eligibility assessment using 12,000 seeded synthetic metadata cases. No `inference_authorized`, `deployment_eligible`, or `incident_eligible` true; `status` in permitted values. S's 84 pytest and HTTP logs are included in ZIP but **full pytest/HTTP have not been independently repeated** (application source tree is only delivered as patch/overlay).

## 2. Scientific interpretation

**The Stage 06 result is negative and important.** One seven-day G36 simulated *healthy* run yielded LightGBM, Ridge, and SAT−SP anomaly decisions on all seven dependent blocks under source-normal LBNL thresholds. It does **not** establish a cross-site false positive rate, a fault mechanism, or failure of all LightGBM models. Stage 07 did not run new scoring, fault files, training, or recalibration.

Source LBNL training set has one active SAT SP (`55.184006 °F` across 70,842 eligible train minutes). The exposed G36 normal run has mean SAT SP `53.2765194761 °F`, while saved LightGBM prediction mean `55.1926765722 °F`, SAT mean `53.3522939127 °F`. This is *consistent* with a control/setpoint mismatch; it does **not** isolate causal contribution. Different pairwise correlations (e.g., MAT/RA source 0.986, G36 −0.424) show a larger joint-domain mismatch even though univariate X min–max pass.

The post hoc exclusion of 6 minutes from the last block, with fixed thresholds, leaves all three z-scores >3. It is sensitivity analysis only; no new result should replace the registered seven original decisions.

## 3. Limitations found in the API and claims

1. `SOURCE_REGIME_MATCH_ONLY` is **not proof of source-equivalent regimes**. Its implementation checks caller-supplied `origin='VERIFIED_BAS'`, caller-supplied boolean `physical_roles_verified`, exact SP, `RUNNING_WARM`, and three *one-dimensional* min/max ranges. It does **not** authenticate raw BAS metadata, measure multivariate domain similarity, validate data quality, confirm 300-second fan-hold, or check temporal controls. Synthetic physically implausible but per-feature in-range vectors yield `SOURCE_REGIME_MATCH_ONLY`. Thus the exact return reason `EXACT_SOURCE_SUPPORT_MATCH` is **broader than evidence**: it means SP and 1D numerical bounds matched, nothing more.
2. The same request also accepts some numeric strings for `FiniteFloat` feature fields (Pydantic coercion). This is not yet a diagnostic vulnerability, because all positive returns preserve `inference_authorized=false`, `deployment_eligible=false`, `incident_eligible=false`; however callers could misinterpret `VERIFIED_BAS` and the return status as verified provenance. Make the provenance verification server-owned (or clearly declare *self-attested metadata only*) and name statuses so no client may treat them as an authorization token.
3. Exact SP matching is scientifically conservative but practically only meaningful with documented sensor resolution/accuracy. No retrospective tolerance selection based on G36 is allowed.
4. Research page `/research/virtual-sensors` still depicts a separate **native** LBNL model. Stage 07 introduced a research API for the **reduced** model and did **not** add a UI warning there. This was an explicitly allowed alternative in Stage 07, but the scope distinction must remain clear to users.
5. The absence of new model calls is supported by delivered audit code, allowed-member reads and receipts; independent proof about *every action in S's external runtime* is not possible. The ZIP contains only the relevant new code; no complete application source was received for running a full regression suite.

## 4. Decision

`ACCEPT_NEGATIVE_TRANSFER_RESULT / STOP_OOD_HEALTHY` — research API and documentary gate accepted. **No faulted G36 scoring, no field deployment, no automatic incident generation, no promotion of reduced candidate, no retrospective target tuning.** Existing within-source LightGBM results remain valid in their restricted LBNL simulation scope.

Next: `BP-ML-FIELD-DATA-QUALIFICATION-08`. Prioritize a **new real-world external source** for future genuinely informative evaluation, rather than reusing the exposed G36 healthy week or designing another model before data verification.

## 5. External new candidate (prequalified at source metadata ONLY)

- Nehasil et al., *Versatile AHU fault detection – Design, field validation and practical application*, Energy and Buildings 237, 110781 (2021), DOI `10.1016/j.enbuild.2021.110781`. Research summary: field testing 25 intentionally induced fault conditions on six AHUs; 94/105 fault occurrences detected by the **authors' APAR-based tool**. These numbers **are not LightGBM benchmark results** and must not be attributed to BuildingPulse.
- Companion field BMS dataset: Nehasil (2021), Mendeley Data V1 DOI `10.17632/jkw85sm4v4.1`. Files include six AHU `.xlsx`, a fault schedule and a point-tag explanation image. Includes both nonfault and induced faults, but **sensor columns, units, sampling interval, setpoint variability, negative control validity, usable days, and compatible training regime have NOT yet been verified**. Six AHUs from one pilot do not mean six independent buildings.
- This is a *candidate for qualification*, not evidence that cross-site transport of the current LBNL model is possible. It could instead support a separate field APAR baseline, sensor-coverage study, or normal-only site-adapted research if actual files satisfy an independently locked protocol.
