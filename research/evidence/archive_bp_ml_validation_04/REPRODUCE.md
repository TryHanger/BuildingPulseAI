# Воспроизведение BP-ML-VALIDATION-04

`REPRO02` и `REPRO03` обозначают каталоги распакованных предыдущих поставок. `APP` — изолированная копия проекта после REPRO-03. `OUT04` — распакованная текущая поставка. `SCRATCH` — отдельный каталог проверки.

```sh
(cd "$OUT04" && sha256sum -c SHA256SUMS.txt)
(cd "$REPRO02" && sha256sum -c SHA256SUMS.txt)
(cd "$REPRO03" && sha256sum -c SHA256SUMS.txt)
(cd "$APP" && sha256sum -c "$OUT04/BASE_FILES_SHA256.txt")
git -C "$APP" apply --check "$OUT04/BP_ML_VALIDATION_04.patch"
git -C "$APP" apply "$OUT04/BP_ML_VALIDATION_04.patch"
cd "$APP"
python -m research.ml_validation_04.evidence "$REPRO03/SCORE_PARITY_FULL_COHORT.csv" \
  "$REPRO02/reference_v1/experiments/PRODUCT_BASIC/daily.csv" "$SCRATCH/recalculation"
cmp "$SCRATCH/recalculation/RECALCULATION.json" "$OUT04/RECALCULATION.json"
cmp "$SCRATCH/recalculation/SAT_VS_SYSTEM_11_SCENARIOS.csv" "$OUT04/SAT_VS_SYSTEM_11_SCENARIOS.csv"
cmp "$SCRATCH/recalculation/ALARM_PARITY_DIVERGENCE.csv" "$OUT04/ALARM_PARITY_DIVERGENCE.csv"
```

Пересчёт использует сохранённые дневные квитанции и стандартную библиотеку Python 3.11+. Для аудита заголовков, частоты и дублирования MAT используйте локальные копии проверяемых файлов, перечисленные с SHA в `EXTERNAL_SOURCE_INVENTORY.json`. Команда `python -m research.ml_validation_04.source_inventory "$COPIED_DATA" "$SCRATCH/inventory.json"` требует NumPy/PyArrow и не выполняет предсказаний. Для пояснения расхождений приложен компактный фрагмент уже существовавшего повторного fit и исходный журнал REPRO-01. Не запускайте новый fit ради сверки.

Подготовьте копии SQLite и данных для pytest по инструкции REPRO-02/03. `DATABASE_URL`, `DATA_ROOT`, `BUILDINGPULSE_AUDIT_SCRATCH` должны указывать на отдельную SQLite и копии данных. Укажите исходные папки и архивы в `BUILDINGPULSE_PROTECTED_ROOTS`.

```sh
export VIRTUAL_SENSOR_RESEARCH_DIR="$REPRO02/registry"
export VIRTUAL_SENSOR_RESEARCH_MANIFEST_SHA256=359afbe1d3022e64c52ec5e1d916bb731a8c4c45aef9a835d0c9ab6ba73c0734
python -m pytest -q backend/tests contracts tests research/ml_reproduction/test_repro.py \
  research/ml_repro_02/test_research.py research/ml_repro_03/test_coverage.py research/ml_validation_04/test_boundary.py
npm --prefix frontend ci
npm --prefix frontend run build
python contracts/check_fixture_types.py
python -m research.ml_repro_02.export_openapi "$SCRATCH/openapi.json"
cmp "$SCRATCH/openapi.json" contracts/openapi-virtual-sensor-research.json
npx --yes openapi-typescript@7.10.1 "$SCRATCH/openapi.json" -o "$SCRATCH/openapi.ts"
cmp "$SCRATCH/openapi.ts" frontend/src/types/virtual-sensor-research.generated.ts

# В отдельных терминалах, с отдельной SQLite для HTTP
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 18055
VITE_API_URL=http://127.0.0.1:18055 npm --prefix frontend run dev -- --host 127.0.0.1 --port 15185
python -m research.ml_validation_04.verify_live --api http://127.0.0.1:18055 --web http://127.0.0.1:15185 \
  --offline "$REPRO02/SAT_OFFLINE_WINDOW.csv" --output "$SCRATCH/screens"
```

Команды контейнерного smoke выполняются только с локальным тестовым образом, SQLite tmpfs и реестром только для чтения.

```sh
docker build -t buildingpulse-validation04:local -f backend/Dockerfile .
docker run --rm -i --network none --tmpfs /scratch \
  -e DATABASE_URL=sqlite:////scratch/smoke.db -e DATA_ROOT=/scratch/data \
  -e VIRTUAL_SENSOR_RESEARCH_DIR=/registry -e VIRTUAL_SENSOR_RESEARCH_MANIFEST_SHA256 \
  -v "$REPRO02/registry:/registry:ro" buildingpulse-validation04:local python - < "$OUT04/evidence/docker_smoke.py"
```
