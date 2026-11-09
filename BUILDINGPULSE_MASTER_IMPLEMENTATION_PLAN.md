# BuildingPulse AI — план реализации продукта, исследований и защиты

**Версия:** `PLAN-2026-11-07-v1.0`  
**Основание:** предоставленное пользователем описание восьми экранов, перечня методов и исключений; выводы предыдущих независимых ревью.  
**Статус:** технический план. **Не** подтверждение того, что перечисленные функции уже реализованы в текущем репозитории. До изменений обязателен read-only аудит рабочего дерева.

## 0. Решение, которое больше не меняем без зарегистрированного основания

**Продукт:** интерактивное рабочее место инженера для воспроизведения исторической телеметрии AHU, обнаружения отклонений несколькими специализированными средствами и проверки свидетельств / ограничений инженерного заключения.

**Главный прикладной исследовательский вопрос:** что даёт совместное использование *режимно-корректных правил*, *проверенного статистического или ML-детектора* и *контекстного анализа управляющих команд* относительно каждого слоя отдельно — при одинаковой доступной панели измерений, общей тестовой выборке и одинаковом бюджете ложных тревог? Отдельно: помогает ли интерфейс инженеру принимать корректные решения на фиксированных задачах?

**Не претендуем** на мировой новый алгоритм, автоматическую истинную локализацию каждой неисправности, доказанное внедрение на реальном здании, экономию энергии без счётчиков, живое BAS-подключение, строгую вероятностную калибровку без данных, или причинную идентифицируемость по одному residual.

**Обязательная демонстрация** не зависит от ML: импорт → валидация → схема AHU + replay → режимно-корректное правило/измеримый симптом → инцидент → карточка наблюдений/нехватки данных → отчёт. Если ML подтверждён, добавляем его остаток и сравнение. Нельзя демонстрировать выдуманную тревогу как вычисленную.

## 1. Роли и права работы двух агентов

| Роль | Может читать/изменять | Не может самостоятельно решать | Результаты на каждом переходе |
|---|---|---|---|
| Умный агент `S` (Research & Backend) | `backend`, `data adapters`, `research`, `experiments`, серверные контракты, миграции/скрипты | Выбирать научную истину по хорошему графику; подменять dataset; переписывать чужую часть фронта; назначать себе self-approved SOTA; пушить/deploy без разрешения | Код + доказательства, source hashes, сравнительный журнал, тесты, выпуск API контрактов |
| Фронтенд-агент `F` (UI) | `frontend`, UI fixtures, стейт, charts, SVG, E2E UI tests | Менять типы/смысл backend Evidence, придумывать fault probability, генерировать fake live данные, запускать/изменять ML и серверное reasoning | Готовые страницы на fixtures, visual screenshots, build/tests, список требуемых API |
| ChatGPT (научный аудитор) | Решения по SCIENCE/GO/STOP и независимая проверка артефактов | Объявлять результат воспроизведённым без исходного кода/байтов и сравнения | Независимый вердикт после каждого research gate |
| Пользователь (владелец) | Архитектурные и продуктовые приоритеты, выпуск и публикация | — | Утверждение scope, breakpoints, существенных изменений |

**Разделение файлов:** S владеет backend и `contracts/openapi.yaml`; F — фронтом. F имеет только *read-only* доступ к контракту и fixture JSON; при необходимости изменений создаёт `API_CHANGE_REQUEST.md`, не правит backend-схему. S не изменяет UI без выделенного совместного integration task.

**Нужны два отдельных branch/worktree**, общая папка только для версионированных схем/fixtures и отдельный интеграционный branch. Не выполнять commit/push/deploy в общий remote автоматически без принятой политики владельца.

## 2. Внешние ограничения — отсеять невозможное ДО эксперимента

