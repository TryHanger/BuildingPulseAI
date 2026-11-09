# Воспроизведение BP-ML-REPRO-02

## Применить код

Распакуйте архив как `/review` и выполните `(cd /review && sha256sum -c SHA256SUMS.txt)`. В существующей рабочей копии восстановите принятые G6.0 и REPRO-01 по их patch/overlay и инструкциям. Идентификаторы и контрольные суммы приведены в MANIFEST.json. Используйте изолированную копию проекта.

```sh
git apply --check /review/BP_ML_REPRO_02.patch
git apply /review/BP_ML_REPRO_02.patch
python3.12 -m venv /scratch/repro02-venv
. /scratch/repro02-venv/bin/activate
python -m pip install -r backend/requirements.txt -r research/ml_reproduction/requirements-run.txt \
  scipy==1.18.1 fastapi==0.162.0 pydantic==2.14.3 uvicorn==0.54.0 pytest==9.2.0 httpx==0.28.1 playwright==1.64.1
npm --prefix frontend ci
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=4
```

## Открыть архивные окна без годового набора

```sh
export VIRTUAL_SENSOR_RESEARCH_DIR=/review/registry
# Значение берётся из проверенного MANIFEST.json ZIP, оно совпадает с SHA модели-реестра в SHA256SUMS.txt.
export VIRTUAL_SENSOR_RESEARCH_MANIFEST_SHA256=$(python -c 'import json; print(json.load(open("/review/MANIFEST.json"))["registry_manifest_sha256"])')
mkdir -p /scratch/research-data
export DATA_ROOT=/scratch/research-data
export DATABASE_URL=sqlite:////scratch/research-demo.db
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8050
```

Во втором терминале в корне проекта запустите `npm --prefix frontend run dev -- --host 127.0.0.1 --port 5180`. Откройте `http://127.0.0.1:5180/research/virtual-sensors`. Страница входит в существующую лабораторию. Оба окна содержат по семь календарных дней. Приложение по умолчанию отключает вычисление при отсутствии закреплённого реестра. Данные исследования не зависят от SQLite. Для регрессий FDD необходима принятая база с данными, скопированная отдельно.

```sh
python -m playwright install chromium
python -m research.ml_repro_02.check_replay --api http://127.0.0.1:8050 --web http://127.0.0.1:5180 \
  --offline /review/SAT_OFFLINE_WINDOW.csv --output /scratch/research-screens
```

## Перестроить расчёты и артефакты

```sh
mkdir -p /scratch/source /scratch/repro02-results
prefix=https://fdddata.lbl.gov/data/Simulated_LBNL_FDD_Data_Sets_SDAHU
curl --fail --location "$prefix/LBNL_FDD_Data_Sets_SDAHU.zip" -o /scratch/source/SD-AHU.zip
python -m research.ml_repro_02.gate /scratch/source/SD-AHU.zip /review/reference_v1/official.ttl \
  /review/reference_v1/source-audit.json /scratch/repro02-d0
/usr/bin/time -v python -m research.ml_repro_02.controls /review/reference_v1/experiments /scratch/repro02-d0 \
  /review/reference_v1/official.ttl /scratch/repro02-results
/usr/bin/time -v python -m research.ml_repro_02.build_registry /scratch/repro02-d0 /review/reference_v1/official.ttl \
  /scratch/repro02-results/p1-gate.json /scratch/repro02-registry /scratch/repro02-results
/usr/bin/time -v python -m research.ml_repro_02.bagging /scratch/repro02-d0 /review/reference_v1/official.ttl /scratch/repro02-results
```

Перестроенный реестр получает собственный SHA и собственную квитанцию офлайн. Для проверки перестроенного реестра используйте именно его SHA и `SAT_OFFLINE_WINDOW.csv`. Для проверки переданного ZIP используйте его опубликованный SHA и приложенные точки. BP-ML-REPRO-01 показал небольшую вычислительную вариативность отдельных исходных scores при повторном fit. Проверка 10⁻⁹ относится к одному фиксированному реестру и его offline/HTTP/UI, а не к независимо обученным моделям.

В среде испытания P1 занял 2:37.51 (peak RSS 1 133 988 KiB), построение реестра — 11.89 с (973 192 KiB), bagging — 1:05.37 (1 208 216 KiB). CPU/RAM, пакеты и логи приведены в evidence.

## Проверки

Для pytest скопируйте принятую `buildingpulse.db` и дерево `data` в отдельный временный каталог, добавьте принятые G36-источники и задайте `DATABASE_URL` / `DATA_ROOT` на копии. Временная SQLite и директории raw/processed для тестов импорта должны быть доступны для записи. Установите `BUILDINGPULSE_AUDIT_SCRATCH` на scratch и `BUILDINGPULSE_PROTECTED_ROOTS` на список исходных путей и доверенного реестра через двоеточие. Включите реестр указанными выше переменными.

```sh
python -m pytest -q backend/tests contracts tests research/ml_reproduction/test_repro.py research/ml_repro_02/test_research.py
npm --prefix frontend run build
python contracts/check_fixture_types.py
python -m research.ml_repro_02.export_openapi /scratch/openapi-virtual-sensor-research.json
cmp /scratch/openapi-virtual-sensor-research.json contracts/openapi-virtual-sensor-research.json
npx --yes openapi-typescript@7.10.1 contracts/openapi-virtual-sensor-research.json -o /scratch/research-api.ts
cmp /scratch/research-api.ts frontend/src/types/virtual-sensor-research.generated.ts
```

Для прежнего интерфейса использованы `scripts/smoke_g01_http.py` и `scripts/test_playwright_{g01,g3,g4,g36,g54}.py`. Docker smoke запустил FastAPI TestClient с lifespan в локальном backend-образе, приложением и реестром в read-only bind mount, `--network none` и SQLite в контейнерном tmpfs. Сверены health и SAT двух сценариев. Полный Compose не запускался.
