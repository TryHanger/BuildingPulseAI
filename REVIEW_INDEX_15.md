# BP-15 · Evidence-to-Action · индекс проверки

**Вердикт: `STOP_SOURCE_OR_CONTRACT`.** Все четыре случая проходят через исследовательскую цепочку Investigator. Для A воспроизводится сигнал модели, а обязательная идентичность заявленной инъекции SAT bias остаётся `UNAVAILABLE`. Для `ACCEPT_PRODUCT_DECISION_TRACE` требуется издательская привязка инъекции к конкретному члену ZIP и каналу SAT.

| Версия | SHA |
| --- | --- |
| Принятый Stage14 · `ACCEPT_STOP_RULE_INPUTS_UNQUALIFIED` | `1fc9265720f08957a8d28ab2d278b86800394fab` |
| Заморозка сценариев, методов и ожиданий до правок | `83c5ef46bfb30e01a201f6bfeb3d197625680cfb` |
| Точный HEAD проверенной реализации | `7adff0b4d1d17219a8321ae7d96e7d6e8040584d` |

Ветка `feat/evidence-to-action-15` основана на принятом SHA Stage14. База Draft PR — `research/field-apar-gate-14`. Финальный HEAD ветки включает этот отчёт и снимки экрана. Его точный SHA зафиксирован в описании Draft PR. Из корня опубликованного checkout он доступен через `git rev-parse HEAD`.

[Аудит исходного состояния, замороженный протокол и prior art](research/evidence/bp15/AUDIT_AND_PROTOCOL_15.md) · [заморозка SHA-256](research/evidence/bp15/PROTOCOL.sha256)

## Матрица результата

| Случай | Сигнал и ограничения | Следующая проверка | Результат |
| --- | --- | --- | --- |
| A · LBNL SAT | Stage02 PRODUCT_BASIC / SAT_ONLY. `MODEL_ANOMALY`, средний z = 5.52584424404951 > 3, 955/1440 минут. Идентичность члена ZIP проверена. Идентичность инъекции `UNAVAILABLE` по G0/G1 D002 и Stage02 `UNVERIFIED_PUBLISHER_ALIAS`. Причина `ABSTAIN`. | Запросить у LBNL привязку имени файла к инъекции. Сопоставить SAT с независимым калиброванным датчиком в том же режиме и сечении. | **STOP** по идентичности источника. **PASS** по вычислению и отказу. [Stage02](research/ml_repro_02/registry/MODEL_ARTIFACT_MANIFEST.json) · [D002](research/g0-g1/DECISION_REGISTER.md) · [снимок](research/evidence/bp15/screenshots/A-lbnl.png) |
| B · G36 healthy OOD | Stage06 / Stage07, `reduced-thermal-sat-v1`. 7/7 архивных блоков с ALERT на одном нормальном симуляционном прогоне, допущено 5425/10080 минут. Перенос `STOP_OOD_HEALTHY`. Активная уставка меняется в целевом прогоне, на обучении использовался домен с единственным значением уставки. Эксплуатационное наблюдение и причина `ABSTAIN`. | Сверить журнал активной уставки и режим. Собрать независимые нормальные прогоны с сопоставимыми режимами. | **PASS**. [Receipt](research/evidence/archive_bp_ml_transfer_normal_06/TARGET_NORMAL_06_RECEIPT.json) · [снимок](research/evidence/bp15/screenshots/B-g36.png) |
| C · Mendeley AHU23 | Stage09/10, `bas-fan-observation@1.0.0`. Правило A наблюдает ON → OFF притока (13:45, повтор 13:50 по часам книги). Правило B — `NO_OBSERVED_CHANGE`. В 17/18 отсчётах окна приток OFF, вытяжка ON. Оба правила опираются на одну книгу BAS. Для физической причины `ABSTAIN`. | Сверить привязку тегов. Измерить обратную связь каждого привода и расход или перепад давления исправным прибором. | **PASS**. [Трасса](research/evidence/field_native_09/observed/traces/event-AHU23.csv) · [снимок](research/evidence/bp15/screenshots/C-AHU23.png) |
| D · Mendeley AHU2 | 18 отсчётов окна, 2 PRE. Все четыре канала отсутствуют. Оба правила `INSUFFICIENT_DATA` / `ABSTAIN`. Для причины `ABSTAIN`. | Восстановить тренды статусов обоих вентиляторов и запросов нагрева и охлаждения. Получить обратную связь приводов и независимый расход. | **PASS**. [Трасса](research/evidence/field_native_09/observed/traces/event-AHU2.csv) · [снимок](research/evidence/bp15/screenshots/D-AHU2.png) |

