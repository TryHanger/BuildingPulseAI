# Воспроизведение G5.4

Возьмите принятую рабочую копию G5.3. Контрольная сумма `BUILDINGPULSE_G5_3_GATE_REVIEW.zip` — `de06bf8b90aeef4092bfb0cc2ae93dfa15f57e65e6d42a9b9274139a45694d0b`. Таблица файлов и хэшей основы в `MANIFEST.json` определяет исходное состояние точнее, чем имя каталога. Из корня копии примените `git apply --check /review/G5_4.patch` и `git apply /review/G5_4.patch`. Альтернативно скопируйте содержимое `overlay/` в корень копии. Проверьте распакованный пакет через `sha256sum -c SHA256SUMS.txt`. В `dependencies/` находятся исходные описания зависимостей и контекст контракта, совпадающие с принятой копией. Версии среды, использованной для проверки, в `evidence/environment.log`.

## Исходники

| Принятый архив | SHA-256 архива | Член ZIP |
|---|---|---|
| BUILDINGPULSE_G5_3_G36_1WK_SOURCE_BYTES.zip | 8a4973ee0b624221b2bb993f7f3ce8c088a84345f2b45393868d127cf96930cf | g36-1wk/CoolingSeason/BaselineSystem.csv |
| BUILDINGPULSE_G5_2_G36_SOURCE_BYTES.zip | fb9ad25e4bad4f2299c70bb63d0a2bb4e1806883c175cd8dbae57c5c268d324f | g36-1wk-probe/CooCoiValStuck_0.csv |
| BUILDINGPULSE_G5_2_G36_SOURCE_BYTES.zip | fb9ad25e4bad4f2299c70bb63d0a2bb4e1806883c175cd8dbae57c5c268d324f | g36-1wk-probe/00_explanations.pdf |

Побайтовые SHA членов и пути в оригинальном архиве Figshare перечислены в `MANIFEST.json`. Положите три члена по их исходным именам в отдельный каталог с доступом на чтение, далее `/scratch/g36-1wk`. Для 1wk API скопируйте два CSV в `$DATA_ROOT/g36-1wk`. Используйте отдельную копию служебной SQLite и данных G5.3 для старых HTTP и браузерных сценариев. Исходные 5wk CSV остаются в `$DATA_ROOT/g36-5wk` по инструкции G5.3. Паспорт взят из проверенного архива G5.2. [Публикация данных, лицензия CC BY 4.0](https://doi.org/10.6084/m9.figshare.29297999.v3)

## Расчёт, тесты и HTTP

Из корня копии с установленными зависимостями выполните:

```sh
mkdir -p /scratch/results
sha256sum research/g54/PROTOCOL_G5_4_PRE_SCORE.md
for run in BaselineSystem CooCoiValStuck_0; do
  python -m backend.app.services.g36_week "/scratch/g36-1wk/$run.csv" \
    "/scratch/results/$run-summary.json" --trace "/scratch/results/$run-trace.csv"
done
python research/g54/verify_independent.py /scratch/g36-1wk /scratch/results
python research/g53/profile_transport.py /scratch/g36-1wk /scratch/results/SOURCE_METADATA_QA.json
python -m pytest backend/tests contracts/test_evidence_v1.py tests -q
npm --prefix frontend ci
npm --prefix frontend run build
python -m openapi_spec_validator contracts/openapi-v1.yaml
python contracts/check_fixture_types.py
```

Запустите FastAPI на 8050 с изолированными `DATABASE_URL` и `DATA_ROOT`. Запустите Vite на 5180 с `VITE_API_URL=http://127.0.0.1:8050`. Для браузерных проверок установите Playwright Chromium через `python -m playwright install chromium`.

```sh
python research/g54/verify_independent.py /scratch/g36-1wk /scratch/results --url http://127.0.0.1:8050
PYTHONPATH=. python scripts/smoke_g01_http.py --url http://127.0.0.1:8050 --output /scratch/http
python scripts/test_playwright_g54.py --url http://127.0.0.1:5180 --output /scratch/screenshots
python scripts/test_playwright_g36.py --url http://127.0.0.1:5180 --output /scratch/screenshots
```

Маршрут Investigator `/assets/ahu-g36`. Из нового профиля доступны только NOMINAL и VALVE_CLOSED. Пример direct seek — `/api/v1/g36-benchmark?dataset=g36-1wk&scenario=VALVE_CLOSED&start=17647920&limit=3`. Последнее окно oracle — `/api/v1/g36-benchmark?dataset=g36-1wk&scenario=VALVE_CLOSED&panel=EXTRA_SIMULATED&start=18230340&limit=2`. Без query `dataset` используется принятый профиль 5wk.

Для Docker используйте отдельный backend-образ. `/scratch/docker-fixtures/input.sqlite3` должен содержать копию SQLite из принятой основы с известными fixtures.

```sh
docker build -t buildingpulse-g54-review:local -f backend/Dockerfile .
docker run --rm \
  --mount "type=bind,src=$DATA_ROOT,dst=/app/data,readonly" \
  --mount "type=bind,src=/scratch/docker-fixtures,dst=/g54-fixtures,readonly" \
  -e DATABASE_URL=sqlite:////tmp/buildingpulse-g54.db -e DATA_ROOT=/app/data \
  buildingpulse-g54-review:local sh -c \
  'cp /g54-fixtures/input.sqlite3 /tmp/buildingpulse-g54.db && exec python scripts/smoke_g01_container.py --g54'
```
