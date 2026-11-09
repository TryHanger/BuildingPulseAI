# BuildingPulse AI — Independent audit of CD-01 Parallel Pilots

Дата независимой проверки: 2026-11-05. Объект: предоставленный `BUILDINGPULSE_AUDIT_CD01_PARALLEL_PILOTS.zip`. Это проверка предоставленной копии, не утверждение о Git-ветке проекта или скрытых исходниках.

## 1. Целостность и воспроизводимость

- ZIP SHA-256: `f978612b0f339dd17208cb9b0adf0f359036b81e2889c75ca61accbf60b847dd`.
- В ZIP 110 файлов; `audit/SHA256SUMS.txt` покрывает 109 файлов, все 109 хэшей правильны; проверка ZIP `testzip` успешно завершилась.
- `python verify_package.py --replay` прошёл проверку SHA, frozen inputs, проверку соответствия отчёта JSON и восемь тестов `unittest`. Дорожки A–E выполнены без ошибки. **Последний шаг строгого побайтового сравнения не прошёл**, начиная с `results/lanes/A/metrics.json`.
- Независимый повторный запуск `python run_parallel.py --output ... --logs ...`: все 5 дорожек завершились кодом 0. Для A, B, D различаются лишь численные значения с плавающей точкой (наибольшее абсолютное расхождение по JSON: A 6.94e-11, B 1.90e-10, D 2.22e-16); C и E идентичны побайтово. У A/B **все булевы флаги тревоги и onset в pointwise идентичны**, все пять файлов `eventwise.csv` идентичны побайтово. Следовательно, научные выводы и решения воспроизводятся с численной толерантностью, но требование byte-identical в неприкреплённом к образу окружении неустойчиво.
- Испытано окружение: Python 3.13.5, numpy 2.3.5, pandas 2.2.3, scipy 1.17.0. В requirements закреплены Python 3.12 (документация), numpy 2.2.6, pandas 2.2.3, scipy 1.15.3, pyarrow 19.0.1. Pyarrow отсутствует в проверяемом окружении, но не требуется для replay упакованных CSV.
- Ни полный исходный проект, ни `.git`, ни production frontend/API в CD-01 не включены; неизменность production и отсутствие commit/push независимо этим ZIP не доказываются. Полные сырьевые upstream архивы также не вложены; package-data воспроизводимы, но upstream-byte-parity не подтверждена.

## 2. Пилот A: Conditional Risk / Probability Models

- Основание: `search2 C01`, conditional quantile by exogenous weather mode; из назначенных риск-статей не следует доказанный AHU detector.
- Global Q95: 988 / 1785 (FAR 55.350%), 2.366 FA ep/8h, new-onset 7/14 наблюдаемых физических эпизодов.
- Conditional Q95: 1214 / 1785 (FAR 68.011%), 3.711 FA ep/8h, new-onset 7/14.
- Permuted-mode placebo: 997 / 1785 (FAR 55.854%), 2.689 FA ep/8h, new-onset 7/14.
- На 24 eval-днях conditional FAR выше 5% в 21 дне, на 11 днях FAR составляет 100%. Погодная стратификация не помогла, но это **только одна реализация из двух weather bins**; нельзя объявлять все conditional-calibration методы опровергнутыми.
- **STOP для конкретного пилота**, не переносить пороги в приложение.

## 3. Пилот B: Partial Mixing / Conservation

- На Nesbitt (AHU2): базовый M1 54/3154 (FAR 1.712%), 0.365 эп/8h, new onset 1/8; lagged SAT-ARX 47/3154 (1.490%), 0.944 эп/8h, new onset 4/8; MixBound 14/3154 (0.444%), 0.213 эп/8h, new onset 0/8; подмена MAT на SAT 54/3154 (1.712%), 0/8.
- **MixBound — только граница смешения `min(OAT,RAT) <= MAT <= max(OAT,RAT)`, а не полный баланс энергии и не дифференциальная диагностика клапана.** Без достоверных независимых расхода воздуха, расхода/мощности coil, влажности и давления полная физическая гипотеза НЕ ОЦЕНЕНА.
- ARX 4/8 — отдельная интересная проверка простого временного baseline, но НЕ победа transfer механизма Conservation. По `eventwise.csv` его 4 тревоги: 2017-01-03 damper 5 мин; 2017-07-18 damper **605 мин**; 2017-08-11 cooling valve 5 мин; 2018-07-09 **BAS setpoint demand adjust**, 0 мин (не подтверждённая физическая неисправность датчика).
- При дополнительном **эксплораторном** критерии задержки <=60 минут: 3/8; после исключения BAS setpoint adjust 2/7. Восстановить постфактум такой критерий как preregistered нельзя. Парная точная проверка 3 новых успешных эпизодов против M1 без обратных расхождений даёт двустороннее p=0.25 при допущении независимых эпизодов; зависимость дней/объекта ещё ослабляет вывод.
- ARX увеличивает число ложных эпизодов/8h относительно M1 (~2.58 раза), хотя обе конфигурации ниже лимита 2 эп/8h.
- **STOP для MixBound; ARX сохраняется как exploratory baseline, требующий внешнего фальсифицирующего теста и фиксированной задержки.**

## 4. Пилот C: Proxy Reliability

