"""
Causal Feature Engineering Module for Control Effort Modeling.
Strictly excludes future points, target leakage, and banned signals.
"""

from typing import List, Tuple
import numpy as np
import pandas as pd

from ml.control_aware.channel_semantics import (
    ALLOWED_EXOGENOUS_FEATURES,
    validate_feature_matrix_columns
)


def extract_control_effort_features(
    df: pd.DataFrame,
    target_col: str = "CHWC_VLV_DM"
) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Extracts exogenous context features for predicting expected control effort u_hat.
    Guarantees no target leakage and causal feature construction.
    """
    if target_col not in df.columns:
        raise KeyError(f"Target column '{target_col}' not found in DataFrame!")

    X = pd.DataFrame(index=df.index)

    # 1. Direct exogenous temperatures and setpoints
    X["OA_TEMP"] = df["OA_TEMP"].astype(float)
    X["RA_TEMP"] = df["RA_TEMP"].astype(float)
    X["SA_TEMPSPT"] = df["SA_TEMPSPT"].astype(float)

    # 2. Physics-inspired temperature gradients
    X["T_target_diff"] = (df["RA_TEMP"] - df["SA_TEMPSPT"]).astype(float)
    X["T_oa_sa_diff"] = (df["OA_TEMP"] - df["SA_TEMPSPT"]).astype(float)

    # 3. Harmonic diurnal time features
    if isinstance(df.index, pd.DatetimeIndex):
        hours = df.index.hour + df.index.minute / 60.0
    else:
        # Fallback if index is string/other
        dt_idx = pd.to_datetime(df.index)
        hours = dt_idx.hour + dt_idx.minute / 60.0

    X["hour_sin"] = np.sin(2.0 * np.pi * hours / 24.0)
    X["hour_cos"] = np.cos(2.0 * np.pi * hours / 24.0)

    # 4. Supply fan command
    X["SF_CS"] = df["SF_CS"].astype(float)

    # Target series
    y = df[target_col].astype(float)

    # Validate no leakage and no banned channels
    validate_feature_matrix_columns(X.columns.tolist(), target_name=target_col)

    return X, y
