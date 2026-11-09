# G5.2 · Воспроизведение

Проверьте SHA256SUMS.txt и MANIFEST.json. Примените overlay к принятому G5.1. Исходные файлы из отдельного артефакта проверяются его SHA256SUMS.txt. В исследовательской копии разместите два CSV BaselineSystem.csv и CooCoiValStuck_0.csv в DATA_ROOT/g36-5wk. Оригинальные данные и SQLite держите отдельно. При отсутствии артефакта G36 endpoint сообщает об отсутствии источника. При несовпадении SHA выдаёт 409.

Серверная зависимость для G36 — стандартная библиотека Python. Независимый пересчёт использует существующие pandas и NumPy. Используйте FastAPI, Pytest, Vite и Playwright из принятой среды. Тесты требуют отдельной SQLite, DATA_ROOT, BUILDINGPULSE_AUDIT_SCRATCH и BUILDINGPULSE_PROTECTED_ROOTS как в G5.1.

```sh
python -m pytest backend/tests contracts/test_evidence_v1.py tests -q
npm --prefix frontend ci
npm --prefix frontend run build
python contracts/check_fixture_types.py
```

С работающими FastAPI и Vite проверьте /assets/ahu-g36. API выдаёт окно в исходных модельных секундах.

```sh
curl -fsS 'http://127.0.0.1:8050/api/v1/g36-benchmark?scenario=VALVE_CLOSED&panel=EXTRA_SIMULATED' > /scratch/g36-window.json
python research/g52/verify_experiment.py /unpacked/g36-5wk /review/outputs/G36_EXPERIMENT_SUMMARY.json /scratch/profile.json --http-window /scratch/g36-window.json
python scripts/test_playwright_g36.py --url http://127.0.0.1:5180 --output /scratch/browser
```

Для получения официальных байтов вместо отдельного артефакта можно выполнить python research/g52/fetch_members.py /scratch/g36-5wk. Опция --one-week-probe получает только два указанных probe-члена, а --directory-only читает только ZIP-каталог. При смене ETag диапазоны отклоняются до повторной квалификации источника.

Выпуск предназначен для воспроизводимости описательного результата. Настройка новых порогов по сохранённым результатам меняет протокол.
