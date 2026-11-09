# STAGE 6 — ОТЧЁТ О ТЕСТИРОВАНИИ И ВОСПРОИЗВОДИМОСТИ (GATE 6)

- **Дата проведения:** 2026-11-03
- **Окружение:** Python 3.11.6, Pytest 8.3.4, Node v20+, Vite 5.4.21, Playwright 1.58.0
- **Итоговый результат:** **71/71 Pytest PASS (100%), Frontend Build PASS (0 type errors), 3 E2E Playwright Screenshots PASS**

---

## 1. Сводный протокол запуска автоматических тестов (Pytest)

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
collected 71 items

backend\tests\test_adaptation_api.py .....                               [  7%]
backend\tests\test_decision_layer.py ........                            [ 18%]
backend\tests\test_diagnostics.py .......                                [ 28%]
backend\tests\test_health.py .                                           [ 29%]
backend\tests\test_import.py ....                                        [ 35%]
backend\tests\test_ml.py .......                                         [ 45%]
backend\tests\test_physical_refutation_regression.py ......              [ 53%]
backend\tests\test_quality_and_rules.py .                                [ 54%]
backend\tests\test_recommendations.py .......                            [ 64%]
backend\tests\test_selective_metrics.py ..                               [ 67%]
backend\tests\test_sensor_profiles.py ...                                [ 71%]
backend\tests\test_stage5_experiment_hygiene.py ....                     [ 77%]
backend\tests\test_stage6_mapping.py ....                                [ 83%]
backend\tests\test_stage6_negative_controls.py ......                    [ 91%]
backend\tests\test_stage6_splits.py .....                                [ 98%]
backend\tests\test_telemetry.py .                                        [100%]

============================= 71 passed in 8.77s ==============================
```

---

## 2. Структура новых тестовых наборов Stage 6

### А. Модуль физического маппинга и аудита (`backend/tests/test_stage6_mapping.py` — 4 теста)
1. `test_temperature_unit_conversions_deterministic`: точный детерминированный пересчет °F в °C.
2. `test_csiro_raw_data_integrity`: проверка целостности сырых данных `csiro_ahu9.parquet` и подтверждение выявленного аудитом равенства `AHU9ahuMaTemp == AHU9ahuSaTemp`.
3. `test_csiro_fault_experiments_structure`: валидация журнала инъекций неисправностей (198 экспериментов для AHU9).
4. `test_reproduced_manifest_exists_and_valid`: машинный манифест `stage6_zero_shot_reproduction.json` существует и содержит воспроизведенные числа Stage 5.

### Б. Модуль изоляции сплитов и гигиены данных (`backend/tests/test_stage6_splits.py` — 5 тестов)
1. `test_temporal_split_no_overlap`: нулевое пересечение индексов Train, Val и Test.
2. `test_temporal_split_strictly_chronological`: строгое соблюдение хронологии $\max(\text{Train}) < \min(\text{Val}) < \min(\text{Test})$.
3. `test_no_fault_contamination_in_train_and_val`: нулевое загрязнение обучающего и валидационного пула известными окнами поломок и 60-минутным защитным интервалом (embargo).
4. `test_feature_sanitization_and_no_target_leakage`: невозможность использовать $SA\_TEMP$ или метки дефектов в качестве входов модели инференса.
5. `test_physical_mixed_air_estimation`: корректность термодинамической оценки смеси $\hat{T}_{ma}$ между границами $OA$ и $RA$.

### В. Отрицательные проверки и негативный контроль (`backend/tests/test_stage6_negative_controls.py` — 6 тестов)
1. `test_source_model_immutability`: строгая проверка неизменности SHA-256 хэша исходной модели `models/vs-sa-temp-v2.joblib`.
2. `test_missing_essential_feature_raises`: удаление обязательного признака вызывает `ValueError`, предотвращая неявное заполнение нулями.
3. `test_empty_or_zero_division_handled_cleanly`: пустые массивы и нулевая дисперсия возвращают явный `None`, исключая `ZeroDivisionError`.
4. `test_unfitted_model_inference_guard`: попытка вызова `predict()` на необученном калибраторе вызывает `RuntimeError`.
5. `test_fault_contamination_injection_detected`: синтетическое добавление точки поломки в нормальный Train немедленно маркируется маской embargo.
6. `test_temporal_split_chronological_integrity`: инвертированный порядок дат вызывает ошибку инициализации сплиттера.

### Г. Интеграционное тестирование REST API (`backend/tests/test_adaptation_api.py` — 5 тестов)
1. `test_get_adaptation_datasets`: эндпоинт `/api/adaptation/datasets` возвращает CSIRO AHU9 со статусом `LOCALLY_EVALUATED`.
2. `test_get_adaptation_models`: эндпоинт `/api/adaptation/models` отдает все 6 моделей (Z0, C1, C2, A1, L1, L2).
3. `test_get_adaptation_summary`: эндпоинт `/api/adaptation/summary` отдает снижение MAE на 75.2% и победившую модель C2.
4. `test_get_adaptation_predictions`: эндпоинт `/api/adaptation/predictions` возвращает даунсемплированные точки с фактом, Z0 и адаптированным прогнозом.
5. `test_get_adaptation_runs`: эндпоинт `/api/adaptation/runs` отдает воспроизводимые манифесты запусков.

---

## 3. Проверка клиентской части (Frontend TypeScript Strict Build)

Команда:
```bash
npm --prefix frontend run build
```

Результат:
```text
> buildingpulse-ui@0.1.0 build
> tsc && vite build

vite v5.4.21 building for production...
transforming...
✓ 2077 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                     0.56 kB │ gzip:   0.42 kB
dist/assets/index-DTwrll4s.css     31.54 kB │ gzip:   6.09 kB
dist/assets/index-BgTF40JU.js   1,335.74 kB │ gzip: 428.39 kB
✓ built in 7.30s
```
**0 ошибок компиляции TypeScript, 0 регрессий интерфейса.**

---

## 4. Скриншоты сквозного браузерного тестирования (Playwright E2E)

1. `docs/screenshots/stage6_csiro_before_after.png`: Общий экран подраздела адаптации на странице «Исследования» с метрическими карточками, таблицей стратегий до/после и баннером статуса `LOCALLY_EVALUATED`.
2. `docs/screenshots/stage6_csiro_prediction_chart.png`: Детальный вид интерактивного графика ECharts, отображающего реальный $SA\_TEMP$, расходящийся $Z0$ и точно скорректированный адаптированный прогноз с выделенными окнами экспериментов.
3. `docs/screenshots/stage6_csiro_guard.png`: Визуализация работы защитного барьера Domain Guard при переключении на исходную невалидированную модель LBNL ($Z0$, статус `OUT_OF_DOMAIN_UNVALIDATED`).
