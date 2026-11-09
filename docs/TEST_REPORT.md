# TEST REPORT — Полный отчет о тестировании BuildingPulse AI (Stage 8B & RBC-Nesbitt)

- **Дата актуализации:** 2026-11-04
- **Версия системы:** `v0.7.1-stage7.1` (Production Core заморожен; Stage 8B-R и RBC-Nesbitt валидированы в исследовательских пакетах)
- **Окружение:** Python 3.11.6, Pytest 8.3.4, Node v20+, Vite 5.4.21, Playwright 1.58.0
- **Итоговый результат:** **103/103 Pytest PASS (100%), Frontend Strict TypeScript Build PASS (0 type errors)**

---

## 1. Автоматические модульные и интеграционные тесты (Pytest)

Команда запуска:
```bash
pytest backend/tests
```

Вывод консоли (stdout):
```text
============================= test session starts =============================
platform win32 -- Python 3.11.6, pytest-8.3.4, pluggy-1.6.0
rootdir: C:\Users\Nikita\Desktop\BuildingPulseAi\backend
configfile: pyproject.toml
plugins: anyio-4.6.2.post1, Faker-36.1.1, asyncio-1.1.0, cov-6.0.0
asyncio: mode=Mode.STRICT, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 103 items

backend\tests\test_adaptation_api.py .....                               [  4%]
backend\tests\test_decision_layer.py ........                            [ 12%]
backend\tests\test_diagnostics.py .......                                [ 19%]
backend\tests\test_health.py .                                           [ 20%]
backend\tests\test_import.py ....                                        [ 24%]
backend\tests\test_ml.py .......                                         [ 31%]
backend\tests\test_physical_refutation_regression.py ......              [ 36%]
backend\tests\test_quality_and_rules.py .                                [ 37%]
backend\tests\test_recommendations.py .......                            [ 44%]
backend\tests\test_selective_metrics.py ..                               [ 46%]
backend\tests\test_sensor_profiles.py ...                                [ 49%]
backend\tests\test_stage5_experiment_hygiene.py ....                     [ 53%]
backend\tests\test_stage6_mapping.py ....                                [ 57%]
backend\tests\test_stage6_negative_controls.py ......                    [ 63%]
backend\tests\test_stage6_splits.py .....                                [ 67%]
backend\tests\test_stage7_science_regressions.py .........               [ 76%]
backend\tests\test_stage8a_control_aware.py ............                 [ 88%]
backend\tests\test_stage8b_dynamic.py ...........                        [ 99%]
backend\tests\test_telemetry.py .                                        [100%]

============================ 103 passed in 13.74s =============================
```

