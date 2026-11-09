> Текущий runtime handoff и запуск на scratch описаны в [handoff/README_REPRODUCE](../../handoff/README_REPRODUCE.md). Ниже сохранён порядок воспроизведения исходного аудита.

# BuildingPulse AI — пакет независимой проверки G0/G1

Дата 2026-11-07. Основание `PLAN-2026-11-07-v1.0`, SHA-256 мастер-плана `d51ca33845710396957b231d18204ea12b62b3bd379b85b0d2a3d6ae5c789d9f`.

Откройте [CURRENT_STATE](CURRENT_STATE.md), [DATASET_IDENTITY_LEDGER](DATASET_IDENTITY_LEDGER.md), [DECISION_REGISTER](DECISION_REGISTER.md) и [PRE-INTEGRATION_GATE](PRE-INTEGRATION_GATE.md). Все добавленные исходники находятся в `research/g0-g1/` и `contracts/`. В ZIP включены также неизменённые backend/ML, frontend source, тесты, pinned runtime versions, локальная SQLite и входы исторических тестов. Локальная SQLite отражает наблюдаемое состояние после G0; использованное при сборке состояние отдельно зафиксировано в [KNOWN_BROKEN](KNOWN_BROKEN.md). Полный публичный ZIP LBNL загружается по ссылке, а проверенные локальные срезы уже входят в пакет. Пакет исключает `.env`, кэши, node_modules, runtime dist и старые audit ZIP.

## Проверка ZIP

Распакуйте в отдельный каталог. `SHA256SUMS.txt` содержит хэш каждого файла архива, кроме самого списка. В Linux/WSL из каталога распаковки запустите `sha256sum -c SHA256SUMS.txt`. Внешняя сумма у файла `BUILDINGPULSE_G0_G1_AUDIT.zip.sha256`.

## Контракт

```sh
python -m venv .venv-audit
# Активировать это окружение согласно ОС.
python -m pip install -r contracts/requirements-audit.txt
python -B -m pytest -p no:cacheprovider -q contracts
python -B research/g0-g1/check_signal_map.py
python -B contracts/check_fixture_types.py
```

Node 24.11.0 для проверки типов, `openapi-typescript@7.10.1` и `typescript@5.7.3` вызываются через npx. Python validator использует JSON Schema 2020-12 и доверенный fixture registry. Проверены запрещённые enum/тип, invalid role и target/context, applicability, data mismatch, конфликт, запрет discriminator, uncertain, alias/source identity, empty roots, provenance события, probability и causal claim. Верификация включает отсутствие `SYS_CTL` в runtime, duplicate physical roots и независимую тревогу при плохом SAT.

## Legacy backend и локальный запуск

Используйте Windows Python 3.11.6 для исторической копии. В SQLite имеются относительные Windows пути; для Linux их нужно переводить в отдельной копии БД. Не запускайте исторические тесты на рабочем DB/Data Root. Далее команды PowerShell из корня распакованной копии.

```powershell
py -3.11 -m venv .venv-legacy
.\.venv-legacy\Scripts\Activate.ps1
python -m pip install -r research/g0-g1/requirements-baseline.txt
$Scratch = Join-Path ([System.IO.Path]::GetTempPath()) ("buildingpulse-g01-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $Scratch | Out-Null
Copy-Item buildingpulse.db (Join-Path $Scratch "baseline.db")
Copy-Item -Recurse data (Join-Path $Scratch "data")
$env:DATABASE_URL = "sqlite:///" + ((Join-Path $Scratch "baseline.db") -replace '\\','/')
$env:DATA_ROOT = Join-Path $Scratch "data"
python -B -m pytest -p no:cacheprovider backend/tests tests
python -B -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8050
```

Health доступен по `http://127.0.0.1:8050/api/health`. Для локального frontend в распакованной копии установите зависимости через `npm --prefix frontend ci`, затем запустите `npm --prefix frontend run dev -- --port 5180`. Typecheck проверен, browser E2E остаётся будущим gate. `docker compose config --quiet` проверяет конфигурацию; известный дефект image recipe в [KNOWN_BROKEN](KNOWN_BROKEN.md).

## Источники и отрицательные результаты

Команды скачивания и сверки в [DATASET_IDENTITY_LEDGER](DATASET_IDENTITY_LEDGER.md). Скрипт `python research/g0-g1/probe_basic_windows.py /path/to/official.zip` повторяет read-only поиск двух окон. Его вывод является исследовательским probe, а не проверкой production incident. Журналы в `research/g0-g1/logs/` содержат HTTP evidence, Git errors, test baselines, actual legacy OpenAPI и результаты contract/type checks.

Приёмка G0/G1 ожидается. На решение владельца вынесены исходный checkout с Git metadata и политика времени LBNL. Соответствие `coi_bias`/SAT и дубли severity остаются заблокированными до издательского подтверждения, а rules-first demo использует другой исходник при успешном G2/G3.
