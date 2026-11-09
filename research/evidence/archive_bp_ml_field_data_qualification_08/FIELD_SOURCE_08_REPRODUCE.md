# Воспроизведение аудита Stage 08

Аудит выполнен в Python 3.12.3. openpyxl открывает Excel в режиме read_only с data_only. et-xmlfile — закреплённая транзитивная зависимость openpyxl. pypdf используется только для проверки и чтения рукописи CTU. Аудит пишет JSON и CSV в отдельный каталог, оставляя оригиналы байт-в-байт.

## Подготовка

Извлеките архив. Приведённые команды предполагают запуск из корня распакованного архива. Для аудита таблиц приложенный overlay самодостаточен. Для проверок API примените патч к принятым файлам Stage 07.

```bash
python3.12 -m venv /tmp/bp08-audit-env
source /tmp/bp08-audit-env/bin/activate
cd overlay
export PYTHONDONTWRITEBYTECODE=1
python -m pip install -r research/ml_field_data_08/requirements-audit.txt
RAW="$(mktemp -d)"
OUT="$(mktemp -d)/results"
export RAW OUT
```

Оригинальные имена, публичные URL, размеры и контрольные суммы находятся в `research/ml_field_data_08/PUBLISHER_FILES_V1.json`. Скачайте все восемь файлов на диск, например:

```bash
python - <<'PY'
import json
import os
import subprocess
from pathlib import Path

manifest = Path("research/ml_field_data_08/PUBLISHER_FILES_V1.json")
for name, record in json.loads(manifest.read_text())["files"].items():
    dest = Path(os.environ["RAW"]) / name
    partial = dest.with_suffix(dest.suffix + ".part")
    subprocess.run([
        "curl", "--fail", "--location", "--retry", "2", "--max-time", "180",
        "--output", str(partial), record["download_url"],
    ], check=True)
    partial.rename(dest)
PY
```

Проверьте рукопись по официальной ссылке ниже. Размер 1 814 037 байт, MD5 репозитория `a4749a55c2366deb298a3cae6104c504`, проверенный SHA-256 `4a03914e8064ae3b42ffce9a806a724f7451bae7596d940ff3884b6c50a072ef`. При обрыве полной загрузки в этом аудите использовались 28 запросов Range с проверкой каждого Content-Range и финального хеша. Сверены §§3.1–3.3 и таблицы 2–3. Рукопись и легенда оригиналов доступны отдельно. [Официальный PDF CTU](https://dspace.cvut.cz/server/api/core/bitstreams/2f9d64ab-bbd6-487c-b120-3d01bcbf4af2/content) · [Легенда Mendeley](https://data.mendeley.com/datasets/jkw85sm4v4/1)

```bash
PAPER="$RAW/CTU_AAM_350037.verified.pdf"
python -m research.ml_field_data_08.inspect_08 "$RAW" "$OUT" --manuscript "$PAPER"
python -m research.ml_field_data_08.check_pair_lineage_08 "$RAW" "$OUT/AHU2_AHU8_LINEAGE_CHECK_08.json"
diff -r ../observed "$OUT"
```

При воспроизведении только Excel-аудита флаг `--manuscript` можно опустить. В этом случае `file_verified_in_this_run` будет false, остальные результаты идентичны. При отсутствии любого из восьми исходников аудитор останавливается до чтения Excel. `observed/SOURCE_SAMPLES_08.json` содержит реальные заголовки и образцы каждого XLSX, все три листа журнала, SHA-256 и описание содержимого оригинальной легенды JPEG. `observed/WORKBOOK_AUDIT_08.json` содержит полные агрегаты. `observed/FIELD_SIGNAL_MAP_08.csv` фиксирует физический смысл, принадлежность к контролю, единицы, заполненность и основания отказа. `observed/HEALTHY_WINDOW_LEDGER_08.csv` и `observed/EVENT_LEDGER_08.csv` хранят наивные даты и отдельную разметку без переноса в предсказательные входы.

## Проверки в приложении

Используйте изолированную копию Stage 07, локальные тестовые зависимости и отдельные DATABASE_URL и DATA_ROOT. `BASE_FILES_SHA256` задаёт контрольные суммы трёх заменяемых файлов до применения патча. Хеш принятого ZIP Stage 07 записан в `evidence/base.sha256`. В корне изолированного приложения:

```bash
BP08_RAW="$RAW" python -m pytest -q research/ml_field_data_08 research/ml_domain_shift_07
python -m research.ml_field_data_08.check_api_08 \
    "$STAGE07_FULL_OPENAPI" "$STAGE06_FULL_OPENAPI" /tmp/bp08-openapi.json
cmp /tmp/bp08-openapi.json contracts/openapi-domain-shift-07.json
```

`STAGE07_FULL_OPENAPI` и `STAGE06_FULL_OPENAPI` — абсолютные пути к `evidence/openapi-baseline-07.json` и `evidence/openapi-baseline-06.json` из поставки. Дополнительные проверки и живой HTTP зафиксированы в `evidence/`. Фронтенд не изменялся, поэтому отдельная сборка, Playwright и скриншот для Stage 08 не требовались. Docker и Compose не запускались.
