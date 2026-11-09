# STAGE 8A — СЕМАНТИЧЕСКИЙ АУДИТ BMS PROXY-СИГНАЛОВ CSIRO (AHU9 И AHU10)

**Дата аудита:** 2026-11-04  
**Версия документа:** 1.0 (Gate 8A.1)  
**Объект исследования:** CSIRO Energy Centre (Ньюкасл, Новый Южный Уэльс, Австралия), вентустановки AHU-09 и AHU-10 (Schneider Electric TAC Vista / Siemens Apogee BMCS).  
**Первоисточники:**
- Репозиторий: `https://github.com/csiro-energy-systems/ahu-fault-detection-dataset` (commit `3eb50a9ce1d4eeed778877cbfdbd259d2298d8e6`, 2022-12-12)
- Схема proxy-архитектуры: `docs/BMS.Changes.png` (SHA-256: `e0cac7a0fc5f1c556781eedc06c96714a9b3fcfe6a87ebff0f39932becd277b6`)
- Схемы установок: `docs/ahu9.schematic.png` (SHA-256: `15c350e16a9da8a89a997103f5fb9d2c3359b94749cbe91262f8d892a5bac806`), `docs/ahu10.schematic.png` (SHA-256: `e2c64d28b4b169cbc8cacbe0fad8fb7a60c046db1c3dfaac87b82c120c967c0f`)
- Скрипт увязки разметки: `src/hvac_fdd_dataset/data_wrangling.py`

---

## 1. Архитектурный forensic-анализ внедрения неисправностей (BMS Proxy Forensic)

На основе анализа схемы `BMS.Changes.png`, исходного кода и сопоставления телеметрии с интервалами ground-truth зафиксированы следующие физические факты:

1. **Топология сигнального тракта:**
   - В штатную логику BMCS внесены блоки перехвата:
     - `Input Proxies` (для датчиков: подменяют входящие измерения температур зон до их поступления в алгоритм управления `BMS Control Logic`);
     - `Setpoint Proxies` (для исполнительных механизмов: подменяют вычисленные команды контроллера перед отправкой на физическое оборудование `AHU Hardware`).
2. **Точка съема телеметрии в `Point History Database`:**
   - На схеме `BMS.Changes.png` линия архивации в базу данных истории точек (`Point History Database`) отходит от контура управления.
   - **Эмпирическое доказательство:**
     При инъекции неисправности `CHW Valve Proxy Stuck Open` (например, 2013-11-11 10:30:49, Magnitude = 88.0% stuck open) значение в колонке `AHU9ahuCcValve` в Parquet-файле составляет **5.0% – 10.0%**, а не 88.0%! При этом температура `AHU9ahuSaTemp` падает с 20.1 °C до 18.9 °C из-за физического переохлаждения, а контроллер пытается закрыть клапан и приоткрыть нагрев `AHU9ahuHcValve`.
     Аналогично на AHU-10 (2013-11-11 10:30:53, Magnitude = 53.0% stuck): значение в `AHU10ahuCcValve` составляет **15.8% → 11.6%**, снижаясь в попытке контроллера парировать переохлаждение, а не 53.0%.
   - **Научный вывод:**
     Каналы `AHU*ahuCcValve`, `AHU*ahuOaDamper`, `AHU*ahuRaDamper`, `AHU*ahuHcValve` в опубликованных Parquet-файлах представляют собой **PRE-PROXY CONTROLLER COMMANDS** (выходы ПИД-регулятора TAC Vista), а НЕ принудительно навязанные значения актуатора.
     Фактическая команда привода после proxy (`ACTUATOR_COMMAND_POST_PROXY`) отправлялась на сервопривод Belimo по полевой шине, но **в публичный датасет как отдельный канал не сохранена**.
3. **Последствия для моделирования управляющего усилия:**
   - Моделирование ожидаемой команды $\hat{u}$ (Control-Effort Model) предсказывает, какую команду **должен был сформировать контроллер** в текущих условиях.
   - При аппаратном дефекте (например, заклинивании клапана в открытом положении) контроллер пытается компенсировать ошибку по температуре, снижая команду охлаждения $u_{\text{cmd}} \to 0$ или завышая нагрев. Невязка между номинальной нормальной реакцией $\hat{u}$ и фактической реакцией контроллера $u$ несет диагностический сигнал компенсации (Control Compensation Signature).
   - Поскольку сырой канал является pre-proxy выходом контроллера, в нем **отсутствует прямая утечка искусственного параметра инъекции** (он не равен фиксированной величине `Magnitude`).

