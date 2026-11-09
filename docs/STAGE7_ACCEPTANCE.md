# STAGE 7 — МАТРИЦА ФИНАЛЬНОЙ ПРИЁМКИ (ACCEPTANCE MATRIX)

- **Дата фиксации приёмки:** 2026-11-03
- **Итоговый вердикт проекта:** `ACCEPTED_WITH_LIMITATIONS` (Техническая и научно-методологическая готовность дипломного прототипа подтверждена; ограничения честно задокументированы).
- **Стек исполнения:** Python 3.11.6, FastAPI 0.115.6, React 18, TypeScript (strict), Vite, Tailwind CSS, Apache ECharts, PyArrow 19.0.1, LightGBM 4.6.0, Scikit-learn 1.8.0.

---

## 1. Фактическая матрица приёмки Gates 0–7

| Gate | Наименование и цель | Статус | Фактические доказательства и метрики | Ссылки на артефакты |
| :---: | :--- | :---: | :--- | :--- |
| **Gate 0** | **Научный аудит Stage 6:** устранение противоречий C2, знаков bias, аудит гипотез H4a–c и CHW | **PASS** | Коэффициенты C2 подтверждены ($y = 2.0138 x - 10.1104$, численная невязка $0.00^\circ\text{C}$). H4b официально переквалифицирована в `NOT_SUPPORTED`. H4c квалифицирована как `PARTIALLY_SUPPORTED_WITH_LOW_SENSITIVITY`. Сформирована факторная матрица 2×2. Закрыта уязвимость path traversal в API. | `docs/STAGE7_STAGE6_SCIENCE_AUDIT.md`<br>`research/runs/stage7_stage6_reproduction.json`<br>`research/reports/STAGE7_STAGE6_CORRECTIONS_ADDENDUM.md`<br>`backend/tests/test_stage7_science_regressions.py` (5/5 PASS)<br>`docs/STAGE7_MODEL_CARDS.md` |
| **Gate 1** | **Аудит итогов H1–H3 и научный корпус:** фиксация единой матрицы гипотез без сокрытия отрицательных результатов | **PASS** | H1: Selective Risk снижен с 55.6% до 29.4% при cov $\approx 42\%$. H2: прирост F1 от клапана +15.26 pp (с 0.5196 до 0.6722). H3: рекомендатель превзошел Random (+7.91 pp, $p < 0.05$), но равен Fixed ($0.6722 \equiv 0.6722$). Все 6 гипотез сверены по манифестам. | `research/runs/stage7_final_scientific_summary.json`<br>`research/reports/STAGE7_FINAL_SCIENTIFIC_SUMMARY.md` |
| **Gate 2** | **Надежность продукта и данных:** безопасность API, защита от утечек, Domain Guard, обработка аномалий | **PASS** | Закрыт path traversal в `/api/adaptation/runs/{run_id}` и `/api/adaptation/predictions`. Проверена защита целевой переменной $SA\_TEMP$. Исключен таргет-лик в CSIRO ($MA\_TEMP \equiv SA\_TEMP$). Внедрен статус `LOCALLY_EVALUATED: REGRESSION_ONLY`. | `backend/app/api/endpoints/adaptation.py`<br>`backend/app/services/adaptation_service.py`<br>`backend/app/schemas/adaptation.py` |
| **Gate 3** | **UI/UX: финальная демонстрационная версия:** разрыв ночей на графике, динамическая формула C2, честные статусы H4 | **PASS** | В ECharts устранены фиктивные ночные диагонали (`connectNulls: false` + вставка точек разрыва в нерабочие часы). Добавлен `markArea` для 34 инъекций. Формула C2 подгружается динамически из метаданных. Бейджи версий обновлены до `v0.7-stage7`. Сняты 6 скриншотов Playwright. | `frontend/src/pages/ResearchPage.tsx`<br>`frontend/src/pages/MonitoringPage.tsx`<br>`frontend/src/pages/DiagnosticsPage.tsx`<br>`docs/screenshots/stage7_*.png` (6 файлов) |
| **Gate 4** | **Развертывание и воспроизводимость:** автономный запуск, диагностика окружения, воспроизведение раннеров | **PASS** | Автономный запуск в нативном стеке (FastAPI + React + SQLite) подтвержден. Создан скрипт проверки `scripts/verify_environment.py` (100% PASS). Создан единый раннер `scripts/reproduce_research.py` (все 3 пайплайна PASS). Зафиксирована точная причина сбоя Docker (истекший сертификат / временной рассинхрон Swarm TLS). | `scripts/verify_environment.py`<br>`scripts/reproduce_research.py`<br>`docs/STAGE7_PRODUCT_ARCHITECTURE_REPORT.md` |
| **Gate 5** | **Пакет для диплома:** технический и научный отчеты, сценарий защиты на 5-7 мин, структура диплома | **PASS** | Подготовлены 4 самостоятельных документа: архитектурный отчет, научный отчет, поминутный сценарий защиты и структура дипломного текста с доказательными ответами на 10 типовых вопросов комиссии. | `docs/STAGE7_PRODUCT_ARCHITECTURE_REPORT.md`<br>`research/reports/STAGE7_FINAL_SCIENTIFIC_REPORT.md`<br>`docs/STAGE7_DEMO_SCRIPT.md`<br>`docs/STAGE7_THESIS_OUTLINE.md` |
| **Gate 6** | **Комплексное тестирование:** регрессионный сьют pytest, typecheck TypeScript, Playwright E2E | **PASS** | Pytest: **76 из 76 тестов PASS (100%)**. Сборка TypeScript: **0 ошибок типов**. Playwright: 6 E2E скриншотов зафиксированы. | `docs/TEST_REPORT.md` (актуализирован)<br>Логи запусков тестов |
| **Gate 7** | **Приёмка и рабочая память:** актуализация документации проекта, передача контекста | **PASS** | Созданы `docs/STAGE7_ACCEPTANCE.md`, `docs/STAGE7_HANDOFF.md`. Актуализированы `docs/STATE.md`, `docs/DECISIONS.md`, `docs/NEXT_STEPS.md`. Никаких `git commit`, `push`, `deploy` без разрешения не выполнялось. | `docs/STATE.md`<br>`docs/DECISIONS.md`<br>`docs/NEXT_STEPS.md`<br>`docs/STAGE7_HANDOFF.md` |

---

## 2. Честно зафиксированные открытые риски и ограничения

1. **Ограниченность одним реальным объектом (CSIRO AHU9):**
   Все выводы доменной адаптации H4 получены на одной приточной установке с водяным охлаждением в климате Ньюкасла. Перенос на установки с VAV-регулированием расхода или рекуперацией требует отдельной локальной валидации.
2. **Низкая чувствительность детектора к умеренным дефектам при жестком бюджете ложных тревог (H4c):**
   При соблюдении эксплуатационного бюджета ложных тревог ($\le 5\%$, факт 2.8%) скалярная невязка виртуального датчика надежно детектирует только катастрофические аварии (88% stuck valve, recall 25%), пропуская умеренные заклинивания 25–75%.
3. **Docker Swarm TLS рассинхрон:**
   Локальный Docker Desktop имеет системное предупреждение об истечении сертификата Swarm TLS и временном сдвиге, из-за чего сборка образов через внешний интернет нестабильна. Нативный запуск (Python 3.11 + SQLite + Vite) функционирует безотказно и полностью покрывает демонстрацию.
