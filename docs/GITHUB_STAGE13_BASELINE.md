# BuildingPulse AI · публичный baseline Stage13

Исходники проекта, включая исследовательский интерфейс Stage10, восстановлены из локального экспорта и принятых материалов проверки. Все 227 путей, закреплённых принятым манифестом Stage09, были проверены до наложения принятого изменения Stage10. Путь к исходному архиву для каждого из восстановленных файлов указан в [реестре восстановления](../research/evidence/stage13_bootstrap/ARCHIVE_RECOVERY.tsv). История Git начинается с этой восстановленной версии. Ранее принятые методы, значения и исходы сохраняются в [каталоге свидетельств](../research/evidence/).

## Запуск

Linux/WSL и Windows используют Python 3.11 или 3.12 и Node 24.11.0. Python 3.12.3 был использован для проверок baseline. На Windows используйте `py -3.12 -m venv .venv` и `.\.venv\Scripts\Activate.ps1`. На Linux используйте `python3.12 -m venv .venv` и `source .venv/bin/activate`.

```sh
python -m pip install -r backend/requirements.txt
npm --prefix frontend ci
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8050
# Во втором терминале:
npm --prefix frontend run dev -- --port 5180
```

Без Docker приложение создаёт локальную SQLite. Для Compose создайте свой `.env` из `.env.example` и задайте `POSTGRES_PASSWORD`. Исторические интеграционные тесты используют копии локальных данных и БД. На Linux нормализуйте разделители Windows в `scenarios.data_path` только в тестовой копии. Укажите `BUILDINGPULSE_AUDIT_SCRATCH`, `BUILDINGPULSE_PROTECTED_ROOTS`, `DATABASE_URL` и `DATA_ROOT` перед pytest. Путь к исследовательскому реестру виртуальных датчиков задают `VIRTUAL_SENSOR_RESEARCH_DIR` и `VIRTUAL_SENSOR_RESEARCH_MANIFEST_SHA256`. Реестр входит в дерево, SHA его манифеста — `359afbe1d3022e64c52ec5e1d916bb731a8c4c45aef9a835d0c9ab6ba73c0734`.

## Входы и модели

- LBNL SD-AHU, DOI 10.25984/1881324. URL, размеры, SHA и соответствие локальных срезов оригинальным ZIP members находятся в [манифесте LBNL](../research/g0-g1/DATASET_MANIFEST.json). `scripts/freeze_g01_annual.py` создаёт проверенный годовой Parquet в отдельной копии.
- G36. Источники Figshare и точные SHA закреплены в [проверке входов](../research/g52/fetch_members.py) и реестрах [G5.2](../research/evidence/archive_g5_2_gate/) и [G5.3](../research/evidence/archive_g5_3_gate/).
- Полевые книги Nehasil V1. DOI 10.17632/jkw85sm4v4.1, CC BY 4.0. [Идентификаторы, ссылки загрузки и SHA-256](../research/evidence/field_replication_13/evidence/SOURCE_PROVENANCE_11.json). [Stage13](../research/evidence/field_replication_13/README_REPRODUCE.md) содержит код воспроизведения, семь малых парных вырезок, предрегистрацию и научные ограничения.
- Сохранённые [хэши модельных артефактов](../research/evidence/stage13_bootstrap/MODEL_ARTIFACTS.sha256). Исследовательский LightGBM-реестр и два производных среза имеют [отдельный манифест происхождения](../research/ml_repro_02/registry/MODEL_ARTIFACT_MANIFEST.json). У старых локальных артефактов в `models/` сведения о происхождении приведены в соседних метаданных и в отчётах этапов. Исторический режим, исходные метки и область применимости сохраняются.
- Из Git исключены исходные XLSX, большие выгрузки, архивы передачи, локальные БД, секреты и сборки. Ранее выпущенные SHA архивов сохранены в соответствующих папках свидетельств. В архивных инструкциях пути относятся к прежним пакетам. В текущем дереве код этапов размещён в `research/`, а таблицы и журналы в `research/evidence/`.

Stage13 установил повторение направления медианного изменения SAT в нескольких AHU на одной площадке. Причинный эффект и полевая точность остаются неподтверждёнными. Результаты Stage14 публикуются отдельно для независимого аудита.

Полный Linux-аудит можно повторить с `backend/requirements-audit-linux-py312.lock`. Для этого создайте отдельное виртуальное окружение и установите его через `python -m pip install -r backend/requirements-audit-linux-py312.lock`. Для исследования Stage13 из корня Git:

```sh
ART=research/evidence/field_replication_13
OUT=$(mktemp -d)
python -m research.ml_field_replication_13.replay prepare "$RAW" "$ART" "$OUT"
python -m research.ml_field_replication_13.replay calculate "$RAW" "$ART" "$OUT"
mkdir -p "$OUT/evidence"
cp "$ART/FIELD_REPLICATION_13_PREREG.json" "$OUT/"
cp "$ART/evidence/SOURCE_PROVENANCE_11.json" "$OUT/evidence/"
python -m research.ml_field_replication_13.oracle "$RAW" "$OUT"
STAGE13_ARTIFACTS="$ART" python -m pytest -p no:cacheprovider -q research/ml_field_replication_13/test_replay.py
```

Свежий системный прогон baseline использовал отдельно проверенный годовой Parquet LBNL, две выгрузки G36 и нормализованную локальную тестовую копию SQLite. Установка из Git оставляет базы и исходники локальными. Диагностическая логика не менялась при публикации.
