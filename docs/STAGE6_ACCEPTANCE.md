# STAGE 6 — МАТРИЦА ПРИЁМКИ И ВЕРИФИКАЦИИ (ACCEPTANCE MATRIX)

- **Дата верификации:** 2026-11-03
- **Тема этапа:** Адаптация виртуального датчика и диагностического контура к реальной AHU CSIRO (Gates 0–7)
- **Итоговый статус:** **COMPLETE (ВСЕ GATES 0–7 УСПЕШНО ВЫПОЛНЕНЫ И ПРИНЯТЫ)**

---

## 1. Сводная таблица выполнения Gates 0–7

| Gate | Наименование контрольного рубежа | Статус | Подтверждающие артефакты и ключевые факты |
| :--- | :--- | :---: | :--- |
| **Gate 0** | Физический аудит CSIRO и репродуцируемость Stage 5 | **PASS** | `docs/STAGE6_BASELINE_AUDIT.md`, `docs/STAGE6_CSIRO_SIGNAL_MAPPING.md`, `research/runs/stage6_zero_shot_reproduction.json`, `backend/tests/test_stage6_mapping.py` (4 теста PASS). Доказано аппаратное равенство $T_{ma} \equiv T_{sa}$ во всех 457k строках; выявлены 54 эксперимента вместо 7. |
| **Gate 1** | Предрегистрация протокола H4 и строгий временной сплит | **PASS** | `research/protocols/stage6_csiro_adaptation_protocol.md`, `research/splits/stage6_csiro_split.json`, `ml/adaptation/splits.py`, `ml/adaptation/data.py`, `backend/tests/test_stage6_splits.py` (5 тестов PASS). Нулевое пересечение индексов, защита embargo 60 мин вокруг аварий, zero test leakage. |
| **Gate 2** | Реализация семейства локальных калибраторов (C1, C2, A1, L1, L2) | **PASS** | `ml/adaptation/calibrators.py`, `ml/adaptation/train.py`, `models/csiro-ahu9-*_v1.joblib`, `models/csiro-ahu9-*_metadata.json`, `research/runs/stage6_csiro_adaptation_train.json`, `docs/STAGE6_MODEL_CARD.md`. Обучены строго на 1 588 чистых точках Train Local; исходные модели LBNL не перезаписаны. |
| **Gate 3** | Оффлайн-эксперимент на независимом отложенном тесте | **PASS** | `ml/adaptation/evaluate_csiro_adaptation.py`, `research/runs/stage6_csiro_adaptation_eval.json`, `research/reports/STAGE6_CSIRO_ADAPTATION_REPORT.md`, 3 графика в `research/figures/stage6_*.png`. C2 Affine снизил MAE с 4.46 °C до 1.11 °C (-75.2%); ложные тревоги снижены со 100% до 2.8% при сохранении детекции заклинивания клапана. |
| **Gate 4** | Серверная интеграция REST API и модель доменных статусов | **PASS** | `backend/app/schemas/adaptation.py`, `backend/app/services/adaptation_service.py`, `backend/app/api/endpoints/adaptation.py`, `backend/app/api/router.py`, `backend/tests/test_adaptation_api.py` (5 тестов PASS). Эндпоинты `/api/adaptation/*`, строгий статус `LOCALLY_EVALUATED` без ложных аварийных классов. |
| **Gate 5** | Пользовательский интерфейс: наглядное «до/после» для CSIRO | **PASS** | `frontend/src/pages/ResearchPage.tsx`, `frontend/src/api/client.ts`, `frontend/src/types/api.ts`. Подраздел «Локальная адаптация», селектор 6 моделей, интерактивный график ECharts, таблица 7 стратегий, баннеры ограничений. Сборка `npm run build` (0 ошибок), 3 E2E скриншота Playwright в `docs/screenshots/stage6_*`. |
| **Gate 6** | Комплексное тестирование, регрессия и отрицательные проверки | **PASS** | `backend/tests/test_stage6_negative_controls.py` (6 тестов PASS). Полный сьют `pytest backend/tests` — **71 из 71 тестов PASS (100%)**. Проверена неизменность хэшей Stage 5, защита от отсутствующих каналов и деления на ноль. |
| **Gate 7** | Научная интерпретация, готовность к защите диплома | **PASS** | `research/reports/STAGE6_CSIRO_ADAPTATION_REPORT.md`, `docs/STAGE6_TEST_REPORT.md`, обновлены `docs/STATE.md`, `docs/DECISIONS.md`, `docs/NEXT_STEPS.md`. Честное описание компромисса чувствительности/ложных тревог и границ применимости. |

---

## 2. Итоговые численные результаты на Held-Out Test (N=1,074 чистых точек)

| Метрика | Исходный LBNL Zero-Shot (Z0) | Адаптированный C2 (Affine) | Локальный L2 (LightGBM) | Итоговый научный эффект |
| :--- | :---: | :---: | :---: | :--- |
| **MAE ошибки** | **4.4552 °C** | **1.1062 °C** | **1.2703 °C** | **Снижение ошибки на 75.2%** (в 4.0 раза) |
| **RMSE ошибки** | **4.7334 °C** | **1.6661 °C** | **1.8230 °C** | **Снижение среднеквадратичной ошибки на 64.8%** |
| **Систематический сдвиг** | **+4.4552 °C** | **+0.3260 °C** | **-0.0631 °C** | Полное устранение климатического смещения |
| **Коэффициент $R^2$** | **-3.3026** | **+0.4669** | **+0.3618** | Восстановление предсказательной силы |
| **Ложные тревоги в норме (3$\sigma$)** | **100.0%** (лавина) | **2.8%** | **4.4%** | **Соблюдение бюджета ложных тревог ($\le 5\%$)** |
| **CHW Valve Stuck Recall** | **0.0%** (при 3$\sigma$) | **25.0%** | **25.0%** | Детекция грубых дефектов сохранена |

---

## 3. Подтверждение соблюдения ограничений проекта

1. **Запрет несанкционированных действий:** `git commit`, `git push`, `git merge`, deploy не выполнялись.
2. **Изоляция других агентов:** Никаких сторонних LLM-делегатов не привлекалось.
3. **Сохранность артефактов 1–5:** Все исходные модели LBNL (`vs-sa-temp-v1`, `vs-sa-temp-v2`, `classifier_*.joblib`) и их манифесты остались нетронутыми (подтверждено криптографическими хэшами SHA-256).
4. **Защита от утечек:** Целевая переменная $SA\_TEMP$ и метки аварий ни в одной модели не использовались в качестве входных признаков.
5. **Stage 7:** Работы по Stage 7 не начинались.
