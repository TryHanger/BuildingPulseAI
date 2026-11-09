# NEXT STEPS — Очередь задач BuildingPulse AI

## Статус выполнения Этапа 8C (Release Candidate на реальных данных CSIRO AHU-10) — Завершено
- [x] **Gate A: Комплектность и техническая воспроизводимость (PASS)**
  - [x] Исходная телеметрия `data/raw/csiro_ahu10.parquet` (7.88 MB, 422,169 строк, SHA-256: `f789...`) включена.
  - [x] Реестр экспериментов `data/raw/csiro_fault_experiments.parquet` (103 испытания AHU-10, SHA-256: `b7eb...`) включён.
  - [x] Исторические зависимости Stage 8B (`rbc_nesbitt_reconciled_manifest.json`, `STAGE8B_R2_EVIDENCE_REPORT.md`, 23 CSV) включены под оригинальными путями.
  - [x] Pinned окружение зафиксировано в `requirements.txt`.
  - [x] Оркестратор `run_csiro_validation.py` и модуль `scripts/evaluate_csiro_ahu10_validation.py` компилируются (`py_compile`) и исполняются без ошибок.
- [x] **Gate B: Целостность исходной разметки и времён (PASS)**
  - [x] Единая 5-минутная сетка: ровно 3199 точек на 33 дня, 0 дубликатов, 0 NaT.
  - [x] Глобальная маска 103 экспериментов AHU-10 с 30-минутным washout устранила наложение событий 224, 225, 226 на 2013-10-31.
  - [x] Контрольный срез: 873 чистые точки обучения, 1861 нормальная рабочая точка (485 зима, 485 лето, 485 весна, 406 дни аварий).
- [x] **Gate C: Единый канонический контракт научных метрик (PASS)**
  - [x] Единая функция расчёта; 100% числовой паритет между JSON, CSV и Markdown.
  - [x] Первичная метрика `new_onset_observable_7` на 7 наблюдаемых событиях: M1 $\tau=3$: **4/7 (57.1%)**, M2 $\tau=4$: **2/7 (28.6%)**, M3 $\tau=3$: **4/7 (57.1%)**.
  - [x] Выделены 3 left-censored события (ID 176, 194, 322); обобщённая метрика `post_observation_alarm_all_10` (5/10, 3/10, 5/10).
  - [x] Точные значения FAR: M2 $\tau=4$: **750/1861 (40.30%)**, лето: **220/485 (45.36%)**; M1 $\tau=3$: **979/1861 (52.61%)**, лето: **480/485 (98.97%)**.
  - [x] Zero-Shot перенос переведён в статус `NOT_COMPARABLE` (`INVALID_SEMANTIC_CONTROL`).
- [x] **Gate D: Прозрачное происхождение моделей, σ и порогов (PASS)**
  - [x] Пороги $\tau=3.00$ и $\tau=4.00$ зафиксированы как константы; приведены фактические диагностические процентили (Thermal p99=4.668, p99.5=5.419; Control p99=3.974, p99.5=4.073).
  - [x] Формула стандартизации $\sigma = \text{std}(\|\text{residual}\|)$ явно документирована.
  - [x] Оформлен `research/protocols/SCIENTIFIC_CORRIGENDUM.md`.
- [x] **Gate E: Независимые тесты на регрессии и утечки (PASS)**
  - [x] 10 специальных алгоритмических проверок в `tests/test_csiro_ahu10_validation.py`.
  - [x] Полный сьют `pytest tests -v` — **43/43 PASS (100%)**.
- [x] **Gate F: Финальный релиз и остановка (PASS)**
  - [x] Сформирован `BUILDINGPULSE_AUDIT_STAGE_8C_RELEASE_CANDIDATE.zip` (10,090,597 байт, 9.62 MB, SHA-256: `a0a5ee00d7ba761215e4def309bb0b30416b28667332124c12d8be0a8844ffb0`).
  - [x] Изолированная верификация в чистом каталоге: 100% совпадение SHA-256 (67 файлов), 43/43 теста PASS, fresh run код 0, 100% numerical parity.
- [ ] **Следующий этап: Исследование физической наблюдаемости и минимальной различимости неисправностей (Value of Information)**
  - [x] Подготовлен проект исследования `research/NEXT_SCIENTIFIC_DIRECTION.md` (гипотезы H1–H3, матрица различимости, criteria STOP/GO).
  - [ ] **СТОП:** Ожидание явного подтверждения владельца перед реализацией.

---

## Статус выполнения Этапа 1 (Фундамент и паспорт данных) — Завершено
- [x] M0: Инвентаризация инструментов и окружения
- [x] M1: Каркас FastAPI + React + PostgreSQL/SQLite
- [x] M2: Данные, словарь канонических каналов и манифест
- [x] M3: API-контракт и Parquet-хранилище с Min-Max Downsampling
- [x] M4: Frontend Dashboard (мнемосхема AHU, ECharts, плеер)
- [x] M5: Качество данных и базовый rule baseline
- [x] M6: Тестирование, приёмка и документация

---

## Статус выполнения Этапа 2 (Виртуальный датчик LightGBM и зимний эксперимент) — Завершено
- [x] Аудит и устранение дефектов этапа 1 (`docs/STAGE2_BASELINE_AUDIT.md`)
- [x] Инженерия данных LBNL и физический аудит (4 зимних сценария по 14 дней)
- [x] Предварительная фиксация протокола (`research/protocols/virtual_sensor_v1.md`)
- [x] Реализация ML Pipeline и обучение моделей `vs-sa-temp-v1` (LightGBM) и `vs-sa-temp-baseline-ridge` (Ridge)
- [x] REST API расширение (`/api/ml/*`)
- [x] Интеграция в пользовательский интерфейс мониторинга
- [x] Научный отчет `research/reports/VIRTUAL_SENSOR_V1_REPORT.md`

---

## Статус выполнения Этапа 3 (Многосезонная надежность, локализация семейств дефектов и экран «Диагностика») — Завершено
- [x] **M3.0: Аудит Stage 2 и устранение рисков (Gate 0)**
  - [x] Оформлен `docs/STAGE3_BASELINE_AUDIT.md`.
  - [x] Реализован UI Domain Guard: блокировка выдачи невязок на `SYNTHETIC_DEMO` за валидированные ML-тревоги.
  - [x] Исправлена версия интерфейса в шапке на `v0.3-stage3`.
  - [x] Проверена защита от утечки `SA_TEMP`, единицы измерения и физические каналы Basic.
- [x] **M3.1: Многосезонные данные и предрегистрация (Gate 1)**
  - [x] Утвержден научный протокол: `research/protocols/stage3_multiseason_and_fault_baselines.md`.
  - [x] Импортирован полный год нормы `AHU_annual.csv` (525 540 строк, Chicago TMY).
  - [x] Импортированы 12 сценариев неисправностей LBNL разных интенсивностей.
  - [x] Реализован `MultiSeasonTemporalSplit` (4 сезона по 14 дней: Train 9d, Val 2d, Held-out Test 3d).
  - [x] Обучен многосезонный LightGBM `vs-sa-temp-v2` (MAE = 0.0387 °C, RMSE = 0.1739 °C, $R^2 = 0.7534$, 0 ложных тревог).
  - [x] Обучен контрольный Ridge `vs-sa-temp-baseline-ridge-v2` (MAE = 0.1083 °C).
  - [x] Оформлен научный отчет `research/reports/STAGE3_MULTI_SEASON_REPORT.md` и манифест `research/runs/stage3_multiseason_evaluation.json`.
- [x] **M3.2: Первичная классификация семейств дефектов (Gate 2)**
  - [x] Разработан модуль извлечения физических признаков `ml/diagnostics/features.py` (Basic-only, каузальные окна 15 мин).
  - [x] Разработан инженерный бейзлайн правил `RuleDiagnosticEngine` с честным выходом в `UNRESOLVED`.
  - [x] Разработан и обучен классификатор `FaultFamilyClassifier` (LightGBM и Ridge).
  - [x] Оценка по схеме Scenario-Level Split на независимых уровнях дефектов:
    - Rule-based Baseline: Macro F1 = 0.1197 (30.2% UNRESOLVED).
    - Ridge Baseline: Macro F1 = 0.3975.
    - LightGBM Classifier: Macro F1 = 0.5367 (Cooling Valve Stuck F1 = 0.8398).
  - [x] Оформлен научный отчет `research/reports/STAGE3_FAULT_FAMILY_BASELINES.md`.