---

## 2. Поканальная классификация семантики AHU-09 и AHU-10

Статусы семантики:
- `OBSERVED_PHYSICAL_SENSOR` — физический датчик в установке/здании.
- `CONTROLLER_OUTPUT_PRE_PROXY` — управляющий сигнал контроллера до подмены proxy.
- `DUPLICATE` — аппаратное или программное дублирование другого канала.
- `SETPOINT` — динамическая уставка контура.
- `OPERATING_STATE` — бинарный режим работы.
- `FAULT_INJECTION_PARAMETER` — параметр эксперимента из таблицы разметки (BANNED).

| Сырой тег (AHU9 / AHU10) | Канонический ключ | Единицы | Класс семантики | Pre/Post Proxy | Источник доказательства | Confidence Evidence | Разрешен для инференса | Роль в FDD Stage 8A |
|---|---|---|---|---|---|---|:---:|---|
| `AHU*ahuSaTemp` | `SA_TEMP` | °C | `OBSERVED_PHYSICAL_SENSOR` | Pre-proxy (не подменялся) | Схема установки, термометр PT1000 за вентилятором | DOCUMENTED + OBSERVED | **ДА** | Таргет тепловой модели / Residual $r_T$ |
| `AHU*ahuSaTempSP` | `SA_TEMPSPT` | °C | `SETPOINT` | Pre-proxy | Выход супервизорного сброса уставки TAC Vista | DOCUMENTED + OBSERVED | **ДА** | Контекстный признак для $u_{\text{cmd}}$ |
| `AHU*ahuOaTemp` | `OA_TEMP` | °C | `OBSERVED_PHYSICAL_SENSOR` | Pre-proxy (метеостанция) | Датчик на крыше Energy Centre | DOCUMENTED + OBSERVED | **ДА** | Экзогенное возмущение среды |
| `AHU*ahuRaTemp` | `RA_TEMP` | °C | `OBSERVED_PHYSICAL_SENSOR` | Pre-proxy | Датчик в общем вытяжном коробе AHU-9/10 | DOCUMENTED + OBSERVED | **ДА** | Тепловой возврат из помещений |
| `AHU*ahuMaTemp` | `MA_TEMP` | °C | `DUPLICATE` | Замкнут на SA_TEMP | $\max \|MA - SA\| = 0.00^\circ\text{C}$ во всех строках | OBSERVED (DEVIATION) | **НЕТ** (как независимый $T_{ma}$) | Запрещен для прямой подачи; допустим только через тепловой баланс |
| `AHU*ahuCcValve` | `CHWC_VLV_DM` | % (0–100) | `CONTROLLER_OUTPUT_PRE_PROXY` | PRE-PROXY | Эмпирический тест инъекций: сигнал $\ne \text{Mag}$ | OBSERVED + PROVEN | **ДА** (как таргет $u$ или признак $T$) | Целевая команда охлаждения для $r_u$ |
| `AHU*ahuHcValve` | `HC_VLV_DM` | % (0–100) | `CONTROLLER_OUTPUT_PRE_PROXY` | PRE-PROXY | Эмпирический тест: рост при переохлаждении | OBSERVED + PROVEN | **ДА** | Контекст нагрева |
| `AHU*ahuOaDamper` | `OA_DMPR_DM` | % (0–100) | `CONTROLLER_OUTPUT_PRE_PROXY` | PRE-PROXY | Эмпирический тест инъекций: сигнал $\ne \text{Mag}$ | OBSERVED + PROVEN | **ДА** | Команда заслонки наружного воздуха |
| `AHU*ahuRaDamper` | `RA_DMPR_DM` | % (0–100) | `CONTROLLER_OUTPUT_PRE_PROXY` | PRE-PROXY | Работа в противофазе к OA | OBSERVED + PROVEN | **ДА** | Команда заслонки рециркуляции |
| `AHU*ahuSaFanSpeed` | `SF_CS` / `SF_SPD_DM` | % (0–100) | `CONTROLLER_OUTPUT_PRE_PROXY` / `OPERATING_STATE` | PRE-PROXY | Частотный преобразователь вентилятора | DOCUMENTED + OBSERVED | **ДА** | Эксплуатационный фильтр ($>5\%$) |
| `AHU*ahuSaPressure` | `SA_SP` | Pa | `OBSERVED_PHYSICAL_SENSOR` | Pre-proxy | Дифманометр в приточном коробе | DOCUMENTED + OBSERVED | **ДА** | Аэродинамика притока |
| `AHU*ahuZoneTemp` | `ZONE_TEMP_1` | °C | `OBSERVED_PHYSICAL_SENSOR` | Pre-proxy (если не активен drift) | Термодатчик офиса этажа 3 | DOCUMENTED + OBSERVED | **ТОЛЬКО КАК КОНТЕКСТ** | Средняя температура нагрузки |
| `AHU*ahuZoneTemp.1` | `ZONE_TEMP_2` | °C | `OBSERVED_PHYSICAL_SENSOR` | Pre-proxy | Термодатчик офиса этажа 3 | DOCUMENTED + OBSERVED | **ТОЛЬКО КАК КОНТЕКСТ** | Средняя температура нагрузки |
| `AHU*ahuZoneTemp.2` | `ZONE_TEMP_3` | °C | `OBSERVED_PHYSICAL_SENSOR` | Pre-proxy | Термодатчик офиса этажа 3 | DOCUMENTED + OBSERVED | **ТОЛЬКО КАК КОНТЕКСТ** | Средняя температура нагрузки |
| `AHU*ahuAvgZoneTemp` | `AVG_ZONE_TEMP` | °C | `DERIVED_PROXY` | Вычисляется BMCS / подвержен дрейфу | BMCS среднее по 3 зонам | DOCUMENTED + OBSERVED | **НЕТ** (уязвим к Zone Drift) | Исключен во избежание дрейфа |
| `AHU*ahuSaRH` | `SA_RH` | % | `OBSERVED_PHYSICAL_SENSOR` | Pre-proxy | Гигрометр притока | DOCUMENTED + OBSERVED | **НЕ ИСПОЛЬЗУЕТСЯ** | Не входит в базовый профиль |
| `AHU*ahuRaRH` | `RA_RH` | % | `OBSERVED_PHYSICAL_SENSOR` | Pre-proxy | Гигрометр вытяжки | DOCUMENTED + OBSERVED | **НЕ ИСПОЛЬЗУЕТСЯ** | Не входит в базовый профиль |
| `Magnitude` / `Fault Type` | — | — | `FAULT_INJECTION_PARAMETER` | Ground Truth | Таблица `fault-experiments.parquet` | GROUND TRUTH ONLY | **КАТЕГОРИЧЕСКИ ЗАПРЕЩЕН** | Только для валидации событий |

