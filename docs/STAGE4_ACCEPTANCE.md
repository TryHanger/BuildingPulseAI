# STAGE 4 ACCEPTANCE — Матрица приёмки и верификации требований

- **Версия ТЗ:** BuildingPulse AI Master Prompt Stage 4 v1.1
- **Дата приёмки:** 2026-11-03
- **Итоговый статус:** **STAGE 4 ПОЛНОСТЬЮ РЕАЛИЗОВАН (ALL GATES PASS)**

---

## 1. Сводная матрица требований и доказательств

| Требование / Артефакт | Метод верификации | Доказательство / Путь к артефакту | Фактический результат | Статус |
| :--- | :--- | :--- | :--- | :---: |
| **Gate 0: Аудит и воспроизведение Stage 3** | Pytest, CLI скрипты, SHA-256 | `docs/STAGE4_BASELINE_AUDIT.md` | 18/18 pytest PASS; LightGBM multiseason MAE=0.0387°C воспроизведен; F1=0.5367 воспроизведен | **PASS** |
| **Gate 1: Предрегистрация протокола и метрик** | Документ протокола, unit-тест формул | `research/protocols/stage4_evidence_observability_protocol.md`, `backend/tests/test_selective_metrics.py` | Зафиксированы H1 и H2; Тест Приложения B (таблица 6 окон) пройден на 100% | **PASS** |
| **Gate 2: Библиотека свидетельств и Decision Layer** | Unit-тесты Python | `ml/diagnostics/evidence.py`, `ml/diagnostics/decision_layer.py`, `backend/tests/test_decision_layer.py` | 7 тестов PASS; реализованы SINGLE_CAUSE, MULTIPLE_PLAUSIBLE, CAUSE_UNRESOLVED, B1, B2 | **PASS** |
| **Gate 3: Профили наблюдаемости датчиков** | Unit-тесты изоляции каналов | `ml/diagnostics/sensor_profiles.py`, `backend/tests/test_sensor_profiles.py` | 3 теста PASS; искажение скрытых колонок не меняет BASIC-вывод ни на один бит | **PASS** |
| **Gate 4: Научные эксперименты (E4.1 & E4.2)** | Репродуцируемый запуск скрипта | `ml/diagnostics/evaluate_stage4.py`, `research/runs/stage4_*.json`, `research/figures/*.png` | E4.1: Risk при Coverage=0.40 упал с 0.556 до 0.294 (M Basic) и 0.156 (M +Valve). E4.2: F1 вырос с 0.5196 до 0.6722 | **PASS** |
| **Gate 5: Серверная и UI интеграция** | Pytest, TypeScript build, Playwright | `backend/app/api/endpoints/diagnostics.py`, `frontend/src/pages/DiagnosticsPage.tsx`, `npm run build` | 33/33 Pytest PASS; build без ошибок типов; 5 скриншотов Playwright | **PASS** |
| **Gate 6: Итоговая приёмка и документация** | Полный прогон тестов, аудит памяти | `docs/STATE.md`, `docs/DECISIONS.md`, `docs/NEXT_STEPS.md`, `docs/TEST_REPORT.md` | Все инварианты I1–I12 соблюдены; никаких commit/push без разрешения | **PASS** |

---

## 2. Проверка ключевых научных инвариантов

1. **Инвариант I1 (Нет Ground Truth leakage):** Поле `source_fault_label` не участвует в инференсе, классификации и формировании свидетельств. Доступно только в изолированной исследовательской панели.
2. **Инвариант I2 (Нет скрытых каналов):** Профиль `BASIC` строго фильтрует DataFrame. Исполняемый регрессионный тест `test_hidden_channel_guard_in_basic_profile` доказал: заполнение колонок `CHWC_VLV` и `OA_DMPR` экстремальными значениями (9999.0 и -8888.0) дает побитово идентичный результат с вариантом их полного отсутствия.
3. **Инвариант I3 (Нет Test leakage):** Пороги детектора и веса Decision Layer зафиксированы на обучающих и валидационных сценариях до оценки held-out test.
4. **Инвариант I5 (Абстенция $\neq$ отсутствие тревоги):** Поля `anomaly.status` и `diagnosis.status` строго разделены. При неопределенности причины статус аномалии `DETECTED` сохраняется в неизменном виде.
5. **Инвариант I7 (Нет вымышленных вероятностей):** В интерфейсе скоры четко подписаны как некалиброванные эмпирические баллы.
6. **Инвариант I8 (Domain Guard):** На `SYNTHETIC_DEMO` валидированный ML-вывод штатно блокируется.
7. **Инвариант I9 (Отсутствующий сигнал $\neq 0$):** Отсутствие датчика обратной связи не заменяется нулем, а фиксируется как `missing_measurements: ['CHWC_VLV']`.

---

## 3. Перечень сохраненных скриншотов Playwright

1. `docs/screenshots/stage4_diagnostics_viewport.png`: Вьюпорт 1440x900 страницы «Диагностика» с селектором 5 профилей и карточками статусов.
2. `docs/screenshots/stage4_diagnostics_basic_ambiguity.png`: Режим `BASIC` на сценарии температурного смещения, честный возврат `MULTIPLE_PLAUSIBLE` и отсутствие ложного диагноза.
3. `docs/screenshots/stage4_diagnostics_valve_feedback_single_cause.png`: Переключение на профиль `BASIC_PLUS_VALVE` на сценарии заклинивания клапана — физическое подтверждение `CONFIRMED_BY_FEEDBACK` и статус `SINGLE_CAUSE`.
4. `docs/screenshots/stage4_diagnostics_synthetic_domain_guard.png`: Работа барьера Domain Guard на синтетическом датасете.
5. `docs/screenshots/stage4_diagnostics_research_tables.png`: Научный блок с реальными экспериментальными таблицами Risk–Coverage и ценности каналов.
