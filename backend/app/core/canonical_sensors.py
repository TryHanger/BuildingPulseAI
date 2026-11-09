from typing import Dict, Any, Optional

CANONICAL_SENSOR_METADATA: Dict[str, Dict[str, Any]] = {
    "OA_TEMP": {
        "display_name_ru": "Температура наружного воздуха",
        "component": "OUTDOOR",
        "signal_kind": "MEASUREMENT",
        "unit": "degF",
        "is_basic": True,
        "aliases": ["oa_temp", "oat", "outdoor_temp", "t_oa", "outdoor_air_temp", "outdoorairstreamtemperature"]
    },
    "RA_TEMP": {
        "display_name_ru": "Температура возвратного воздуха",
        "component": "RETURN",
        "signal_kind": "MEASUREMENT",
        "unit": "degF",
        "is_basic": True,
        "aliases": ["ra_temp", "rat", "return_temp", "t_ra", "return_air_temp", "returnairstreamtemperature"]
    },
    "MA_TEMP": {
        "display_name_ru": "Температура смешанного воздуха",
        "component": "MIXING",
        "signal_kind": "MEASUREMENT",
        "unit": "degF",
        "is_basic": True,
        "aliases": ["ma_temp", "mat", "mixed_temp", "t_ma", "mixed_air_temp", "mixedairstreamtemperature"]
    },
    "SA_TEMP": {
        "display_name_ru": "Температура приточного воздуха",
        "component": "FAN",
        "signal_kind": "MEASUREMENT",
        "unit": "degF",
        "is_basic": True,
        "aliases": ["sa_temp", "sat", "supply_temp", "t_sa", "discharge_temp", "supply_air_temp", "supplyairstreamtemperature"]
    },
    "SA_TEMPSPT": {
        "display_name_ru": "Уставка температуры притока",
        "component": "FAN",
        "signal_kind": "COMMAND",
        "unit": "degF",
        "is_basic": True,
        "aliases": ["sa_tempspt", "sat_spt", "sat_sp", "supply_air_temperature_setpoint"]
    },
    "CHWC_VLV_DM": {
        "display_name_ru": "Команда охлаждающему клапану",
        "component": "COOLING_COIL",
        "signal_kind": "COMMAND",
        "unit": "0-1",
        "is_basic": True,
        "aliases": ["chwc_vlv_dm", "chw_valve_cmd", "ccv_cmd", "cooling_valve_dm", "chw_vlv_dm"]
    },
    "CHWC_VLV": {
        "display_name_ru": "Положение охлаждающего клапана (факт)",
        "component": "COOLING_COIL",
        "signal_kind": "FEEDBACK",
        "unit": "0-1",
        "is_basic": False,
        "aliases": ["chwc_vlv", "chw_valve_pos", "ccv_pos", "cooling_valve_pos", "chw_vlv"]
    },
    "OA_DMPR_DM": {
        "display_name_ru": "Команда наружной заслонке",
        "component": "OUTDOOR",
        "signal_kind": "COMMAND",
        "unit": "0-1",
        "is_basic": True,
        "aliases": ["oa_dmpr_dm", "oad_cmd", "oa_damper_cmd", "damper_dm", "oa_damper_dm"]
    },
    "OA_DMPR": {
        "display_name_ru": "Положение наружной заслонки (факт)",
        "component": "OUTDOOR",
        "signal_kind": "FEEDBACK",
        "unit": "0-1",
        "is_basic": False,
        "aliases": ["oa_dmpr", "oad_pos", "oa_damper_pos", "oa_damper"]
    },
    "RA_DMPR_DM": {
        "display_name_ru": "Команда возвратной заслонке",
        "component": "RETURN",
        "signal_kind": "COMMAND",
        "unit": "0-1",
        "is_basic": True,
        "aliases": ["ra_dmpr_dm", "rad_cmd", "ra_damper_cmd", "ra_damper_dm"]
    },
    "RA_DMPR": {
        "display_name_ru": "Положение возвратной заслонки (факт)",
        "component": "RETURN",
        "signal_kind": "FEEDBACK",
        "unit": "0-1",
        "is_basic": False,
        "aliases": ["ra_dmpr", "rad_pos", "ra_damper_pos", "ra_damper"]
    },
    "SF_SPD_DM": {
        "display_name_ru": "Команда пуска приточного вентилятора",
        "component": "FAN",
        "signal_kind": "COMMAND",
        "unit": "0/1",
        "is_basic": True,
        "aliases": ["sf_spd_dm", "sf_stat", "supply_fan_cmd", "sf_cmd"]
    },
    "SF_CS": {
        "display_name_ru": "Сигнал скорости приточного вентилятора",
        "component": "FAN",
        "signal_kind": "COMMAND",
        "unit": "0-1",
        "is_basic": True,
        "aliases": ["sf_cs", "sf_speed_cmd", "supply_fan_cs"]
    },
    "SF_SPD": {
        "display_name_ru": "Фактическая скорость приточного вентилятора",
        "component": "FAN",
        "signal_kind": "FEEDBACK",
        "unit": "0-1",
        "is_basic": False,
        "aliases": ["sf_spd", "supply_fan_speed", "sf_speed_feedback"]
    },
    "SF_WAT": {
        "display_name_ru": "Мощность приточного вентилятора",
        "component": "FAN",
        "signal_kind": "MEASUREMENT",
        "unit": "W",
        "is_basic": False,
        "aliases": ["sf_wat", "sf_power", "supply_fan_watts"]
    },
    "RF_SPD_DM": {
        "display_name_ru": "Команда пуска возвратного вентилятора",
        "component": "RETURN",
        "signal_kind": "COMMAND",
        "unit": "0/1",
        "is_basic": True,
        "aliases": ["rf_spd_dm", "rf_stat", "return_fan_cmd"]
    },
    "RF_CS": {
        "display_name_ru": "Сигнал скорости возвратного вентилятора",
        "component": "RETURN",
        "signal_kind": "COMMAND",
        "unit": "0-1",
        "is_basic": True,
        "aliases": ["rf_cs", "rf_speed_cmd"]
    },
    "RF_SPD": {
        "display_name_ru": "Фактическая скорость возвратного вентилятора",
        "component": "RETURN",
        "signal_kind": "FEEDBACK",
        "unit": "0-1",
        "is_basic": False,
        "aliases": ["rf_spd", "return_fan_speed"]
    },
    "RF_WAT": {
        "display_name_ru": "Мощность возвратного вентилятора",
        "component": "RETURN",
        "signal_kind": "MEASUREMENT",
        "unit": "W",
        "is_basic": False,
        "aliases": ["rf_wat", "rf_power"]
    },
    "OA_CFM": {
        "display_name_ru": "Расход наружного воздуха",
        "component": "OUTDOOR",
        "signal_kind": "MEASUREMENT",
        "unit": "CFM",
        "is_basic": False,
        "aliases": ["oa_cfm", "outdoor_airflow"]
    },
    "RA_CFM": {
        "display_name_ru": "Расход возвратного воздуха",
        "component": "RETURN",
        "signal_kind": "MEASUREMENT",
        "unit": "CFM",
        "is_basic": False,
        "aliases": ["ra_cfm", "return_airflow"]
    },
    "SA_CFM": {
        "display_name_ru": "Расход приточного воздуха",
        "component": "FAN",
        "signal_kind": "MEASUREMENT",
        "unit": "CFM",
        "is_basic": False,
        "aliases": ["sa_cfm", "supply_airflow"]
    },
    "SA_SP": {
        "display_name_ru": "Статическое давление в притоке",
        "component": "FAN",
        "signal_kind": "MEASUREMENT",
        "unit": "in. w.g.",
        "is_basic": True,
        "aliases": ["sa_sp", "supply_static_pressure"]
    },
    "SA_SPSPT": {
        "display_name_ru": "Уставка статического давления",
        "component": "FAN",
        "signal_kind": "COMMAND",
        "unit": "in. w.g.",
        "is_basic": True,
        "aliases": ["sa_spspt", "supply_static_pressure_setpoint"]
    },
    "SYS_CTL": {
        "display_name_ru": "Режим занятости / работы AHU",
        "component": "SYSTEM",
        "signal_kind": "COMMAND",
        "unit": "0/1",
        "is_basic": False,
        "aliases": ["sys_ctl", "occupancy_mode", "occ_mode", "system_control"]
    },
    "ZONE_TEMP_1": {
        "display_name_ru": "Температура Зоны 1",
        "component": "ZONE",
        "signal_kind": "MEASUREMENT",
        "unit": "degF",
        "is_basic": True,
        "aliases": ["zone_temp_1", "zt1", "zone1_temp"]
    },
    "ZONE_TEMP_2": {
        "display_name_ru": "Температура Зоны 2",
        "component": "ZONE",
        "signal_kind": "MEASUREMENT",
        "unit": "degF",
        "is_basic": True,
        "aliases": ["zone_temp_2", "zt2", "zone2_temp"]
    },
    "ZONE_TEMP_3": {
        "display_name_ru": "Температура Зоны 3",
        "component": "ZONE",
        "signal_kind": "MEASUREMENT",
        "unit": "degF",
        "is_basic": True,
        "aliases": ["zone_temp_3", "zt3", "zone3_temp"]
    },
    "ZONE_TEMP_4": {
        "display_name_ru": "Температура Зоны 4",
        "component": "ZONE",
        "signal_kind": "MEASUREMENT",
        "unit": "degF",
        "is_basic": True,
        "aliases": ["zone_temp_4", "zt4", "zone4_temp"]
    },
    "ZONE_TEMP_5": {
        "display_name_ru": "Температура Зоны 5",
        "component": "ZONE",
        "signal_kind": "MEASUREMENT",
        "unit": "degF",
        "is_basic": True,
        "aliases": ["zone_temp_5", "zt5", "zone5_temp"]
    }
}

def resolve_canonical_key(col_name: str) -> Optional[str]:
    """Match raw column name to canonical key case-insensitively or via aliases."""
    raw = col_name.strip()
    upper = raw.upper()
    if upper in CANONICAL_SENSOR_METADATA:
        return upper
    lower = raw.lower()
    for key, meta in CANONICAL_SENSOR_METADATA.items():
        if lower in meta["aliases"]:
            return key
    return None
