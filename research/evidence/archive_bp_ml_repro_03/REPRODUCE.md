# Проверка и повторный запуск BP-ML-REPRO-03

Выполняйте команды в изолированной копии. Архив REPRO-03 содержит патч, overlay, итоговые таблицы, метаданные и журналы. REPRO-02 содержит native LightGBM, два архивных Parquet-окна и исходные суточные таблицы REPRO-01. Полный LBNL ZIP доступен на странице датасета. [LBNL SD-AHU](https://faultdetection.lbl.gov/dataset/simulated-sd-ahu/)

## Проверка артефактов и установка

```sh
(cd "$REPRO03" && sha256sum -c SHA256SUMS.txt)
(cd "$REPRO02" && sha256sum -c SHA256SUMS.txt)
# Изолированная рабочая копия после REPRO-02
(cd "$APP" && sha256sum -c "$REPRO03/BASE_FILES_SHA256.txt")
git -C "$APP" apply --check "$REPRO03/BP_ML_REPRO_03.patch"
git -C "$APP" apply "$REPRO03/BP_ML_REPRO_03.patch"
```

Разверните базу G6.0 → REPRO-01 → REPRO-02 по `REPRODUCE.md` предыдущей поставки. Все три ZIP идентифицированы в `MANIFEST.json`. Для среды используйте версии из REPRO-02. Для научного прогона использованы Python 3.12.3, LightGBM 4.6.0, pandas 2.3.3, NumPy 2.5.4, PyArrow 19.0.1, четыре потока прогноза и штатные признаки из REPRO-01.

## Полная когорта

```sh
cd "$APP"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=4
# Если D0 ещё не подготовлен, получите официальный LBNL ZIP с SHA из MANIFEST.json.
python -m research.ml_repro_02.gate "$LBNL_ZIP" "$REPRO02/reference_v1/official.ttl" \
  "$REPRO02/reference_v1/source-audit.json" "$SCRATCH/d0"
python -m research.ml_repro_03.replay "$LBNL_ZIP" "$SCRATCH/d0" "$REPRO02" "$SCRATCH/cohort"
python -m research.ml_repro_03.compare \
  "$SCRATCH/cohort/SCORE_PARITY_FULL_COHORT.csv" "$SCRATCH/cohort/SCORE_PARITY_METADATA.json" \
  "$REPRO02/reference_v1/experiments" "$SCRATCH/comparison"
```

Можно использовать принятую копию D0 со сверенными хешами из `evidence/D0_VERIFIED.json`. Новый результат записывается в новый каталог. Нужен полный исходный ZIP. Для независимой арифметической проверки достаточно вызвать `compare` с CSV и JSON из поставки REPRO-03 и суточными CSV из REPRO-02. Сторонние Python-пакеты этому шагу не нужны.

`ORIGINAL_ARM_MASK` использует замороженную маску каждого прогона. `MATCHED_MINUTES` использует пересечение минут исправного и соответствующего fault-прогона с общим идентификатором `pair_member`. Хеши минут вычислены по наносекундам источника в формате little-endian int64 без UTC-конверсии. Хеши масок рассчитаны из одного байта 0/1 на каждый тик указанного интервала. Поля `*_z` и `*_historical_alarm` используют исходный допуск по наличию хотя бы одной минуты. Поля `*_policy_z` и `*_policy_alarm` учитывают новую версию политики. `*_repro01_z` означает значение из исходной суточной таблицы. Пустые поля означают отсутствие допустимого значения. Исторические Ridge и PCA используются на пересечении только при равенстве исходного и парного наборов минут. `alias_status` — атрибут разметки, отделённый от модельных признаков.

## API, браузер и контейнер

Подготовьте копии SQLite и тестовых данных, как описано в REPRO-02. Укажите пути в `DATABASE_URL`, `DATA_ROOT`, `BUILDINGPULSE_AUDIT_SCRATCH` и `BUILDINGPULSE_PROTECTED_ROOTS`. API для архива требует SHA реестра из MANIFEST.json.

```sh
export VIRTUAL_SENSOR_RESEARCH_DIR="$REPRO02/registry"
export VIRTUAL_SENSOR_RESEARCH_MANIFEST_SHA256=359afbe1d3022e64c52ec5e1d916bb731a8c4c45aef9a835d0c9ab6ba73c0734
python -m pytest -q backend/tests contracts tests research/ml_reproduction/test_repro.py \
  research/ml_repro_02/test_research.py research/ml_repro_03/test_coverage.py
npm --prefix frontend ci
npm --prefix frontend run build
python contracts/check_fixture_types.py
python -m research.ml_repro_02.export_openapi "$SCRATCH/openapi.json"
cmp "$SCRATCH/openapi.json" contracts/openapi-virtual-sensor-research.json
npx --yes openapi-typescript@7.10.1 "$SCRATCH/openapi.json" -o "$SCRATCH/openapi.ts"
cmp "$SCRATCH/openapi.ts" frontend/src/types/virtual-sensor-research.generated.ts

# В отдельных терминалах
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 18053
VITE_API_URL=http://127.0.0.1:18053 npm --prefix frontend run dev -- --host 127.0.0.1 --port 15183
python -m research.ml_repro_02.check_replay --api http://127.0.0.1:18053 --web http://127.0.0.1:15183 \
  --offline "$REPRO02/SAT_OFFLINE_WINDOW.csv" --output "$SCRATCH/screenshots"
```

Для контейнерной проверки используйте `docker build -t buildingpulse-repro03-smoke:local -f backend/Dockerfile .`. `evidence/compose.sqlite.yml` задаёт изолированные контейнеры frontend/backend и реестр только для чтения. Запуск использует `docker compose -p bp-repro03-check -f docker-compose.yml -f "$REPRO03/evidence/compose.sqlite.yml" up --no-deps backend frontend` с переменными `BP_REPRO03_REGISTRY_DIR` и `BP_REPRO03_REGISTRY_SHA` и обращением к frontend через порт 15184. Остановите тестовые контейнеры командой Compose `down` в том же проекте.
