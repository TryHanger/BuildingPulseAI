# Проверка Stage 07

STAGE07 — распакованная поставка. APP — изолированная копия проекта после принятого Stage 06. SOURCE_NORMAL — копия закреплённого AHU_annual.csv. DESIGN05 и NORMAL06 — неизменённые ZIP предыдущих стадий. SCRATCH — отдельная папка вывода. До применения патча экспортируйте полную схему REST исходной копии. Используйте копии SQLite и LBNL-данных для smoke, как в VALIDATION-04.

```sh
(cd "$STAGE07" && sha256sum -c SHA256SUMS.txt)
cd "$APP"
python -c 'import json; from backend.app.main import app; print(json.dumps(app.openapi(), sort_keys=True))' > "$SCRATCH/openapi-before.json"
git apply --check "$STAGE07/BP_ML_DOMAIN_SHIFT_07.patch"
git apply "$STAGE07/BP_ML_DOMAIN_SHIFT_07.patch"
python -m research.ml_domain_shift_07.verify_no_model_07 \
  "$SOURCE_NORMAL" "$DESIGN05" "$NORMAL06" "$SCRATCH/registry.json"
cmp "$SCRATCH/registry.json" research/ml_domain_shift_07/DOMAIN_SHIFT_07_REGISTER.json
python -m research.ml_domain_shift_07.export_contract_07 "$SCRATCH/openapi-before.json" "$SCRATCH/research-openapi.json"
cmp "$SCRATCH/research-openapi.json" contracts/openapi-domain-shift-07.json
python -m pytest -q research/ml_domain_shift_07/test_applicability.py contracts/test_evidence_v1.py

# В отдельных терминалах для теста только исследовательского guard и неизменной ленты LBNL.
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 18057
python -m research.ml_domain_shift_07.verify_http_07 --api http://127.0.0.1:18057
```

Источник AHU_annual.csv берётся из проверенной копии Stage 05 либо извлекается из LBNL ZIP как LBNL_FDD_Dataset_SDAHU/AHU_annual.csv. SHA исходного CSV — 13a61e5b3e62dcf214b387dc57632073a8044c794eb8102d90d074aa80702d8b. Прочие контрольные суммы и версии лежат в DOMAIN_SHIFT_07_REGISTER.json и evidence. Аудит использует только стандартную библиотеку Python. Ни LBNL CSV, ни исходный G36 CSV, ни веса не дублируются в поставке.

Для локального HTTP используйте DATABASE_URL с отдельной SQLite, DATA_ROOT со скопированными данными и BUILDINGPULSE_AUDIT_SCRATCH внутри scratch. Рабочие оригиналы внесите в BUILDINGPULSE_PROTECTED_ROOTS. Endpoint принимает °F, отдельное подтверждение точности SP и физической роли, BAS origin и наблюдаемый режим. Полная схема новой операции сохранена в contracts/openapi-domain-shift-07.json.