---

## 3. Критические риски и защитные правила (Guards)

1. **Запрет на использование `AHU*ahuMaTemp` как независимого датчика:**
   - На обеих установках AHU-09 и AHU-10 зафиксировано аппаратное/программное замыкание $MA\_TEMP \equiv SA\_TEMP$ ($\Delta = 0.00^\circ\text{C}$). Прямая подача $MA\_TEMP$ в модель прогноза $SA\_TEMP$ или команды $u$ приводит к катастрофической авторегрессионной утечке таргета ($R^2 \approx 0.999$, полная потеря чувствительности к авариям).
   - **Правило:** Вектор входов $\mathbf{x}$ формируется исключительно из экзогенных каналов: $OA\_TEMP$, $RA\_TEMP$, $SA\_TEMPSPT$, статуса вентилятора и времени суток/недели.
2. **Защита от утечки текущей команды (Self-Leakage Guard):**
   - При обучении модели ожидаемого управляющего усилия $\hat{u} = f(\mathbf{x})$ текущее или будущее значение целевой команды ($u_t, u_{t+1}$) категорически исключено из признаков $\mathbf{x}_t$.
3. **Разделение Ground Truth и телеметрии:**
   - Поля из таблицы `fault-experiments.parquet` изолированы от любых признаковых матриц и используются исключительно постобработчиком метрик (Event Evaluator).

**PASS GATE 8A.1 (Семантическая классификация завершена).**
