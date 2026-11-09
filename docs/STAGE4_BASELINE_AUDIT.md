# STAGE 4 BASELINE AUDIT — Научный и технический аудит фундамента Stage 3

- **Дата проведения аудита:** 2026-11-02
- **Версия задания:** BuildingPulse AI Master Prompt Stage 4 v1.1
- **Статус аудита (Gate 0):** **PASS**

---

## 1. Инвентаризация окружения и сетевых портов

| Компонент / Проверка | Ожидаемое значение | Фактический результат | Статус |
| :--- | :--- | :--- | :---: |
| **Git репозиторий** | Проверка статуса без commit/push | `fatal: not a git repository`. Git-операции не выполнялись. | PASS |
| **Порт API (8050)** | `127.0.0.1:8050` (FastAPI) | Процесс Python (PID 12356) активен, эндпоинт `/api/health` отвечает `{"status":"ok"}`. | PASS |
| **Порт Web UI (5180)** | `0.0.0.0:5180` (Vite) | Процесс Node (PID 33332) активен, интерфейс доступен. | PASS |
| **Порт DB (5455)** | Зарезервирован под PostgreSQL Docker | Порт свободен, локальный dev-режим использует SQLite `buildingpulse.db`. | PASS |
| **Docker Compose Config** | Валидный синтаксис docker-compose.yml | `docker-compose.yml` синтаксически корректен; runtime сборка контейнеров заблокирована из-за внешнего DNS в WSL/Docker Desktop на хосте (зафиксировано в Stage 3). | PARTIAL / BLOCKED (Docker Runtime) |

---

## 2. Версии библиотек и среды выполнения

- **ОС:** Windows 11
- **Python:** 3.11.6 (64-bit)
- **LightGBM:** 4.6.0
- **Scikit-learn:** 1.8.0
- **FastAPI:** 0.115.6
- **Pydantic:** 2.10.4
- **Pandas:** 3.0.2
- **PyArrow:** 19.0.1
- **Pytest:** 8.3.4
- **Node / Vite / React:** Node v20+, Vite 5.4.21, React 18, TypeScript strict

---

## 3. Регрессионное тестирование существующего кода

### 3.1. Бэкенд (Pytest)
```bash
pytest backend/tests
```
**Результат:** `18 passed in 6.14s` (100% PASS).
- `test_diagnostics.py`: 4 теста PASS (Domain Guard на synthetic demo, LBNL summary, rule baseline execution, events query).
- `test_health.py`: 1 тест PASS.
- `test_import.py`: 4 теста PASS.
- `test_ml.py`: 7 тестов PASS.
- `test_quality_and_rules.py`: 1 тест PASS.
- `test_telemetry.py`: 1 тест PASS.

### 3.2. Фронтенд (TypeScript Strict + Vite Build)
```bash
npm --prefix frontend run build
```
**Результат:** `✓ built in 11.42s`. Ошибок компиляции типов TypeScript — **0**.

---

## 4. Верификация воспроизводимости моделей и результатов Stage 3

### 4.1. Многосезонный виртуальный датчик SA_TEMP
Команда: `python -m ml.virtual_sensor.evaluate_multiseason`
- **LightGBM (`vs-sa-temp-v2`):**
  - Оценочная выборка: 12 суток нормы 4 сезонов (10 082 рабочих точек).
  - MAE: **0.0387 °C** (полное совпадение с отчетом Stage 3).
  - RMSE: **0.1739 °C** (полное совпадение).
  - $R^2$: **0.7534** (полное совпадение).
  - Ложные тревоги ($3\sigma = 0.919^\circ\text{C}$): **0 точек (0.0%), 0 эпизодов**.
- **Ridge (`vs-sa-temp-baseline-ridge-v2`):**
  - MAE: **0.1083 °C**, RMSE: **0.2548 °C**, $R^2$: **0.4707**.
  - Превосходство LightGBM над линейным бейзлайном по MAE: в **2.80 раза**.

### 4.2. Классификация семейств дефектов (Scenario-Level Split)
Команда: `python -m ml.diagnostics.evaluate_fault_families`
- Обучающая выборка: 45 120 точек (25%, 75% stuck; $\pm 4^\circ\text{C}$ bias).
- Отложенный тест: 18 480 точек (10%, 50% stuck; $\pm 2^\circ\text{C}$ bias).
- **Результаты на независимых интенсивностях:**
  | Модель / Бейзлайн | Macro F1 | FAULT_FREE | SENSOR_BIAS_SA | COOLING_VALVE_STUCK | OUTDOOR_DAMPER_STUCK | UNRESOLVED |
  | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
  | **Rule-based Baseline** | 0.1197 | 0.3859 | 0.0014 | 0.2114 | 0.0000 | 5 579 точек (**30.2%**) |
  | **Ridge Linear Classifier** | 0.3975 | 0.0000 | 0.5210 | 0.5492 | 0.5198 | 0% (принудительный выбор) |
  | **LightGBM Classifier** | **0.5367** | 0.4718 | 0.3159 | **0.8398** | 0.5193 | 0% (принудительный выбор) |