| Идея | Известное предварительное ограничение | Gate до написания кода | Если gate не пройден |
|---|---|---|---|
| `sa_bias` / `coi_bias` как wow | Официальный LBNL PDF именует SAT файлы `sa_bias_*`; в исторических материалах встречается `coi_bias_*` | Получить **реальный** ZIP, записать список, SHA256 файлов, сравнить содержание/происхождение, подтвердить версию и каналы | Не делать scientific claim и auto alarm на этом кейсе; оставить как неподтверждённый архив/скрыть демо |
| Сравнение клапанной команды с реальным перемещением | `CHWC_VLV_DM` Basic=Y, `CHWC_VLV` Basic=N | Проверить наличие реального независимого position feedback и его семантику в подключаемом источнике | BASIC показывает `NOT_EVALUABLE`; EXTRA отдельно помечается SIMULATION/EXTRA |
| Физический баланс охлаждающего теплообменника | Для BASIC LBNL потоки `SA_CFM/OA_CFM/RA_CFM` не входят в панель; влажность тоже не подтверждена в BASIC | Инвентарь независимых приборов + режим сухой/влажный + единицы/местоположение | Не разрабатывать thermal balance для BASIC; оставить plugin interface |
| Раннее обнаружение fault по onset | В годовых fault files моделируемая неисправность может присутствовать весь период; onset внутри не подтверждён | Документированная дата воздействия и исходная здоровая история | Нет latency metric; оцениваем steady fault classification/detection без имитации onset |
| Open-FDD plug-and-play | Python oracle и большой backend — разные продукты; разные snapshots документации | Exact package/tag, LICENSE, source functions, required points, prerequisite behavior; локальный маленький compatibility proof | Реализовать 1–2 простых APAR правила самостоятельно на опубликованной физической логике |
| LightGBM virtual SAT | Прежний smoke на одном зимнем дне дал высокую ошибку на здоровом дне; авторские SOTA-метрики на другой панели/горизонте | Достаточный healthy train + validation + test, feature policy, matched simple baselines | Не выпускать ML-сигнал в продукт, оставить rules-first; не считать провалом всей архитектуры |
| PELT / ruptures | Offline changepoint использует будущее относительно точки изменения | Видимое обозначение `retrospective`, отсутствие заявления об online alarm | Только research/offline view или исключить |
| Bayesian Network | Есть библиотеки, но нет проверенных CPDs, причин и независимой калибровки | Документированные fault signatures/независимые эпизоды/BN sensitivity | Не выдавать вероятности; evidence catalogue без численного posterior |
| TS-TCC/CA-TCC/KoopmanVAE | Разные задачи и недоступность прямой репликации в нашей текущей задаче | Full author protocol/code + same-label classes / target task + matched baseline | Paper-only / future candidates, не блокируют MVP |
| 3D/BIM, live BACnet, LLM diagnoses | Инфраструктура, безопасность и отсутствие пользы для первого end-to-end | Реальная инженерная необходимость, тестовый стенд, подтверждённая ценность | Не включать в MVP |

**Дополнительный источникный конфликт:** страница LBNL упоминает загрузку 20 CSV, а официальный PDF перечисляет 20 faulted + 1 healthy = 21 сценарий. Фактическое число физических CSV установить только по реальному ZIP; количество в статье не подменяет инвентаризацию.

