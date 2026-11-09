# Задание агенту — Stage 8B-R.4 Scientific Integrity Correction (NON-MODEL HOTFIX)

Цель: **исправить неправдивые отчёты, метрики начала событий и provenance**, сохранить отрицательный результат на 5 раскрытых экспериментах. **Не создавать новую версию FDD и не подбирать пороги**.

Прочитай полностью `BUILDINGPULSE_STAGE_8BR4_INDEPENDENT_AUDIT.md` и исходные данные, код и научную документацию в репозитории.

## Обязательные исправления, строго в порядке

1. **P0 — отчёт.** В `generate_markdown_report` исключить все фиксированные положительные заявления про 3/3 летних событий, 1.45% FAR, физическую причинность Circular Shift и положительную No-MA абляцию. Данные в каждом заключении должны вычисляться из конкретного ключа `evaluation_slices`. Добавить автоматические consistency tests, которые **падают** при противоречии нарратива и JSON. Статус летнего M2/M3: 0/3, не подтверждено.
2. **P0 — временная причинность.** Разделить `any alarm during fault` (legacy metric) и `new alarm onset after fault start`; добавить `PRE_EXISTING_ALARM` и pre-fault quiet-window detection; при непрерывной тревоге с 08:40, когда fault начинается в 10:00, это **не новая детекция**. Включить независимые синтетические и реальные тесты для сценариев 2016-12-01 и 2017-01-03. Вывести delay от реального onset, отдельную метрику `missed_due_to_preexisting_alarm`, а не объявлять 0 мин. Проверить исправленные значения при исходных порогах, не меняя параметры.
3. **P0 — замороженность.** Сравнить реальные train/val дни, коэффициенты и sigma модели Stage 8B-R.3 с текущим Stage 8B-R.4. Текущий код переобучает Ridge, веса и sigma изменились. Либо использовать действительно сериализованную старую модель с точными байтами и корректной совместимостью, но не пересчитывать заново текущий holdout как подтверждение, либо честно классифицировать R.4 как новый locally-fitted exploratory model with fixed thresholds. Не выдавать его за frozen-weight / CSIRO zero-shot transfer. Отсутствие pre-access hash — явное ограничение blind preregistration.
4. **P0 — физический смысл.** M2 прогнозирует ACTUATOR_FEEDBACK_POTENTIOMETER, не команду контроллера. M6 читает BAS damper signals непосредственно, маркировка `INJECTION_OBSERVABLE`. Не утверждать физическую механическую причину по прямому следу override. В `20180709_TSup_m3.5` первичный протокол применял override `setpoint demand adjust`, уточнить описание.
5. **P1 — контроль нормальности.** Зафиксировать `official`, `override_masked`, `washout_60m` и baseline-days-only sensitivity для всех главных методов, их отдельные знаменатели/coverage. Не называть все точки вне официального fault чистой нормой без проверки и washout.
6. **P1 — поэлементные доказательства.** Внешний CSV 3744 строки должен содержать для каждой выбранной конфигурации `eligible`, `z`, threshold, `alarm`, `alarm_onset`, `preexisting_alarm_at_fault_start`, `event_id`, `event_detected_by_new_onset`, `domain_status` и время; точный исходник данных и canonical signal ID.
7. **P1 — статистика.** Точные биномиальные интервалы на физических днях/событиях, разделение по сезону и типу дефекта. В отчёте показать зимнюю FAR и цену DomainGuard (0% fault coverage). НЕ объявлять статистическое превосходство.
8. **Не подгонять 5 новых holdout событий!** Они теперь `TEST-EXPOSED`; расчёты/исправления скоринга допустимы лишь как post-hoc forensic reanalysis, не как новый независимый тест. Заморозить предыдущий ZIP и исходные отчёты.

## Итоговый пакет

`BUILDINGPULSE_AUDIT_STAGE_8B_R_4_CORRECTED.zip`: полный исполняемый код (все зависимости), все исходные CSV, модельные коэффициенты и hashes, старые и исправленные машинные манифесты, per-timestamp evidence с тревогами и onset, event-level counterfactual scoring, прошедшие и неудачные тесты, полные логи, sha256, `README_REPRODUCE.md`, `CLAIMS_TO_EVIDENCE.md`, `KNOWN_LIMITATIONS.md`, diff/status либо честное сообщение об отсутствии истории Git. Проверить независимый запуск в распакованной директории.

Не изменять production Stages 1–7.1, не делать commit/push/merge/deploy, не вызывать других LLM агентов, не запускать Active Probing/Stage 8C/N4SID/Kalman. Следующий физический эксперимент оформляется отдельно и только на **новом** до анализа запечатанном holdout.
