# Проверка Stage 06 без повторного target inference

`STAGE06` — распакованный архив. `APP` — изолированная копия после Stage 05. `ARTIFACTS` — распакованный `source_fit` из принятого Stage 05. `INPUTS` — копии утверждённых `AHU_annual.csv` и `BaselineSystem.csv`. Их SHA указаны в квитанции. Папка содержит только эти два CSV. `SCRATCH` — отдельный каталог для вывода.

```sh
(cd "$STAGE06" && sha256sum -c SHA256SUMS.txt)
git -C "$APP" apply --check "$STAGE06/BP_ML_TRANSFER_NORMAL_06.patch"
git -C "$APP" apply "$STAGE06/BP_ML_TRANSFER_NORMAL_06.patch"
cd "$APP"
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
BP06_INPUTS="$INPUTS" BP06_ARTIFACTS="$ARTIFACTS" python -m pytest -q \
  research/ml_transfer_05/test_contract.py research/ml_transfer_06/
python -m research.ml_transfer_06.verify_trace_06 "$STAGE06" "$ARTIFACTS" "$SCRATCH/trace-check.json"
cmp "$SCRATCH/trace-check.json" "$STAGE06/INDEPENDENT_TRACE_CHECK.json"
```

Python 3.12.3, LightGBM 4.6.0, pandas 2.3.3 и NumPy 2.5.4 использованы в scoring. Остальные зависимости установлены по Stage 05 requirements. Тест с утверждённым CSV проверяет байты, сетку и загрузку весов без прогнозирования. Арифметический пересчёт использует стандартную библиотеку и не загружает LightGBM.

## История единственного исполнения

Точная форма команды запуска приведена для аудита. Разрешение Stage 06 исчерпано выполненным прогоном. Для проверки содержимого используйте пересчёт выше.

```sh
python -m research.ml_transfer_06.audit_execute_06 --role target_reference \
  --inputs "$INPUTS" --artifacts "$ARTIFACTS" --output "$SCRATCH/scored" \
  --audit-log "$SCRATCH/file-open-audit.json"
python -m research.ml_transfer_06.seal_existing_trace_06 "$SCRATCH/scored" "$ARTIFACTS"
```

Первая команда записала трассу и блоки, затем завершилась с отказом проверки доступа при попытке чтения выходной таблицы для SHA. Вторая команда восстановила только квитанцию. Первоначальная обёртка из `evidence/frozen_overlay` вместе с остальным overlay воспроизводит `evidence/PRE_EXECUTION_CODE.sha256`. Основной патч включает исправление чтения ожидаемых выходов, покрытое тестом с заглушкой.
