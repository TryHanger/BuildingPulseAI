# Повторение Stage 05

Выполняйте команды в изолированной копии принятого проекта после VALIDATION-04. Патч добавляет `research/ml_transfer_05/`. Переменная `OUT05` обозначает распакованный архив, `APP` — изолированный проект, `INPUTS` — каталог копий исходных файлов, `SCRATCH` — отдельный каталог вывода.

```sh
(cd "$OUT05" && sha256sum -c SHA256SUMS.txt)
git -C "$APP" apply --check "$OUT05/BP_ML_TRANSFER_DESIGN_05.patch"
git -C "$APP" apply "$OUT05/BP_ML_TRANSFER_DESIGN_05.patch"
cd "$APP"
sha256sum -c "$OUT05/evidence/PRE_SCORE_LOCK.sha256"
```

Получите оригинальный LBNL SD-AHU ZIP по странице издателя и сверьте его SHA с `TRANSFER_05_PROTOCOL.json`. Извлеките только здорового члена `LBNL_FDD_Dataset_SDAHU/AHU_annual.csv`. Файлы G36-1wk baseline/probe можно взять из уже проверенной копии VALIDATION-04 или из публикации Figshare при совпадении точных SHA. Исходное имя probe в проверочной поставке отличается от локального расположения. Его идентичность подтверждает SHA. В INPUTS используются имена `AHU_annual.csv`, `BaselineSystem.csv`, `CooCoiValStuck_0.csv`. [LBNL SD-AHU](https://faultdetection.lbl.gov/dataset/simulated-sd-ahu/) · [G36 Figshare](https://doi.org/10.6084/m9.figshare.29297999)

```sh
unzip -p "$LBNL_ZIP" LBNL_FDD_Dataset_SDAHU/AHU_annual.csv > "$INPUTS/AHU_annual.csv"
sha256sum "$INPUTS/"*.csv
# Python 3.12.3, с фиксированными версиями пакетов в requirements.txt.
python -m pip install -r research/ml_transfer_05/requirements.txt
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python -m pytest -q research/ml_transfer_05/test_contract.py
python -m research.ml_transfer_05.preflight "$INPUTS" "$SCRATCH/preflight.json"
python -m research.ml_transfer_05.fit_source "$INPUTS" "$SCRATCH/source-fit"
python -m research.ml_transfer_05.audit_support "$INPUTS" \
  "$SCRATCH/source-fit/SOURCE_FIT_RECEIPT.json" "$SCRATCH/input-support.json"
```

Для сверки сравните preflight, input-support и содержимое source-fit с файлами в поставке. Утверждённые версии и LightGBM SHA указаны в квитанции. Скрипт обучения проверяет SHA source перед чтением и не имеет ветки целевого inference. Поддержка входов использует только диапазоны, заголовки и маски. Файл эпизодов предназначен для будущей evaluation-разметки. В Stage 05 workflow scoring на G36 отсутствует.
