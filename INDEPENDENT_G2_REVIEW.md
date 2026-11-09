# BuildingPulse AI — независимый аудит G2

**Дата:** 2026-11-07. **Пакет:** `BUILDINGPULSE_G2_GATE_REVIEW.zip`, SHA-256 `43299824769243bf53b74c09f9bbe1599c2bbfc2a3ac574b59b50180b8b7efa1`. **База:** `BUILDINGPULSE_G0_G1_RC2_REVIEW.zip`, SHA-256 `e3ded076024cdfca0a2839ecec9b15a9c9fb2a6bcc043c29208bc3e4d5625eb5`.

## Вердикт

**G2 CONDITIONAL ACCEPT / GO только в заявленных операционных границах**: read-only fan-state, входное качество, погода как *контекст* и решения об ограниченной применимости. **Не считать** G2 валидированной диагностикой охлаждения, economizer, физического клапана и причины отказа. Документированный `BLOCKED_BY_DATA` — корректное состояние; не обходить его с G3.

## Независимо проверено

1. Архив имеет 63 ZIP-записи, `testzip() is None`, все 62 строки `SHA256SUMS.txt` совпадают с хэшами actual member bytes, ZIP SHA-256 совпадает с заявленным. Базовый 208-МБ RC2 ZIP по SHA-256 соответствует `MANIFEST.json`.
2. Разобраны реальные файлы overlay: `g2_mode.py`, `g2_quality.py`, `g2_applicability.py`, FastAPI endpoints/service, runtime test, OpenAPI, React Investigator и отчёт.
3. В исходном `g2_mode.py` нет доступа к `SYS_CTL`, симуляторному истинному положению `CHWC_VLV`, fault oracle или будущим наблюдениям; входы `SF_SPD_DM` и `OA_TEMP`. Пять минут удержания явно версионированы. Физические режимы mechan. cooling / economizer неизменно UNKNOWN.
4. Собственный изолированный скрипт `independent_g2_semantic_checks.py`: **6830 assertions PASS**. Проверены положительный/отрицательный статусы вентилятора, все невалидные статусы, перезапуск hold на пропусках, OAT ± boundary, отсутствие proof охлаждения/valve, диапазон команд, невалидные величины, 80 псевдослучайных причинных последовательностей × 85 отсчётов. Сравнивался прямой расчёт полного потока с расчётом на 5-минутном lookback-префиксе. Это НЕ полный HTTP, НЕ произвольный датасет и НЕ статистическая оценка детектора.
5. Исходный лог исполнителя действительно содержит `235 passed, 67 warnings`; Vite TypeScript PASS, Playwright 4 viewport + негативные сценарии, Docker scratch HTTP. Два списочных файла original-pre/post.sha256 идентичны. **Сами 235 тестов, Docker, frontend build и 178 оригинальных хэшей не воспроизводились в этой среде**: нет `pyarrow`/Docker и мы не выполняли полный checkout. Поэтому статус — `AGENT_LOG_VERIFIED`, а не `INDEPENDENTLY_RERUN`.
6. Открыт скриншот `g2-midyear-running.png`: Investigator показывает simulation clock, `RUNNING`, `UNKNOWN` для mechanical cooling / economizer, источники и причины неприменимости. Открытые raw pressure значения помечены «единица не проверена».

## Проверяемые недочёты и открытые вопросы

### G2-OBS-01 — `P1`: диапазон EXTRA fraction position не проверяется

`g2_quality.signal_quality()` проверяет диапазон [0,1] только для `source_unit == fraction` **и** `kind == COMMAND`. Но `CHWC_VLV`, `OA_DMPR`, `RA_DMPR`, `SF_SPD` в EXTRA помечены как `MEASUREMENT` с fraction. Независимо воспроизведено: `CHWC_VLV=1.5` возвращает `flags=[]`, тогда как `CHWC_VLV_DM=1.5` возвращает `COMMAND_OUT_OF_RANGE`. До подключения EXTRA к физическим проверкам в G3/G7 требуется добавить `MEASURED_FRACTION_OUT_OF_RANGE` или явно документированное исключение по сигналам и отрицательный тест. **Не блокирует текущую BASIC fan-mode G2.**

