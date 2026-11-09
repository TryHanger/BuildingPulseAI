# BuildingPulse AI · G0–G5.7 · Реестр научных утверждений

Этот реестр отделяет подтверждённую работу программы, наблюдение в симуляции и доказательство физической причины. Принятый код содержит исторические модели и результаты B0–B5. Они остаются архивом и не используются как активные baselines G6.0.

| Этап | Что допускается утверждать и на каких входах | Что закрыто или ограничено, контроль и ссылка в принятой сдаче |
|---|---|---|
| G0 | Воспроизводимый runtime FastAPI, React, SQLite/Parquet, OpenAPI и импорт с проверкой даты и идентичности источника. | UI mock и синтетические данные имеют DEMO_FIXTURE. Нет доказанной причины. Доказательства `handoff/rc2`, RC2 manifest. |
| G1 | LBNL SD-AHU имеет верифицированный набор 15 исходных локальных префиксов, карту ролей и read-only Investigator. BASIC использует статус вентилятора и команду, EXTRA отделяет модельную обратную связь. | LBNL SD-AHU — симуляция. Повторённые severity payload и имена coi_bias/sa_bias не подтверждают пары или семантику. Давление/поток с непроверенной единицей исключены из физических правил. `DATASET_MANIFEST.json`, `SIGNAL_MAP_V1.yaml`. |
| G2 | `lbnl-fan-hold@1.0.0`, SF_SPD_DM и OA_TEMP, выдержка 300 s. OFF / UNKNOWN / TRANSITION_HOLD / RUNNING. Direct seek использует предысторию. | Выход 1,5 диапазона команды — нарушение кодирования без причины. Разрывы сбрасывают удержание. Физическое механическое разрешение, economizer и run proof не проверены. `G2_GATE_RESULT.md`. |
| G3 | `mat-below-mixing-envelope@1.0.0` (Open-FDD FC2-derived). MA/OA/RA, fan status, fan command, нижний допуск 7 °F, разнос 10 °F и выдержка 600 s. На годе 187 192/525 540 оценено, 0 событий. | Ноль по предикату не оценивает физическую норму или false-alarm rate. Верхняя граница FC3 заблокирована из-за положения RAT перед возвратным вентилятором. Контроли пагинации и сброса на разрывах. `G3_GATE_RESULT.md` и `G3_INCIDENT_INDEX.json`. |
| G4 | Investigator, Evidence Inspector, QA, журнал и HTML/JSON экспорт работают с прежним индексом. Годовой LBNL показывает охват и пустой список. | Демонстрационное подтверждение на 11-м минутном наблюдении и 55 исходных значений из пяти каналов проверяют продукт, а не чувствительность метода. Причина не установлена. `G4_GATE_RESULT.md`. |
| G4.1 / G5 | Отдельно показаны неоценённые, оценённые, нарушения без подтверждения и эпизоды. G5 проверил готовность данных и допустимость только описательного nominal-пилота LBNL. | 10 нарушающих точек не подтверждают 600 s. LBNL 21 официальный файл → 15 уникальных payload; периоды внутри одного года не независимы. Нужны instrumented trials, а не обучение по дубликатам. `G5_GATE_RESULT.md`. |
| G5.1 | CSIRO подтверждён как реальный источник BMS с журналом вмешательств. Инвентаризация даёт 23 структурно допустимые строки в 17 building-day блоках после исключения просмотренных дат. | STOP_NO_QUALIFIED_INTERVENTION_FAMILY. Максимум 6 блоков на семейство против предварительного пола 35, 0 проверенных референсных блоков, MAT дублирует SAT, proxy/overlap/onset не дают физический GT. `qualification.json`, `EVENT_LABEL_LEDGER.csv`. |
| G5.2 | G36-5wk, `g36-sat-high@1.0.0`, SAT−SP >2 K, 600 s, SAT/SP/MAT, fan status, cooling/heating commands и валидность погоды. В valve WINDOW 7 428/7 920 применимо и 7 420 подтверждено. | Контрольные окна тоже дают симптом. Команда не подтверждает физическое охлаждение. Oracle отдельно от BASIC, перенос на поле и paired causal не установлены. `PRE_EXPERIMENT_GATE.md`, `G5_2_GATE_RESULT.md`. |
| G5.3 | 5wk PASS_DESCRIPTIVE_CROSS_FAULT. Один прогон на сценарий. В WINDOW подтверждено nominal 60, valve 7 420, damper 305, duct 510. | Неспецифичность SAT проверена перекрёстными контролями. 1wk paired STOP, расхождения OAT/OWB, fan, SP и две крайние строки oracle. Не считывать исторический metadata score_computed=false как состояние G5.4. `G5_3_GATE_RESULT.md`. |
| G5.4 | Независимое **применение по отдельности** в двух 1wk симуляциях по 10 081 минутному отсчёту. Nominal 5 423 применимо / 0 подтверждений, valve 8 391 применимо / 8 351 подтверждённый отсчёт / 4 начала симптома. | 20 162 поточечных совпадения двух расчётов. Обе крайние строки сохранены, oracle исключён из scorer. Четыре начала внутри одного прогона. Paired STOP, причина и полевая валидность не установлены. `G5_4_GATE_RESULT.md`. |
| G5.5 | Аудит доступности измерений и условных гипотез для SAT, BAS, воздуха и воды. UI явно отделяет paired STOP и unpaired PASS. | STOP_METHOD_NOT_EVALUABLE. Не подтверждены I/O места температурной пары и измерение ветвевого CHW flow. UNKNOWN mode, SAT alias, неверные единицы, дополнительная колонка и oracle не расширяют BASIC. `SIGNAL_ROLE_AUDIT_G5_5.csv`, `PRE_EXPERIMENT_ENTRY_G5_5.md`. |
| G5.6 | RBC: два уже известных baseline-дня, #62 и #55 различаются в 574/576 строках. Издательская схема показывает нагреватель → охладитель → вентилятор. | FIELD_NOT_QUALIFIED. #62 правдоподобно перед охладителем, I/O не доказан. #7 гидравлический охват не установлен. Overrides 80/100% открытия не эквивалентны G36 закрытию. Oracle-исключения ограничены SHA источника. `RBC_AHU2_TOPOLOGY_AUDIT.md`. |
| G5.7 | SECTION_CONTEXT_SIM_ONLY. В 16 716 подтверждённых отсчётах превышение SAT SP уже видно на coil-out, 0 впервые пересекли ориентир после точки. Один общий симуляционный контур. | STOP_ADDITIONAL_COIL_CHANNEL_AS_DIAGNOSTIC_METHOD по независимой приёмке. Оба знака при 1e−9 K не показывают инженерной пользы, это числовая точность сравнения. Прямой crosswalk экспорта не найден. Контроли отсутствия, алиаса, ложных единиц, сдвига и порядка. `INDEPENDENT_G5_7_REVIEW.md`, `G5_7_PROTOCOL_FROZEN.md`. |