### Детализация добавленных тестов Stage 8B и RBC-Nesbitt (`backend/tests/test_stage8b_dynamic.py`):
1. `test_dynamic_lags_reset_on_overnight_gap`: верификация разрыва лагов и фильтров при $\Delta t > 120$с (защита от ночной утечки 17:00 $\to$ 09:00).
2. `test_dynamic_lags_reset_on_fan_start`: проверка сброса динамического состояния при переходе вентилятора из OFF в ON.
3. `test_feature_leakage_prohibits_banned_columns`: защита от аппаратного дубликата `MA_TEMP` и утечки текущей команды $u_t$.
4. `test_regime_classification_boundaries`: проверка граничных условий тепловых режимов (Cooling, Economizer, Transition).
5. `test_causal_persistence_filter_with_gap`: верификация сброса K-of-N персистенции при сбое связи / выпадении отсчетов.
6. `test_robust_regime_scaler`: проверка робастного масштабирования невязок по режимам с защитой от нулевой дисперсии.
7. `test_physical_episode_grouping`: консолидация одновременных строк таблицы разметки в единые непрерывные физические эпизоды.
8. `test_ahu10_clean_split_embargo_isolation`: подтверждение исключения аварийных экспериментов и 60-мин эмбарго из Train/Val на AHU-10.
9. `test_stage8b_manifest_integrity`: проверка валидности манифеста v2 (`REFUTED_VALIDATION_OVERFITTING`, `REFUTED_FAR_BUDGET_EXCEEDED`, `M4_U_DYN_EXO_STRICT`).
10. `test_rbc_nesbitt_external_manifest`: проверка внешнего манифеста Nesbitt Hall (540 столбцов, Gate 0 PASSED, M2 Recall 75% при FAR $\le 5\%$, M1 Recall 0%, существование карты каналов).
11. `test_rbc_nesbitt_reconciled_manifest`: проверка манифеста сверки Stage 8B-R (версия 2.0-reconciled, строгие пороги M2 3.5 и M3 4.0, нулевой отклик M1, двойной учёт N=4 и N=3, наличие пошаговых предсказаний на 1 152 точки).
1. `test_dynamic_lags_reset_on_overnight_gap`: верификация разрыва лагов и фильтров при $\Delta t > 120$с (защита от ночной утечки 17:00 $\to$ 09:00).
2. `test_dynamic_lags_reset_on_fan_start`: проверка сброса динамического состояния при переходе вентилятора из OFF в ON.
3. `test_feature_leakage_prohibits_banned_columns`: защита от аппаратного дубликата `MA_TEMP` и утечки текущей команды $u_t$.
4. `test_regime_classification_boundaries`: проверка граничных условий тепловых режимов (Cooling, Economizer, Transition).
5. `test_causal_persistence_filter_with_gap`: верификация сброса K-of-N персистенции при сбое связи / выпадении отсчетов.
6. `test_robust_regime_scaler`: проверка робастного масштабирования невязок по режимам с защитой от нулевой дисперсии.
7. `test_physical_episode_grouping`: консолидация одновременных строк таблицы разметки в единые непрерывные физические эпизоды.
8. `test_ahu10_clean_split_embargo_isolation`: подтверждение исключения аварийных экспериментов и 60-мин эмбарго из Train/Val на AHU-10.
9. `test_stage8b_manifest_integrity`: проверка валидности JSON-манифеста `stage8b_dynamic_results.json` и подтверждения гипотез.
backend\tests\test_stage6_splits.py .....                                [ 87%]
backend\tests\test_stage7_science_regressions.py .........               [ 98%]
backend\tests\test_telemetry.py .                                        [100%]

============================= 80 passed in 7.02s ==============================
```

### Детализация добавленных тестов Stage 7.1:

В `backend/tests/test_stage7_science_regressions.py` добавлены 4 новых регрессионных теста:
1. `test_csiro_model_loading_without_transformer_error`: подтверждает загрузку моделей адаптации CSIRO без трансформера LBNL (`transformer is None`, 0 ошибок `FileNotFoundError`).
2. `test_csiro_model_incompatible_scenario_blocks_inference`: подтверждает, что при попытке инференса модели CSIRO на LBNL возвращается исключение с кодом `INCOMPATIBLE_DATASET_DOMAIN`.
3. `test_csiro_model_compatible_scenario_executes`: подтверждает исполнение инференса модели C2 на натурном датасете CSIRO AHU9 (7 666 строк) с расчетом невязок и порогов.
4. `test_ml_models_api_lists_models_with_domain_flags`: проверяет флаги `target_domain`, `source_kind`, `is_adaptation` в контракте `/api/ml/models`.

### Детализация тестовых наборов Stage 7:

1. `backend/tests/test_stage7_science_regressions.py` (5 тестов, Gate 0 & Gate 6):
   - `test_c2_model_coefficients_and_hand_parity`: подтверждение, что фактические коэффициенты в joblib и metadata равны `slope = 2.013821`, `intercept = -10.110449`, а расхождение с ручным аналитическим расчетом на 5 точках строго равно $0.00 \cdot 10^{-16}$.
   - `test_c1_model_fitted_bias`: верификация поправки постоянного сдвига $+4.593268^\circ\text{C}$ и совпадение прогноза с аддитивным сдвигом.
   - `test_bias_convention_and_mae_reduction`: проверка соблюдения конвенции невязки ($\text{residual} = y_{\text{true}} - y_{\text{pred}}$) и формулы процентного снижения ошибки MAE (75.17%).
   - `test_reproduction_manifest_validity`: валидация манифеста репродукции, подтверждающая строгие статусы гипотез `H4a: SUPPORTED_ON_THIS_TEST`, `H4b: REFUTED_ON_TEST`, `H4c: PARTIALLY_SUPPORTED_WITH_LOW_SENSITIVITY`.
   - `test_safe_run_id_path_traversal`: проверка отклонения атак Path Traversal в эндпоинте `/api/adaptation/runs/{run_id}` с возвратом HTTP 400/404.

2. Ранее созданные тестовые сьюты (71 тест Stages 1–6):
   - `test_adaptation_api.py` (5 тестов) — 100% PASS;
   - `test_decision_layer.py` (8 тестов) — 100% PASS;
   - `test_diagnostics.py` (7 тестов) — 100% PASS;
   - `test_health.py` (1 тест) — 100% PASS;
   - `test_import.py` (4 теста) — 100% PASS;
   - `test_ml.py` (7 тестов) — 100% PASS;
   - `test_physical_refutation_regression.py` (6 тестов) — 100% PASS;
   - `test_quality_and_rules.py` (1 тест) — 100% PASS;
   - `test_recommendations.py` (7 тестов) — 100% PASS;
   - `test_selective_metrics.py` (2 теста) — 100% PASS;
   - `test_sensor_profiles.py` (3 теста) — 100% PASS;
   - `test_stage5_experiment_hygiene.py` (4 теста) — 100% PASS;
   - `test_stage6_mapping.py` (4 теста) — 100% PASS;
   - `test_stage6_negative_controls.py` (6 тестов) — 100% PASS;
   - `test_stage6_splits.py` (5 тестов) — 100% PASS;
   - `test_telemetry.py` (1 тест) — 100% PASS.

---

## 2. Сборка и Typecheck фронтенда (TypeScript strict)

Команда:
```bash
npm --prefix frontend run build
```
Вывод:
```text
> buildingpulse-ui@0.1.0 build
> tsc && vite build

