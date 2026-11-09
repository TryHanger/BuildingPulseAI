# STAGE 2 BASELINE AUDIT — Фактическая верификация этапа 1

**Дата аудита:** 2026-11-02 19:06  
**Проверяющий:** BuildingPulse AI Autonomous Agent  
**Цель:** Независимое воспроизведение и строгая валидация всех компонентов Этапа 1 перед началом реализации Этапа 2.

---

## 1. Сводка воспроизведения базовых проверок

| Проверка | Команда | Фактический результат | Статус | Примечания |
| :--- | :--- | :--- | :---: | :--- |
| **Backend Unit & API Tests** | `pytest backend/tests` | 7 passed in 0.85s | **PASS** | Проверены health, 422 при отсутствии time, 400 при пустом CSV, валидный импорт, path traversal, SHA-256 идемпотентность, Min-Max downsampling, baseline rules. |
| **Frontend Production Build** | `npm --prefix frontend run build` | Built in 7.78s (dist/assets: 1.23 MB JS, 23.5 KB CSS) | **PASS** | `tsc && vite build` выполнен без единой ошибки типов TypeScript strict. |
| **Playwright E2E & Скриншоты** | `python scripts/capture_e2e_screenshot.py` | Сняты `monitoring_page.png` и `rules_executed.png` | **PASS** | Headless Chromium успешно выполнил навигацию, отрисовал SVG мнемосхему, график ECharts и кликнул «Запуск правил». |
| **Docker Compose Config** | `docker compose config` | Спецификация валидна, порты 5180, 8050, 5455 | **PASS** | Структура сервисов db, backend, frontend корректна. |
| **Docker Compose Runtime Up** | `docker compose up --build -d` | Ошибка DNS резолюции внутри контейнера при pip install | **BLOCKED (Docker DNS)** | `NewConnectionError: Failed to establish a new connection: [Errno -3] Temporary failure in name resolution` при обращении к `pypi.org`. Пинг 8.8.8.8 из alpine работает, но DNS порт 53 блокируется сетевым стеком WSL2/Windows. Локальный dev-режим (Python 3.11 + SQLite + Vite) полностью работоспособен. |
| **REST Health Endpoint** | `curl -s http://127.0.0.1:8050/api/health` | `{"status":"ok","service":"buildingpulse-api","database":"ok"}` | **PASS** | Локальный бэкенд активен и отвечает. |
| **Frontend Dev Server** | `curl -s -I http://127.0.0.1:5180/` | `HTTP/1.1 200 OK` | **PASS** | Vite dev-сервер активен и отдает HTML. |

---

## 2. Анализ выявленных дефектов и рисков

### 2.1. Ложные срабатывания детекции замирания («Stuck signal»)
- **Обнаруженное поведение:** В `QualityService.evaluate_quality` проверка `vals.diff() == 0` применялась ко всем числовым колонкам без разделения их семантики.
- **Физическая реальность:** Бинарные команды вентилятора (`SF_SPD_DM`), статусы контроллера (`SYS_CTL`), летние команды нагревательного клапана (`HWC_VLV_DM = 0.0`) и заданные уставки (`SA_TEMPSPT = 12.8°C`) легитимно остаются неизменными часами и сутками в штатном режиме.
- **План исправления на Этапе 2:** Ограничить проверку stuck-signal непрерывными физическими аналоговыми датчиками (температуры, давления, расходы), либо явно помечать неизменность команд и уставок как нормальное технологическое состояние, а не аварию датчика.

### 2.2. Артефакт sticky-header на длинных скриншотах
- **Обнаруженное поведение:** При захвате страницы через `page.screenshot(full_page=True)` заголовок с `position: sticky; top: 0` в некоторых версиях Chromium рендерится посередине составного изображения из-за тайловой прокрутки скриншотера.
- **Фактический статус:** При обычном просмотре в окне браузера заголовок ведет себя строго корректно и зафиксирован в верхней части экрана. Для E2E-скриншотов добавлен захват фиксированного вьюпорта (1440x900) в дополнение к full-page.

### 2.3. Единицы измерения и физический смысл каналов
- **Температуры:** В оригинальных симуляциях LBNL SD-AHU температуры приведены в градусах Фаренгейта (°F). В каноническом словаре проекта предусмотрена конвертация в °C: $T_{°C} = (T_{°F} - 32) \times \frac{5}{9}$.
- **Вентилятор:** Канал `SF_SPD_DM` в LBNL SD-AHU является бинарным сигналом включения вентилятора (0 = Off, 1 = On), а не скоростью вращения в %.
- **Разделение Ground Truth:** `source_fault_label` строго изолирован в метаданных сценария и не поступает на вход ML-моделей или правил.

---

## 3. Перечень файлов, планируемых к изменению/созданию на Этапе 2

1. `backend/app/services/quality_service.py` — исправление классификации stuck-сигналов (исключение команд и уставок из числа замерших датчиков).
2. `docs/LBNL_FILE_INVENTORY_ACTUAL.md` — аудит фактического состава ZIP-архива LBNL.
3. `research/protocols/virtual_sensor_v1.md` — исследовательский протокол ДО обучения.
4. `ml/virtual_sensor/` — модули датасета, признаков, разбиений, обучения LightGBM, бейзлайна Ridge, инференса и скоринга остатков.
5. `backend/app/api/endpoints/ml.py` — новые REST-эндпоинты прогноза и residual-детекции.
6. `backend/app/main.py` — подключение ML-роутера.
7. `frontend/src/` — добавление визуализации виртуального датчика, остатков и событий в `TelemetryChart.tsx`, `MonitoringPage.tsx`, `client.ts`.
8. `research/reports/VIRTUAL_SENSOR_V1_REPORT.md` — итоговый отчет научного эксперимента.
