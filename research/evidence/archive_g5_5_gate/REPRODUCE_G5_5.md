# G5.5 · Воспроизведение

Из распакованного архива выполните `sha256sum -c SHA256SUMS.txt`. Используйте принятую основу `BUILDINGPULSE_G5_4_GATE_REVIEW.zip`, SHA-256 `edebf001020e5ddd13efb76c046e2c22a99ac10ae5819d04a3d3fd0b702b3417`. В отдельной восстановленной рабочей копии G5.4 примените `git apply --check /review/G5_5.patch`, затем `git apply /review/G5_5.patch` или скопируйте `overlay/` в корень. Для каждого изменённого файла MANIFEST приводит SHA принятой основы и G5.5.

Скрипт инвентаризации принимает каталог оригинального проекта, где лежат исходные ZIP G5.2 и G5.3 и каталог `data/raw`. Он читает только заголовки G36 и RBC-Nesbitt вмешательств, схемы CSIRO Parquet, заголовок LBNL и значения трёх температур в двух номинальных RBC-Nesbitt файлах.

```sh
python research/g55/SOURCE_AUDIT_G5_5.py /original /scratch/source-headers.json
cmp /scratch/source-headers.json /review/evidence/source-headers.json
```

Для продуктовых проверок возьмите те же G36-1wk/5wk CSV, что в G5.4. Пути членов и SHA в принятых манифестах и `evidence/source-receipts.sha256`. Установите зависимости как в G5.4. Для backend тестов задайте `BUILDINGPULSE_AUDIT_SCRATCH`, `BUILDINGPULSE_PROTECTED_ROOTS`, `DATABASE_URL` на доступную для записи временную копию SQLite и `DATA_ROOT` на отдельную временную копию данных. Оригинальные данные и SQLite остаются защищёнными.

```sh
python -m pytest backend/tests contracts/test_evidence_v1.py tests -q
npm --prefix frontend run build
python -m openapi_spec_validator contracts/openapi-v1.yaml
python contracts/check_fixture_types.py
```

Запустите FastAPI на 8050 и Vite на 5180 с `VITE_API_URL=http://127.0.0.1:8050`, затем:

```sh
PYTHONPATH=. python scripts/smoke_g01_http.py --url http://127.0.0.1:8050 --output /scratch/http
python scripts/test_playwright_g54.py --url http://127.0.0.1:5180 --output /scratch/screenshots
python scripts/test_playwright_g36.py --url http://127.0.0.1:5180 --output /scratch/screenshots
```

В `evidence/http-*.json` сохранены окна NOMINAL BASIC, VALVE_CLOSED BASIC direct seek и VALVE_CLOSED EXTRA_SIMULATED tail. Вызовы приведены в `evidence/http-g55.log`. После удаления трёх новых полей окна и флага `source_oracle_status` ответы совпадают с одноимёнными JSON G5.4. Для G36-5wk сравните `/api/v1/g36-benchmark/comparison` с принятым `G36_5WK_COMPARISON.json`.

```sh
docker build -t buildingpulse-g55-review:local -f backend/Dockerfile .
docker run --rm \
  --mount "type=bind,src=$DATA_ROOT,dst=/app/data,readonly" \
  --mount "type=bind,src=/scratch/docker-fixtures,dst=/g55-fixtures,readonly" \
  -e DATABASE_URL=sqlite:////tmp/g55.db -e DATA_ROOT=/app/data \
  buildingpulse-g55-review:local sh -c \
  'cp /g55-fixtures/input.sqlite3 /tmp/g55.db && exec python scripts/smoke_g01_container.py --g54'
```

В каталоге fixtures требуется отдельная копия SQLite принятой основы с существующими данными G0–G5.
