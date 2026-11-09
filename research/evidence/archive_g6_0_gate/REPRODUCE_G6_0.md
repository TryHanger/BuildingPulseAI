# G6.0 · Воспроизведение

Из распакованного архива выполните `sha256sum -c SHA256SUMS.txt`. Основа — рабочая копия принятого G5.7 `BUILDINGPULSE_G5_7_GATE_REVIEW.zip`, SHA-256 `2781f810c6c9fc6a38e31531ae1691d219a3987d9f71f480f56c84e390252cbf`. В отдельной копии выполните `git apply --check /review/G6_0.patch` и `git apply /review/G6_0.patch` либо скопируйте `overlay/`.

```sh
python /review/verify_design.py /original
python /review/verify_design.py /original --seed 20261108 --blocks 2
```

`/original` содержит принятые G5.3 и G5.7 ZIP. Скрипт сверяет окна и фокусы по архивным результатам, квитанции LBNL/RBC и баланс расписания. Он не запускает scorer и не собирает ответы. Таблицу задач и ответы держите отдельно от материалов участника. Воспроизведение стимулов и предварительная проверка утечек описаны в ENGINEER_EVALUATION_PROTOCOL_V1.md.

Для проверки продукта используйте временную SQLite и DATA_ROOT с источниками G5.7. Задайте BUILDINGPULSE_AUDIT_SCRATCH и BUILDINGPULSE_PROTECTED_ROOTS, как в принятой основе. Запустите FastAPI и Vite с VITE_API_URL, указывающим на backend.

```sh
python -m pytest backend/tests contracts tests -q
npm --prefix frontend run build
python -m openapi_spec_validator contracts/openapi-v1.yaml
python contracts/check_fixture_types.py
PYTHONPATH=. python scripts/smoke_g01_http.py --url http://127.0.0.1:8050 --output /scratch/http
for scenario in g54 g36 g01 g3 g4; do
  python "scripts/test_playwright_$scenario.py" --url http://127.0.0.1:5180 --output "/scratch/screens-$scenario"
done
```
