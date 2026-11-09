# Воспроизведение предварительного source gate

Python 3.12.3. Установите окружение из `backend/requirements-audit-linux-py312.lock`. Возьмите восемь файлов по ссылкам `download_url` в `evidence/SOURCE_PROVENANCE_11.json` и сохраните с исходными именами в отдельный каталог `RAW`. Для принятой рукописи используйте [файл CTU](https://dspace.cvut.cz/server/api/core/bitstreams/2f9d64ab-bbd6-487c-b120-3d01bcbf4af2/content) и задайте путь в `PAPER`. При необходимости можно скачивать его последовательными HTTP Range и проверять полный хэш. Оригиналы остаются локальными.

```sh
EV=research/evidence/field_apar_gate_14
OUT=$(mktemp -d)
(cd "$EV" && sha256sum -c PREREGISTRATION.sha256)
python -m research.field_apar_gate_14.audit "$RAW" "$PAPER" "$EV" "$OUT"
for f in CHANNEL_ROLES_14.csv COMPARISON_ELIGIBILITY_14.csv GATE_RESULT_14.json; do
  cmp "$EV/$f" "$OUT/$f"
done
python -m research.field_apar_gate_14.verify_independent "$RAW" "$PAPER" "$EV"
python -m pytest -p no:cacheprovider -q research/field_apar_gate_14/test_audit.py
```

Источник содержит 118 строк расписания на 19 датах. Ledger компактно задаёт каждый нативный 300-секундный отсчёт через дату, первую метку и исключённый конец. Разворачивать интервалы можно с шагом 300 с без округления. Календарные отметки вмешательств и ±1 день не являются разметкой здоровья. Числа температуры, сравнения и прогнозы не выгружаются.
