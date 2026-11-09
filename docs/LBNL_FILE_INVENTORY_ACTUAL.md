# LBNL FILE INVENTORY (ACTUAL) — Фактический инвентарь архива LBNL SD-AHU

**Дата составления:** 2026-11-02 19:08  
**Источник архива:** `https://fdddata.lbl.gov/data/Simulated_LBNL_FDD_Data_Sets_SDAHU/LBNL_FDD_Data_Sets_SDAHU.zip`  
**Размер архива:** 607 666 899 байт (~607.7 МБ)  
**Официальный документ (PDF):** `LBNL_FDD_Data_Sets_SDAHU.pdf`  
**Расхождение DOI:** В шапке PDF указан DOI `10.25984/188132`, на официальной веб-странице указан DOI `10.25984/1881324`. Официальным признается DOI страницы `10.25984/1881324`.

---

## 1. Сводная таблица соответствия файлов архива и документации PDF

В документации (Таблица 4) заявлен 21 файл (1 исправный и 20 неисправных сценариев). В реальном ZIP-архиве содержится ровно 21 CSV-файл (внутри папки `LBNL_FDD_Dataset_SDAHU/`).

| № | Фактическое имя файла в ZIP | Имя в Таблице 4 PDF | Заявленный тип неисправности (PDF) | Верифицированный физический тип | Интенсивность | Статус верификации |
|---|-----------------------------|---------------------|-----------------------------------|----------------------------------|---------------|-------------------|
| 1 | `AHU_annual.csv` | `AHU_annual.csv` | Fault free | Исправный базовый режим (EnergyPlus Chicago TMY) | Baseline | **VERIFIED** |
| 2 | `coi_bias_-2_annual.csv` | `sa_bias_-2_annual.csv` | Supply air temp sensor bias | Смещение датчика температуры притока (выход змеевика) | -2°C | **VERIFIED** (семантика подтверждена) |
| 3 | `coi_bias_-4_annual.csv` | `sa_bias_-4_annual.csv` | Supply air temp sensor bias | Смещение датчика температуры притока (выход змеевика) | -4°C | **VERIFIED** (семантика подтверждена) |
| 4 | `coi_bias_2_annual.csv` | `sa_bias_2_annual.csv` | Supply air temp sensor bias | Смещение датчика температуры притока (выход змеевика) | +2°C | **VERIFIED** (семантика подтверждена: сдвиг `SA_TEMP` ~2.0) |
| 5 | `coi_bias_4_annual.csv` | `sa_bias_4_annual.csv` | Supply air temp sensor bias | Смещение датчика температуры притока (выход змеевика) | +4°C | **VERIFIED** (семантика подтверждена) |
| 6 | `coi_leakage_010_annual.csv` | `coi_leakage_010_annual.csv`| Cooling coil valve leaking | Утечка клапана охладителя через седло | 10% leakage | **VERIFIED** |
| 7 | `coi_leakage_025_annual.csv` | `coi_leakage_025_annual.csv`| Cooling coil valve leaking | Утечка клапана охладителя через седло | 25% leakage | **VERIFIED** |
| 8 | `coi_leakage_040_annual.csv` | `coi_leakage_040_annual.csv`| Cooling coil valve leaking | Утечка клапана охладителя через седло | 40% leakage | **VERIFIED** |
| 9 | `coi_leakage_050_annual.csv` | `coi_leakage_050_annual.csv`| Cooling coil valve leaking | Утечка клапана охладителя через седло | 50% leakage | **VERIFIED** |
| 10 | `coi_stuck_010_annual.csv` | `coi_stuck_010_annual.csv` | Cooling coil valve stuck | Механическое заклинивание клапана охладителя | 10% stuck | **VERIFIED** |
| 11 | `coi_stuck_025_annual.csv` | `coi_stuck_025_annual.csv` | Cooling coil valve stuck | Механическое заклинивание клапана охладителя | 25% stuck (`CHWC_VLV = 0.25` при `CHWC_VLV_DM = 0`) | **VERIFIED** |
| 12 | `coi_stuck_050_annual.csv` | `coi_stuck_050_annual.csv` | Cooling coil valve stuck | Механическое заклинивание клапана охладителя | 50% stuck | **VERIFIED** |
| 13 | `coi_stuck_075_annual.csv` | `coi_stuck_075_annual.csv` | Cooling coil valve stuck | Механическое заклинивание клапана охладителя | 75% stuck | **VERIFIED** |
| 14 | `damper_stuck_010_annual.csv` | `damper_stuck_010_annual.csv`| Outdoor air damper stuck | Заклинивание заслонки наружного воздуха | 10% stuck | **VERIFIED** |
| 15 | `damper_stuck_025_annual.csv` | `damper_stuck_025_annual.csv`| Outdoor air damper stuck | Заклинивание заслонки наружного воздуха | 25% stuck (`OA_DMPR = 0.25` при `OA_DMPR_DM = 0`) | **VERIFIED** |
| 16 | `damper_stuck_075_annual.csv` | `damper_stuck_075_annual.csv`| Outdoor air damper stuck | Заклинивание заслонки наружного воздуха | 75% stuck | **VERIFIED** |
| 17 | `damper_stuck_100_annual_short.csv` | `damper_stuck_100_annual_short.csv`| Outdoor air damper stuck | Заклинивание заслонки (укороченный годовой прогон) | 100% stuck | **VERIFIED** (укороченный файл) |
| 18 | `oa_bias_-2_annual.csv` | `oa_bias_-2_annual.csv` | Outdoor air temp sensor bias | Смещение датчика температуры наружного воздуха | -2°C | **VERIFIED** |
| 19 | `oa_bias_-4_annual.csv` | `oa_bias_-4_annual.csv` | Outdoor air temp sensor bias | Смещение датчика температуры наружного воздуха | -4°C | **VERIFIED** |
| 20 | `oa_bias_2_annual.csv` | `oa_bias_2_annual.csv` | Outdoor air temp sensor bias | Смещение датчика температуры наружного воздуха | +2°C | **VERIFIED** |
| 21 | `oa_bias_4_annual.csv` | `oa_bias_4_annual.csv` | Outdoor air temp sensor bias | Смещение датчика температуры наружного воздуха | +4°C | **VERIFIED** |

---

## 2. Физическое разрешение расхождения `coi_bias` vs `sa_bias`

1. **Технический контекст:** В схеме Single-Duct AHU охладительный змеевик (Cooling Coil) расположен непосредственно перед приточным вентилятором/выходом в воздуховод. В модели EnergyPlus сенсор, измеряющий температуру воздуха за охладительным змеевиком, в схеме контроллера называется Coil Leaving / Supply Air Sensor.
2. **Экспериментальное доказательство:** Анализ данных в моменты работы вентилятора показал, что в файле `coi_bias_2_annual.csv` среднее отклонение `SA_TEMP` от нормального года составляет $\approx +1.95^\circ\text{C}$, в то время как `OA_TEMP` и `RA_TEMP` остаются на уровне нормы ($< 0.01$). Это полностью подтверждает соответствие файла `coi_bias_2_annual.csv` пункту 4 Таблицы 4 («Supply air temperature sensor bias +2°C»).
3. **Использование в исследовании:** Для исключения путаницы в метаданных сценария BuildingPulse AI файл регистрируется с каноническим ярлыком `SENSOR_BIAS_SA_POS_2C` и описанием «Смещение датчика приточного воздуха (Coil discharge SA) +2°C».
