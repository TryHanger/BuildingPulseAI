"""
Data loading and preprocessing module for CSIRO AHU9 and AHU10 telemetry.
Reads immutable raw parquet files, performs 1-minute canonical aggregation,
and preserves zero-modification provenance.
"""

from pathlib import Path
from typing import Dict, Optional, Tuple
import numpy as np
import pandas as pd


def load_canonical_csiro_dataframe(
    raw_parquet_path: str,
    ahu_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Tuple[pd.DataFrame, Dict]:
    """
    Loads raw CSIRO parquet, resamples 30s -> 1m mean, maps to canonical column names,
    and returns DataFrame and metadata dict with excluded points report.
    """
    path = Path(raw_parquet_path)
    if not path.exists():
        raise FileNotFoundError(f"CSIRO raw parquet file not found: {path}")

    df_raw = pd.read_parquet(path)
    raw_total_rows = len(df_raw)

    if start_date and end_date:
        df_slice = df_raw.loc[start_date:end_date].copy()
    else:
        df_slice = df_raw.copy()

    if df_slice.empty:
        raise ValueError(f"No records found for AHU{ahu_id} in date range {start_date} to {end_date}")

    raw_slice_rows = len(df_slice)

    # 1-minute mean aggregation
    df_1m = df_slice.resample("1min").mean().dropna(how="all")
    resampled_total_rows = len(df_1m)

    prefix = f"AHU{ahu_id}ahu"

    # Canonical mapping
    df_canonical = pd.DataFrame(index=df_1m.index)
    df_canonical["OA_TEMP"] = df_1m[f"{prefix}OaTemp"].values.round(2)
    df_canonical["RA_TEMP"] = df_1m[f"{prefix}RaTemp"].values.round(2)
    df_canonical["MA_TEMP"] = df_1m[f"{prefix}MaTemp"].values.round(2)
    df_canonical["SA_TEMP"] = df_1m[f"{prefix}SaTemp"].values.round(2)
    df_canonical["SA_TEMPSPT"] = df_1m[f"{prefix}SaTempSP"].values.round(2)

    # Actuators: convert 0..100% to fraction 0..1
    df_canonical["CHWC_VLV_DM"] = np.clip(df_1m[f"{prefix}CcValve"].values / 100.0, 0.0, 1.0).round(4)
    df_canonical["HC_VLV_DM"] = np.clip(df_1m[f"{prefix}HcValve"].values / 100.0, 0.0, 1.0).round(4)
    df_canonical["OA_DMPR_DM"] = np.clip(df_1m[f"{prefix}OaDamper"].values / 100.0, 0.0, 1.0).round(4)
    df_canonical["RA_DMPR_DM"] = np.clip(df_1m[f"{prefix}RaDamper"].values / 100.0, 0.0, 1.0).round(4)

    # Fan Command & Speed
    fan_spd = df_1m[f"{prefix}SaFanSpeed"].values
    df_canonical["SF_CS"] = np.clip(fan_spd / 100.0, 0.0, 1.0).round(4)
    df_canonical["SF_SPD_DM"] = (fan_spd > 5.0).astype(float)

    # Static Pressure: Pa to in. w.g. (1 Pa = 0.00401463 in. w.g.)
    df_canonical["SA_SP"] = (df_1m[f"{prefix}SaPressure"].values * 0.00401463).round(3)

    # Operating filter mask (fan on > 5%)
    operating_mask = df_canonical["SF_SPD_DM"] > 0.5
    operating_rows = int(operating_mask.sum())
    non_operating_rows = resampled_total_rows - operating_rows

    metadata = {
        "ahu_id": ahu_id,
        "raw_file": str(path),
        "raw_total_rows": raw_total_rows,
        "raw_slice_rows": raw_slice_rows,
        "resampled_total_rows": resampled_total_rows,
        "operating_rows": operating_rows,
        "non_operating_rows": non_operating_rows,
        "operating_pct": round(operating_rows / resampled_total_rows * 100, 2) if resampled_total_rows > 0 else 0.0,
    }

    return df_canonical, metadata