- [x] **M3.3: Реальная страница «Диагностика» и интеграция (Gate 3)**
  - [x] Разработаны эндпоинты `/api/diagnostics/summary`, `/api/diagnostics/events`, `/api/diagnostics/run-rules`.
  - [x] Реализована интерактивная страница `frontend/src/pages/DiagnosticsPage.tsx`.
  - [x] Реализовано переключение вкладок «Мониторинг AHU» ↔ «Диагностика» в шапке.
  - [x] Внедрена изолированная панель Ground Truth для исследовательской оценки.
  - [x] Успешно пройдены 18 тестов Pytest (`backend/tests/test_diagnostics.py`).
  - [x] Сборка `npm run build` выполнена без ошибок типов.
  - [x] Сняты 4 скриншота Playwright (`docs/screenshots/stage3_*`).

---

## Статус выполнения Этапа 4 (Formal Evidence-Aware Decision Layer & Observability Analysis) — Завершено
- [x] **M4.0: Научный аудит и фиксация базовой линии (Gate 0)**
  - [x] Оформлен `docs/STAGE4_BASELINE_AUDIT.md`.
  - [x] Воспроизведены 18/18 тестов Pytest и сборка фронтенда.
  - [x] Подтверждена репродуцируемость моделей v2 и Macro F1 Stage 3.
  - [x] Зафиксированы SHA-256 хэши исходных артефактов.
- [x] **M4.1: Предрегистрация протокола и API селективных метрик (Gate 1)**
  - [x] Утвержден `research/protocols/stage4_evidence_observability_protocol.md`.
  - [x] Утверждена спецификация `research/protocols/stage4_decision_layer_spec.md`.
  - [x] Разработан модуль `ml/diagnostics/metrics_selective.py`.
  - [x] Пройден unit-тест `backend/tests/test_selective_metrics.py` (контрольная таблица Приложения B).
- [x] **M4.2: Библиотека свидетельств и Formal Decision Layer (Gate 2)**
  - [x] Разработан модуль `ml/diagnostics/evidence.py`.
  - [x] Реализованы baseline-стратегии B1 (Confidence-only) и B2 (Margin/Entropy) в `ml/diagnostics/confidence_baselines.py`.
  - [x] Разработан `EvidenceAwareDecisionLayer` в `ml/diagnostics/decision_layer.py`.
  - [x] Пройдены 7 тестов в `backend/tests/test_decision_layer.py`.
- [x] **M4.3: Профили наблюдаемости датчиков (Gate 3)**
  - [x] Создан `SensorProfileRegistry` (BASIC, BASIC_PLUS_VALVE, BASIC_PLUS_DAMPER, BASIC_PLUS_BOTH, FULL).
  - [x] Реализована функция `extract_profile_diagnostic_features` со строгой изоляцией каналов.
  - [x] Пройден регрессионный тест скрытых каналов `backend/tests/test_sensor_profiles.py`.
- [x] **M4.4: Воспроизводимые научные эксперименты E4.1 и E4.2 (Gate 4)**
  - [x] Разработан и запущен раннер `ml/diagnostics/evaluate_stage4.py`.
  - [x] E4.1: Сравнение Risk–Coverage подтвердило гипотезу H1 (снижение риска с 0.556 до 0.294 при cov=0.40).
  - [x] E4.2: Сравнение профилей подтвердило гипотезу H2 (ценность обратной связи клапана $\Delta \text{F1} = +15.3\%$).
  - [x] Сохранены манифесты `research/runs/stage4_*.json` и графики `research/figures/*.png`.
  - [x] Оформлены отчеты `research/reports/STAGE4_DECISION_LAYER_REPORT.md` и `STAGE4_OBSERVABILITY_REPORT.md`.
- [x] **M4.5: Серверная и клиентская интеграция (Gate 5)**
  - [x] Добавлены эндпоинты `/api/diagnostics/profiles` и `/api/experiments/stage4/summary`.
  - [x] Расширен эндпоинт `/api/diagnostics/summary` параметром `profile_id`.
  - [x] Обновлена страница `frontend/src/pages/DiagnosticsPage.tsx` (селектор 5 профилей, карточки решений, свидетельства, экспериментальные таблицы).
- [x] **M4.6: Тестирование, скриншоты и финальная приёмка (Gate 6)**
  - [x] Pytest: 33 из 33 тестов PASS.
  - [x] TypeScript Strict Build: успешен, 0 ошибок типов.
  - [x] Playwright E2E: сняты 5 скриншотов `docs/screenshots/stage4_*`.
  - [x] Оформлена матрица приёмки `docs/STAGE4_ACCEPTANCE.md`.

---

## Статус выполнения Этапа 5 (Sensor Recommendation Engine, H3 Experiment, CSIRO Real Building & Research Hub) — Завершено
- [x] **M5.A: Научный аудит и устранение физических дефектов Stage 4 (Gate A)**
  - [x] Оформлен `docs/STAGE5_STAGE4_SCIENCE_AUDIT.md`.
  - [x] Устранено ложное опровержение заклинивания клапана: введена проверка динамического возбуждения ($\Delta \text{cmd} \ge 0.15$). При статической команде возвращается `INSUFFICIENT_ACTUATOR_EXCITATION`.
  - [x] Разделены `VALVE_STUCK` и `VALVE_LEAKAGE` (утечка не опровергается положением привода).
  - [x] Обеспечена симметрия классификаторов и профилей при сравнении H1 и H2.
  - [x] Пройдены 6 тестов регрессии `backend/tests/test_physical_refutation_regression.py`.
- [x] **M5.B: Предрегистрация протокола H3 и барьеров утечки (Gate B)**
  - [x] Утвержден протокол: `research/protocols/stage5_sensor_recommendation_protocol.md`.
  - [x] Зафиксированы: бюджет 1 канал, пространство кандидатов $\{CHWC\_VLV, OA\_DMPR\}$, критерий максимизации прироста информационной ценности на валидации $V_j(c)$, негативный контроль, условия отказа (`OUT_OF_DOMAIN`, `PROFILES_EXHAUSTED`, `INSUFFICIENT_EXCITATION`).
- [x] **M5.C: Реализация Sensor Recommendation Engine и API (Gate C)**
  - [x] Разработан модуль `ml/diagnostics/recommender.py` (`SensorRecommendationService`).
  - [x] Созданы Pydantic схемы `backend/app/schemas/recommendations.py`.
  - [x] Реализованы эндпоинты `/api/diagnostics/recommendable-channels`, `/api/sensors/recommend`, `/api/experiments/stage5/*`.
  - [x] Пройдены unit-тесты `backend/tests/test_recommendations.py`.
- [x] **M5.D: Эксперимент H3 на независимых тестовых сценариях (Gate D)**
  - [x] Разработан и исполнен раннер `ml/diagnostics/evaluate_stage5_recommendations.py`.
  - [x] Проведено сравнение стратегий: Baseline (Basic 0.5196), Random ($0.5931 \pm 0.0015$), Fixed Heuristic (0.6722), Validation-Based Recommender (0.6722, +15.26 pp к базовому, +7.91 pp к Random, $p < 0.05$), Oracle (0.6969).
  - [x] Сохранены манифест `research/runs/stage5_recommendation_eval.json` и графики `research/figures/stage5_*`.
  - [x] Оформлен отчет `research/reports/STAGE5_RECOMMENDATION_REPORT.md`.
