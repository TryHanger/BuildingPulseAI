# STAGE 8A — ОТЧЕТ О ТЕСТИРОВАНИИ И ВЕРИФИКАЦИИ (TEST REPORT)

**Дата прогона:** 2026-11-04  
**Версия платформы:** `BuildingPulse AI v0.8.0-stage8a` (База: `v0.7.1-stage7.1`)  
**Окружение:** Windows 11, Python 3.11.6, pytest-8.3.4, Node.js v20+, Vite 5.4.21, TypeScript 5.5 (strict mode).

---

## 1. Сводные результаты прогона тестов

| Категория тестов | Набор файлов | Количество тестов | Статус | Время выполнения |
|---|---|:---:|:---:|:---:|
| **Stage 1–7.1 Regression Suite** | `backend/tests/test_*.py` (без stage8a) | 80 | **80 / 80 PASS (100%)** | 12.4s |
| **Stage 8A Control-Aware Suite** | `backend/tests/test_stage8a_control_aware.py` | 12 | **12 / 12 PASS (100%)** | 0.72s |
| **ИТОГО PYTEST** | `backend/tests/` | **92** | **92 / 92 PASS (100%)** | **13.16s** |
| **Frontend Strict Typecheck & Build** | `frontend/` (`npm run build`) | — | **0 ошибок типов, PASS** | 19.80s |

---

## 2. Поэлементный протокол тестов Stage 8A (`test_stage8a_control_aware.py`)

1. `test_channel_semantics_classification`: **PASS** — Проверка корректности семантических типов всех ключевых каналов CSIRO AHU9 и AHU10 (`OBSERVED_PHYSICAL_SENSOR`, `CONTROLLER_OUTPUT_PRE_PROXY`, `DUPLICATE`, `SETPOINT`).
2. `test_no_target_self_leakage`: **PASS** — Защита от авторегрессионной утечки: попытка включить целевую команду `CHWC_VLV_DM` в матрицу признаков $X$ мгновенно вызывает `ValueError("Target leakage violation")`.
3. `test_banned_channels_rejected`: **PASS** — Защита от утечки параметров неисправностей: колонки разметки `Magnitude`, `Fault Type`, `Fault Name` вызывают отказ (fail-closed) `ValueError("Banned channel violation")`.
4. `test_duplicate_ma_temp_rejected`: **PASS** — Защита от аппаратного дефекта BMS: колонка `MA_TEMP` (замкнутая на `SA_TEMP`) вызывает отказ `ValueError("CSIRO MA_TEMP violation")`.
5. `test_chronological_splits_no_overlap`: **PASS** — Проверка строгой временной изоляции: $Train_{\text{end}} < Val_{\text{start}}$ и $Val_{\text{end}} < Test_{\text{start}}$ с нулевым пересечением индексов.
6. `test_feature_extraction_causality_and_bounds`: **PASS** — Каузальность извлечения признаков: гармоники времени, физические перепады $\Delta T$, отсутствие таргета и будущих точек.
7. `test_control_effort_model_bounded_predictions`: **PASS** — Ограничение выходов модели: предсказания $\hat{u}$ строго лежат в диапазоне $[0.0, 1.0]$.
8. `test_causal_k_of_n_filter_logic`: **PASS** — Каузальный фильтр персистенции: строгое требование накопления $K=10$ превышений порога в окне $N=15$ без заглядывания вперед.
9. `test_causal_k_of_n_filter_gap_reset`: **PASS** — Сброс персистенции при временном разрыве: пробел $> 5$ минут сбрасывает счетчик превышений, предотвращая сшивание ночей.
10. `test_event_level_single_detection`: **PASS** — Оценка на уровне событий: аварийный эпизод длительностью 60 тревожных минут регистрируется как ровно одно обнаруженное событие.
11. `test_false_alarm_episode_grouping`: **PASS** — Группировка ложных тревог: непрерывная серия минут тревоги на чистой норме объединяется в один ложный эпизод.
12. `test_negative_controls_degrade_correlations`: **PASS** — Проверка негативных контролей: сдвиг по времени (+6ч) и случайное перемешивание признаков разрушают корреляцию с таргетом ($r < 0.35$).

---

## 3. Статус прохождения контрольных шлюзов (Gates 8A.0 – 8A.4)

| Gate | Наименование шлюза | Проверочные артефакты | Результат |
|---|---|---|:---:|
| **Gate 8A.0** | Исходный baseline freeze | `docs/STAGE8A_BASELINE_FREEZE.md`, SHA-256 моделей и манифестов, 80/80 pytest PASS | **PASS** |
| **Gate 8A.1** | Физическая семантика и аудит данных | `docs/STAGE8A_CSIRO_PROXY_SEMANTICS.md`, `docs/STAGE8A_AHU9_AHU10_INVENTORY.md`, `research/runs/stage8a_inventory.json`, `docs/STAGE8A_DATA_ELIGIBILITY.md` | **PASS** |
| **Gate 8A.2** | Предрегистрация протокола | `research/protocols/stage8a_control_effort_v1.md` (до запуска моделей) | **PASS** |
| **Gate 8A.3** | Минимальная реализация | Пакет `ml/control_aware/` (9 модулей, строгая изоляция от Stage 1–7.1) | **PASS** |
| **Gate 8A.4** | Негативные контроли и автотесты | 12 unit/regression тестов в `backend/tests/test_stage8a_control_aware.py` | **PASS** |

**ВСЕ ТЕСТЫ И КОНТРОЛЬНЫЕ ШЛЮЗЫ УСПЕШНО ПРОЙДЕНЫ.**
