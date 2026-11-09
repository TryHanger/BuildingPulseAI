# Воспроизведение G0–G1

Текущая версия описана в [приёмке rc.2](rc2/REVIEW.md). Ниже сохранён исторический прогон rc.1.

Тестирование выполнено в WSL2 x86_64, Python 3.12.3, Node 24.11.0, npm 11.6.1, Chromium 156.0.8078.4. Backend image отдельно запущен с Python 3.11.17. Точные версии пакетов в [environment.txt](logs/environment.txt).

## Локальная копия

Распакуйте ZIP, перейдите в его корень и проверьте `sha256sum -c SHA256SUMS.txt`. Команды ниже предназначены для Linux/WSL с Node и Python. Скрипт создаёт новую копию вне исходника и выводит переменные для запуска на ней.

```bash
scratch_env=$(bash scripts/prepare_g01_scratch.sh "$(mktemp -d)/runtime") && eval "$scratch_env"
python -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements-test.txt
python -m playwright install chromium
npm ci --prefix frontend
```

Для второго терминала примените те же переменные `scratch_env` и перейдите в ту же копию. Для smoke после изменяющих тестов можно использовать второй свежий scratch. В обоих случаях запускайте сервер с адресом 127.0.0.1.

```bash
python -m pytest -p no:cacheprovider -q --basetemp "$TMPDIR/pytest-backend" backend/tests
python -m pytest -p no:cacheprovider -q --basetemp "$TMPDIR/pytest-contract" backend/tests/test_investigator_v1.py contracts
python -m pytest -p no:cacheprovider -q --basetemp "$TMPDIR/pytest-research" tests
npm --prefix frontend run build
python contracts/check_fixture_types.py
docker compose config --quiet
docker build -f backend/Dockerfile -t buildingpulse-g01-audit:local .
```

```bash
# Терминал 1
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8050
# Терминал 2
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5180 --strictPort
# Терминал 3
PYTHONPATH=. python scripts/smoke_g01_http.py
python scripts/test_playwright_g01.py
```

Собранный backend image проверен в одноразовом контейнере с `--network none`. В контейнер монтировалась только scratch-копия, с `DATABASE_URL=sqlite:////audit-scratch/docker-smoke.db`, `DATA_ROOT=/audit-scratch/data` и audit guard. Изнутри контейнера запрошены `/api/health` и `/api/v1/datasets`. Для переноса контейнерных путей используйте копию scratch БД.

## Результаты

| Проверка | Результат |
|---|---|
| Полный `backend/tests` | 119 PASS. Первый прогон выявил отсутствие matplotlib, второй — Windows-разделители в SQLite. Логи первых прогонов сохранены, исправления включены. |
| Отдельный runtime/negative contract | 55 PASS. В том числе ошибки timestamp, повтор и конкурентный импорт, rollback, отсутствующий и изменённый источник, запрет OFF + VIOLATED, неизвестная модель, причинные подмены, отдельные статусы методов и guard. |
| Исторический `tests` | 43 PASS. |
| Frontend и fixture types | TypeScript/Vite PASS, 8 fixtures типизированы. Предупреждения npm и Vite сохранены. |
| Playwright | 1440×900, 1280×800, 1024×768, 390×844. Скриншоты используют живой FastAPI. Отдельные тесты браузера подставляют HTTP 503, пустой ряд, недоступный канал и разрыв, чтобы проверить обработку пограничных случаев. |
| HTTP smoke | Все запрошенные операции 200, ответы сверены со схемой. 2018-01-01T01:00:00 даёт OFF / NOT_EVALUABLE. 2018-01-02T06:01:00 даёт fan-on, UNKNOWN и выполненную проверку диапазона команды. |
| Docker | Compose config, отдельный backend image build, import ml/models, health и v1 datasets PASS. Первый smoke через проброс порта WSL завершился reset, проверка внутри изолированного контейнера прошла. |
| Docker Python 3.11, копия пакета | `python -m pytest -p no:cacheprovider -q --basetemp /candidate/tmp/pytest-full backend/tests contracts tests` · 208 PASS. |
| Независимая проба | 8 fixtures PASS, три выявленные недопустимые подмены отклонены. Исходный probe допускает point detection без event. В тесте с обязательной регистрацией инцидента тот же payload отклонён. |

Логи находятся в `logs/`, HTTP ответы — в `http/`, снимки экрана — в `screenshots/`. Научные исходники, манифест и исторические правила лежат в `research/g0-g1/`.
