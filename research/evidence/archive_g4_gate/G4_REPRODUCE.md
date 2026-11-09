# G4 · Воспроизведение из принятого снимка

1. Проверьте `SHA256SUMS.txt` внутри архива. Сверьте исходные RC2, G2 и G3 с `evidence/input-archives.sha256`. Распакуйте RC2 в новую папку. Примените `overlay/` из G2, затем G3, затем этот G4. Каждый манифест содержит исходный и результирующий SHA для изменённых файлов. Снимки переданы в ZIP и не содержат Git ancestry.
2. Используйте отдельный временный каталог для тестов. Скопируйте туда SQLite и `data/`. Укажите абсолютные `BUILDINGPULSE_AUDIT_SCRATCH` и `DATA_ROOT` для тестовой копии, `DATABASE_URL=sqlite:////absolute/scratch/test.db` и `BUILDINGPULSE_PROTECTED_ROOTS` для защищённых исходных путей через двоеточие. Создайте временный каталог для `TMPDIR` при необходимости. Исходный замороженный Parquet нужен годовому incident endpoint.
3. Установите зависимости из backend requirements, backend requirements-test, contracts requirements-audit, корневого requirements для исследовательских тестов и lock-файла frontend. Запустите проверки из корня распакованного приложения.

```bash
python -m pytest backend/tests contracts/test_evidence_v1.py tests -q
npm --prefix frontend ci
npm --prefix frontend run build
python contracts/check_fixture_types.py
```

4. Запустите FastAPI на 8050 и Vite на 5180 согласно README. Используйте тестовую SQLite. Установите Playwright и Chromium для браузерной проверки.

```bash
PYTHONPATH=. python scripts/smoke_g01_http.py --url http://127.0.0.1:8050 --output /absolute/scratch/http
python scripts/test_playwright_g4.py --url http://127.0.0.1:5180 --output /absolute/scratch/g4
```

Откройте `/incidents` для LBNL. Ссылка «Открыть синтетический эпизод G4» ведёт в изолированное демо. На карточке эпизода переход к подтверждающему отсчёту открывает replay с тем же датасетом и SHA. Повтор запроса отчёта возвращает те же байты.

```text
/api/v1/investigation?dataset_id=demo-g4-mat
/api/v1/investigation?dataset_id=ds_8e5b1ddfdd14&start=2018-01-02T11:08:00
```

Добавьте `&format=html` для HTML. Проверка офлайновых индексов в новом каталоге выполняется командами ниже.

```bash
PYTHONPATH=. python scripts/build_g4_demo.py /absolute/scratch/demo
PYTHONPATH=. python scripts/build_g3_incident_index.py /absolute/scratch/G3_INCIDENT_INDEX.json
```

Сравните demo CSV, манифест и индекс с `contracts/fixtures/g4/`, а два файла G3 с `research/g0-g1/`. В Compose smoke использованы отдельные порты 15205/18075/15455, отдельные имена контейнеров и read-only mount для данных. Этот локальный override лежит в `evidence/compose.g4.yml`. В конфигурации PostgreSQL использован временный том.
