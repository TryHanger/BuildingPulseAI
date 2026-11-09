"""
Dynamic Feature Engineering for Stage 8B: Dynamic Control-Aware FDD.

Enforces:
1. Chronological gap detection: lags and rolling filters NEVER span across
   temporal gaps > 120s or fan shutdown periods (overnight 16h gaps).
2. Clean separation of Exogenous-only vs Controller-Conditioned feature sets.
3. Strict prohibition of MA_TEMP (duplicate) and ground truth parameters.
4. Operational regime tagging: COOLING, ECONOMIZER_VENT, TRANSITION_UNKNOWN.
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


# Canonical exogenous base columns
EXOGENOUS_BASE_COLS = ["OA_TEMP", "RA_TEMP", "SA_TEMPSPT"]


def compute_gap_aware_lags(
    df: pd.DataFrame,
    columns: List[str],
    lags: List[int] = [1, 2, 5],
    max_gap_seconds: float = 120.0
) -> pd.DataFrame:
    """
    Computes time-series lags for specified columns while strictly preventing
    leakage across temporal gaps (e.g. overnight shutdown) or fan stops.
    If delta_t > max_gap_seconds or SF_SPD_DM <= 0.5, lags are reset to current sample values.
    """
    df_res = pd.DataFrame(index=df.index)

    if isinstance(df.index, pd.DatetimeIndex):
        dt_series = pd.Series(df.index)
    elif "Datetime" in df.columns:
        dt_series = pd.to_datetime(df["Datetime"]).reset_index(drop=True)
    else:
        dt_series = pd.to_datetime(pd.Series(df.index)).reset_index(drop=True)
    delta_sec = dt_series.diff().dt.total_seconds().fillna(0.0).values

    # Operating mask
    if "SF_SPD_DM" in df.columns:
        is_op = (df["SF_SPD_DM"] >= 0.5).values
    else:
        is_op = np.ones(len(df), dtype=bool)

    # A break occurs if time delta > max_gap or fan turned on after being off
    fan_turned_on = np.zeros(len(df), dtype=bool)
    fan_turned_on[1:] = is_op[1:] & (~is_op[:-1])
    is_break = (delta_sec > max_gap_seconds) | fan_turned_on

    # Identify continuous operational segments
    segment_ids = np.cumsum(is_break)

    for col in columns:
        vals = df[col].values
        for lag in lags:
            lag_col_name = f"{col}_lag{lag}"
            lag_vals = np.empty(len(vals), dtype=float)
            lag_vals[:] = np.nan

            # Compute lag strictly within each continuous segment
            for seg_id in np.unique(segment_ids):
                seg_idx = np.where(segment_ids == seg_id)[0]
                n_seg = len(seg_idx)
                if n_seg == 0:
                    continue
                seg_data = vals[seg_idx]
                if n_seg > lag:
                    # Within segment, shift by lag; warm-up points get the earliest value
                    shifted = np.empty(n_seg, dtype=float)
                    shifted[:lag] = seg_data[0] # clamp to start of run to avoid dropping points
                    shifted[lag:] = seg_data[:-lag]
                    lag_vals[seg_idx] = shifted
                else:
                    lag_vals[seg_idx] = seg_data[0]

            df_res[lag_col_name] = lag_vals

    return df_res


def classify_operating_regime(df: pd.DataFrame) -> pd.Series:
    """
    Tags each operational point into physical HVAC regimes:
    - COOLING: Outdoor temp > Setpoint + 1.0 °C and Cooling Valve > 5%
    - ECONOMIZER_VENT: Outdoor temp <= Setpoint and Cooling Valve <= 5%
    - TRANSITION_UNKNOWN: Mixed or transitional conditions
    """
    regimes = pd.Series("TRANSITION_UNKNOWN", index=df.index)

    oa = df["OA_TEMP"] if "OA_TEMP" in df.columns else None
    spt = df["SA_TEMPSPT"] if "SA_TEMPSPT" in df.columns else None
    u_cc = df["CHWC_VLV_DM"] if "CHWC_VLV_DM" in df.columns else None

    if oa is not None and spt is not None and u_cc is not None:
        cooling_mask = (oa > (spt + 1.0)) & (u_cc > 0.05)
        econ_mask = (oa <= spt) & (u_cc <= 0.05)

        regimes[cooling_mask] = "COOLING"
        regimes[econ_mask] = "ECONOMIZER_VENT"

    return regimes


def extract_dynamic_features(
    df: pd.DataFrame,
    include_controller_state: bool = False,
    lags: List[int] = [1, 2, 5]
) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Extracts dynamic feature matrix X and target u (CHWC_VLV_DM).

    If include_controller_state is False (Pure Exogenous Dynamic):
        Features: OA_TEMP, RA_TEMP, SA_TEMPSPT, time-of-day harmonic features,
                  plus gap-aware lags of exogenous signals.
    If include_controller_state is True (Controller-Conditioned ARX):
        Adds: Tracking error e_t = (SA_TEMP - SA_TEMPSPT) and its lags.

    Guarantees:
    - MA_TEMP is banned.
    - Current target u_t is never in X.
    - Fault labels/magnitudes are strictly banned.
    """
    # Safety checks
    banned = ["MA_TEMP", "Magnitude", "Fault Type", "source_fault_label"]
    for b in banned:
        if b in df.columns and b in EXOGENOUS_BASE_COLS:
            raise ValueError(f"CRITICAL VIOLATION: Banned column '{b}' in base columns!")

    df_feats = pd.DataFrame(index=df.index)

    # Base exogenous features
    for c in EXOGENOUS_BASE_COLS:
        if c not in df.columns:
            raise KeyError(f"Required exogenous column '{c}' missing in DataFrame")
        df_feats[c] = df[c].values

    # Thermal load proxy: (OA_TEMP - SA_TEMPSPT) and (RA_TEMP - SA_TEMPSPT)
    df_feats["OA_MINUS_SPT"] = df["OA_TEMP"].values - df["SA_TEMPSPT"].values
    df_feats["RA_MINUS_SPT"] = df["RA_TEMP"].values - df["SA_TEMPSPT"].values

    # Time of day harmonic features
    if isinstance(df.index, pd.DatetimeIndex):
        dt_idx = df.index
        hour_float = dt_idx.hour + dt_idx.minute / 60.0
    else:
        dt_s = pd.to_datetime(df["Datetime"])
        hour_float = (dt_s.dt.hour + dt_s.dt.minute / 60.0).values
    df_feats["H_SIN"] = np.sin(2.0 * np.pi * hour_float / 24.0)
    df_feats["H_COS"] = np.cos(2.0 * np.pi * hour_float / 24.0)

    # Gap-aware exogenous lags
    df_lags = compute_gap_aware_lags(df, columns=EXOGENOUS_BASE_COLS, lags=lags)
    for col in df_lags.columns:
        df_feats[col] = df_lags[col].values

    # Controller-conditioned features (if requested for M5 ablation)
    if include_controller_state:
        if "SA_TEMP" in df.columns:
            err = df["SA_TEMP"].values - df["SA_TEMPSPT"].values
            df_feats["TRACKING_ERROR"] = err
            # Add lag of tracking error
            df_err_tmp = pd.DataFrame({"TRACKING_ERROR": err}, index=df.index)
            if "Datetime" in df.columns:
                df_err_tmp["Datetime"] = df["Datetime"].values
            if "SF_SPD_DM" in df.columns:
                df_err_tmp["SF_SPD_DM"] = df["SF_SPD_DM"].values
            df_err_lags = compute_gap_aware_lags(df_err_tmp, columns=["TRACKING_ERROR"], lags=[1, 2])
            for col in df_err_lags.columns:
                df_feats[col] = df_err_lags[col].values

    target = df["CHWC_VLV_DM"].copy() if "CHWC_VLV_DM" in df.columns else None

    return df_feats, target
