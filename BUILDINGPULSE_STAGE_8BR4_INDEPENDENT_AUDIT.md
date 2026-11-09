# BuildingPulse AI — Independent Audit Stage 8B-R.4 (2026-11-04)

## Вердикт

**Пакет и арифметическая воспроизводимость: PASS. Научное подтверждение и предрегистрация: NOT ACCEPTED / EXPLORATORY-ONLY. Не внедрять в production.**

Выполнена независимая распаковка `/mnt/data/BUILDINGPULSE_AUDIT_NEXT_EXTERNAL_VALIDATION.zip`, сверка SHA-256, `pytest tests -q`, независимый повторный запуск `python run_independent_validation.py`, сравнение машинных матриц исходного архива и повторного запуска, анализ кода `scripts/evaluate_rbc_nesbitt_independent_validation.py`, данных и оригинального PDF `data/raw/rbc_nesbitt/00_explanations.pdf`. Для сопоставления моделей использован предоставленный ранее ZIP `BUILDINGPULSE_AUDIT_STAGE_8B_R_3.zip`.

### A. Подтверждённые технические факты

- Размер ZIP: 4 546 961 байт; SHA-256 `93848c58fd95a6bf49bad0cf55e6dbe173c30652936fd550f915c5d57001f64c` — совпал.
- ZIP CRC: OK; 251 записей; 249 файлов перечислены в `SHA256SUMS.txt`, все 249 совпали. Не перечислены сами две копии списка SHA.
- Набор `tests`: **26/26 PASS** независимо. Это подтверждает заявленный автономный сьют, но не является независимым доказательством correctness научной оценки.
- Повторный запуск `python run_independent_validation.py`: exit 0; 3744 строки точечных остатков; все `evaluation_slices` повторно созданного JSON **точно совпали** с оригинальным JSON (кроме timestamp запуска).
- 13 holdout CSV = 5 новых дней экспериментов + 8 baseline; все файлы читаются; примеры разметки соответствуют приложенному оригинальному документу Drexel.

### B. Реальные результаты (исходный JSON и независимый повторный запуск)

| Конфигурация | Summer 3 faults | Summer FAR | Winter 2 faults | Winter FAR | All 5 faults | All FAR | False episodes / 8h all |
|---|---:|---:|---:|---:|---:|---:|---:|
| M1 thermal τ=2.75 | 2/3 | 8.05% | 0/2 | 0.00% | 2/5 | 4.26% | 0.37 |
| M2 valve feedback τ=3.00 (Val rule) | 0/3 | 0.79% | 2/2 | 47.59% | 2/5 | **21.61%** | 2.70 |
| M2 valve feedback τ=3.50 (exploratory) | **0/3** | **0.00%** | 2/2 | **29.16%** | 2/5 | **12.90%** | 1.26 |
| M2 valve feedback τ=4.00 (post-hoc matched) | 0/3 | 0.00% | 2/2 | 6.59% | 2/5 | 2.56% | 0.68 |
| M3 fusion τ=4.00 | **0/3** | **5.14%** | 2/2 | **6.59%** | 2/5 | 5.28% | 0.89 |
| M2 no MA τ=3.50 | 0/3 | 0.00% | 0/2 | 0.00% | 0/5 | 0.00% | 0.00 |
| M6 direct BAS damper τ=4.00 | 2/3 | 0.00% | 2/2 | 66.27% | 4/5 | **30.35%** | 3.56 |
| M2 OOD-abstention τ=3.50 | 0/3 | 0.00% | 0/2 | 0.00% | 0/5 | **0.00% conditional** | 0.00 |

For OOD-abstention, normal coverage **39.2%**, fault coverage **0.2%** across all seasons. No operational effectiveness can be inferred from conditional FAR=0% with almost zero fault exposure. All denominators use 5-minute sampling and SF_SPD >=10%.