## Источники

- G36/RBC издательская версия и описание. G36-HIL использует реальные контроллеры с виртуальной установкой. [Figshare v3](https://doi.org/10.6084/m9.figshare.29297999.v3) · [Scientific Data 2026](https://doi.org/10.1038/s41597-025-06179-y)
- LBNL SD-AHU, отдельная симуляция с собственным паспортом. [DOI набора LBNL](https://doi.org/10.25984/1881324) · [паспорт SD-AHU](https://fdddata.lbl.gov/data/Simulated_LBNL_FDD_Data_Sets_SDAHU/LBNL_FDD_Data_Sets_SDAHU.pdf)
- CSIRO real BMS, proxies, журнал вмешательств. [Репозиторий издателя](https://github.com/csiro-energy-systems/ahu-fault-detection-dataset)
- Open-FDD reference для G3. [Закреплённый каталог правил](https://github.com/bbartling/open-fdd/blob/32a6d4479abed81f9d6d0ff426260cc8ad8e30e2/open_fdd/rules/cookbook_catalog.py)

## Контрольные суммы архивов

Ниже SHA-256 фактически сверенных архивов. Пути в MANIFEST указывают, где находились принятые копии в этом запуске.

```text
332ae178d9db16bd976f185595ee4805868d3e0fb56e9bc6af8154878067c51e  BUILDINGPULSE_G0_G1_RC2_COMPACT_REVIEW.zip
43299824769243bf53b74c09f9bbe1599c2bbfc2a3ac574b59b50180b8b7efa1  BUILDINGPULSE_G2_GATE_REVIEW.zip
95f7d0486d41ff637d8d611898632b5471822fae49026ae91a95295ca7ed3144  BUILDINGPULSE_G3_GATE_REVIEW.zip
e322463add826bc6d8b5418e9cd0ce3e7fbabd1aac25c699e8854df4729eea0d  BUILDINGPULSE_G4_GATE_REVIEW.zip
beaba01bcf4350065ea2cf0d70bc865c7a2c49d71a32c333fffa698f4e0aeab3  BUILDINGPULSE_G4_1_G5_DATA_GATE_REVIEW.zip
f74cc7f1f20139f44ef8bac919ceecee26624b05431534ce0e76c2f45ce9c0b8  BUILDINGPULSE_G5_1_GATE_REVIEW.zip
f918723b84acc9e30471163f3116bdb31f2e1700228e200099bab168f7629fda  BUILDINGPULSE_G5_2_GATE_REVIEW.zip
de06bf8b90aeef4092bfb0cc2ae93dfa15f57e65e6d42a9b9274139a45694d0b  BUILDINGPULSE_G5_3_GATE_REVIEW.zip
edebf001020e5ddd13efb76c046e2c22a99ac10ae5819d04a3d3fd0b702b3417  BUILDINGPULSE_G5_4_GATE_REVIEW.zip
8e69c380c34dee26ed41c5d948dbd5c103ea5ed13960668d4affc8cd8d2d6ed6  BUILDINGPULSE_G5_5_GATE_REVIEW.zip
d8f1b5e25b9402b5cc8408e58101e47326411400a9daffdf04617d199bb22e09  BUILDINGPULSE_G5_6_GATE_REVIEW.zip
2781f810c6c9fc6a38e31531ae1691d219a3987d9f71f480f56c84e390252cbf  BUILDINGPULSE_G5_7_GATE_REVIEW.zip
fb9ad25e4bad4f2299c70bb63d0a2bb4e1806883c175cd8dbae57c5c268d324f  BUILDINGPULSE_G5_2_G36_SOURCE_BYTES.zip
8a4973ee0b624221b2bb993f7f3ce8c088a84345f2b45393868d127cf96930cf  BUILDINGPULSE_G5_3_G36_1WK_SOURCE_BYTES.zip
```