**Источники, проверенные перед формированием плана:** официальный [LBNL SDAHU inventory](https://fdddata.lbl.gov/data/Simulated_LBNL_FDD_Data_Sets_SDAHU/LBNL_FDD_Data_Sets_SDAHU.pdf), [LBNL dataset page](https://faultdetection.lbl.gov/dataset/simulated-sd-ahu/), [Open-FDD Python package](https://github.com/bbartling/open-fdd/blob/master/docs/ecm/README.md), [Open-FDD `pyproject.toml`](https://github.com/bbartling/open-fdd/blob/master/pyproject.toml), [ECharts official API](https://echarts.apache.org/en/api). Релиз/тег каждого внешнего компонента закрепить в реестре до копирования кода.

## 3. Что входит в продукт к первой полноценной защите

### MUST (демонстрация без необоснованных допущений)

1. **Dataset Explorer:** загрузка или выбор проверенного исторического CSV, `source_type`, инвентарь, соответствие колонок, статусы ошибок, source hash.
2. **AHU Replay:** корректная 2D-мнемосхема, основной режим (`OFF / COOLING / ECONOMIZER / TRANSITION / UNKNOWN`), общий контролируемый таймлайн и синхронные графики.
3. **Simple Diagnostic Engine:** по крайней мере 2 проверенные инженерные проверки; один независимый простой baseline; качественная кластеризация исходных событий во временные инциденты.
4. **Incident Queue & Inspector:** серьёзность как инженерная категория, не выдуманная вероятность; факты, условия применимости, причины неоднозначности, исходные точки и рекомендации проверки.
5. **Sensor Panel BASIC/EXTRA:** только реальные ранее записанные каналы. `EXTRA` — отдельное привилегированное исследовательское представление; `GROUND_TRUTH_ONLY` никогда не поступает в модель.
6. **Report & Research:** один экспорт с источниками/версиями/ограничениями; матрица fault × method там, где есть достоверная fault разметка, иначе `N/A`.
7. **Tests & Repro:** интерфейсный E2E, правильность времени, единиц, режимов, гейтов, lineage, неизменяемость исходных файлов.

### SHOULD (после готового MUST)

- Ridge virtual SAT или LightGBM при доказанной нормальной калибровке и полезности.
- Controller-effort model со сравнением на корректно сопоставленных режимах.
- Evidence Graph через React Flow и переключение двух историй.
- Лаборатория изменения доступной панели с пересчётом применимости методов.
- UX-исследование на заранее заданных инженерных заданиях.

### NOT NOW

- BN fault posterior, автоматические оптимальные рекомендации измерения, полнофункциональный BMS live connector, 3D-BIM, LLM диагностика, full multi-fault, обучение собственного KoopmanVAE, универсальная HVAC-платформа для произвольного здания.

## 4. Единый контракт — обязательный до параллельной разработки

В версии `api-v1` **не повторять старый учебный `evidence_contract.py`**: у него обнаружены проблемы с Pydantic/runtime типов, статусами, missing quality, конфликтами и свободным `validated_discriminator`. Он НЕ должен быть импортирован в production.

### 4.1 Канонические сущности

- `Dataset`: immutable sha256, license/source, simulation/field, scenario_id, scenario_label_source, time_zone, original units, release identity, import status.
- `Signal`: canonical_id, original_column, equipment_id, kind (`MEASUREMENT|COMMAND|SETPOINT|DERIVED|MODEL_INTERNAL|GROUND_TRUTH_ONLY`), unit, physical_sensor_id?, lineage_roles (`TARGET|CONTEXT|DERIVED_FROM`), basic_eligibility, quality.
- `TimeWindow`: `[from_utc, to_utc)`, sample rate, missingness, source hash, future cutoff.
- `ModeState`: mode, entered_at, transition hold, evidence of mode, confidence as `KNOWN|INFERRED|UNKNOWN` (не вероятность).
- `MethodApplicability`: `APPLICABLE|INAPPLICABLE|INCONCLUSIVE`, reason, missing signal roles, regime, source.
- `Observation`: method_id/version, time, predicate `VIOLATED|NOT_VIOLATED|INDETERMINATE`, observed_values, threshold, source lineage, quality status, mode, anomaly signal vs cause candidate.
- `Evidence`: observation ref, hypothesis refs only if method is valid for causal inference, support/contradict/unknown, source dependencies, explanation and trace.
- `Incident`: event start/confirmation/end, group key, evidence refs, `detection_state`, `cause_state`, `data_state`, `model_state`, exact raw source links.
- `Hypothesis`: cause type, supported/contradicted/unknown checks, applicability and *which independent test would discriminate*; no numerical probability without calibration.
- `Recommendation`: non-automatic inspection instruction, preconditions, safety notes and expected type of measurement, never auto OT action.

### 4.2 Five independent status axes

1. `data_status: VALID|DEGRADED|INVALID|UNKNOWN`
2. `method_status: APPLICABLE|INAPPLICABLE|INCONCLUSIVE` **per method**
3. `anomaly_status: DETECTED|NOT_DETECTED_IN_EVALUATED_TESTS|UNASSESSED|CONFLICTED`
4. `cause_status: UNEXPLAINED|AMBIGUOUS|ISOLATED_CONDITIONAL|CONFIRMED_EXTERNALLY`
5. `model_scope: IN_SCOPE|OUT_OF_SCOPE|UNKNOWN`

UX отображаемая метка вычисляется на сервере, но не уничтожает эти оси. `NOT_DETECTED` не означает физическую исправность. `CONFIRMED_EXTERNALLY` только с привязанным событием независимого теста/инженерным актом.

### 4.3 Обязательная строгая проверка

- Pydantic strict enums и `extra='forbid'`; `Literal` только как подсказка Python недопустим без runtime validation.
- Нормализовать aliases `SAT` / `SA_TEMP` в один canonical ID с source dataset + physical sensor ID; не объединять разные реальные датчики по одинаковой строке.
- Разделять роли источников `target`, `context`, `derived` и `ground truth`; пересечение контекстов **не равно** независимости/зависимости физического показания. Provenance groups — вспомогательная карта, не доказательство статистической независимости.
- Не принимать пустой список первичных корней измерения для измеряемого факта. Synthetic/handwritten policy должна иметь явно заданный иной provenance type.
- Не прятать конфликт `ANOMALY vs NORMAL`; сохранить несовместимые observations и режим/версию.
- Невалидное качество SAT по умолчанию делает SAT-зависимое заключение `INCONCLUSIVE`, но не отменяет сигнал о неисправности самого датчика.
- Нет сервера с подтверждением -> `validated_discriminator` не может выставляться через клиентский JSON. Серверный registry: test_id, hypothesis scope, source hash, method_version, validation report.
- `NO_ALARM` только когда реально выполнен хотя бы один информативный применимый тест с достоверным отрицательным результатом и нет активных противоречий/аномалий в заявленном охвате.

### 4.4 API v1 (S выпускает OpenAPI, F по нему делает UI)

```text
GET  /api/v1/datasets
GET  /api/v1/datasets/{dataset_id}
GET  /api/v1/datasets/{dataset_id}/signals
GET  /api/v1/equipment/{equipment_id}/modes?start=&end=
GET  /api/v1/equipment/{equipment_id}/capability-map?dataset_id=&panel=
GET  /api/v1/series?dataset_id=&signal_ids=&start=&end=&resolution=
POST /api/v1/analyses                 # immutable run config
GET  /api/v1/analyses/{run_id}
GET  /api/v1/analyses/{run_id}/incidents
GET  /api/v1/incidents/{incident_id}/evidence
POST /api/v1/analyses/{run_id}/ablate-signal # OPTIONAL later, replay only
GET  /api/v1/analyses/{run_id}/report
```

Все endpoints на раннем этапе могут быть mock-backed, но типы и смысл должен быть версионирован. Не формировать `probability` из score.

## 5. План работ по последовательным GATE / вертикальным срезам

### G0 — исходный код, реальное состояние и границы (S и F могут начать одновременно)

**S:** read-only аудит существующего FastAPI, БД, импортера, тестов, Docker/dev mode, Python versions, лейаут рабочих каталогов. Никаких правок до inventory. Составить `CURRENT_STATE.md`, `KNOWN_BROKEN.md`, source inventory, тестовый baseline; зафиксировать owner decisions и `EXP_REGISTRY.md`. Указать какие endpoints уже существуют, не выдумывать их.

**F:** read-only аудит React, роутинга, существующих компонентов, тестов, стилей, ECharts; `UI_CURRENT_STATE.md` и дизайн-система. Подготовить wireframe главного investigation workspace без изменения backend.

**Gate:** воспроизводимые команды для запуска имеющегося приложения; карта рисков и существующих тестов. Если Docker DNS заблокирован — использовать документированный локальный fallback Python3.11/SQLite/Vite, не переписывая инфраструктуру.

### G1 — data identity & API contract (блокирующий gate для научных claims)

**S:** получить и проверить *реальные байты* исходного LBNL, в том числе разночтение `sa_bias`/`coi_bias`; sha256 + file count, timestamps, units, simulation type, mode-control docs, official BASIC data points, QA; сохранить `SOURCE_IDENTITY_LEDGER.md`, `DATASET_MANIFEST.json`, `SENSOR_MAP.yaml`. Заморозить `CONTRACT_V1.md` + `openapi-v1.yaml` + 6–10 честных JSON fixtures. Для аналитики отдельно флаг `FAULT_ORACLE`, не отдавать клиенту без research mode.

**F:** по fixtures строит каркас Incident List и страницу AHU. Все примеры размечаются `DEMO FIXTURE`, а реальный режим replay пока не имитируется. Список требований к контракту через changeset proposals.

**Gate:** успешный roundtrip source unit conversion; официальные Basic/Extra verified; спорный wow-сценарий либо доказан как source-alias, либо явно исключён из научного demo. Fixtures проходят JSON Schema/typed TS validation.

### G2 — Signal Registry, Data Quality, Mode Engine (всегда перед правилами)

**S:** канонический mapping и роли, SI/°F→°C c отдельным delta conversion; enum types; missingness, analog stuck, binary exempt, physical range, time parsing, duplicate points, break detection; конкретный LBNL state machine: fan off, occupied inferred/unknown, mechanical cooling allowed by OAT and economizer, control SAT eligibility, transitions and hold. **Не используем `SYS_CTL` для BASIC**, даже если в CSV он присутствует. All rule modes not assumed known when source lacks signal.

**F:** SVG схема AHU с реальными типами каналов, tooltip с каноническими именами, единицами и quality flags. Синхронный Replay component поверх fixtures; ECharts с общей временной осью, min/max downsampling и запросом raw zoom; без fake air flow magnitude.

**Gate:** state machine truth table по всем веткам official LBNL control sequence; TEST `fan off`, `economizer`, `below 33.8°F`, `above 60°F`, `in between`, `startup delay`, `unknown mode`; нет скрытой постфактум truth информации.

### G3 — первые APAR / физические проверки и инциденты

**S:** preflight на Open-FDD Python `oracle` для **конкретных** правил и required points; если не подходит, реализовать 2 простых полноценных и тестируемых symptoms отдельно. Претенденты: SAT deviation только при активно регулируемой SAT и стабильном режиме; persistent command saturation при выполненных prerequisites; optional mixed-air plausibility только если корректное расположение и измерения. Не утверждать root cause по одному правилу. Добавить stateful event aggregator: persistence, exit hysteresis, merge gap, missing-data break, incident uniqueness.

**F:** Incident List, time filters, badges только для значимых statuses, cards, detail tabs. Нажатие инцидента перематывает графики и SVG. `NO ALARM` и `NOT EVALUABLE` различаются.

**Gate:** минимум один воспроизводимый реальный rule event из проверенного источника; тесты transitions и no-alert on invalid data; инциденты не дублируются на каждом минутном окне.

### G4 — работающий end-to-end MVP (перед дополнительным ML)

**S:** OpenAPI реализован; статусы/применимость/доказательства/журнал результатов записываются; отчет JSON/Markdown с data hashes, version, limitations; нет физических классов без подтверждения.

**F:** complete flow «выбрать dataset → replay → обнаруженный symptom → evidence → рекомендации → экспорт». Состояния loading/error/empty/no-alarm, responsive and keyboard navigation. E2E Playwright.

**Gate:** демонстрируем полный сценарий без ML и Bayesian. Это защищает диплом от провала отдельной исследовательской гипотезы.

### G5 — ML competition с известными вводными (может идти параллельно UX polishing)

**S:** после source gate и полного здорового периода: healthy train/validation/test деление по неперекрывающимся contiguous time blocks; baseline residual (SAT/SP), Ridge/регрессионная модель, PCA для same panel и LightGBM *как кандидат*. Санкционированные признаки, model scope, drift checks; compare with/without `CHWC_VLV_DM` как заранее описанная абляция, без oracle channels и future leakage. Валидировать здоровый false alert budget, не подстраивать порог под тест fault. Выбрать модель только по данным из независимого test window и исследовательскому протоколу, без объявления SOTA по 2 зимним дням. При неудовлетворительном результате оставить rules-only.

**F:** визуально отображает `predicted SAT`, residual, calibration scope; если модель не выпущена, UI показывает `UNAVAILABLE`, не рисует выдуманную предсказанную кривую.

**Gate:** документированная config, feature panel, datasets/splits, производительность, coverage, false episode rate, воспроизводимый код; решение `INCLUDE | CONDITIONAL | REJECT`.

### G6 — Controller Effort (независимый дополняющий worker)

**S:** проверить достаточность данных здоровой работы по режимам/погоде/уставке, baseline статистика команды с контекстом; отдельный невысокопараметрический метод first, только потом ARX/complex model. Positive example может быть **simulator counterfactual**, не real measurement. Отдельно оценить normal mode change, OAT/load confounding, saturation episodes. Не считать большую команду доказательством sensor bias.

**F:** вкладка «регулирование» с corridor нормальной команды, saturation полосой, отметкой режима, A/B comparison только с source-verified matched trajectories.

**Gate:** добавочная ценность на заранее определённых эпизодах при сопоставимой частоте ложных тревог; либо `RESEARCH_ONLY`.

### G7 — Evidence Engine, Issue Reasoning, Capability Map

**S:** заменить учебный контракт строгим `EvidenceV1`, обработать 12 отрицательных тестов ревьюера и новые кейсы; минимальная версионированная таблица symptom→candidate+exclusion rules, no Bayesian percentages. Учитывать raw lineage и роль контекста без ложного допущения независимости. Capability Map = **доступность конкретных тестов**, не физическая идентифицируемость вообще. Recommendations — whitelist инженерных проверок, не autonomous BAS control.

**F:** Evidence Graph (React Flow), карточки supporting/contradicting/missing, missing sensor reasons, Sensor Lab BASIC/EXTRA/remove-input (исключительно recorded/offline), tech-report.

**Gate:** нельзя получить `ISOLATED` через произвольную строку API; invalid SAT не даёт подтверждённый SAT fault; contradictions видны; недоступность physics не скрывает другого incident.

### G8 — единый научный benchmark и матрица покрытия

**S:** создать `EXPERIMENT_PROTOCOL_V1.md` с новым уникальным ID; не повторять старые B0–B5 значения. Предлагаемый именованный ряд:

- `R0`: корректный mode-specific rule baseline;
- `R1`: `R0 + selected detector`;
- `R2`: `R1 + controller effort`;
- `R3`: `R2 + evidence reasoning / abstention` (оценивается по *качеству диагностики/отказа*, не просто по F1 detection);
- `R4`: conditional external physical measurement при фактическом наличии, иначе `NOT_EVALUABLE`;
- `RUX`: исследование интерфейса без изменения результатов FDD (не смешивать UI metrics с algorithm metrics).

Метрики по fault types, severity, сезонам, панелям, сбоям качества и тем случаям, где GT действительно есть. Не считать строки независимыми зданиями, не строить «95% CI по 100000 минутам одной модели», не выдавать latency если неизвестен onset. Если независимых кампаний мало, даём честную описательную матрицу, не статистическую значимость.

**F:** Research Lab экран с fixed baseline selector, Coverage Matrix; `N/A` для несуществующего GT/невалидной метрики; A/B timeseries. Все графики указывают источник, конфигурацию и дату запуска.

**Gate:** воспроизводимый запуск от raw к итоговым таблицам; предупреждения о случаях отрицательного результата; одна общая панель/время для сравниваемых методов.

### G9 — инженерный UX-аудит

**S:** заморозить ответы системы и набор 3–5 задач для участников: компенсируемая модельная ошибка (только если source verified), saturated valve w/o position feedback, norm mode transition, missing SAT, conflicting detectors. Чёткие правильные действия и ограничения. Небольшая UX-проверка — **исследовательская разведка**, не доказательство «все инженеры стали лучше».

**F:** два режима: baseline charts-only и Investigation Workspace; уравнять данные/время; фиксировать time-to-decision, incorrect actions, successful finding of limitations и короткую обратную связь. При наличии добровольцев/разрешений; без них проводить проверку экспертным walkthrough без статистического заявления.

**Gate:** протокол, задачи, результаты и негативные наблюдения; end-to-end screenshots/videos с корректной маркировкой demo.

### G10 — выпуск дипломного артефакта

**S:** freeze dependency versions, API, source hashes, scientific report, experiment ZIP with real code (no metadata-only handoff), exact run commands, known failures, tests, fixed decision register; secure local demo with sample data and optional read-only import, no actual OT write endpoint.

**F:** визуальная доработка, responsive screen widths, Playwright screenshots, error handling, keyboard/accessibility, финальный демонстрационный сценарий и manual QA.

**Gate:** чистое воспроизведение с самого raw источника или документированным локальным fallback, отчёт и демонстрация связаны с действительными данными и проверенным методом, проходящие backend/frontend tests/E2E. Release only with owner approval.

## 6. Порядок параллельной работы (чтобы не блокировать друг друга)

| Волна | Умный S | Фронтенд F | Обязательный handoff |
|---|---|---|---|
| A | G0 read-only + G1 source/API schema | G0 UI audit + wireframe/mock layout | `CONTRACT_V1`, OpenAPI, fixture `demo_manifest.json` |
| B | G2 Signal/Mode/DQ | SVG AHU + Replay + ECharts на fixtures | real `Signal`/`Mode` schema, stable time axis |
| C | G3 Rules/Event + G4 endpoints | Incident Queue + Inspector + E2E | endpoint shape + incident fixtures |
| D | G5 ML competition + G6 effort | Matched A/B charts and inspector polish | validated model `AVAILABLE/UNAVAILABLE`, actual trajectories |
| E | G7 reasoner + G8 experiments | React Flow + Sensor Lab + Matrix | EvidenceV1, CapabilityMap, versioned experiment ID |
| F | G9/G10 experiment report & release | G9/G10 UX/testing & demo | frozen artifact bundle and release notes |

**Между волнами:** API freeze. Breaking change только с новой `schema_version`, тестом миграции, отметкой обеих сторон. Front может брать следующий UI screen на mock, пока S занят исследованием, без программной зависимости от ML.

## 7. Инварианты и тесты, предотвращающие известные ошибки

**Data gates:** имена/хэши/alias, ASCII/CSV encodings, monotonic time, HHMM vs minutes, °F vs °C offset and ΔT, timezone/DST, identical weather comparison only where paired, no leak from filename/fault label/model-only channels.

**Operating modes:** `SYS_CTL` запрещён в BASIC; все temperature thresholds по правильной единице, fan-on before SAT rule, transition hold, uncertainty unknown, economizer/cooling loop truth table vs LBNL official sequence, no fake generic G36 behavior.

**Evidence/contract (как минимум):** unsupported role rejected, wrong source aliases fail/normalize correctly, empty raw roots rejected for sensor facts, context shared ≠ physical independence, duplicate derived SAT does not create separate evidence, invalid SAT quality ≠ trusted diagnosis, anomaly-vs-normal conflict preserved, uncertain result cannot yield NO_ALARM, arbitrary discriminator cannot isolate, missing feedback cannot silently be treated as measured, unknown fault still shows UNEXPLAINED, one model failing doesn't cancel other valid anomaly.

**Temporal/UI:** no incident every minute, stateful interval grouping, no smoothing that erases maxima/minima, zoom restores raw measurements, linked charts keep identical timestamp, pause/replay states, screenshot on 1440/1280/1024/mobile widths, handling missing model prediction and no GT, no live label for CSV replay.

**Scientific:** all methods same sensor panel and time horizon, no random overlapping window split, no test-used-to-pick-threshold, no cloned label ground truth, no artificial CI using minute count, no hidden test leaks, model output never promoted to causal probability.

## 8. Demonstration flow, without fake AI

1. Открываем список verified датасетов и AHU; выбираем source with simulation marker.
2. Нажимаем «Воспроизвести»: SVG, SAT/SP, OAT и valve command синхронно показывают **действительные сохранённые** значения.
3. Переходим к заранее проверенному rule event (например, устойчивое отклонение SAT в допустимом охлаждающем режиме) → появляется реальная карточка, правило, исходные интервалы и ограничения.
4. Если модель подтверждена, включаем её отдельный слой и сравниваем с rule; если нет — явный unavailable, без фиктивного score.
5. Открываем возможные причины и показываем, что BASIC не содержит фактического valve stem feedback. Разумные проверки инженера представлены как *вопросы к оборудованию*, а не «73% виноват клапан».
6. В научном режиме выбираем VERIFIED matched normal/fault simulation: показываем отличие `SAT` и command **как свойство симуляции**, не как самостоятельное научное открытие.
7. Открываем Sensor Lab и убираем recorded signal → пересчитываются применимость правил, диагнозы могут стать более неопределёнными.
8. Экспорт отчёта и матрицы покрытия с source identity, score semantics, авторством, версиями и честными `N/A`.

**Fallback:** даже если спорная пара `coi_bias/sa_bias` не подтверждена или LightGBM не проходит качество, достаточно verified valve stuck или SAT-rule cases и работающего end-to-end интерфейса. Нельзя блокировать продукт неуспехом одного научного сценария.

## 9. Определение готовности дипломного продукта (Definition of Done)

**Functional:** проходится 8-шаговый демонстрационный путь; нет обязательных заглушек, демонстрируемых как факты; одна установленная AHU конфигурация с источником и фиксированной политикой; датасеты корректно импортируются и сохраняются без изменения исходных файлов.

**Engineering:** контрактный тест, unit/integration/E2E без критических ошибок; immutable source hashes, stable mode logic, непротиворечивые статусы, no invalid alias and oracle leakage; запуск в документированном local mode, без необходимости Docker DNS.

**Scientific:** воспроизводимые эксперименты c честными оговорками, хотя бы два сопоставимых диагностических варианта; количественный результат **или честный отрицательный**; различение метрик обнаружения, причин и пользовательских решений; dataset evidence table.

**Visual:** 2D мнемосхема, синхронный replay, 3 связанных графика, обнаруженный incident, Evidence Inspector, BASIC/EXTRA coverage, отчёт — без 3D и fake gauges.

**Handoff:** финальный ZIP: изменённый исполняемый код, тесты, конфигурации, pinned deps, example inputs/manifest, воспроизводимые отчёты, screenshots, decision log, список отсутствующих файлов и SHA256. Не принимать пакет, содержащий только отчёты без кода.

## 10. Журнал решений (фиксируется вместе с кодом)

Каждое изменение технологии: `Decision ID`, текущая проблема, варианты, первичные источники/ссылки, именно для нашей задачи доступные данные, licensing/repro, known limitation, выбор `GO/CONDITIONAL/PARK/STOP`, reason, validation gate, дата/версия, кто утвердил.

Пример:
- `D-001`: **SOTA source identity** — `coi_bias` не объявлять официальным `sa_bias` до sha/lineage проверки (`CONDITIONAL`).
- `D-002`: **Virtual SAT** — Ridge vs LightGBM в честном эксперименте, отсутствует вечное «обязательно» (`CANDIDATES`).
- `D-003`: **Open-FDD** — только pinned Python oracle 1–3 проверенных rule adapters (`CONDITIONAL`).
- `D-004`: **BN** — нет доказанной калибровки, не делать numerical posterior (`PARK`).
- `D-005`: **EvidenceV1** — старый учебный прототип не production-safe; strict validated replacement (`REQUIRED`).
- `D-006`: **Scenario Demo** — только source-verified recorded or explicitly `DEMO FIXTURE` (`REQUIRED`).

## 11. Что делать первым — два автономных задания

**Умный агент:** выполнить G0/G1 без изменения кода продукта, подготовить реестр доступных исходных байтов, состояние репозитория, контракты `EvidenceV1`, `Signal`, `Mode`, строго описать реальный рабочий сценарий с 1–2 проверяемыми правилами. Выдать научные BLOCK/GO до попытки установки длинного списка ML.

**Фронтенд-агент:** параллельно выполнить G0/F UX skeleton на фикстурах, реализовать интерактивный AHU layout/replay/incident list + UI состояниями. Ни один физический факт или score не вычислять на клиенте. Сразу провести Playwright screenshot review.

**Никаких ожиданий “сначала закончим всю науку”.** Каждый модуль подключается к зафиксированному API, а исследовательские неудачи показываются в UI как честные ограниченные состояния.