**Statistical uncertainty:** for 2/5, exact Clopper-Pearson 95% CI is 5.3%-85.3%; for 1/5 it is 0.5%-71.6%. This is not strong evidence of comparative superiority.

### C. P0-01 — report-generation falsifies its own table

`generate_markdown_report()` in `scripts/evaluate_rbc_nesbitt_independent_validation.py` lines **787–801** appends **literal fixed positive scientific claims**:
- M2 and M3 = **3/3 summer**, whereas machine `summer_in_domain` has **0/3 and 0/3** at τ=3.50/4.00.
- Summer FAR M2 = **1.45%, 0.67%** whereas real values are **0.00%, 0.00%** at τ=3.50/4.00.
- Claims M2 no-MA maintains strong summer fault detection while actual summer recall **0/3**.
- Says circular shift proves physical diagnosis, but winter circular shift detects 2/2 while FAR is 40.66% — not evidence of causal physical diagnosis.

The same auto-generated report has correct metric tables immediately above false narratives. **Must remove all hardcoded outcome prose; assertions and report generation must refer only to numeric manifest, with consistency tests.**

### D. P0-02 — pre-existing alarms counted as detecting later faults

Current event scoring is `ep_detected = bool(np.any(alarms[eff_fault]))` (lines **252–265**). This counts already ongoing alarms when the official injected fault begins, and incorrectly records `latency_min=0`.

Independent re-evaluation of alarm traces using unchanged `apply_time_aware_causal_k_of_n`:

- **2016-12-01** AHU2 winter OA damper override starts **10:00** (source PDF). At M2 τ=4, alarm is already active at **08:40**, *80 minutes before fault* and continues through the whole fault window. M2 τ=3.5 also has pre-fault alarms and no new onset in the fault interval.
- M6 on **both winter fault days** has alarm active well before official fault begins (onset observed pre-10:00), with **zero new alarm onsets during fault windows**.
- M2 τ=4 has only **one new within-fault alarm onset across all five events** (2017-01-03), rather than the reported 2/5. M6 has **two new within-fault onsets** (the two summer damper overrides), rather than 4/5.

Note: new within-fault alarm onset is a stricter proxy, NOT itself proof of fault causality. Use separate outcomes: `ALARM_STARTED_BEFORE_FAULT`, `NEW_ALARM_AFTER_FAULT`, `NO_ALARM`, plus validation of a pre-fault quiet window, and report both the original ANY overlap metric and corrected onset metric without retroactively rewriting history.

### E. P0-03 — “frozen previous model” is false

Earlier Stage 8B-R.3 actual training used **2016-06-01, 2016-07-12, 2017-07-14** (3 days) and validation **2017-07-29**. Stage 8B-R.4 code lines **422–445** now trains **2016-06-01, 2016-07-12** (2 days), validates **2017-06-18 and 2017-07-02** (2 days), uses 2017-07-14 and 2017-07-29 in OOD dev envelope, and calls `Ridge(alpha=10).fit(...)` anew.

The actual M2 model coefficients changed materially: previous intercept **82.8814**, new intercept **272.7788**; previous RA_TEMP coef **15.3204**, new **1.5260**; previous MA_TEMP coef **-11.5637**, new **-7.9550**; previous residual-scale sigma_abs **13.589**, new **18.363**. Thus weights are **not** frozen from R.3. The R.4 configuration may still be a valid new locally trained experiment *if fitted before reading holdout*, but the ZIP alone does not cryptographically prove that chronology. Re-label accordingly; provide model hashes and pre-holdout timestamp/commitment or do not claim blinded preregistration.

### F. P0-04 — proxy and mechanism

M6 is not general autonomous fault diagnosis: it computes `z_direct = 5 if RELIEF_DAMPER>20% or RETURN_DAMPER>20% else 0`, reading BAS channels that may be directly overridden by experimenters. Thus 2/3 summer detection may be reading experimental imposed positions, not inferring hidden physical fault. Winter baseline FAR **66.27%** and combined FAR **30.35%** demonstrate poor operational robustness. It must remain `INJECTION_OBSERVABLE / DIRECT_BAS_RULE`, not a product candidate.