- [x] **M5.E: Подключение совместимой полевой телеметрии реального здания CSIRO AHU9 (Gate E)**
  - [x] Скачана и сохранена полевая телеметрия с экспериментами по внесению неисправностей `data/raw/csiro_ahu9.parquet`.
  - [x] Оформлен документ совместимости `docs/EXTERNAL_DATASET_COMPATIBILITY.md`.
  - [x] Реализован импортер `scripts/import_csiro.py` (сценарий `sc_89e2c6028b4f` на 7 666 минутных строк).
  - [x] Разработан и исполнен раннер `ml/diagnostics/evaluate_csiro_transfer.py`: зафиксирован катастрофический domain shift нулевого переноса (MAE = 4.47 °C vs 0.039 °C, 98.6% ложных тревог).
  - [x] Подтверждена надежность барьера `Domain Guard` (`OUT_OF_DOMAIN_UNVALIDATED`).
  - [x] Сохранены манифест `research/runs/stage5_external_validation.json` и отчет `research/reports/STAGE5_EXTERNAL_VALIDATION_REPORT.md`.
- [x] **M5.F: Реализация отдельной страницы «Исследования» и клиентская интеграция (Gate F)**
  - [x] Разработана страница `frontend/src/pages/ResearchPage.tsx` с 5 научными вкладками.
  - [x] В шапку добавлена навигация по трем разделам: «Мониторинг AHU», «Диагностика», «Исследования».
  - [x] На странице «Диагностика» внедрена интерактивная кнопка «Какое измерение поможет?» с inline-вызовом рекомендатора и быстрым переходом на профиль `BASIC_PLUS_VALVE`.
  - [x] Сборка `npm run build` выполнена успешно (0 ошибок TypeScript).
- [x] **M5.G: Комплексное тестирование, E2E скриншоты и финальная приёмка (Gate G)**
  - [x] Разработаны тесты гигиены экспериментов `backend/tests/test_stage5_experiment_hygiene.py`.
  - [x] Pytest сьют: 51 из 51 тестов пройдены успешно (100% PASS).
  - [x] Playwright E2E: сняты 5 скриншотов `docs/screenshots/stage5_*`.
  - [x] Оформлена матрица приёмки `docs/STAGE5_ACCEPTANCE.md`.

---

## Статус выполнения Этапа 6 (Адаптация к реальному зданию CSIRO AHU9: Gates 0–7) — Завершено
- [x] **Gate 0: Физический аудит датчиков и репродукция базового эксперимента**
  - [x] Обнаружен критический аппаратный дубликат: `AHU9ahuMaTemp` $\equiv$ `AHU9ahuSaTemp` (100% строк идентичны в сыром BMS).
  - [x] Разработана физическая оценка температуры смеси $\hat{T}_{ma} = \alpha T_{oa} + (1-\alpha) T_{ra}$.
  - [x] Воспроизведены baseline-метрики Stage 5 zero-shot (MAE = 4.4666 °C, $R^2 = -1.9244$, breach rate = 98.55%).
  - [x] Оформлены `docs/STAGE6_BASELINE_AUDIT.md`, `docs/STAGE6_CSIRO_SIGNAL_MAPPING.md`, манифест `research/runs/stage6_zero_shot_reproduction.json`.
  - [x] Пройден тест маппинга `backend/tests/test_stage6_mapping.py` (4/4 PASS).
- [x] **Gate 1: Предрегистрация протокола и строгое хронологическое разбиение**
  - [x] Зафиксирован протокол `research/protocols/stage6_csiro_adaptation_protocol.md`.
  - [x] Сформирован манифест разбиения `research/splits/stage6_csiro_split.json`.
  - [x] Реализовано строгое хронологическое разбиение Train/Val/Held-out Test с буфером 60 мин:
    - Train Local (норма): 2013-10-28..2013-11-01 (1 588 точек).
    - Val Local (норма): 2013-11-04..2013-11-06 (726 точек).
    - Held-Out Test: 2013-11-07..2013-11-12 (1 074 нормы, 846 дефектов, 34 инцидента).
  - [x] Пройден тест разбиения `backend/tests/test_stage6_splits.py` (5/5 PASS).
- [x] **Gate 2: Реализация методов локальной адаптации и обучение**
  - [x] Реализованы калибраторы Z0, C1, C2, A1, L1, L2, B0 в `ml/adaptation/calibrators.py`.
  - [x] Обучены модели строго на Train Local; калиброваны $3\sigma$ пороги строго на Val Local.
  - [x] Сохранены модели `models/csiro-ahu9-*_v1.joblib` и метаданные.
  - [x] Оформлены `docs/STAGE6_MODEL_CARD.md` и манифест `research/runs/stage6_csiro_adaptation_train.json`.
- [x] **Gate 3: Офлайн-эксперимент на Held-Out Test выборке**
  - [x] Запущен раннер `ml/adaptation/evaluate_csiro_adaptation.py`.
  - [x] Получены результаты на 1 074 точках тестовой нормы:
    - Z0 Zero-Shot: MAE = 4.4552 °C, False Alarms = 100.0%.
    - C1 Constant Bias: MAE = 1.2037 °C (-73.0%), False Alarms = 2.5%.
    - C2 Affine: MAE = 1.1062 °C (-75.2%), False Alarms = 2.8%.
    - A1 Residual Ridge: MAE = 1.8323 °C (-58.9%).
    - L1 Local Ridge: MAE = 2.9792 °C (-33.1%).
    - L2 Local LightGBM: MAE = 1.2703 °C (-71.5%), False Alarms = 4.4%.
  - [x] Подтверждены научные гипотезы: H4a (ПОДТВЕРЖДЕНА, $\Delta\text{MAE} > 70\%$), H4b (ЧАСТИЧНО ПОДТВЕРЖДЕНА), H4c (ПОДТВЕРЖДЕНА С ЧЕСТНЫМ КОМПРОМИССОМ).
  - [x] Сгенерированы графики `research/figures/stage6_*.png` и отчет `research/reports/STAGE6_CSIRO_ADAPTATION_REPORT.md`.
- [x] **Gate 4: REST API интеграция адаптации**
  - [x] Созданы схемы `backend/app/schemas/adaptation.py`, сервис `backend/app/services/adaptation_service.py`.
  - [x] Реализован роутер `/api/adaptation/{datasets, models, summary, runs/{run_id}, predictions}`.
  - [x] Пройден тест API `backend/tests/test_adaptation_api.py` (5/5 PASS).
- [x] **Gate 5: Интерактивный UI хаба «Исследования»**
  - [x] Добавлены типы в `frontend/src/types/api.ts` и методы API в `frontend/src/api/client.ts`.
  - [x] Обновлена вкладка реального здания CSIRO на `frontend/src/pages/ResearchPage.tsx`:
    - Селектор 6 моделей адаптации;
    - 4 ключевые KPI карточки;
    - Интерактивный ECharts график с фактом, Z0 и адаптированным прогнозом + подсветкой окон дефектов;
    - Сводная таблица 7 стратегий и статусов H4a/H4b/H4c;
    - Таблица чувствительности к дефектам и ложных тревог (FDD Sensitivity);
    - Карточка ограничений и статуса Domain Guard (`LOCALLY_EVALUATED`).
  - [x] Версия фронтенда обновлена до `v0.6-stage6`. TypeScript сборка: 0 ошибок.
  - [x] Сняты Playwright E2E скриншоты: `docs/screenshots/stage6_*.png`.
- [x] **Gate 6: Комплексное тестирование и негативные контроли**
  - [x] Создан сьют негативных контролей `backend/tests/test_stage6_negative_controls.py` (6/6 PASS).
  - [x] Полный Pytest сьют: 71/71 тестов PASS (100%).
  - [x] Оформлены `docs/STAGE6_TEST_REPORT.md` и `docs/STAGE6_ACCEPTANCE.md`.
- [x] **Gate 7: Научная интерпретация и обновление памяти проекта**
  - [x] Оформлен сводный отчет `research/reports/STAGE6_CSIRO_ADAPTATION_REPORT.md`.
  - [x] Обновлены `docs/STATE.md`, `docs/DECISIONS.md`, `docs/NEXT_STEPS.md`, `docs/TEST_REPORT.md`.

