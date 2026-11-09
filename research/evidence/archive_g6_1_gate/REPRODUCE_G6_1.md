# G6.1 · Воспроизведение материалов для рассмотрения

Проверьте `sha256sum -c SHA256SUMS.txt`. Принятая основа G6.0 имеет SHA-256 `6cf3f518734abebc24281cb5cc7b38019052d5a4961e3a005ce79cc5c0a7209f` поверх G5.7. Примените `git apply --check /review/G6_1.patch` и `git apply /review/G6_1.patch` из корня восстановленной копии или скопируйте `overlay/`.

Запустите сервер обзора из рабочей копии, передав только каталог стимулов:

```sh
python -m research.study.serve /review/stimuli --port 18161
```

Маршруты A/B/C берутся из закрытого `coordinator-only/STUDY_BUILD.json`. Полный архив не предназначен для участников. Для сборки положите исходные проверенные CSV в `/scratch/data/g36-1wk` и `/scratch/data/g36-5wk`, а принятый G5.7 ZIP в `/original`. В MANIFEST приведена цепочка SHA.

```sh
python -m research.study.build /scratch/data /original /review/coordinator-only/SOURCE_TASK_MATRIX.csv /scratch/public /scratch/private
diff -qr /review/stimuli /scratch/public
python -m research.study.assignment
python -m pytest -q research/study/test_preflight.py
python -m research.study.check_browser http://127.0.0.1:18161 /scratch/data /original/BUILDINGPULSE_G5_7_GATE_REVIEW.zip /review/coordinator-only /scratch/screenshots
```

Используйте Playwright Chromium. Стандартный экран пилота по протоколу — 1440×900. Обзор и QA не записывают исследовательские ответы. Для будущего расписания координатор запускает `python -m research.study.assignment --seed PRIVATE_SEED --blocks 2` и сохраняет результат с SHA вне браузера. Требования одобрения, добровольности, конфиденциальности и порядок оценки в закрытом README и RUBRIC_V2.

Проверка продукта выполняется отдельно по REPRODUCE_G6_0.md на временной SQLite и DATA_ROOT. Журналы в `evidence/`.
