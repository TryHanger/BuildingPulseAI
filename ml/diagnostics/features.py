import numpy as np
import pandas as pd
from typing import List, Tuple, Dict, Optional
from ml.virtual_sensor.features import fahrenheit_to_celsius

BASIC_OBSERVATION_COLUMNS = [
    "MA_TEMP",
    "OA_TEMP",
    "RA_TEMP",
    "SA_TEMP",
    "CHWC_VLV_DM",
    "OA_DMPR_DM",
    "SF_SPD_DM",
    "SA_TEMPSPT"
]

DIAGNOSTIC_FEATURE_NAMES = [
    "res_sa_signed",          # Signed virtual sensor residual: SA_TEMP - SA_TEMP_pred (°C)
    "res_sa_abs",             # Absolute residual: |SA_TEMP - SA_TEMP_pred| (°C)
    "res_sa_roll_mean_15",    # Causal 15-minute rolling mean of signed residual
    "res_sa_roll_std_15",     # Causal 15-minute rolling std of signed residual
    "delta_t_chwc",           # MA_TEMP - SA_TEMP: thermal drop across cooling coil (°C)
    "delta_t_mixing",         # MA_TEMP - OA_TEMP: mixed air temperature difference (°C)
    "error_spt",              # SA_TEMP - SA_TEMPSPT: control error from setpoint (°C)
    "chwc_vlv_dm",            # Cooling coil command [0..1]
    "oa_dmpr_dm",             # Outdoor air damper command [0..1]
    "oa_temp",                # Outdoor air temperature (°C)
    "cooling_demand_discrepancy"  # Discrepancy indicator: CHWC_VLV_DM vs delta_t_chwc
]

def extract_diagnostic_features(
    df: pd.DataFrame,
    vs_pred: np.ndarray,
    operating_mask: pd.Series
) -> pd.DataFrame:
    """
    Extracts strictly Basic-profile physical features for fault-family diagnosis.
    Guaranteed:
      - Causal timing (only current and past 15 points, no future leakage).
      - Target SA_TEMP is an available runtime observation for diagnosis,
        while virtual sensor prediction vs_pred was computed without SA_TEMP.
      - No actual position feedback (CHWC_VLV, OA_DMPR) used.
      - No source labels or filenames.
    """
    df_clean = df.copy()

    # Unit normalization to °C
    for col in ["MA_TEMP", "OA_TEMP", "RA_TEMP", "SA_TEMP", "SA_TEMPSPT"]:
        if col in df_clean.columns:
            if df_clean[col].dropna().mean() > 30.0:
                df_clean[col] = fahrenheit_to_celsius(df_clean[col])

    sa_act = df_clean["SA_TEMP"].values
    ma_temp = df_clean["MA_TEMP"].values if "MA_TEMP" in df_clean.columns else np.zeros(len(df))
    oa_temp = df_clean["OA_TEMP"].values if "OA_TEMP" in df_clean.columns else np.zeros(len(df))
    vlv_dm = df_clean["CHWC_VLV_DM"].values if "CHWC_VLV_DM" in df_clean.columns else np.zeros(len(df))
    dmpr_dm = df_clean["OA_DMPR_DM"].values if "OA_DMPR_DM" in df_clean.columns else np.zeros(len(df))
    spt = df_clean["SA_TEMPSPT"].values if "SA_TEMPSPT" in df_clean.columns else np.full(len(df), 12.8)

    # 1. Residual features
    res_signed = sa_act - vs_pred
    res_abs = np.abs(res_signed)

    # Causal rolling statistics (15 minutes, closed on the right, min_periods=1)
    s_res = pd.Series(res_signed, index=df_clean.index)
    res_roll_mean = s_res.rolling(window=15, min_periods=1).mean().values
    res_roll_std = s_res.rolling(window=15, min_periods=1).std().fillna(0.0).values

    # 2. Physical thermal drops
    delta_t_chwc = ma_temp - sa_act
    delta_t_mixing = ma_temp - oa_temp
    error_spt = sa_act - spt

    # Cooling demand discrepancy:
    # If valve commanded open (vlv_dm > 0.2) but cooling drop is small or negative -> stuck closed / under-cooling
    # If valve commanded closed (vlv_dm < 0.05) but strong cooling drop (> 2°C) -> stuck open / over-cooling
    cooling_discrepancy = np.where(
        vlv_dm < 0.05,
        np.maximum(0.0, delta_t_chwc - 1.0),
        np.where(vlv_dm > 0.3, np.maximum(0.0, 3.0 * vlv_dm - delta_t_chwc), 0.0)
    )

    X_diag = pd.DataFrame({
        "res_sa_signed": res_signed,
        "res_sa_abs": res_abs,
        "res_sa_roll_mean_15": res_roll_mean,
        "res_sa_roll_std_15": res_roll_std,
        "delta_t_chwc": delta_t_chwc,
        "delta_t_mixing": delta_t_mixing,
        "error_spt": error_spt,
        "chwc_vlv_dm": vlv_dm,
        "oa_dmpr_dm": dmpr_dm,
        "oa_temp": oa_temp,
        "cooling_demand_discrepancy": cooling_discrepancy
    }, index=df_clean.index)

    return X_diag