## Контракты и границы

- В Investigator добавлен маршрут `/assets/evidence-to-action`. Режим `RESEARCH_ONLY` показывает часы источника, качество, применимость, аномалию или наблюдение, статус физической причины, свидетельства с общей линией происхождения и рекомендуемое измерение. Для LBNL отображается исходный SAT на всех оценённых минутах дня. Пропуски и минуты вне оценки не интерполируются. Для G36 доступны 60 нативных минут и 7 исходов блоков. Для Mendeley показаны два PRE и 18 оконных отсчётов каждого случая, включая отсутствующие значения.
- Один дополнительный [GET /api/research/transfer-trace-15](backend/app/api/endpoints/transfer_trace_15.py) отдаёт [замороженный JSON](backend/app/research_data/transfer_trace_15.json). Входные параметры отвергаются с 422, отсутствующий или изменённый артефакт с 503, операции записи с 405. Ответ содержит нативные секунды, исходную строку, SAT, активную уставку, сохранённый прогноз или null, допуск и причину отказа, блочные решения, покрытие и SHA-256. Чтение не вызывает модель или БД. [Контрактные проверки](backend/tests/test_transfer_trace_15.py)
- Переиспользованы Stage02 `/virtual-sensors/day`, Stage07 `/domain-shift-07` и Stage10 `/field-evidence`. Снимок OpenAPI совпадает с принятым после удаления одного нового GET и его четырёх схем. При ошибке источника представление показывает `UNAVAILABLE` и очищает данные предыдущего случая. Stage02 выполняет ранее утверждённый inference без изменения весов, калибровки и порога. Stage06 воспроизведён из сохранённого результата.
- Ссылки и SHA источников закреплены в [манифесте LBNL](research/g0-g1/DATASET_MANIFEST.json), [протоколе переноса с Figshare DOI](research/ml_transfer_05/TRANSFER_05_PROTOCOL.json) и [манифесте Mendeley V1](research/evidence/field_native_09/observed/SOURCE_MANIFEST_09.json). В Git добавлена принятая производная трасса Stage06 размером 500 571 байт, идентичная члену исследовательского архива по SHA-256. Она нужна для независимой сверки экрана без частной копии ZIP. Большие исходные выгрузки не входят в поставку.
- Проверка prior art ограничена сопоставлением подходов к FDD, объяснимости и измерениям. H1, новые APAR-кандидаты и производственный FDD вне эксперимента. B — один симуляционный нормальный прогон. C/D — одна полевая площадка и один день вмешательств. Статусы BAS и журнальные метки не подтверждают физическую причину.

## Сравнение представлений

| Проверяемая возможность | Только сигнал | Свидетельства и действие |
| --- | --- | --- |
| Точный статус наблюдения | Один и тот же вычисленный статус в A–D | Тот же статус, с отдельным статусом причины |
| Проверить утверждение по данным | Видно название случая и статус | Нативные отсчёты, источник и SHA, метод и применимость |
| Распознать ложную локализацию | Причина не отображается | Видны явный отказ и конкретное противоречие или пробел |
| Воспроизвести отказ и выбрать измерение | Видно `ABSTAIN`, где он является статусом наблюдения | Видны причины отказа и следующая проверка |

Например, в AHU23 обе версии показывают один переход BAS. Расширенная версия показывает отличающийся статус вытяжки, общий источник и необходимость независимого измерения. [Только сигнал](research/evidence/bp15/screenshots/C-signal-only.png) · [свидетельства и действие](research/evidence/bp15/screenshots/C-AHU23.png)

