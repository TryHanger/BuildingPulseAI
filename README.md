# BuildingPulse AI

> **Интеллектуальная система анализа данных инженерных систем зданий (AHU)**
> Дипломный проект: разработка веб-платформы диагностики вентиляционных установок, исследования достаточности диагностических свидетельств и локализации неисправностей при ограниченной наблюдаемости.

---

## Архитектура системы (Этап 1: Фундамент)

- **Frontend:** React 18, TypeScript (strict), Vite, Tailwind CSS, Apache ECharts.
- **Backend:** Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2.0, Uvicorn.
- **Хранилище телеметрии:** Apache Parquet (колоночное сжатие, чтение через PyArrow / Pandas).
- **Хранилище метаданных:** SQLite (локальный автономный режим) / PostgreSQL 16 (Docker Compose).
- **Изолированные порты:** `WEB_PORT=5180`, `API_PORT=8050`, `DB_PORT=5455` (настроены в `.env` во избежание конфликтов).

---

## Публичный baseline Stage13

[Происхождение, исходные данные и воспроизведение](docs/GITHUB_STAGE13_BASELINE.md).

## Быстрый запуск

### Вариант А: Локальный запуск (быстрый dev-режим)

1. **Клонируйте репозиторий и настройте `.env`:**
   ```bash
   cp .env.example .env
   ```

2. **Запустите генерацию демонстрационного набора:**
   ```bash
   python scripts/make_synthetic_demo.py
   ```
   *(Опционально: загрузить реальный 7-дневный срез LBNL:)*
   ```bash
   python scripts/import_lbnl.py --remote-file AHU_annual.csv --days 7
   ```

3. **Запустите Backend API (порт 8050):**
   ```bash
   python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8050
   ```

4. **Запустите Frontend (порт 5180):**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   Откройте в браузере: `http://localhost:5180`

---

### Вариант Б: Запуск в Docker Compose

Перед запуском скопируйте `.env.example` в `.env` и задайте локальный `POSTGRES_PASSWORD`.

```bash
docker compose up --build
```
- Frontend доступен: `http://localhost:5180`
- Backend API доступен: `http://localhost:8050`
- Swagger OpenAPI документация: `http://localhost:8050/docs`

---

## Скрипты работы с данными

1. **Генерация реалистичного синтетического демо:**
   ```bash
   python scripts/make_synthetic_demo.py
   ```
2. **Импорт официального симуляционного датасета LBNL SD-AHU:**
   ```bash
   # Потоковый импорт среза через HTTP Range (без скачивания 600 МБ архива):
   python scripts/import_lbnl.py --remote-file AHU_annual.csv --days 14
   
   # Из локального файла:
   python scripts/import_lbnl.py --local-file path/to/file.csv
   ```
3. **CLI инспекция датасетов (CSV / Parquet):**
   ```bash
   python scripts/inspect_dataset.py data/processed/sc_d11cbb117b57_lbnl_AHU_annual.csv.parquet
   ```

---

## Тестирование и воспроизведение научных экспериментов

```bash
# 1. Запуск тестов бэкенда (API, валидация CSV, Parquet, Downsampling, Rules, Diagnostics):
pytest backend/tests

# 2. Сборка и typecheck фронтенда (React strict + TypeScript):
cd frontend
npm run build
cd ..

# 3. Воспроизведение многосезонного эксперимента виртуального датчика:
python -m ml.virtual_sensor.evaluate_multiseason

# 4. Воспроизведение классификации семейств дефектов (Scenario-Level Split):
python -m ml.diagnostics.evaluate_fault_families

# 5. Браузерный E2E тест со снятием скриншотов (Playwright):
python scripts/capture_e2e_screenshot.py
```

---

## Примеры вызова REST API

- **Проверка здоровья сервиса:**
  ```bash
  curl http://127.0.0.1:8050/api/health
  ```
- **Список доступных сценариев:**
  ```bash
  curl http://127.0.0.1:8050/api/scenarios
  ```
- **Сводная диагностика сценария (детекция, локализация, свидетельства, Domain Guard):**
  ```bash
  curl "http://127.0.0.1:8050/api/diagnostics/summary?scenario_id=sc_bd7fe667fc33&model_id=vs-sa-temp-v2"
  ```
- **События диагностики сценария:**
  ```bash
  curl "http://127.0.0.1:8050/api/diagnostics/events?scenario_id=sc_bd7fe667fc33"
  ```
- **Каналы сценария:**
  ```bash
  curl "http://127.0.0.1:8050/api/sensors?scenario_id=sc_bd7fe667fc33"
  ```
- **Запрос телеметрии с серверным Min-Max downsampling (1500 точек):**
  ```bash
  curl "http://127.0.0.1:8050/api/telemetry?scenario_id=sc_bd7fe667fc33&channels=SA_TEMP,MA_TEMP,CHWC_VLV_DM&max_points=1500"
  ```
- **Отчет о качестве данных (разрывы, дубли, монотонность, замирание):**
  ```bash
  curl "http://127.0.0.1:8050/api/data-quality?scenario_id=sc_bd7fe667fc33"
  ```

---

## Документация проекта

- `docs/STATE.md` — Текущее состояние и проверенные факты.
- `docs/DECISIONS.md` — Архитектурные и научные решения (Parquet, Domain Guard, Scenario-level Split).
- `docs/NEXT_STEPS.md` — Очередь задач (переход к Этапу 4).
- `docs/STAGE3_BASELINE_AUDIT.md` — Результаты аудита и устранения дефектов Stage 2.
- `docs/DATA_DICTIONARY.md` — Словарь канонических каналов AHU (30 точек).
- `docs/DATASET_MANIFEST.md` — Паспорт датасетов (LBNL SD-AHU, Synthetic Demo).
- `docs/TEST_REPORT.md` — Отчет о прогоне автоматических тестов.
- `research/protocols/stage3_multiseason_and_fault_baselines.md` — Пререгистрированный протокол Stage 3.
- `research/reports/STAGE3_MULTI_SEASON_REPORT.md` — Отчет по многосезонному виртуальному датчику.
- `research/reports/STAGE3_FAULT_FAMILY_BASELINES.md` — Отчет по классификации семейств дефектов.
- `research/runs/` — Воспроизводимые JSON-манифесты запусков.
- `docs/screenshots/` — Скриншоты интерфейса мониторинга и диагностики.