---

## Статус выполнения Этапа 7 (Финальная дипломная интеграция, научный аудит и подготовка к защите) — Завершено
- [x] **Gate 0: Независимый научный аудит Stage 6 (Приоритет P0)**
  - [x] Устранен конфликт коэффициентов C2: подтверждена зависимость $y = 2.0138 x - 10.1104$, опечатка $0.582x + 2.459$ исправлена.
  - [x] Проверены знаки bias и конвенция невязки ($\text{residual} = y_{\text{true}} - y_{\text{pred}}$).
  - [x] Пересмотрены статусы гипотез: H4a (SUPPORTED_ON_THIS_TEST), H4b (REFUTED_ON_TEST / NOT_SUPPORTED), H4c (PARTIALLY_SUPPORTED_WITH_LOW_SENSITIVITY).
  - [x] Построена факторная матрица 2×2 (Модель vs Порог).
  - [x] Оформлены `docs/STAGE7_STAGE6_SCIENCE_AUDIT.md`, `research/runs/stage7_stage6_reproduction.json`, `research/reports/STAGE7_STAGE6_CORRECTIONS_ADDENDUM.md`, `backend/tests/test_stage7_science_regressions.py` (5/5 PASS), `docs/STAGE7_MODEL_CARDS.md`.
- [x] **Gate 1: Аудит итогов H1–H3 и единый научный корпус**
  - [x] Сверены метрики H1 (Decision Layer, Risk 29.4% vs 55.6% при cov $\approx 42\%$), H2 (Observability, +15.26 pp F1 от клапана), H3 (Sensor Recommendation, равенство с Fixed, +7.91 pp к Random).
  - [x] Оформлены `research/runs/stage7_final_scientific_summary.json` и `research/reports/STAGE7_FINAL_SCIENTIFIC_SUMMARY.md`.
- [x] **Gate 2: Надежность продукта и данных**
  - [x] Устранена уязвимость Path Traversal в `/api/adaptation/runs/{run_id}` и `/api/adaptation/predictions` с возвратом HTTP 400.
  - [x] Подтверждена защита Domain Guard и целостность контрактов Pydantic v2.
- [x] **Gate 3: UI/UX финальная демонстрационная версия**
  - [x] Устранены ложные ночные диагонали в ECharts: внедрен разрыв серий (`connectNulls: false` + вставка разрывов в нерабочие часы).
  - [x] Наложены подтвержденные зоны инъекций неисправностей (`markArea`).
  - [x] Динамическая подгрузка формул моделей из метаданных.
  - [x] Обновлена версия интерфейса на `v0.7-stage7` на всех трех экранах.
  - [x] Сняты 6 Playwright скриншотов: `docs/screenshots/stage7_*.png`.
- [x] **Gate 4: Развертывание и воспроизводимость на чистой среде**
  - [x] Разработан диагностический скрипт `scripts/verify_environment.py` (100% PASS).
  - [x] Разработан сквозной раннер `scripts/reproduce_research.py` (100% PASS).
  - [x] Документирована причина сбоя Docker (Swarm TLS рассинхрон в Docker Desktop); нативный запуск полностью автономен.
- [x] **Gate 5: Пакет материалов для диплома**
  - [x] `docs/STAGE7_PRODUCT_ARCHITECTURE_REPORT.md` (Технический отчет);
  - [x] `research/reports/STAGE7_FINAL_SCIENTIFIC_REPORT.md` (Итоговый научный отчет);
  - [x] `docs/STAGE7_DEMO_SCRIPT.md` (Поминутный сценарий защиты на 5–7 мин);
  - [x] `docs/STAGE7_THESIS_OUTLINE.md` (Структура текста диплома, доказательные ответы на 10 вопросов комиссии).
- [x] **Gate 6: Комплексное тестирование**
  - [x] Регрессионный сьют Pytest: **76 из 76 тестов PASS (100%)**.
  - [x] Typecheck фронтенда: **0 ошибок TypeScript**.
  - [x] E2E Playwright: 6 скриншотов зафиксированы.
- [x] **Gate 7: Финальная приёмка и рабочая память**
  - [x] Оформлены `docs/STAGE7_ACCEPTANCE.md` (ACCEPTED_WITH_LIMITATIONS) и `docs/STAGE7_HANDOFF.md`.
  - [x] Актуализированы `docs/STATE.md`, `docs/DECISIONS.md`, `docs/NEXT_STEPS.md`, `docs/TEST_REPORT.md`.

---

## Статус выполнения Корректирующей итерации Этапа 7.1 — Завершено
- [x] **Дефект 1: Маршрутизация моделей CSIRO и устранение Transformer file not found**
  - [x] `load_model()` в `VirtualSensorInferenceEngine` загружает адаптационные модели без трансформера LBNL (`transformer = None`).
  - [x] Добавлена eagerly-загрузка датасета `joinedload(Scenario.dataset)` в `load_scenario_data`.
  - [x] Внедрен строгий барьер `Domain Guard`: попытка применить модель CSIRO к несовместимым сценариям LBNL/synthetic блокируется с HTTP 400 (`INCOMPATIBLE_DATASET_DOMAIN`).
  - [x] Для совместимых сценариев CSIRO инференс выполняется штатно с расчетом `MA_TEMP_EST` и невязок.
  - [x] Во фронтенде добавлен `optgroup` в селектор моделей, предупреждающий баннер с кнопками сброса в 1 клик, а запуск некорректной детекции заблокирован.
- [x] **Дефект 2: Устранение дублирования событий и React key warnings**
  - [x] Дедупликация событий по `id` через `Map` в `MonitoringPage.tsx`.
  - [x] Уникальные составные ключи `${ev.id}-${idx}` в `DataQualityPanel.tsx`.
- [x] **Научный пункт 3: Сопоставимость охвата (Coverage) в H1**
  - [x] Сравнение зафиксировано на строго сопоставимых срезах: срез $\approx 60\%$ (B1 risk 54.7%, B2 risk 55.4%, M risk 36.2%, выигрыш -19.2 pp) и срез $\approx 46\%$ (B1 risk 55.6%, M risk 32.1%, выигрыш -23.6 pp).
  - [x] Устранена неточная формулировка «при охвате ~42%» в отношении стратегии B2.
- [x] **Научный пункт 4: Статистический аудит H3 и отзыв псевдорепликации**
  - [x] Выполнен парный статистический тест по $N=7$ независимым сценариям ($t=1.632, p=0.154$; Вилкоксон $p=0.297$).
  - [x] Утверждение $p < 0.05$ (вычисленное по 5 сидам случайного генератора) официально отозвано.
  - [x] Зафиксирован корректный статус `SUPPORTED_WITH_LIMITATIONS`.
- [x] **Научный пункт 5: Удаление неподтвержденных формулировок**
  - [x] Удалены утверждения о мировой/отечественной первизне, фундаментальной неидентифицируемости и гарантированной переносимости.
- [x] **Сценарий защиты (пункт 6):**
  - [x] `docs/STAGE7_DEMO_SCRIPT.md` обновлен: устранены термины «вероятность 99.9%», согласованы точные числа со сценарием `coi_stuck_025_annual` (порог 0.92 °C, MAE 3.19 °C, 10 915 мин аномалий, рассогласование 45.7%).
- [x] **Унификация версий и единиц (пункт 7):**
  - [x] Все компоненты и документы приведены к версии `v0.7.1-stage7.1`, единицы температуры строго $^\circ\text{C}$.
- [x] **Тестирование Playwright E2E, Pytest и TypeScript (пункт 8):**
  - [x] `scripts/test_playwright_e2e_stage7_1.py`: 100% PASS, проверены оба разрешения 1440×900 и 1280×800 на всех 3 экранах.
  - [x] Pytest: 80 из 80 тестов PASS (100%).
  - [x] TypeScript build: 0 ошибок типов.
- [x] **Итоговый аудит (пункт 9):**
  - [x] Подготовлен отчет `docs/STAGE7_1_FINAL_AUDIT.md`.

