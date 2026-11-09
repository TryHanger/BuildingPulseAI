# Воспроизведение G5.6

Из распакованной сдачи выполните `sha256sum -c SHA256SUMS.txt`. Основа — рабочая копия принятого G5.5. SHA-256 `BUILDINGPULSE_G5_5_GATE_REVIEW.zip` равен `8e69c380c34dee26ed41c5d948dbd5c103ea5ed13960668d4affc8cd8d2d6ed6`. Примените `git apply --check /review/G5_6.patch` и `git apply /review/G5_6.patch` либо скопируйте `overlay/` в корень отдельной копии.

Номинальная проверка читает два CSV из существующего `data/raw/rbc_nesbitt`. Ожидаемые SHA и заголовки входят в квитанцию. Матрица находится в `overlay/research/g56/SENSOR_SEMANTICS_STATUS.csv`.

```sh
python research/g56/audit_rbc_nominal.py /original/data/raw/rbc_nesbitt /scratch/nominal.json
cmp /scratch/nominal.json /review/evidence/rbc-nominal-receipt.json
```

Для регрессий восстановите временные DATA_ROOT и SQLite по инструкции G5.5. Backend тестам нужна отдельная SQLite с правом записи, `BUILDINGPULSE_AUDIT_SCRATCH` и `BUILDINGPULSE_PROTECTED_ROOTS` с оригинальными путями. CSV G36 берутся из принятых ZIP, зафиксированных в манифесте G5.5.

```sh
python -m pytest backend/tests contracts/test_evidence_v1.py tests -q
npm --prefix frontend run build
python -m openapi_spec_validator contracts/openapi-v1.yaml
python contracts/check_fixture_types.py
```

При работающих FastAPI (8050) и Vite (5180, `VITE_API_URL=http://127.0.0.1:8050`):

```sh
PYTHONPATH=. python scripts/smoke_g01_http.py --url http://127.0.0.1:8050 --output /scratch/http
python scripts/test_playwright_g54.py --url http://127.0.0.1:5180 --output /scratch/screenshots
python scripts/test_playwright_g36.py --url http://127.0.0.1:5180 --output /scratch/screenshots
```

Контрольные HTTP ответы на принятых данных указаны в `evidence/http-g56.log` и `evidence/http-*.json`. Docker backend smoke использует ту же read-only папку данных и временную копию SQLite, как в G5.5, с образом из текущего backend Dockerfile и запуском `python scripts/smoke_g01_container.py --g54`.