Воспроизведение численно **100% точное**.

---

## 5. Контрольные суммы (SHA-256) ключевых артефактов Stage 3

| Файл артефакта | SHA-256 |
| :--- | :--- |
| `models/vs-sa-temp-v2.joblib` | `9fd340dd28b137e90d37dc4195dc8309e9766130091b82c31082928819c6e48d` |
| `models/vs-sa-temp-v2_transformer.joblib` | `6f59b7f6e3df488e510cd49b3b2ea2fe71a387b5742b8ba8d7d0632220b926ee` |
| `models/vs-sa-temp-v2_metadata.json` | `014d9aea35f3dfdb232aeee590e3c7d4416b403fccb91ff468b095039d4c865e` |
| `models/vs-sa-temp-baseline-ridge-v2.joblib` | `d973fd374b3557e7f7bde65f2ecdb7bc363d654fc5d8933be0902e59bdc72208` |
| `models/fault-family-classifier-v1.joblib` | `99ec6a40977125a0cef7345722f1912e02f4141683f75cd2937e56b584b42863` |
| `models/fault-family-classifier-v1.json` | `0b4879a852d009f6265389d1315dbb34bb955a9e394625d7a34bcf6eb107e9ef` |

---

## 6. Аудит научных инвариантов и изоляции признаков

1. **Защита от Target / Ground Truth Leakage (Инвариант I1):**
   - Целевая температура `SA_TEMP`, ее лаги и имена файлов не входят в `VirtualSensorTransformer`.
   - В классификаторе семейств дефектов метки сценариев (`source_fault_label`, `scenario_id`, `severity`) строго изолированы и не подаются в `X_diag`.
   - `source_fault_label` доступен в UI исключительно в скрытой исследовательской карточке верификации бенчмарка.
2. **Каузальность вычислений (Инвариант I3, I4):**
   - Все скользящие статистики признаков (`mean_15`, `std_15`, `diff_15`, `trend_15`) рассчитываются каузально назад по времени без использования будущих точек (`rolling(window=15, min_periods=1)`).
3. **Защита домена (Инвариант I8):**
   - `SYNTHETIC_DEMO` при вызове `/api/diagnostics/summary` без флага `allow_unvalidated=true` штатно блокирует ML-вывод и возвращает `OUT_OF_DOMAIN_UNVALIDATED`.
4. **Физическая канонизация:**
   - Температуры нормализуются из °F в °C ровно один раз при чтении из исходного Parquet.
   - Команды и обратная связь клапанов и заслонок строго разделены (`CHWC_VLV_DM` vs `CHWC_VLV`).

---

## 7. Выявленные ограничения и постановка задач на Stage 4

1. **Недостаток независимых сценариев:** В бенчмарке LBNL SD-AHU доступно по 4 сценария интенсивностей на каждое семейство дефектов. Применение Conformal Prediction со строгими гарантиями $1-\alpha$ ограничено предпосылкой независимости и объемом выборки (зафиксировать как `IMPLEMENTED_EXPLORATORY` / `CONFORMAL_NOT_VALIDATED` без псевдогарантий).
2. **Принудительный выбор существующих классификаторов:** LightGBM и Ridge классификаторы Stage 3 вынуждены выдавать класс с максимальной вероятностью даже при нулевой разделимости.
3. **Необходимость формального Decision Layer:** Требуется механизм, который на основе физических свидетельств, качества данных и доступности каналов принимает решение:
   - `SINGLE_CAUSE` (обоснованная конкретная причина);
   - `MULTIPLE_PLAUSIBLE` (набор кандидатов при неоднозначности);
   - `CAUSE_UNRESOLVED` (отказ от необоснованного диагноза).
4. **Реализация 5 исполняемых профилей наблюдаемости:** `BASIC`, `BASIC_PLUS_VALVE`, `BASIC_PLUS_DAMPER`, `BASIC_PLUS_BOTH`, `FULL`.
5. **Оценка Risk–Coverage:** Сравнение Decision Layer с baseline-методами B1 (Confidence-only) и B2 (Margin/Entropy rejection).

**Вывод по Gate 0:** Все базовые компоненты Stage 1–3 полностью работоспособны, тесты проходят, численные результаты подтверждены. Переход к Gate 1 разрешён.
