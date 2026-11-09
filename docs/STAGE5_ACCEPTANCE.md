# STAGE 5 ACCEPTANCE — Матрица приёмки и научные результаты Этапа 5

- **Проект:** BuildingPulse AI
- **Тема диплома:** «Разработка интеллектуальной системы анализа данных инженерных систем зданий»
- **Статус этапа:** **ПРИНЯТ (ВСЕ GATE A–G ВЫПОЛНЕНЫ В ПОЛНОМ ОБЪЁМЕ)**
- **Дата:** 2026-11-03

---

## 1. Сводная матрица критериев готовности (Gate A–G)

| Gate | Требование мастер-промпта Stage 5 | Статус | Подтверждающие артефакты и тесты |
| :--- | :--- | :---: | :--- |
| **Gate A** | Независимый аудит Stage 4 и исправление физического опровержения (Dynamic Excitation $\Delta \text{cmd} \ge 0.15$, Stuck vs Leakage, симметрия H1/H2) | **ПРИНЯТО** | `docs/STAGE5_STAGE4_SCIENCE_AUDIT.md`, `ml/diagnostics/evidence.py`, `backend/tests/test_physical_refutation_regression.py` (6/6 PASS) |
| **Gate B** | Предрегистрация протокола H3 (Frozen Protocol, Budget $\Delta K=1$, Candidate Set, критерий $\Delta \text{SelectiveRisk}$, отрицательный контроль) | **ПРИНЯТО** | `research/protocols/stage5_sensor_recommendation_protocol.md` |
| **Gate C** | Реализация `SensorRecommendationService` и REST API (`/api/sensors/recommend`, `/api/diagnostics/recommendable-channels`, эндпоинты саммари) | **ПРИНЯТО** | `ml/diagnostics/recommender.py`, `backend/app/api/endpoints/recommendations.py`, `backend/tests/test_recommendations.py` (7/7 PASS) |
| **Gate D** | Эксперимент H3 на $N=7$ независимых тестовых сценариях (18 480 точек), сравнение Random vs Fixed vs Validation-based | **ПРИНЯТО** | `ml/diagnostics/evaluate_stage5_recommendations.py`, `research/runs/stage5_recommendation_eval.json`, `research/reports/STAGE5_RECOMMENDATION_REPORT.md`, 3 графика |
| **Gate E** | Интеграция телеметрии реального здания CSIRO AHU9 (10 МБ parquet), проверка доменного переноса, активация `Domain Guard` | **ПРИНЯТО** | `docs/EXTERNAL_DATASET_COMPATIBILITY.md`, `scripts/import_csiro.py`, `ml/diagnostics/evaluate_csiro_transfer.py`, `research/runs/stage5_external_validation.json`, `research/reports/STAGE5_EXTERNAL_VALIDATION_REPORT.md` |
| **Gate F** | Разработка полноценного экрана «Исследования» (ResearchPage, 5 научных вкладок, интеграция в шапку и экран «Диагностика») | **ПРИНЯТО** | `frontend/src/pages/ResearchPage.tsx`, `frontend/src/pages/DiagnosticsPage.tsx`, `frontend/src/pages/MonitoringPage.tsx`, `npm run build` (0 ошибок) |
| **Gate G** | Автоматические тесты гигиены экспериментов, 51/51 Pytest PASS, Playwright E2E скриншоты, обновление документации | **ПРИНЯТО** | `backend/tests/test_stage5_experiment_hygiene.py`, 5 скриншотов в `docs/screenshots/stage5_*`, `docs/STATE.md`, `docs/DECISIONS.md`, `docs/TEST_REPORT.md` |

---

## 2. Ключевые научные результаты Stage 5

### Гипотеза H1 (Снижение селективного риска Decision Layer):
- На базовом профиле `BASIC` (19 каналов BMS) при целевом охвате Coverage $\approx 0.40$ Decision Layer обеспечивает селективный риск **0.294**, что в 1.9 раза надежнее эвристических бейзлайнов B1 (0.556) и B2 (0.554).
- При Coverage $\approx 0.60$ риск составляет **0.361** (против 0.547 у B1). При этом Decision Layer честно удерживает 28.6% неопределенности (`UNRESOLVED`) и 11.2% неоднозначности (`MULTIPLE_PLAUSIBLE`), отказываясь делать ложные угадывания без физических свидетельств.

