"""
Data loading and physical feature alignment for CSIRO AHU9 adaptation.
Guarantees:
  - Zero target leakage: SA_TEMP is never present in input features X.
  - Zero label leakage: fault labels/indices are never present in X.
  - Hardware defect correction: raw AHU9ahuMaTemp (which duplicates SA_TEMP)
    is excluded from local predictors in favor of physical heat-balance estimation.
"""

from typing import Tuple, Dict, List, Optional
from pathlib import Path
import pandas as pd
import numpy as np

from ml.virtual_sensor.dataset import load_scenario_data

# Features permitted for local adaptation models (Basic-compatible, physically sound)
LOCAL_ADAPTATION_FEATURES: List[str] = [
    "OA_TEMP",          # Outdoor temperature (°C)
    "RA_TEMP",          # Return air temperature (°C)
    "SA_TEMPSPT",       # Supply air temperature setpoint (°C)
    "CHWC_VLV_DM",      # Cooling coil valve command (0..1)
    "OA_DMPR_DM",       # Outdoor air damper command (0..1)
    "RA_DMPR_DM",       # Return air damper command (0..1)
    "MA_TEMP_EST"       # Thermodynamically estimated mixed air temp (°C)
]

def estimate_physical_mixed_air_temp(df: pd.DataFrame) -> pd.Series:
    """
    Computes thermodynamic mixture temperature:
      T_ma_est = alpha * T_oa + (1 - alpha) * T_ra
    where alpha = clip(OA_DMPR_DM, 0.10, 1.0) represents outdoor air fraction.
    Prevents using the flawed raw tag AHU9ahuMaTemp which duplicates SA_TEMP.
    """
    oa_col = "OA_TEMP"
    ra_col = "RA_TEMP"
    dmpr_col = "OA_DMPR_DM"

    if oa_col not in df.columns or ra_col not in df.columns:
        raise ValueError("Cannot estimate MA_TEMP: missing OA_TEMP or RA_TEMP")

    oa = df[oa_col]
    ra = df[ra_col]
    alpha = np.clip(df[dmpr_col].values, 0.10, 1.0) if dmpr_col in df.columns else 0.20
    ma_est = alpha * oa.values + (1.0 - alpha) * ra.values
    return pd.Series(ma_est, index=df.index, name="MA_TEMP_EST")

def load_csiro_dataset(
    scenario_id: str = "sc_89e2c6028b4f",
    fault_experiments_path: str = "data/raw/csiro_fault_experiments.parquet"
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Loads CSIRO scenario telemetry and official fault experiments table.
    """
    df, _ = load_scenario_data(scenario_id)
    if "Datetime" in df.columns:
        df["Datetime"] = pd.to_datetime(df["Datetime"])

    exp_path = Path(fault_experiments_path)
    if not exp_path.exists():
        raise FileNotFoundError(f"Fault experiments file '{exp_path}' not found")

    df_exp = pd.read_parquet(exp_path)
    return df, df_exp

def extract_adaptation_matrices(
    df: pd.DataFrame,
    feature_cols: Optional[List[str]] = None
) -> Tuple[pd.DataFrame, pd.Series, pd.Series]:
    """
    Extracts features matrix X, target y, and fan operational mask.
    Enforces strict feature sanitization.
    """
    cols = feature_cols or LOCAL_ADAPTATION_FEATURES
    df_work = df.copy()

    # Always compute MA_TEMP_EST if requested
    if "MA_TEMP_EST" in cols and "MA_TEMP_EST" not in df_work.columns:
        df_work["MA_TEMP_EST"] = estimate_physical_mixed_air_temp(df_work)

    # Check for forbidden columns in input features
    forbidden = ["SA_TEMP", "source_fault_label", "fault_name", "fault_type", "is_fault"]
    for f in forbidden:
        if f in cols:
            raise ValueError(f"CRITICAL VIOLATION: Forbidden column '{f}' requested as feature!")

    for c in cols:
        if c not in df_work.columns:
            raise ValueError(f"Required adaptation feature '{c}' missing in DataFrame")

    X = df_work[cols].copy()
    y = df_work["SA_TEMP"].copy() if "SA_TEMP" in df_work.columns else None

    # Operational mask
    if "SF_SPD_DM" in df_work.columns:
        op_mask = df_work["SF_SPD_DM"] >= 0.5
    else:
        op_mask = pd.Series(True, index=df_work.index)

    return X, y, op_mask