- Независимая полевая пара `controller command / physically measured feedback` отсутствует. Базовый сценарий LBNL использует `CHWC_VLV` (включая непосредственно imposed malfunction) и `CHWC_VLV_DM`; прямое состояние исключено из fault inference, что научно правильно.
- Вычислены симуляционные описательные контрасты: зимняя ошибка в насыщении 0 -> 50 процентных пунктов; парные 14 отсчётов для temperature contrast ~4.83°C. Это не доказанная диагностика и не полевая репликация. В парных состояниях `RA_TEMP` также заметно различается — не отождествлять тепловую разность с чистым causal effect при неизменном возвращаемом воздухе.
- **NOT_EVALUABLE_FIELD; требуются независимая обратная связь и физически независимый тепловой/расходный сигнал.**

## 5. Пилот D: Identifiability / NLID

- Синтетическая локальная модель с неизвестной нагрузкой: projected fault rank = 0 для SAT/command, 0 при повторе SAT, 1 при независимом flow, 1 при независимом SAT reference, 2 при обоих.
- В модельном примере независимое измерение добавляет ранговую информацию, но flow/reference дают одинаковую оценку по рангу (ничья), fixed expert выбирает reference. Показатель случайного выбора 0.67 — математическое ожидание по трём гипотетическим каналам, **не результат реального тестирования выбора датчика**.
- Коэффициенты и чувствительности в D условны. Ранги устойчивы в игрушечной линейной постановке, но сингулярные числа зависят от единиц и уровней шума. Эмпирического преимущества над H3 нет.
- **TOY_VALIDATED, FIELD_NOT_EVALUABLE.** Этот пилот приоритетен для планирования целевого измерения, но не является доказательством эффективности.

## 6. Пилот E: Reranking of causes

- Агент корректно остановился при отсутствии подходящей независимой трёхклассовой разметки и двух физически независимых каналов. Проверена лишь игрушечная демонстрация: дублированная температура может поменять ranking.
- Нет top-1/top-2, false attribution, field accuracy. **NOT_EVALUABLE**, не внедрять мультимодальную fusion или вывод «найдена причина».

## 7. Найденный дефект метрики новых onset (P1, воспроизведено отдельно)

В `code/common/core.py` (строки 114–123):

```python
preexisting = bool(x.continuous.loc[grid[0]] and fire.get(prev, False))
new = bool(observed and len(onset_times) and not preexisting)
```

Если тревога тянулась из нормального времени в начало fault, затем исчезла и возникла заново в fault, `preexisting` навсегда блокирует учёт **любого** более позднего onset. На независимом 5-минутном synthetic test: `[ALARM, ALARM, NORMAL, ALARM, NORMAL]` с fault с 09:05 — реальный новый onset в 09:15, но событие `new=False`.

В действительных A-результатах conditional четыре preexisting события содержат последующий новый onset, среди них три имеют наблюдаемое начало без цензуры: 2013-09-19 13:42 и 14:52, 2013-11-11 12:31. Это не автоматически три корректно обнаруженные неисправности: последующая тревога может быть случайной при огромном FAR. Но нынешняя реализация не соответствует обычному определению «новое начало тревожного эпизода внутри fault-window» и не показывает чувствительности к этому выбору. Если разрешить новый onset после очистки preexisting-фона, доля conditional изменится по арифметике, **но не изменит FAIL по FAR 68%**.

Предлагаемое исправление: сохранять две отдельные метрики и не перезаписывать исторический run:
1. `strict_clean_start_onset` — требование отсутствия активной тревоги непосредственно перед началом fault (сохранить историческую семантику);
2. `any_new_onset_after_fault` — новый alarm-start после официального onset, даже если ранее была другая тревога, с обязательным `preexisting_before_fault` флагом, указанием длительности очищенного интервала и осторожностью атрибуции.

Прежде чем принять причинность, проверить отрицательную норму за аналогичные окна, минимальную чистую паузу и latency-to-new-alarm; не выдавать смену метрики за рост обнаружения.

## 8. Проблема reproducibility checker (P1)

`verify_package.py` безусловно требует **побайтовой** идентичности файлов `metrics.json` и `pointwise.csv`, включая 15-значные коэффициенты Ridge и неопределённые около нуля значения SVD. Без закрытого воспроизводимого контейнера это слишком жёстко. Отдельно тесты 8/8 покрывают инфраструктуру, но не проверяют полноценную метрику onset при повторном появлении тревоги, оценку ARX по задержке или независимость физических измерений.

Нужна двойная проверка:
- SHA-256 неизменяемых исходников и frozen inputs — строго;
- идентичность alarm/onset/физических episodes, counts, splits, eligibility — строго;
- непрерывные коэффициенты, thresholds, residuals и SVD — с заранее заданной численной абсолютной/относительной погрешностью и записью exact-version окружения.

## 9. Приёмка и дальнейший выбор

- ZIP structure / hash / replayed scientific conclusions: **PASS с caveat на byte comparator**.
- Independent confirmation of benefit: **NONE**.
- A: STOP for simple weather-bin conditional Q95.
- B: STOP for MixBound; ARX is a secondary simple baseline, not field validation of balance.
- C: field NOT_EVALUABLE; simulation screen only.
- D: synthetic mathematical witness valid under its assumptions; no field model efficacy.
- E: field NOT_EVALUABLE; toy score duplication only.
- No production deployment, no scientific novelty claim, no reclassification of Research Navigator scientific claims.

Recommended next: **targeted, short CD-02** rather than another 5-way full modeling sprint: (i) diagnose whether field-relevant independent sensors/simulator truth exist for D+C; (ii) if physically grounded, do one experiment on observable versus nonobservable fault pairs with matched baselines and negative controls; (iii) separately audit ARX 4/8 for lead time, pre-existing alarms, setpoint override and season. If prerequisite channels absent, STOP quickly and propose acquisition/other dataset. Every result must have exact code+numbers+ZIP; prevent yet another cycle of superficial report fixes.