Это сравнение полноты и корректности представления по четырём случаям. Эффект на качество решений инженеров в пользовательском эксперименте не измерялся.

## Воспроизведение

Python 3.12.3, LightGBM 4.6.0, Playwright 1.64.1 / Chromium, Node 24.11.0 и Vite 6.4.5. Из корня checkout создайте окружение и установите [закреплённые зависимости](backend/requirements-audit-linux-py312.lock). Запускайте с отдельной SQLite и отдельным каталогом данных.

```sh
python -m pip install -r backend/requirements-audit-linux-py312.lock
python -m playwright install chromium
npm --prefix frontend ci
npm --prefix frontend run build

export VIRTUAL_SENSOR_RESEARCH_DIR="$PWD/research/ml_repro_02/registry"
export VIRTUAL_SENSOR_RESEARCH_MANIFEST_SHA256=359afbe1d3022e64c52ec5e1d916bb731a8c4c45aef9a835d0c9ab6ba73c0734
export BUILDINGPULSE_AUDIT_SCRATCH="$(mktemp -d)"
export BUILDINGPULSE_PROTECTED_ROOTS="$PWD"
export DATA_ROOT="$BUILDINGPULSE_AUDIT_SCRATCH/data"
export DATABASE_URL="sqlite:///$BUILDINGPULSE_AUDIT_SCRATCH/bp15.db"
export PYTHONPATH="$PWD"
python -m pytest -p no:cacheprovider -q backend/tests/test_transfer_trace_15.py
(cd research/evidence/bp15 && sha256sum -c PROTOCOL.sha256)
python research/evidence/bp15/extract_stage06.py | cmp - backend/app/research_data/transfer_trace_15.json
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 18075
```

```sh
# Второй терминал, из корня checkout
VITE_API_URL=http://127.0.0.1:18075 npm --prefix frontend run preview -- --host 127.0.0.1 --port 15196
# Третий терминал, из корня checkout
python research/evidence/bp15/check_browser.py --url http://127.0.0.1:15196 --screenshots "$(mktemp -d)"
```

Для полной исторической регрессии подготовьте отдельную копию checkout и заполните её `data/` и тестовую SQLite по [руководству baseline](docs/GITHUB_STAGE13_BASELINE.md). Часть старых тестов читает относительные пути `data/` из текущего каталога. Используйте этот checkout как текущий каталог и как `BUILDINGPULSE_AUDIT_SCRATCH`, укажите оригинальный workspace как `BUILDINGPULSE_PROTECTED_ROOTS` и назначьте переменные БД, каталога данных и Stage02-реестра на проверочную копию. На Linux нормализуйте `scenarios.data_path` только в тестовой SQLite.

```sh
export STAGE13_ARTIFACTS="$PWD/research/evidence/field_replication_13"
python -m pytest -p no:cacheprovider -q -rs backend/tests \
  research/ml_domain_shift_07/test_applicability.py research/ml_repro_02/test_research.py \
  contracts/test_evidence_v1.py research/ml_field_replication_13/test_replay.py
```

## Проверки

- [Браузерная сверка](research/evidence/bp15/check_browser.py) использует отдельные от UI источники. A — самостоятельный пересчёт по замороженному Parquet и исходным весам, 955 пар сверены с API, все метки времени и три точки проверены в интерфейсе. B — все 60 отсчётов и 7 блоков из принятых CSV. C/D — все 20 отсчётов на установку, исходы и SHA Stage09. [Результат](research/evidence/bp15/BROWSER_RESULT_15.json)
- Отрицательные проверки покрывают недоступный Stage02/06, повреждённый ответ Stage10, отсутствие данных предыдущего случая, подмену или отсутствие артефакта и запросы вне контракта. В браузерном сценарии фиксируются ошибки JavaScript и запросы записи. Сигналы обоих представлений совпали во всех четырёх случаях.
- [Тесты и сборка](research/evidence/bp15/TEST_RESULT_15.txt). Сборка завершилась с предупреждением Vite о размере основного JS-чанка. Сверка данных выполнена отдельным проверочным кодом. Внешний независимый аудит Draft PR следует после публикации.
