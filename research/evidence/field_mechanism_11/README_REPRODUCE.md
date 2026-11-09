# Воспроизведение BP-ML-FIELD-MECHANISM-11

Поставка содержит исследовательский аудит фазы A. Для приложения патч не требуется. Основное решение находится в `FIELD_MECHANISM_11_GATE_RESULT.md`.

## Входы и запуск

Нужен каталог `RAW` с восемью оригиналами Mendeley V1 и принятой рукописью `CTU_AAM_350037.verified.pdf`. По опубликованному инвентарю восемь оригиналов — это шесть книг AHU, книга расписания и JPG со схемой. Идентификаторы, байтовые размеры и хэши указаны в `SOURCE_PROVENANCE_11.json`. Проверенные локальные экземпляры использовались только для чтения.

```sh
sha256sum -c SHA256SUMS
sha256sum -c PREREGISTERED_11.sha256
python -m pip install openpyxl==3.1.5
mkdir -p /tmp/bp-stage11-replay
python code/audit_phase_a.py "$RAW" "$PWD" /tmp/bp-stage11-replay
python code/check_phase_a_xml.py "$RAW" /tmp/bp-stage11-replay/GAP_CLOCK_CONTEXT_11.json
python code/verify_baselines.py "$STAGE09_ZIP" "$STAGE10_ZIP" evidence/publisher-v1-listing.json
```

`audit_phase_a.py` сверяет зафиксированные хэши предрегистрации и источников. Отчёт о наличии ячеек строится без экспорта их температурных значений. Семантическое решение зафиксировано по рассмотренным источникам и объяснено в отчёте. JSON аудита содержит фактическое время запуска, поэтому при воспроизведении меняется поле `audit_started_utc`. Табличные результаты детерминированы. Независимая проверка читается через ZIP/XML без openpyxl и сверяет нативное время и наличие температурных полей для всех 12 окон. Она не вычисляет отклик.

## Регрессия Stage10

В рабочей папке был старый экспорт. Для проверки использовалась отдельная копия принятого снимка Stage10, описанного в его поставке, и снимок Stage09 для сравнения. Настройте `DATABASE_URL` и `DATA_ROOT` на изолированные копии принятых SQLite и данных. Настройте `VIRTUAL_SENSOR_RESEARCH_DIR` и `VIRTUAL_SENSOR_RESEARCH_MANIFEST_SHA256` на принятый реестр Stage02 с манифестом SHA-256 `359afbe1d3022e64c52ec5e1d916bb731a8c4c45aef9a835d0c9ab6ba73c0734`.

Из корня Stage10:

```sh
python -m pytest backend/tests research/ml_domain_shift_07/test_applicability.py research/ml_repro_02/test_research.py
python research/ml_field_evidence_10/freeze.py "$STAGE09_ZIP" /tmp/field-frozen.json
cmp /tmp/field-frozen.json backend/app/research_data/field_evidence_10.json
```

Запустите Uvicorn на 18061 для Stage09 и 18062 для Stage10. Поднимите frontend Stage10 на 5181 с `VITE_API_URL=http://127.0.0.1:18062`. Каждому backend нужна отдельная копия SQLite.

```sh
python research/ml_field_evidence_10/http_parity.py http://127.0.0.1:18061 http://127.0.0.1:18062 /tmp/openapi-field-evidence.json
python research/ml_field_evidence_10/browser.py "$STAGE09_ZIP" /tmp/field-evidence-screens --base http://127.0.0.1:5181
docker compose config --quiet
timeout 15s docker info --format '{{.ServerVersion}}'
timeout 15s docker compose ps
```

`verify_baselines.py --app "$TESTED_APP" --accepted-app "$ACCEPTED_APP"` дополнительно сравнивает файлы исходников, контрактов, моделей и данных двух снимков. Версии и полученные результаты находятся в `evidence/`. Оригинальные XLSX, PDF, SQLite и веса моделей в ZIP не вложены.
