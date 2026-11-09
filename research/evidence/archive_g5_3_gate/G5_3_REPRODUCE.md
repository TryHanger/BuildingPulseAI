# G5.3 · Воспроизведение

Примените overlay из этой сдачи к принятому G5.2. В MANIFEST.json зафиксированы SHA основы, протоколов и изменённых файлов. Исходные четыре G36-5wk CSV берутся из BUILDINGPULSE_G5_2_G36_SOURCE_BYTES.zip. Поместите их в DATA_ROOT/g36-5wk отдельной рабочей копии. При отсутствии альтернатив окно конкретного прогона доступно при наличии его CSV. Таблица требует все четыре файла.

Официальный новый 1wk CoolingSeason baseline упакован отдельно, без дублирования fault probe. BUILDINGPULSE_G5_3_G36_1WK_SOURCE_BYTES.zip, 3 236 076 байт, SHA-256 8a4973ee0b624221b2bb993f7f3ce8c088a84345f2b45393868d127cf96930cf. CC BY 4.0, неизменённые байты издателя. Fault probe и паспорт берутся из артефакта G5.2. Сложите оба 1wk CSV в отдельный read-only каталог для проверки профиля. Источник не добавляется в runtime.

```sh
python research/g53/profile_transport.py /scratch/g36-1wk /scratch/1wk-profile.json
python research/g52/fetch_members.py /scratch/baseline --one-week-baseline
PYTHONPATH=. python research/g53/cross_controls.py /scratch/g36-5wk /review/outputs/G36_5WK_COMPARISON.json /review/outputs/CROSS_SCENARIO_INDEPENDENT_RESULTS.json /scratch/cross-profile.json
```

Первый скрипт проверяет профиль, не импортирует scorer. Второй выборочно получает один член официального ZIP. Третий читает только 5wk и независимо воспроизводит 12 сводок и бины команды. Ожидаемые результаты независимого аудитора включены как небольшая JSON квитанция.

В изолированном окружении с временной SQLite и DATA_ROOT, как в G5.2, выполните:

```sh
python -m pytest backend/tests contracts/test_evidence_v1.py tests -q
npm --prefix frontend run build
python contracts/check_fixture_types.py
```

Запустите FastAPI и Vite. Откройте /assets/ahu-g36 или вызовите GET /api/v1/g36-benchmark/comparison. Для Playwright используйте python scripts/test_playwright_g36.py --url http://127.0.0.1:5180 --output /scratch/browser. Контракт отдаётся как /api/v1/openapi.json. JSON окна BASIC и EXTRA_SIMULATED приложены как HTTP evidence. Четыре SHA исходных 5wk CSV и CRC содержатся в G36_5WK_MEMBER_RECEIPT.json.