vite v5.4.21 building for production...
transforming...
✓ 2077 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                     0.56 kB │ gzip:   0.42 kB
dist/assets/index-CU_geHeF.css     31.78 kB │ gzip:   6.12 kB
dist/assets/index-Bvuw5fnh.js   1,337.39 kB │ gzip: 429.26 kB
✓ built in 17.39s
```
**Результат:** 0 ошибок типов TypeScript, строгий режим (`strict: true`).

---

## 3. Сквозная репродукция научных пайплайнов

Команда:
```bash
python scripts/reproduce_research.py
```
Вывод:
```text
==================================================================
 BUILDINGPULSE AI — REPRODUCIBLE RESEARCH SUITE (STAGES 3-7)      
==================================================================
[SUCCESS] CSIRO AHU9 Field Adaptation Evaluation (Gate 0 & H4)
[SUCCESS] Sensor Recommendation Engine Evaluation (H3)
[SUCCESS] Decision Layer & Observability Profiles Evaluation (H1 & H2)
------------------------------------------------------------------
ALL RESEARCH PIPELINES REPRODUCED SUCCESSFULLY. [PASS]
------------------------------------------------------------------
```

---

## 4. Скриншоты пользовательского интерфейса (Playwright E2E)

Сняты 6 актуальных скриншотов высокого разрешения:
- `docs/screenshots/stage7_monitoring_ahu.png` — Экран оперативного мониторинга, мнемосхема AHU, плеер и качество данных;
- `docs/screenshots/stage7_diagnostics_fault.png` — Экран диагностики, невязка виртуального датчика, карточка селективного решения;
- `docs/screenshots/stage7_research_overview.png` — Главная страница хаба «Исследования» с обзором H1–H4;
- `docs/screenshots/stage7_research_csiro_prediction.png` — График телеметрии CSIRO с разрывами ночных часов и оранжевыми зонами инъекций дефектов;
- `docs/screenshots/stage7_research_csiro_table.png` — Сводная таблица 7 стратегий адаптации с честными статусами H4a, H4b, H4c;
- `docs/screenshots/stage7_research_recommender.png` — Экран сервиса рекомендаций дооснащения датчиками.

**Итоговый статус тестирования: 100% PASS.**