The source PDF `00_explanations.pdf` documents `20180709_TSup_m3.5` under 'supply air temperature sensor bias' but says the fault was imposed by overriding the **supply-air temperature setpoint-demand-adjust** point by 1.75. One cannot infer actual physical sensor bias mechanism from the dataset label; document BAS manipulation explicitly. Likewise damper faults are **control signal overrides**, not naturally stuck hardware.

### G. P1-05 — official fault windows and FAR contamination

The evaluator supports `washout_mode = official / override_masked / washout_60m` but all three evaluation slices call the default **`official`**; thus normal data directly before/after override is included by default. Independent sensitivity (no training/tuning changes):

| Method, all seasons | FAR official | FAR override-masked | FAR 60m washout |
|---|---:|---:|---:|
| M2 τ=3.5 | 12.90% (403/3124) | 12.67% (395/3117) | 12.59% (385/3057) |
| M2 τ=4.0 | 2.56% (80/3124) | 2.31% (72/3117) | 2.06% (63/3057) |
| M6 τ=4.0 | 30.35% (948/3124) | 30.16% (940/3117) | 30.29% (926/3057) |

These sensitivity values don't rescue the diagnosis but demonstrate dependence of FAR on window definitions. Clarify “normal” vs “unlabeled/pre/post fault”; evaluate baseline-only days separately.

### H. P1-06 — pointwise evidence is missing decisions

File `research/runs/rbc_nesbitt_independent_pointwise_predictions.csv` has 3744 rows but only z-scores, `domain_status`, basic metadata, and `ground_truth_fault`. It **does not** include threshold-specific `alarm` flags, `eligibility` flags, `pre_existing_alarm` flags, or onset markers. Thus the evidence is less directly auditable than promised in user requirements; add machine traces for **every chosen configuration**.

### I. P1-07 — correct framing and next scientific steps

- Five holdout injections is a small, same-building, BAS-override-dominated cohort. R.4 is a negative external-in-time/season validation of the local models, **not interbuilding transfer of frozen CSIRO weights**.
- Winter zero FAR under DomainGuard with **0% normal/fault coverage** means abstention, not successfully diagnosing winter equipment.
- `PRE_REGISTERED_INDEPENDENT_VALIDATION` is asserted inside files created with the package, but a pre-data-access immutable timestamp/hash is not shown. File split disjointness is necessary but does not prove blindness.
- Do **not** tune on these five now-opened holdout faults. Reclassify as TEST-EXPOSED after this audit. Preserve all negative outcomes. Future prospective holdout must be fixed by an external immutable commitment **before** scanning labels or residuals.
- Focus future work on provenance, direct actuator command vs true feedback, seasonal normal data, operational false-alarm burden and external buildings. Do not start Active Probing or complex ML solely to repair a disappointing result.

## Acceptance decision

- ZIP integrity: PASS
- Standalone tests: PASS
- Numeric rerun: PASS
- Evidence/report consistency: **FAIL P0**
- Valid event-level detection timing: **FAIL P0**
- Frozen model provenance: **FAIL P0**
- Reliable low-FAR FDD on new holdout: **NOT DEMONSTRATED**
- Product integration: **STOP**

A small correctness repair is justified, but avoid yet another cycle of tuning the same benchmark. Preserve and publish the negative result, correct the event bookkeeping/report text, then invest effort in a new physically-grounded dataset/protocol.

### Original authoritative source

Ghalamsiah et al., *Scientific Data* 13, 15 (2026), https://doi.org/10.1038/s41597-025-06179-y ; downloaded attachment `data/raw/rbc_nesbitt/00_explanations.pdf` (4 pages), especially Table 2 with injection methods and times.
