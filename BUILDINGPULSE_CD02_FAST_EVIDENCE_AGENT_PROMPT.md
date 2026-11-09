# BuildingPulse AI — CD-02 Fast Evidence Sprint (Master prompt for coding agent)

Твоя роль — исполнитель **короткого экспериментального исследования**. Не задача «спасти» CD-01 или улучшить красивые проценты: нужна независимая проверка, какие механизмы заслуживают следующего более крупного исследования. Работай только в изолированной `research/cd02/` директории. Не делай commit/push/merge/deploy, не меняй production Stages 1–7.1 и предыдущие научные результаты, не привлекай других LLM-агентов, не управляй реальными AHU или BAS.

## Прочитать перед началом

Обязательны:
- `BUILDINGPULSE_CD01_INDEPENDENT_AUDIT.md` — внешний аудит реально выполненного CD-01.
- Исходные файлы из `BUILDINGPULSE_AUDIT_CD01_PARALLEL_PILOTS.zip`: `DECISION_MATRIX.md`, `code/common/core.py`, `code/lanes/{A,B,C,D,E}/run.py`, `results/lanes/*`, `splits/*`, `DATA_PROVENANCE.md`.
- Оригинальные `SCIENTIFIC_REPORT.md`, `AGENT_RESPONSE.json` по механизмам search2 C01/C05/C07, search4 C03/C06, NLID-LV-01. Отчёты — научные гипотезы, не подтверждение field transfer.
- Прошлые отрицательные результаты Stage 8A–8C и H3. Сценарии LBNL/CSIRO/Nesbitt, уже раскрытые в предыдущих этапах, **не могут** стать новой слепой выборкой.

## Цель и неизменные правила

Три **коротких независимых пакета** вместо пяти новых больших моделей: CD02-Q (quality of evidence & data inventory), CD02-D (observability/sensor-signature experiment), CD02-R (robustness of simple ARX). Q — инфраструктурный gate для D; R можно тестировать параллельно. Не начинать необязательные эксперименты, если физическая семантика не доказана.

Для любых сравнений фиксировать до просмотра прогнозных невязок: датасет, physical event grouping, train/cal/test dates, isolation of injection-observable channels, normal masks/washout, maximum acceptable detection delay (предложение: 60 минут; если иной — обосновать заранее), FAR <=5%, false alarms/8h <=2, acceptable coverage, threshold selection, treatment of left-censored and pre-existing alarms. Если тест ранее изучен — DEVELOPMENT-EXPLORATORY без claim независимой валидации. Не объявлять p<0.05 на трёх-четырёх неоднозначных эпизодах.

### Gate 0 — целостность CD01 без переписывания результатов

В отдельной папке **только новые** тесты. Продемонстрировать дефект `core.evaluate` на `[ALARM, ALARM, NORMAL, ALARM, NORMAL]` с fault внутри: текущий `new=False` несмотря на новый alarm-start после очищенного участка. В новом scorer реализовать **две** метрики: `strict_clean_start_onset` и `any_new_onset_after_fault`; вторую не выдавать за causal attribution. Считать эпизоды на календарной сетке с gap resets, fan on/off, pre-fault, left-censored, fault-day overlap, NaN/Inf, no 0/0. Уточнить, что A всё равно FAIL по FAR; исходные CD01 результаты и их хэши оставить неизменными.

Изменить verifier для CD02: строгие SHA на входах и коде; точные сравнения флагов и целочисленных counts; численное сравнение floats по предрегистрированным tolerances; тест, чувствительный к ошибкам метрик, а не чтение готового JSON. Записать все версии зависимостей. Не объяснять несовпадение без реального diff.

### CD02-Q — физическая доступность свидетельств (feasibility first)

Инвентаризировать локальные реальные и симулированные AHU наборы: LBNL SD-AHU, CSIRO AHU9/10, Nesbitt, и другие уже доступные *официальные* датасеты. Для **каждого** требуемого канала указать: физическое местоположение, единицы, pre/post injection, COMMAND vs FEEDBACK vs SETPOINT vs OVERRIDE, достоверность по исходному заголовку/спецификации и независимость от target/label. Отличать estimated sensor и measured sensor. Проверить совместимость единиц °F/°C, расхода/давления, режимов и ресемплинга. Точная копия одного канала не является вторым измерением.