### Гипотеза H2 (Физическая ценность датчика штока клапана):
- Добавление единственного канала обратной связи штока охлаждающего клапана ($CHWC\_VLV$) повышает Macro F1 классификатора семейств с **0.5196** (Basic) до **0.6722** (**+15.26 п.п.**).
- При этом селективный риск при охвате 60% падает с 0.361 до **0.195**, а точность изоляции дефекта смещения датчика приточной температуры возрастает почти в 3 раза (F1 с 0.1886 до 0.5396) за счет физического опровержения механического заклинивания.

### Гипотеза H3 (Валидационно-обоснованный рекомендатель датчиков):
В условиях бюджетного ограничения $\Delta K = 1$ канал из пространства кандидатов $\{CHWC\_VLV, OA\_DMPR\}$:
- **Baseline (Basic, 19 ch):** Macro F1 = **0.5196**;
- **Random Strategy (5 seeds):** Macro F1 = **$0.5931 \pm 0.0015$**;
- **Fixed Heuristic (`CHWC_VLV`):** Macro F1 = **0.6722** (+15.26 п.п. к Basic);
- **Validation-Based Recommender (H3):** Macro F1 = **0.6722** (**+15.26 п.п.** к Basic, **+7.91 п.п.** к Random, статистически значимо $p < 0.05$);
- **Infeasible Oracle Upper Bound:** Macro F1 = **0.6969** (+17.73 п.п. к Basic).

*Научный вывод H3:* Предрегистрационный отбор канала по критерию снижения селективного риска на валидации ($V_{\text{valve}} = 0.203 \gg V_{\text{damper}} = 0.021$) строго превосходит случайный выбор на 7.91 п.п. и воспроизводит результат фиксированной экспертной эвристики, гарантируя защиту от утечки тестовых данных (zero test leakage).

### Внешняя валидация на реальном здании (CSIRO AHU9 Transferability):
- При прямом инференсе виртуального датчика `vs-sa-temp-v2`, обученного на симуляции EnergyPlus, на реальную австралийскую установку полевого BMS (сценарий `sc_89e2c6028b4f`, 7 666 минутных точек) зафиксирован **катастрофический негативный трансфер**:
  - MAE = **4.47 °C** (против 0.039 °C на LBNL);
  - Коэффициент детерминации $R^2 = \mathbf{-1.92}$ (модель хуже тривиального предсказания среднего);
  - Ложные тревоги на нормальном интервале: **98.6% времени работы**.
- *Научный вывод:* Прямой перенос тепловых моделей с виртуальных симуляций на реальные здания без локальной докалибровки принципиально недопустим из-за различий аэродинамики, тепловых инерций и характеристик змеевиков.
- Разработанный защитный механизм **Domain Guard** доказал свою необходимость: система корректно переходит в режим `OUT_OF_DOMAIN_UNVALIDATED`, блокируя ложные диагностические заключения.

---

## 3. Список зафиксированных артефактов Stage 5

### Backend & ML модули:
- `ml/diagnostics/recommender.py`: Движок рекомендаций датчиков с проверкой динамического возбуждения и анти-утечкой.
- `ml/diagnostics/evaluate_stage5_recommendations.py`: Скрипт экспериментального прогона H3.
- `ml/diagnostics/evaluate_csiro_transfer.py`: Скрипт экспериментального аудита переноса на CSIRO AHU9.
- `scripts/import_csiro.py`: Конвертер и импортер австралийской полевой телеметрии.
- `backend/app/schemas/recommendations.py`: Pydantic схемы API.
- `backend/app/api/endpoints/recommendations.py`: REST эндпоинты рекомендатора и научных манифестов.

### Тестовый сьют:
- `backend/tests/test_physical_refutation_regression.py` (6 тестов)
- `backend/tests/test_recommendations.py` (7 тестов)
- `backend/tests/test_stage5_experiment_hygiene.py` (4 теста)
- Суммарно: **51 тест Pytest (100% PASS)**.

### Frontend:
- `frontend/src/pages/ResearchPage.tsx`: Экран «Исследования» (5 вкладок).
- `frontend/src/pages/DiagnosticsPage.tsx`: Кнопка «Какое измерение поможет?» с вызовом H3 рекомендатора.
- `frontend/src/pages/MonitoringPage.tsx` & `frontend/src/App.tsx`: Трехстраничная навигация и бейдж `v0.5-stage5`.
- Сборка Vite: 0 ошибок TypeScript.

### Скриншоты Playwright E2E:
- `docs/screenshots/stage5_research_overview.png`
- `docs/screenshots/stage5_research_risk_coverage.png`
- `docs/screenshots/stage5_research_recommender.png`
- `docs/screenshots/stage5_research_real_building.png`
- `docs/screenshots/stage5_diagnostics_recommender_action.png`
