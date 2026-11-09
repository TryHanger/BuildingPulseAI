# Воспроизведение Stage12

Исходники находятся в `research/ml_field_observational_12/`. Поставка рассчитана на Python 3.12. Версии фактического запуска в `evidence/versions.log`. Код работает автономно и не подключается к API, SQLite или моделям.

Укажите в `RAW` абсолютный каталог V1 с шестью книгами AHU, книгой расписания и JPG схемы. Оригиналы отсутствуют в этой поставке. Файлы и идентификаторы перечислены в `evidence/SOURCE_PROVENANCE_11.json`. В исследовании использовались опубликованные файлы, а Stage11 служил основанием для выбора заранее указанной строки. В оригиналах сверяются размер и SHA-256. Парсятся только AHU1 и книга расписания.

Из корня распакованного архива:

```sh
sha256sum -c SHA256SUMS
sha256sum -c FIELD_OBSERVATIONAL_12_PREREG.sha256
python -m pip install openpyxl==3.1.5 matplotlib==3.11.2 pytest==9.2.0
CODE=research/ml_field_observational_12
OUT=$(mktemp -d)
python "$CODE/replay.py" prepare "$RAW" "$PWD" "$OUT"
cat "$OUT/SELECTION_12.json"
cat "$OUT/FEASIBILITY_12.csv"
(cd "$OUT" && sha256sum -c PREPARED_12.sha256)
python "$CODE/replay.py" calculate "$RAW" "$PWD" "$OUT"
```

Для независимой проверки и графика скопируйте в каталог результата только предрегистрацию и метаданные исходных хэшей:

```sh
mkdir -p "$OUT/evidence"
cp FIELD_OBSERVATIONAL_12_PREREG.json "$OUT/"
cp evidence/SOURCE_PROVENANCE_11.json "$OUT/evidence/"
python "$CODE/oracle.py" "$RAW" "$OUT"
python "$CODE/plot.py" "$OUT"
STAGE12_ARTIFACTS="$PWD" python -m pytest -q "$CODE/test_replay.py"
```

Для повторной сверки регрессии используйте прежние команды Stage10 из его README и принятые исходные снимки Stage09/10. Запустите два backend с изолированными копиями SQLite, настройте архив виртуального датчика и прокси фронтенда к Stage10. В этом запуске использовались порты 18061/18062 и 5181. Прежние `research/ml_field_evidence_10/http_parity.py`, `freeze.py` и `browser.py` проверили HTTP, замороженный пакет и интерфейс. Полный набор запускался командой `python -m pytest backend/tests research/ml_domain_shift_07/test_applicability.py research/ml_repro_02/test_research.py`. Логи находятся в `evidence/`.

## Артефакты

- `ELIGIBILITY_12.csv`, `CONTROLS_12.csv`, `SELECTION_12.json` фиксируют маски, причины, ранг и выбор.
- `FEASIBILITY_12.csv` содержит нативные числа точек, диапазоны, пропуски, переходы команд и роли по частям окна. Переходы считаются между соседними отсчётами внутри соответствующей части.
- `RAW_SLICE_12.csv` содержит 72 отсчёта выбранных окон с исходными заголовками. `PUBLISHER_ANNOTATIONS_12.csv` хранит метки отдельно.
- `DESCRIPTIVE_12.csv`, `RESULT_12.json` и график в `plots/` содержат результат расчёта. На графике линии соединяют соседние отсчёты для чтения формы ряда. Между отсчётами нет новых измерений.
- `INTERPRETATION_12.md` и `STOP_OR_DESCRIPTIVE_RESULT_12.md` фиксируют научные границы, результат и регрессию.
