# Воспроизведение BP-ML-REPRO-01

Основа — принятый G6.0 BUILDINGPULSE_G6_0_GATE_REVIEW.zip, SHA-256 6cf3f518734abebc24281cb5cc7b38019052d5a4961e3a005ce79cc5c0a7209f поверх G5.7. В распакованной сдаче выполните sha256sum -c SHA256SUMS.txt. В корне восстановленной копии примените git apply --check /review/BP_ML_REPRO_01.patch и git apply /review/BP_ML_REPRO_01.patch. В overlay только исследовательские файлы.

```sh
python -m venv /scratch/repro-venv
. /scratch/repro-venv/bin/activate
python -m pip install -r research/ml_reproduction/requirements-run.txt
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=4
```

Фактические пакеты указаны в requirements-run.txt и журнале. В локально закреплённом до fit requirements.txt был PyYAML 6.0.2, активный venv использовал 6.0.3. Параметры YAML и скрипты fit остались побайтно неизменными.

```sh
mkdir -p /scratch/sources /scratch/reports
prefix=https://fdddata.lbl.gov/data/Simulated_LBNL_FDD_Data_Sets_SDAHU
curl --fail --location "$prefix/LBNL_FDD_Data_Sets_SDAHU.zip" -o /scratch/sources/LBNL_FDD_Data_Sets_SDAHU.zip
curl --fail --location "$prefix/LBNL_FDD_Data_Sets_SDAHU_ttl.zip" -o /scratch/sources/ttl.zip
unzip -p /scratch/sources/ttl.zip > /scratch/sources/official.ttl
printf "%s  %s\n" 7dbd8403cc85d49c047173f910aae8a85a297d02f9b7ddb779de7a1887d3aa93 /scratch/sources/official.ttl | sha256sum -c
cd /scratch/sources
printf '%s  %s\n' 8295fcf0f55bc955937cb4ec0198512c28e5ede32e6bbf735257b0df55426471 LBNL_FDD_Data_Sets_SDAHU.zip | sha256sum -c
cd /restored/BuildingPulseAi
python -m research.ml_reproduction.sources /scratch/sources/LBNL_FDD_Data_Sets_SDAHU.zip /scratch/cache /scratch/reports
python -m research.ml_reproduction.panels /scratch/reports/source-audit.json /scratch/sources/official.ttl /scratch/reports
python -m research.ml_reproduction.panels /scratch/reports/source-audit.json /scratch/sources/official.ttl /scratch/missing --missing SA_TEMP
for mode in PAPER_FULL_REPRO STRICT_HOLDOUT PRODUCT_BASIC PRODUCT_BASIC_WITHOUT_COMMANDS; do
  /usr/bin/time -v python -m research.ml_reproduction.run /scratch/cache /scratch/reports/source-audit.json /scratch/sources/official.ttl "/scratch/reports/experiments/$mode" --mode "$mode"
done
for seed in $(seq 0 9); do
  python -m research.ml_reproduction.run /scratch/cache /scratch/reports/source-audit.json /scratch/sources/official.ttl "/scratch/seeds/$seed" --mode PAPER_FULL_REPRO --seed "$seed"
done
python -m research.ml_reproduction.report /scratch/reports --seed-root /scratch/seeds --figure
```

Пустой AUC означает отсутствие одного класса или дней в страте. Каждый эксперимент содержит статистики healthy calibration, daily scores, coverage, rank и, если FULL, actuator MAE. Скрипт report независимым подсчётом пар positive/negative сверяет AUC и confusion по daily scores. Среда CPU/RAM и фактический peak RSS/wall time находятся в evidence. Ряды читаются по одному, временный Parquet кэш остаётся в scratch.

Для регрессии используйте временную SQLite и DATA_ROOT принятой базы, отдельно от кэша исследования. Запустите pytest по backend/tests, contracts, tests и research/ml_reproduction/test_repro.py, строгую frontend сборку, проверку OpenAPI и типизации fixtures, HTTP и Playwright скрипты G6.0. Исследовательский API не требуется.

Для повторов с одинаковым seed используйте ту же команду с новым каталогом результата. Сравните metrics.csv, coverage.csv и run.json. Промежуточные daily scores могут отличаться в последних разрядах и для отдельных дней BASIC на величину порядка 0,0001. Два фактических повтора описаны в TEST_REPORT.md.
