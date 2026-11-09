# Воспроизведение G5.7

Сверьте `sha256sum -c SHA256SUMS.txt` после распаковки. Примените patch к принятому G5.6, SHA-256 ZIP `d8f1b5e25b9402b5cc8408e58101e47326411400a9daffdf04617d199bb22e09`. Из корня восстановленной копии используйте `git apply --check /review/G5_7.patch` и `git apply /review/G5_7.patch` либо скопируйте `overlay/`.

Положите под `/scratch/data/g36-5wk` четыре CSV из принятого source-архива G5.2. В `/scratch/data/g36-1wk` поместите nominal из source-архива G5.3 и valve из G5.2. Точные имена членов и SHA приведены в MANIFEST и observe.py. Исходный Figshare релиз закреплён в принятой цепочке. [Figshare v3](https://doi.org/10.6084/m9.figshare.29297999.v3)

```sh
mkdir -p /scratch/output
python -m research.g57.preflight /scratch/data > /scratch/nominal.json
python -m research.g57.observe /scratch/data /scratch/output
python -m research.g57.verify /scratch/data /scratch/output /original
```

В `/original` должны быть принятые ZIP G5.3 и G5.4. Скрипт verify считает разности независимо с Decimal и сверяет BASIC с архивом. Сравните `/scratch/output` и `outputs/`. В evidence/pre-score.sha256 локальные абсолютные пути приведены для проверки исходного запуска.

Продуктовые проверки запускаются в окружении G5.6 на отдельных SQLite и DATA_ROOT. Для pytest задайте BUILDINGPULSE_AUDIT_SCRATCH и BUILDINGPULSE_PROTECTED_ROOTS. Для браузера запустите FastAPI и Vite, укажите VITE_API_URL для FastAPI.

```sh
python -m pytest backend/tests contracts/test_evidence_v1.py tests -q
npm --prefix frontend run build
python -m openapi_spec_validator contracts/openapi-v1.yaml
python contracts/check_fixture_types.py
PYTHONPATH=. python scripts/smoke_g01_http.py --url http://127.0.0.1:8050 --output /scratch/http
python scripts/test_playwright_g54.py --url http://127.0.0.1:5180 --output /scratch/screenshots
python scripts/test_playwright_g36.py --url http://127.0.0.1:5180 --output /scratch/screenshots
```