### G2-OBS-02 — `P1`: глобальный `data_status=DEGRADED` из-за независимых от диагностического метода каналов

В реальном примере `g2-midyear-point.json` общий `data_status=DEGRADED` вызван предупреждениями `SEMANTICS_UNVERIFIED` у **SA_SP / SA_SPSPT**, хотя `running-command-range` применим и команда корректна. Код специально сохраняет локальные флаги, поэтому оценка метода правильная. Для G3 важно не блокировать MAT/OAT/RAT-физические проверки из-за неподтверждённого статического давления. Разнести `dataset_observation_status` и `method_input_quality`, явно обозначить coverage, проверить интерфейсные подписи. Не удалять предупреждения давления.

### G2-OBS-03 — `P2`: отличие API от изначального задания

Утверждённая в задачах G2 форма была `/api/v1/equipment/{equipment_id}/modes` с start/end; реализована `/api/v1/modes?dataset_id=...&start=...&limit=...`. У работающего UI и `openapi-v1.yaml` она согласована, поэтому это **контрактный дрейф, не runtime failure**. Выбрать канонический вариант и указать ADR; избегать нового несовместимого переименования только ради формата.

### G2-OBS-04 — `P2`: верификация зависимости данных ограничена симулятором

`RUNNING` основано на documented `SF_SPD_DM = SIMULATED_FAN_STATUS`; оно не является независимым доказательством airflow, вращения вала или physical mechanical cooling. `OA_TEMP` — контекст, не статус economizer; равенство OAT границ имеет `BOUNDARY_UNVERIFIED`. Так и оставить. Для реального BMS потребуется отдельный режим команд/обратной связи.

### G2-OBS-05 — `P2`: показатели полного стека недостаточно независимо воспроизведены

Лог Docker Compose config пустой; Docker smoke и 235 pytest документированы, но не выполнены данным аудитором. Полный Compose/PostgreSQL и физический перенос — `NOT_TESTED` как в отчёте S. Нельзя переносить слово `PASS` на эти системы.

## Приёмочное решение

- **ACCEPT:** G2 read-only simulated fan-state, time gaps, per-method applicability, UI live context, API v1 rc.3.
- **FIX NEXT:** P1-extra fractions и селективное агрегирование качества до включения реальных G3 incident labels.
- **NO-GO:** приписывание `COOLING`, `ECONOMIZER`, `FAN_PHYSICALLY_PROVEN`, физической неисправности клапана или достоверной локализации без новых данных.
- **NEXT:** один агент S, G3 pre-integration gate физического правила, затем 1–2 действительно применимые проверки смешанного воздуха, evidence и temporal aggregation; при провале gate остаётся `BLOCKED_BY_DATA`, не искать «проходной» тест после внедрения.

## Первичные источники для выбора G3

- Schein, Bushby, Castro, House, 2006, APAR AHU (DOI `10.1016/j.enbuild.2006.04.014`): https://www.sciencedirect.com/science/article/pii/S0378778806001034
- NIST APAR hierarchical system, 2006: https://www.nist.gov/publications/hierarchical-rule-based-fault-detection-and-diagnostic-method-hvac-systems
- Open-FDD актуальный P0 rule catalog (FC2/FC3, prereqs/rollups): https://bbartling.github.io/open-fdd/rules/cookbook/p0-rule-catalog.html
- Open-FDD Pandas cookbook с `FC2`/`FC3`: https://bbartling.github.io/open-fdd/rules/cookbook/pandas-cookbook.html
- LBNL official SD-AHU inventory: https://fdddata.lbl.gov/data/Simulated_LBNL_FDD_Data_Sets_SDAHU/LBNL_FDD_Data_Sets_SDAHU.pdf

## Статус артефактов

Исходный архив G2 и RC2 не изменялись. Новый скрипт тестирует отдельно чистые модули, без SQLite, raw CSV, Docker, сети или commit. Этот отчёт не является доказательством статистической эффективности диагностики.
