# Stage14 · предварительный аудит источника

Repo · [TryHanger/BuildingPulseAI](https://github.com/TryHanger/BuildingPulseAI)
Base · `main` @ `0cb8b8a70093787b15c694c0ed16e3306fc3bfd1`
Review · `research/field-apar-gate-14`
Точные head SHA и ссылка на draft указаны в описании PR.

## Граница задания

Проверен источник для одного физически осмысленного APAR-кандидата по предоставленному [регламенту GitHub](../../../BUILDINGPULSE_GITHUB_WORKFLOW_FOR_AGENT_S_STAGE14.md). Отдельный `TASK_SINGLE_AGENT_S_BP_ML_FIELD_APAR_GATE_14.md`, на который ссылается регламент, не найден среди материалов. Этот PR фиксирует предварительный STOP для проверенного кандидата. Окончательный Stage14 по отсутствующему полному заданию остаётся открытым.

## Результат

| Проверка | Статус |
| --- | --- |
| Gate A | `STOP_NO_ACTIVE_SUPPLY_AIR_SETPOINT` |
| Gate B | `NOT_RUN_GATE_A_STOP` |
| Область | `APAR_INSPIRED_NOT_PAPER_REPLICATION` |

**CLAIM.** У шести исходных AHU отсутствует активная уставка температуры приточного воздуха для APAR Rule 3. Опубликованные минимальный и максимальный пределы SAT и уставка температуры вытяжки имеют другие роли. SHA-256 всех восьми исходных файлов и принятой рукописи совпал. Проверены 316 230 исходных пятиминутных отсчётов на одной площадке. В 27 600 отсчётах наблюдалась комбинация контекста BAS 1/0/1, которая не устанавливает фактический режим. Ни один отсчёт не прошёл структурный допуск.

**NOT CLAIM.** Не рассчитывались сравнение с SAT-drop, пороги по данным, каузальный эффект, точность FDD и результат 94/105 из публикации. Запрос клапана не аттестует положение, BAS-статус вентилятора не аттестует вращение, опубликованная SAT не является независимо аттестованным измерением относительно вмешательства. Наличие записи в расписании не устанавливает физический отказ; отсутствие записи не устанавливает исправность.

**STOP.** Для Rule 3 нужны аттестованная активная SAT-уставка, подтверждённый режим и применимые допуски. Их отсутствие блокирует численное сравнение. Порог оставлен явно неопределённым, без подгонки под Stage12/13.

## Файлы и проверка

- [Предварительная предрегистрация](PREREGISTRATION.md), [машинная конфигурация](PREREGISTRATION.json), [хэши](PREREGISTRATION.sha256) и [отметка времени](PREREGISTRATION_CREATED_AT.txt).
- [Роли каналов](CHANNEL_ROLES_14.csv), [полный ledger](COMPARISON_ELIGIBILITY_14.csv) и [машинное решение](GATE_RESULT_14.json). Каждая строка ledger задаёт непрерывный полуоткрытый интервал, шаг 300 с и причину для каждого тика. Записи расписания используются только для маркировки дат и буфера ±1 день. `fault` не является входом.
- [Код аудита, независимый XML-парсер и тесты](../../field_apar_gate_14/). Код и результаты расположены только в исследовательских каталогах. Файлы backend, frontend, FDD, OpenAPI, SQLite и моделей отсутствуют в diff.
- [Хэши, размеры и адреса восьми файлов](evidence/SOURCE_PROVENANCE_11.json). Рукопись Nehasil et al. — DOI 10.1016/j.enbuild.2021.110781. Правило — NISTIR 6994, таблица 2.1. [Данные издателя](https://data.mendeley.com/datasets/jkw85sm4v4/1) · [Рукопись CTU](https://dspace.cvut.cz/entities/publication/35d10945-7123-4cdc-8367-50bfdb4c1052) · [NISTIR 6994](https://nvlpubs.nist.gov/nistpubs/Legacy/IR/nistir6994.pdf).
- [Аудит источника](evidence/source-audit.log), [независимый пересчёт](evidence/independent.log), [pytest](evidence/pytest.log), [версии](evidence/versions.log).
- Baseline · [279 backend](../stage13_bootstrap/backend-pytest.log), [49 contracts](../stage13_bootstrap/contracts-pytest.log), [9 Stage13](../stage13_bootstrap/stage13-pytest.log), [совпадение OpenAPI и HTTP](../stage13_bootstrap/http-regression.log), [сборка](../stage13_bootstrap/frontend-build.log), [Playwright Stage10](../stage13_bootstrap/playwright.log), [Compose config](../stage13_bootstrap/versions-compose.log). Docker-контейнеры и браузерное сравнение Stage14 не запускались, так как Stage14 не имеет UI и не меняет приложение.