---

## Статус выполнения Этапа 8A (Control-Aware FDD Pilot: CSIRO AHU9/AHU10) — Завершено
- [x] **Gate 8A.0: Фиксация исходного состояния (Baseline Freeze)**
  - [x] Сверены SHA-256 хэши 19 моделей Stages 1–7.1 и 12 JSON-манифестов.
  - [x] Подтверждена регрессионная база: 80/80 Pytest PASS, 0 ошибок сборки TypeScript.
  - [x] Оформлен `docs/STAGE8A_BASELINE_FREEZE.md`.
- [x] **Gate 8A.1: Физическая семантика и аудит данных CSIRO**
  - [x] Загружен и верифицирован `data/raw/csiro_ahu10.parquet` (7.88 МБ, SHA-256 проверен, 422 169 отсчетов, 102 пригодных эксперимента).
  - [x] Выполнен forensic-анализ `BMS.Changes.png`: доказано, что каналы `AHU*ahuCcValve`, `AHU*ahuOaDamper` представляют собой pre-proxy команды контроллера, а не навязанные величины `Magnitude`.
  - [x] Подтвержден аппаратный дефект $MA\_TEMP \equiv SA\_TEMP$ на AHU-10 (0.00 °C расхождение).
  - [x] Оформлены: `docs/STAGE8A_CSIRO_PROXY_SEMANTICS.md`, `docs/STAGE8A_AHU9_AHU10_INVENTORY.md`, `research/runs/stage8a_inventory.json`, `docs/STAGE8A_DATA_ELIGIBILITY.md`.
- [x] **Gate 8A.2: Предрегистрация протокола до начала моделирования**
  - [x] Утвержден протокол `research/protocols/stage8a_control_effort_v1.md`.
  - [x] Зафиксированы гипотезы H5a (AHU-09 exploratory) и H5b (AHU-10 confirmatory), схема сплитов, вектор экзогенных входов, 3 детектора (`T_ONLY`, `U_ONLY`, `T_PLUS_U`).