Сделать матрицу "fault family × physically independent channel × dataset", указать, какие семейства имеют достоверные (построенные без injection markers) fault labels. Если есть реальные независимые paired controller command + physical feedback + flow/coil power/reference SAT, переходить к D на real data. Если нет — разрешён **только simulation-labelled experiment** с отдельным результатом и с открытой пометкой того, что некоторые simulated actuator states напрямую внедрены в сценарий. Не использовать их как независимое полевое доказательство. Не подменять отсутствующие сенсоры искусственными.

### CD02-D — falsifiable observability experiment

Известный аналитический результат D: после nuisance projection projected rank = 0 для SAT+command при произвольной неизвестной нагрузке, +1 при независимом flow ИЛИ independent SAT ref, +2 при обоих; duplicate SAT не помогает. Это **условный toy**, не новый empirical outcome.

При наличии допустимой физически осмысленной симуляции либо независимых реальных truth сделать минимум три fault families (sensor bias, actuator loss/stuck, air damper) только если данные это позволяют, с одинаковыми погодно/нагрузочными сценариями или явно фиксированными confounders. Идентификация и сравнение должны использовать **только доступные к моменту решения каналы**, без current/future label leakage или proxy from injected state. Считать взаимную различимость пар fault signatures, empirical rank (после нормализации на шум), smallest useful singular value c confidence intervals, top-1 fault isolation, abstention risk/coverage. Тестировать negative controls: duplicate SAT, zero sensitivity flow, common-mode drift, disturbed flow sensor, no-excitation conditions, simultaneous fault. Базовые правила: existing best temperature residual, fixed expert sensor, random choice, all-channel upper bound (только как oracle, не deployable).

Если независимых подписанных каналов и truth нет — **NOT_EVALUABLE на поле**, но можно предоставить корректный toy + physical data requirements. Не выдавать toy за улучшение BuildingPulse AI.

### CD02-R — ARX as a simple baseline only

В CD01-B lagged SAT ARX на TEST-EXPOSED Nesbitt дал 4/8 new onset, FAR 1.49%, 0.94 false episodes/8h, против M1 1/8, FAR 1.71%, 0.37 ep/8h. Из четырёх тревог одна возникла через 605 минут после start, одна — на эксперименте BAS `setpoint demand adjust`. Это **не подтверждение conservation transfer**, и ARX не считается новой победившей моделью.

Провести forensic re-score без переобучения и изменения порогов: latency <=15/30/60/120 min, status of BAS setpoint adjustment, start boundary sensitivity, pre-existing alarms, fault-only masks, seasonwise FAR and coverage; сравнить с M1 на совершенно одинаковых временах, mask, episode grouping, budget. Нельзя выбрать новую latency границу постфактум как основной доказательный критерий. Показать paired uncertainty (exact McNemar where appropriate, grouped bootstrap if enough independent groups) и negative controls (shifted timestamps, no-fault mode changes). Если можно достать действительно новые физические experiment dates для отдельной валидации, freeze before predictions; иначе только DEVELOPMENT-EXPLORATORY.

### Финальный научный triage

Ровно три итоговые строки Q, D, R: data requirements, main comparison, numeric outcome, negative controls, limits, explicit STOP / NEED_NEW_DATA / PROMISING_EXPLORATORY. Допускается ноль продвигаемых идей. Не тратить время на переписывание старого Stage8C или создание новой архитектуры. `CD01-A` погодный Q95 и `CD01-B` MixBound при текущих данных — закрытые отрицательные пилоты, без новой настройки.

### Финальный audit ZIP — ОБЯЗАТЕЛЕН

Название: `BUILDINGPULSE_AUDIT_CD02_FAST_EVIDENCE.zip`. Включить **полный реально изменённый код**, исходники/сэмплы и исходные идентификаторы+SHA, physical signal map, split manifests, immutable freeze, train/cal/test, per-point metrics and timestamps, per-event outcomes, full stdout/stderr и реальные тест-логи, Git diff/status либо явное предупреждение об отсутствии Git, негативные контроли, env versions, reproducible commands, `CLAIM_TO_EVIDENCE` и SHA-256 на все файлы. Выполнить самостоятельную чистую распаковку с повторным запуском в одном процессе проверки. Любые FAIL должны остаться видимыми, а не заменяться отчётным PASS.

Не изменять программу BuildingPulse AI, не предлагать deploy и не утверждать научную новизну. По окончании **остановиться**. Только после нашего независимого аудита можно решать, что делать с полученным экспериментом.
