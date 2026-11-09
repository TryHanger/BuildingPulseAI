# Воспроизведение Stage13

Код запускается из корня распакованной поставки. Используются оригиналы из [Mendeley Data V1](https://data.mendeley.com/datasets/jkw85sm4v4/1). В `evidence/SOURCE_PROVENANCE_11.json` перечислены восемь файлов, идентификаторы, размеры, хэши и адреса загрузки. В `RAW` укажите абсолютный каталог с этими оригиналами. Большие книги, модели и SQLite в ZIP не включены.

```sh
sha256sum -c SHA256SUMS
sha256sum -c FIELD_REPLICATION_13_PREREG.sha256
python -m pip install openpyxl matplotlib pytest fastapi httpx
OUT=$(mktemp -d)
python -m research.ml_field_replication_13.replay prepare "$RAW" "$PWD" "$OUT"
cat "$OUT/SELECTION_13.json"
(cd "$OUT" && sha256sum -c PREPARED_13.sha256)
python -m research.ml_field_replication_13.replay calculate "$RAW" "$PWD" "$OUT"
mkdir -p "$OUT/evidence"
cp FIELD_REPLICATION_13_PREREG.json "$OUT/"
cp evidence/SOURCE_PROVENANCE_11.json "$OUT/evidence/"
python -m research.ml_field_replication_13.oracle "$RAW" "$OUT"
python -m research.ml_field_replication_13.plot "$OUT"
STAGE13_ARTIFACTS="$PWD" python -m pytest -p no:cacheprovider -q research/ml_field_replication_13/test_replay.py
```

`prepare` записывает маски и время выбора до извлечения уровней температуры. Подготовленные файлы фиксируются отдельно до запуска медиан. `calculate` повторно сверяет оригиналы и подготовленные SHA. Значения меток сохраняются в отдельном файле. Воспроизводимость чисел проверяет независимый ZIP/XML-парсер. Версии фактического запуска указаны в `evidence/versions.log`. Неизменённые утилиты Stage12 в комплекте используются для чтения XLSX, нативных масок и базовых функций. Код Stage13 расположен в `research/ml_field_replication_13/`.

Для проверки архивов и отдельного HTTP-обработчика укажите в `WORKSPACE` папку с принятыми ZIP Stage09–12.

```sh
python -m research.ml_field_replication_13.check_accepted "$WORKSPACE"
```

Автономный HTTP-тест не поднимает всё приложение. Логи и точный блокер интегрированного прогона включены. Для повторного расчёта Stage12 используйте `README_REPRODUCE.md` его принятого архива, передав те же оригиналы. `evidence/stage12-regression.log` содержит результаты повторного запуска.

## Состав

- `FIELD_REPLICATION_13_RESULT.md`, `ANOMALY_OF_INTERPRETATION_13.md` · результаты и ограничения.
- `FIELD_REPLICATION_13_PREREG.*` и файл времени · замороженный протокол.
- `EPISODE_LEDGER_13.csv`, `COMPARATOR_ELIGIBILITY_13.csv`, `SELECTION_13.json`, `FEASIBILITY_13.csv`, `PREPARED_13.sha256` · допуск и фиксация до медиан.
- `RAW_SLICE_13.csv`, `PUBLISHER_ANNOTATIONS_13.csv`, `ANNOTATION_AUDIT_13.csv`, `DESCRIPTIVE_EPISODES_13.csv`, `RESULT_13.json` и `plots/` · нативные вырезки, отдельные метки, итоговые числа и семь графиков.
- `evidence/` · SHA источников, прогоны, регрессия и версии.
