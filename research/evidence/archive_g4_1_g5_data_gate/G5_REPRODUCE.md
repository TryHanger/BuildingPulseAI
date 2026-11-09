# G4.1 / G5 · воспроизведение

1. Проверьте `SHA256SUMS.txt` в ZIP. Восстановите приложение из RC2, overlay G2, G3 и G4 по `evidence/freeze.log`, затем примените `overlay/` этой сдачи. В `MANIFEST.json` указаны прежние и новые SHA для каждой правки. Протокол и source outputs также входят в контрольные суммы.
2. Настройте временные SQLite и DATA_ROOT в отдельном каталоге. Используйте `BUILDINGPULSE_AUDIT_SCRATCH` и `BUILDINGPULSE_PROTECTED_ROOTS` согласно G4_REPRODUCE. Установите унаследованные зависимости backend, research и frontend. Выполните `python -m pytest backend/tests contracts/test_evidence_v1.py tests -q`, `npm --prefix frontend ci`, `npm --prefix frontend run build` и `python contracts/check_fixture_types.py`.
3. Для источникового gate используйте локальные копии официального PDF и ZIP из G5 readiness. Большой ZIP в этом пакете не дублируется.

```bash
python research/g0-g1/audit_lbnl.py /path/lbnl.pdf /path/lbnl.zip --local-raw data/raw > /scratch/lbnl-inventory.json
python research/g5/audit_sources.py /scratch/lbnl-inventory.json data/raw /scratch/G5_SOURCE_AUDIT.json
python research/g5/audit_field_receipt.py /unpacked/evidence/csiro-lfs data/raw /scratch/G5_FIELD_RECEIPT.json
```

4. С работающими FastAPI и Vite запустите `PYTHONPATH=. python scripts/smoke_g01_http.py` и `python scripts/test_playwright_g4.py --output /scratch/browser`. Скрипты G0–G3 regression лежат в `scripts/`. Отчёт для контрольного окна 10/11 наблюдений можно получить по `/api/v1/investigation?dataset_id=demo-g4-mat&start=2018-01-02T11:05:00&limit=10` и `limit=11`.
5. Для серверного отрицательного теста соберите `PYTHONPATH=. python scripts/build_g4_demo.py /scratch/missing-mat --omit-mat`. Во втором процессе FastAPI в отдельном scratch выставьте `backend.app.services.investigator_v1.DEMO_DIR = Path('/scratch/missing-mat')` перед запуском Uvicorn. Передайте его URL в `scripts/test_playwright_g4.py --missing-mat-api`. Исходный demo не меняется. Минимальная fixture и фактический ответ также лежат в `outputs/`.
6. Docker-проверка использует `backend/Dockerfile` и `python scripts/smoke_g01_container.py` внутри образа. Установите `DATABASE_URL=sqlite:////tmp/g41.db` и `DATA_ROOT=/app/data`, смонтировав проверенную папку данных read-only.

`PROTOCOL_G5_v1.md` и `G5_SOURCE_AND_TASK_READINESS.md` описывают gate. Запуск обучения требует отдельного решения.