- [x] **Gate 8A.3: Минимальная реализация в пакете ml/control_aware/**
  - [x] Реализованы 9 автономных модулей: `channel_semantics.py`, `dataset.py`, `splits.py`, `features.py`, `baseline_control.py`, `residuals.py`, `alarm_policy.py`, `events.py`, `evaluate_stage8a.py`.
  - [x] Сохранена изоляция от production API и UI.
- [x] **Gate 8A.4: Негативные контроли и автотесты**
  - [x] Разработан тестовый сьют `backend/tests/test_stage8a_control_aware.py` (12 тестов, 100% PASS).
  - [x] Общий счет тестов расширен до 92/92 PASS (100%).
  - [x] Оформлен `docs/STAGE8A_TEST_REPORT.md`.
- [x] **Gate 8A.5: Экспериментальное сравнение T vs U vs T+U**
  - [x] CSIRO AHU-09: `T_ONLY` = 6/36 (16.7%) → `T_PLUS_U` = 9/36 (25.0%, FAR 3.63%, +3 события).
  - [x] CSIRO AHU-10: `T_ONLY` = 6/36 (16.7%) → `T_PLUS_U` = 6/36 (16.7%, FAR 3.83%, +0 событий).
  - [x] Оформлен научный отчет `research/reports/STAGE8A_CONTROL_EFFORT_REPORT.md` и манифест `research/runs/stage8a_control_effort_results.json`.
- [x] **Gate 8A.6: Приёмка этапа 8A**
  - [x] Оформлена финальная матрица приёмки `docs/STAGE8A_ACCEPTANCE.md`.

---

## Статус выполнения Этапа 8B (Dynamic Control-Aware Fault Detection) — Завершено

- [x] **Gate 8B.0: Строгий научный и датасетный аудит**
  - [x] Восстановлен переход 34 → 36 событий на AHU-09 (окно 00:00 vs 09:00, события 254 и 255 в 08:30; числитель $T\_ONLY = 6$ инвариантен).
  - [x] Выявлено и устранено загрязнение Train/Val на AHU-10 (21 эксперимент отфильтрован через `split_clean_ahu` с 60-мин эмбарго).
  - [x] Проведен календарный аудит (16-часовые ночные разрывы 17:00–09:00; разработано правило сброса состояния при $\Delta t > 120$с).
  - [x] Составлена матрица сигналов `research/tables/signal_lineage.csv`.
  - [x] Разобран прирост +3 событий AHU-09 (одновременная инъекция ID 287, 288, 289 в 14:32:34 = 1 физический эпизод).
  - [x] Оформлены: `docs/STAGE8B_0_DATA_AND_METRIC_AUDIT.md`, `research/runs/stage8b_0_audit.json`.
- [x] **Gate 8B.1: Предрегистрация протокола и динамические архитектуры**
  - [x] Утвержден протокол `research/protocols/stage8b_dynamic_control_protocol.md`.
  - [x] Разработаны модули `ml/control_aware/dynamic_features.py` и `dynamic_models.py` (M1–M7).
  - [x] Введен двойной учет: по строкам таблицы ($N=36$) и консолидированным физическим эпизодам ($N=16$).
- [x] **Gate 8B.2: Физический динамический анализ и негативные контроли**
  - [x] Доказано компенсаторное самоподавление в контроллерно-обусловленных моделях $U\_DYN\_CTRL$ (падение с 17 до 11 событий на AHU-09).
  - [x] Проверены негативные контроли: временное перемешивание подтвердило разрушение корреляций ($0/36$ детекций, 0% FAR).
- [x] **Gate 8B.3: Оценка идентифицируемости и обоснованный отказ от N4SID / фильтра Калмана**
  - [x] Доказана недостаточность управляющего возбуждения в замкнутом контуре ($|\Delta u| < 0.003$, диапазон $< 0.30$ $\to$ `DYNAMICS_UNIDENTIFIABLE`).
  - [x] Тест Льюнга-Бокса выявил колоссальную автокорреляцию невязок ($r_1 > 0.91, p < 10^{-130}$), опровергающую белизну инноваций Калмана.
  - [x] Переход к N4SID и фильтру Калмана научно обоснованно отклонен.
- [x] **Gate 8B.4: Проверка переносимости на внешнее здание (RBC-Nesbitt)**
  - [x] Зафиксирован статус `NOT_EVALUABLE_REMOTE_403` из-за блокировки Figshare S3 подписанных ссылок.
  - [x] Оценка переноса проведена между физическими установками AHU-09 и AHU-10 одного здания.
- [x] **Gate 8B.5: Синтез результатов, автотесты и приёмка**
  - [x] Доказан фундаментальный компромисс: при строгом FAR $\le 5\%$ и $\le 2$ эп/день динамическое моделирование $U\_DYN\_EXO$ на AHU-10 дает $3/36$ событий против $6/36$ у $T\_ONLY$.
  - [x] Добавлены 9 unit/regression тестов (`test_stage8b_dynamic.py`), общий счет тестов: **101/101 PASS (100%)**.
  - [x] Frontend strict build: 0 ошибок типов.
  - [x] Оформлены: `research/reports/STAGE8B_DYNAMIC_FDD_REPORT.md`, `docs/STAGE8B_ACCEPTANCE.md`, `research/runs/stage8b_dynamic_results.json`, графики `research/figures/stage8b_*.png`.
  - [x] Итоговый вердикт: **MORE_RESEARCH / NO_GAIN_UNDER_OPERATIONAL_BUDGET** (production-код Stages 1–7.1 сохранен в неизменности).

---

## Статус выполнения Этапа 8B Scientific Reconciliation (Корректирующий научный аудит) — Завершено

- [x] **Task 1: Повторный строгий расчёт R² и разделение Train vs Validation**
  - [x] Исправлена опечатка $0.0518 \to 0.518$ и разграничены Train $R^2$ (AHU9: 0.6105, AHU10: 0.3951) и Validation $R^2$ (AHU9: 0.0512, AHU10: -12.7253).
  - [x] Статус H8B.1 обновлён на `PARTIALLY_SUPPORTED_OVERFITTING_ON_VAL`.
- [x] **Task 2: Пересмотр H8B.3 (Режимная динамическая сшивка M7)**
  - [x] Проверены фактические FAR: 14.62% на AHU-09 и 18.94% на AHU-10 (норматив $\le 5.0\%$).
  - [x] Статус H8B.3 изменён на `REFUTED_FAR_BUDGET_EXCEEDED`.
- [x] **Task 3: Интеграция строгих конфигураций M4 в машинный манифест**
  - [x] M4 Strict ($\tau=6.00$ на AHU-09, $\tau=4.75$ на AHU-10) добавлена в `evaluate_stage8b.py` и сохранена в JSON-манифесте.
- [x] **Task 4: Пересмотр H8B.2 при сопоставимом FAR**
  - [x] При контролируемом FAR ~5% на AHU-09: M4 Strict (15 строк / 6 эп.) превосходит M5 Comparable (8 строк / 3 эп.) в 2 раза, подтверждая компенсаторное маскирование.
- [x] **Task 5: Верификация временной дискретизации**
  - [x] Подтверждён пайплайн: 30 с $\to$ 60 с (1 мин) ресемплинг; лаги 1, 2, 5 = 1, 2, 5 минут; $K=10/N=15$ = 10 мин в 15-мин окне.
- [x] **Task 6: Нормировка ложных эпизодов на 8-часовой операционный день и консолидация инъекций**
  - [x] Стандартизирована формула: $\text{FA Ep/8h} = \frac{N_{FA} \cdot 480}{N_{norm}}$; консолидированы одновременные инъекции (16 физических эпизодов).
- [x] **Task 7: Теоретическая коррекция выводов об идентификации в замкнутом контуре**
  - [x] Разделены свойства текущих данных (отсутствие excitation) и общая теория closed-loop ID.
- [x] **Task 8: Потоковое извлечение датасета RBC-Nesbitt через Figshare API**
  - [x] Разработан HTTP Range экстрактор; извлечены 6 файлов (базовые линии + отказы) в `data/raw/rbc_nesbitt/`.
- [x] **Task 9: Архивирование и версионирование манифестов**
  - [x] Архив v1 сохранён в `stage8b_dynamic_results_v1_archive.json`; манифест v2 записан в `stage8b_dynamic_reconciliation_results.json` и `stage8b_dynamic_results.json`.
  - [x] Оформлен аддендум `research/reports/STAGE8B_RECONCILIATION_ADDENDUM.md`.
- [x] **Task 10: Полные автотесты и итоговая таблица научной сверки**
  - [x] Pytest 101/101 PASS (100%), Frontend build PASS (0 ошибок типов). Сводная таблица сверки сформирована.

---

## Статус выполнения внешнего эксперимента RBC-Nesbitt (Drexel University) — Завершено

- [x] **Task 1: Разрешение остаточных конфликтов Stage 8B**
  - [x] Зафиксированы канонические числа M4 Strict (3/36 строк, 1/16 эпизодов на AHU-09); статус H8B.1 изменён на `REFUTED_VALIDATION_OVERFITTING`; согласованы правила сброса лагов (120 с) и фильтра (300 с); H8B.2 зафиксирован как эмпирическое наблюдение.
- [x] **Task 2: Контроль целостности и размерности RBC-Nesbitt**
  - [x] Проверены все 8 файлов (SHA-256 проверен, размерность ровно 540 столбцов и 288 строк).
- [x] **Task 3: Построение точной карты каналов AHU1/AHU2/AHU3**
  - [x] Составлена таблица `research/tables/rbc_nesbitt_signal_lineage.csv` по абсолютным индексам столбцов, устранены коллизии заголовков.
- [x] **Task 4: Конвертация времени (HHMM) и температур (°F $\to$ °C)**
  - [x] Реализована и протестирована корректная 5-минутная шкала времени и физическая конвертация единиц.
- [x] **Task 5: Точная разметка интервалов неисправностей (Table 2 & 3)**
  - [x] Выделены точные границы аварийных окон (109–121 отсчёт на эксперимент, чистая норма вне окон сохранена).
- [x] **Task 6: Семантика исполнительных механизмов и разделение BAS override**
  - [x] Установлено, что канал клапана является Feedback (потенциометр), а заслонки — управляющим сигналом.
- [x] **Task 7: Формирование обучающей и валидационной нормы**
  - [x] Использованы 3 летних дня нормы (16/06/01, 16/07/12, 17/07/14) для обучения и 17/07/29 для валидации (U_ONLY Val $R^2 = 0.38$).
- [x] **Task 8: Минимальный FDD-эксперимент (M1–M4)**
  - [x] Доказано превосходство Control Effort: `M2_U_ONLY` обнаруживает 3 из 4 физических эпизодов (75.0%) при FAR 4.41%, в то время как `M1_T_ONLY` показывает 0.0% Recall.
- [x] **Task 9: Операционная оценка по Нейману-Пирсону**
  - [x] Рассчитаны Recall точек и эпизодов, Pointwise FAR, частота ложных тревог на 8ч день и задержка детекции (10 минут).
- [x] **Task 10: Научный отчёт, манифест и решение STOP/GO**
  - [x] Оформлены: `research/reports/RBC_NESBITT_EXTERNAL_VALIDATION_REPORT.md`, `research/runs/rbc_nesbitt_fdd_results.json`, автотест `test_rbc_nesbitt_external_manifest`.

---

## Статус выполнения Stage 8B-R (Корректирующий научный аудит эксперимента RBC-Nesbitt) — Завершено

- [x] **Task 1: Согласование результатов и устранение противоречий нарратива**
  - [x] Исправлена ошибка в `key_finding`: подтверждён 0.0% Recall для $M1\_T\_ONLY$, а также Recall 75.0% при FAR 4.41% для $M2\_U\_ONLY\_STRICT$ ($\tau=3.5$) и 2.50% для $M3\_T\_PLUS\_U\_STRICT$ ($\tau=4.0$).
  - [x] Конфигурация $M3$ Strict добавлена в машинный манифест v2.
  - [x] Представлен алгоритм и таблица калибровки порогов $\tau=3.5$ и $\tau=4.0$ строго на чистой валидационной норме.
- [x] **Task 2: Физический аудит каналов и защита от утечек**
  - [x] Документирована причина использования Col 57 (`CCV_FBK`): отсутствие отдельного программного выхода регулятора в выгрузке BAS.
  - [x] Доказано отсутствие целевой утечки в матрицу признаков $X$ (Col 57 строго исключён из входов).
- [x] **Task 3: Разрешение коллизии 11.07.2018 и двойной учёт метрик**
  - [x] Вскрыта динамическая модуляция Col 36 (AHU1, среднее 77.1%) и закрытие Col 57 (AHU2) в 0%.
  - [x] Эксперименту присвоен статус `LABEL_OR_SIGNAL_SEMANTICS_UNRESOLVED`.
  - [x] Выполнен двойной расчёт метрик: по всей выборке ($N=4$, 75.0% recall) и валидной подвыборке ($N=3$, 66.7% recall).
- [x] **Task 4: Проверка эксплуатационных режимов и скорости вентилятора**
  - [x] Выявлен глубокий сброс оборотов вентилятора AHU-2 до 30% в 2018 году (68–88% времени).
  - [x] Оценено влияние эксплуатационной маски $SF\_SPD \ge 40\%$ (падение FAR до 0.00%–0.46% при 100% обнаружении летних аварий 2017 г.).
  - [x] Дополнительно загружены и проверены два летних базовых дня 2017 года (`20170618_Baseline.csv`, `20170702_Baseline.csv`).
- [x] **Task 5: Минимальные физические бейзлайны и абляция**
  - [x] Проведено прямое сравнение на идентичных окнах: $M1$ (термический), $M2$ (ожидаемое управление), $M3$ (макс-слияние), $M4$ (ошибка слежения), $M5$ (правило насыщения), $M6$ (динамический отклик актуатора), негативный контроль (пермутация).
- [x] **Task 6: Машинный манифест v2 и пошаговые предсказания**
  - [x] Сформированы `research/runs/rbc_nesbitt_reconciled_manifest.json` и `research/runs/rbc_nesbitt_pointwise_predictions.csv` (1 152 точки).
  - [x] Оформлен подробный отчёт `research/reports/STAGE8B_R_NESBITT_AUDIT_REPORT.md`.
- [x] **Task 7: Автономный пакет независимого аудита (Audit Package)**
  - [x] Разработан скрипт `scripts/build_audit_package.py`.
  - [x] Собран архив `BUILDINGPULSE_AUDIT_STAGE_8B_R.zip` (1.63 MB, 159 файлов в разделах `code/`, `data/`, `models/`, `results/`, `validation/`, `repository/`, `audit/`).
  - [x] Хэш SHA-256 проверен: `e3dde87919fdda7fb8d4cb8c719d312b487f08ee1823eb55ea2d5e8bf348d539`.
- [x] **Task 8: Автотесты и целостность кодовой базы**
  - [x] Pytest: 103 из 103 PASS (100%).
  - [x] Frontend strict build: 0 ошибок типов, успешная сборка.
  - [x] Производственный код Stages 1–7.1 сохранён в неизменности.

---

## Статус выполнения Stage 8B-R.1 (Научная ревизия FDD-эксперимента RBC-Nesbitt) — Завершено

- [x] **Task 1: Автоматический выбор порога (`select_threshold`) и статус бенчмарка**
  - [x] Реализована функция `select_threshold` и задокументирован выбор: $\tau=3.00$ для M2 и $\tau=3.25$ для M3 при лимите $\text{Val FAR} \le 3\%$.
  - [x] Бенчмарк официально переведён в статус `RETROSPECTIVE_EXPLORATORY_BENCHMARK`.
- [x] **Task 2: Доказательство строгого доминирования M2 над M3**
  - [x] Проведён расчёт по единой сетке $\tau \in [1.5, 5.0]$; доказано, что M3 не добавляет ни одного события и при сопоставимом пороге уступает M2 по FAR (1.91% vs 2.50% при $\tau=4.00$).
- [x] **Task 3: Физический аудит каналов заслонок и Washout**
  - [x] Установлен факт удержания override заслонок 100% до 22:25 на сценарии 2017-07-18 и сброса в 15% только в 22:30.
  - [x] Рассчитан FAR при исключении активного override (падение до 0.00% на 2017-07-18).
- [x] **Task 4: Режимный и подневный FAR (2017 vs 2018)**
  - [x] Вскрыт провал FAR на днях 2018 года (6.59% и 10.18%) из-за ночной скорости вентилятора 30%; доказано падение FAR до 0.00% при рабочей маске $SF\_SPD \ge 50\%$.
- [x] **Task 5: OOD-аудит модели Ridge и эндогенность MA_TEMP**
  - [x] Выявлены 25/109 отрицательных предсказаний клапана (до -9.26%) и 108/109 точек MA_TEMP вне обучающего диапазона. Внедрён `DomainGuard`.
- [x] **Task 6: Прямая наблюдаемость аварии 30% в телеметрии BAS**
  - [x] Доказано детектирование 121/121 точек правила по заслонкам (`RELIEF > 20 | RETURN > 20`), опровергнут догматический тезис о строго обязательном Active Probing.
- [x] **Task 7: Статистическая неопределённость и доверительные интервалы**
  - [x] Рассчитаны 95% точные CI Клоппера-Пирсона ([9.4%, 99.2%]) и точные парные тесты ($p=0.5000$).
- [x] **Task 8: Алгоритмические исправления (эпизоды и шкала нормализации)**
  - [x] Внедрён подневный расчёт ложных эпизодов без искусственного объединения тревог; зафиксирована специфика шкалы $\text{std}(|e|)$.
- [x] **Task 9: Автономный аудит-пакет Stage 8B-R.1**
  - [x] Собран архив `BUILDINGPULSE_AUDIT_STAGE_8B_R_1.zip` (1.69 MB, 173 файла, SHA-256 проверен), содержащий `requirements.txt`, исполняемый сьют из 110 Pytest, манифесты и отчеты.
- [x] **Task 10: Сохранение границ production**
  - [x] Кодовая база Stages 1–7.1 сохранена в полной неприкосновенности.

---

## Статус выполнения Stage 8B-R.2 (Исправление доказательной базы и закрытие независимого аудита) — Завершено

- [x] **Gate 1: Data / Report Parity (P0-B)**
  - [x] Устранены текстовые опечатки Stage 8B-R.1: синхронизированы числа M6 Direct Damper BAS (2/4 эп., 229/472 строк, 4.41% FAR).
  - [x] Внедрена программная сборка `STAGE8B_R2_EVIDENCE_REPORT.md` напрямую из JSON-манифеста с SHA-256 и единым `run_id`.
- [x] **Gate 2: Трёхстатусный DomainGuard и цена OOD-абстиненции (P0-A)**
  - [x] Реализованы статусы `VALIDATED_IN_DOMAIN`, `OOD_DETECTED`, `OOD_ABSTAINED`.
  - [x] Доказано, что наивный train min/max помечает OOD 95/288 нормальных Val-точек; внедрён калиброванный конверт разработки (`dev_envelope`, 100% покрытие нормы).
  - [x] Зафиксировано падение In-Domain Recall M2 до 1/4 (25.0%) при нулевом In-Domain FAR (0.00%) из-за выхода 108/109 точек 2017-07-18 в OOD по $MA\_TEMP$.
- [x] **Gate 3: Validation-only выбор метода и locked benchmark**
  - [x] Пороги зафиксированы строго по чистой норме: $\tau=3.00$ для M2, $\tau=3.25$ для M3. Подтверждён статус `RETROSPECTIVE_EXPLORATORY_BENCHMARK`.
- [x] **Gate 4: Time-aware scoring и разрыв K-of-N на физических границах**
  - [x] Реализовано непрерывное отслеживание времени (`apply_time_aware_causal_k_of_n`), сброс персистенции при $\Delta t > 15$ мин, fan-off и OOD-абстиненции.
  - [x] Добавлены негативные unit-тесты разрыва ложных эпизодов (`tests/test_time_aware_scoring.py`, 3/3 PASS).
- [x] **Gate 5: Regime coverage и цензурирование низкоскоростного режима**
  - [x] Доказано, что маска $SF\_SPD \ge 50\%$ отсекает 71.9% аварийных точек 2018-07-10 и 95.0% аварийных точек 2018-07-11, снижая Recall до 2/4.
- [x] **Gate 6: Causal / semantic ablations**
  - [x] Обучена модель $M2_{\text{No-MA}}$: устранены все отрицательные предсказания (минимум +37.33% против -9.26%), Recall упал до 2/4 (50%).
  - [x] Direct Damper BAS размечен как `INJECTION_OBSERVABLE`; сценарий 2018-07-11 зафиксирован как `LABEL_OR_SIGNAL_SEMANTICS_UNRESOLVED`.
- [x] **Gate 7: Negative controls и статистическая интерпретация**
  - [x] Внедрён Circular Block Shift (3 сида): FAR нормы подскакивает до 32.35% – 39.12%.
  - [x] Рассчитаны 95% точные CI Клоппера-Пирсона ([9.4%, 99.2%] и [19.4%, 99.4%]) и точные парные тесты ($p=0.5000$ и $p=0.2500$).
- [x] **Gate 8: Автономный аудит-пакет Stage 8B-R.2**
  - [x] Сформирован архив `BUILDINGPULSE_AUDIT_STAGE_8B_R_2.zip` (3.49 MB, 329 файлов, SHA-256: `455e154631d6cb2ea117ed22411f164bf6adf7982f713c7738ae1c7e4c4cef22`).
  - [x] Включает автономный тестовый сьют `tests/` (15/15 PASS), runner, 10 сырых CSV, модели, маски и доказательные отчеты. Проверено независимой распаковкой.

---

## Статус выполнения Stage 8B-R.3 (Технический hotfix и закрытие P0 аудита) — Завершено

- [x] **Gate 0: Устранение потери временных меток в `load_clean_nesbitt()`**
  - [x] Присваивание заменено на `clean["timestamp"] = dt_index.to_numpy()`, исключив RangeIndex выравнивание в NaT.
  - [x] Внедрена валидация допустимости HHMM, строгой монотонности, отсутствия NaT и эквивалентности `index`.
  - [x] Интеграционный тест `test_real_csv_loader_timestamp_integrity` пройден (PASS).
- [x] **Gate 1: Доказательство работы Gap Guard, задержки и строгий JSON**
  - [x] Интеграционный тест `test_real_loader_gap_reset` подтвердил сброс памяти $K=2/N=3$ через разрыв $>15$ минут.
  - [x] Интеграционный тест `test_real_loader_false_episode_gap_break` подтвердил разделение эпизодов через разрыв 200 минут.
  - [x] Зафиксированы валидные задержки детекции для M2 ($\tau=3.50$): 2017-07-18 = 30.0 мин, 2017-08-11 = 10.0 мин, 2018-07-10 = None (не обнаружен), 2018-07-11 = 50.0 мин.
  - [x] Вся JSON-сериализация манифестов переведена на `allow_nan=False`. В манифесте устранено 398 литералов `NaN` (строго 0 NaN/Infinity).
- [x] **Gate 2: Полное раскрытие DomainGuard и охвата**
  - [x] Условный FAR 0.00% представлен исключительно со знаменателями охвата: 313/680 (46.0%) нормальных точек, 86/472 (18.2%) аварийных точек, Recall 1/4 (25.0%).
  - [x] В `rbc_nesbitt_pointwise_predictions.csv` добавлены явные статусы `domain_guard_status`, `is_eligible_indomain`, `m2_indomain_status` (`OOD_ABSTAINED`) и поконфигурационные тревоги.
  - [x] Проведён эксплораторный аудит дополнительных нормальных дней `20170618` (16.7% OOD, 0 тревог при $\tau=3.00$) и `20170702` (26.7% OOD, 0 тревог при $\tau=3.00$).
- [x] **Gate 3: Научные границы и сохранение статуса**
  - [x] M2 явно зафиксирован как прогноз обратной связи клапана $CCV\_FBK$; 20180711 сохранён со статусом UNRESOLVED (split N=3 vs N=4).
  - [x] $MA\_TEMP$ охарактеризована как эндогенный симптом; циклический сдвиг — как контроль временной структуры; внедрён базовый guard вентилятора ($SF\_SPD \ge 10\%$).
  - [x] Статус эксперимента сохранён как `RETROSPECTIVE_EXPLORATORY_BENCHMARK`.
- [x] **Gate 4: Автономный аудит-пакет Stage 8B-R.3**
  - [x] Сформирован архив `BUILDINGPULSE_AUDIT_STAGE_8B_R_3.zip` (3.53 MB, SHA-256: `76023630a9b43e3963edebb0072fc6aa1b3b68529cd5ed16092f1dae13c3c577`).
  - [x] Включает 19 автономных тестов `tests/` (100% PASS), 10 сырых CSV, модели, манифест v2.3, пошаговые предсказания, документацию `audit/`.
  - [x] Проведена чистая распаковка скриптом `scripts/verify_unpacked_zip.py`: 332 из 332 контрольных сумм совпали, 19/19 тестов прошли, раннер отработал с кодом 0.
- [x] **Task: Сохранение границ production**
  - [x] Кодовая база Stages 1–7.1 сохранена в полной неприкосновенности. Никаких git commit / push / merge / deploy.

---

## Статус выполнения Stage 8B-R.4 Corrected (Судебно-технический разбор и исправление научной целостности) — Завершено

- [x] **Gate 0: Устранение ложного нарратива в отчёте (P0-01)**
  - [x] Из генератора отчёта полностью удалены любые фиксированные формулировки о «100% обнаружении летом».
  - [x] Отчёт переведён на 100% динамический рендеринг из JSON-манифеста с фактическим отрицательным результатом: M2/M3 летний New Onset Recall = **0.0% (0/3)**.
  - [x] Внедрён сьют `tests/test_report_manifest_consistency.py` (4/4 PASS).
- [x] **Gate 1: Временная причинность и разделение доаварийных тревог (P0-02)**
  - [x] Введено строгое разделение метрик: `Legacy Any Overlap Recall` vs `New Onset Recall` vs `Missed Due to Pre-existing Alarm`.
  - [x] Доказано, что тревоги на `2016-12-01` начались до старта аварии (в 08:40 при старте в 10:00). Истинный New Onset Recall M2 $\tau=4.00$ по 5 сценариям равен **20.0% (1/5)**, а M6 — **40.0% (2/5)**.
  - [x] Внедрён сьют `tests/test_event_onset_and_preexisting_alarms.py` (3/3 PASS).
- [x] **Gate 2: Происхождение моделей и статус TEST-EXPOSED (P0-03)**
  - [x] Зафиксировано, что модели R.4 являются `LOCALLY_FITTED_DEVELOPMENT_MODELS` с фиксированными правилами порогов, а не замороженными весами R.3. Раскрыты коэффициенты и скейлы.
  - [x] Все 5 аварийных дней переведены в статус `TEST-EXPOSED` (повторный анализ носит судебно-технический характер).
- [x] **Gate 3: Физический статус M6 и механизмы инъекций (P0-04)**
  - [x] M6 зафиксирован как `DIRECT_BAS_RULE / INJECTION_OBSERVABLE` (читает навязанные приводам команды, зимний FAR = 66.27%).
  - [x] Сценарий `2018-07-09` документирован как сдвиг уставки `setpoint demand adjust` на 1.75 по первичной документации.
- [x] **Gate 4: Анализ чувствительности Washout и поточечные решения (P1-05, P1-06)**
  - [x] Рассчитан FAR для 4 режимов: `official`, `override_masked`, `washout_60m` и `baselines_only`.
  - [x] Экспортирован полный CSV `rbc_nesbitt_independent_pointwise_predictions.csv` (3744 строки) со всеми флагами тревог, онсетов и применимости.
- [x] **Gate 5: Автономный аудит-пакет и независимая верификация**
  - [x] Собран архив `BUILDINGPULSE_AUDIT_STAGE_8B_R_4_CORRECTED.zip` (4.29 MB, 4,498,208 байт, SHA-256: `12b8a96d614496844a59c0d6301f96c13160b1ad1327293761cdf0b4244adf7e`).
  - [x] Включает 33 автономных теста (100% PASS), 23 сырых CSV, полную документацию аудита (`README_REPRODUCE.md`, `CLAIMS_TO_EVIDENCE.md`, `KNOWN_LIMITATIONS.md`, `DATASET_BLIND_SPLIT_MANIFEST.md`), SHA256SUMS.txt.
  - [x] Независимая проверка распаковкой подтвердила совпадение всех 257 контрольных сумм и успешный запуск раннера.
- [x] **Task: Сохранение границ production**
  - [x] Кодовая база Stages 1–7.1 сохранена в полной неприкосновенности. Никаких git commit / push / merge / deploy.

---

## Очередь задач Этапа 8C (Active Probing / Evidence Synthesis) — ОЖИДАЕТ РАЗРЕШЕНИЯ ВЛАДЕЛЬЦА

---

## Памятка для студента перед выходом на защиту
1. Прогнать перед защитой: `python scripts/verify_environment.py`
2. Запустить бэкенд: `python -m uvicorn backend.app.main:app --port 8050`
3. Запустить фронтенд: `npm --prefix frontend run dev -- --port 5180`
4. Открыть в полноэкранном режиме: `http://localhost:5180`
5. Держать перед глазами шпаргалку с ответами на вопросы: `docs/STAGE7_THESIS_OUTLINE.md` и сценарий `docs/STAGE7_DEMO_SCRIPT.md`.



