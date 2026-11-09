"""
Chronological and Event Splits Module for Stage 8A.
Defines frozen train, validation, and test periods without overlap.
Includes negative control transforms (temporal permutation, temporal shift).
"""

from typing import Dict, Tuple
import numpy as np
import pandas as pd


# Frozen Stage 8A Split Windows
STAGE8A_SPLIT_WINDOWS = {
    "train": {
        "start": "2013-10-28 00:00:00",
        "end": "2013-11-03 23:59:00",
        "description": "Clean normal operating days for baseline model training"
    },
    "val": {
        "start": "2013-11-04 00:00:00",
        "end": "2013-11-06 23:59:00",
        "description": "Clean normal operating days for 3-sigma and scale calibration"
    },
    "test": {
        "start": "2013-11-07 00:00:00",
        "end": "2013-11-12 23:59:00",
        "description": "Held-out test period containing fault injection experiments"
    }
}


def get_stage8a_split(
    df: pd.DataFrame,
    filter_operating: bool = True
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict]:
    """
    Extracts train, validation, and test subsets based on the frozen chronological split.
    Optionally applies operational gating (SF_SPD_DM > 0.5).
    """
    t_cfg = STAGE8A_SPLIT_WINDOWS["train"]
    v_cfg = STAGE8A_SPLIT_WINDOWS["val"]
    s_cfg = STAGE8A_SPLIT_WINDOWS["test"]

    # Verify no chronological overlap
    t_end = pd.to_datetime(t_cfg["end"])
    v_start = pd.to_datetime(v_cfg["start"])
    v_end = pd.to_datetime(v_cfg["end"])
    s_start = pd.to_datetime(s_cfg["start"])

    if t_end >= v_start:
        raise ValueError("Train end overlaps with validation start!")
    if v_end >= s_start:
        raise ValueError("Validation end overlaps with test start!")

    df_train = df.loc[t_cfg["start"]:t_cfg["end"]].copy()
    df_val = df.loc[v_cfg["start"]:v_cfg["end"]].copy()
    df_test = df.loc[s_cfg["start"]:s_cfg["end"]].copy()

    if filter_operating:
        df_train = df_train[df_train["SF_SPD_DM"] > 0.5]
        df_val = df_val[df_val["SF_SPD_DM"] > 0.5]
        df_test = df_test[df_test["SF_SPD_DM"] > 0.5]

    split_manifest = {
        "train_rows": len(df_train),
        "val_rows": len(df_val),
        "test_rows": len(df_test),
        "train_range": [str(df_train.index.min()), str(df_train.index.max())] if len(df_train) > 0 else [],
        "val_range": [str(df_val.index.min()), str(df_val.index.max())] if len(df_val) > 0 else [],
        "test_range": [str(df_test.index.min()), str(df_test.index.max())] if len(df_test) > 0 else [],
        "filter_operating": filter_operating
    }

    return df_train, df_val, df_test, split_manifest


def apply_negative_control_temporal_shift(
    df: pd.DataFrame,
    shift_hours: int = 24
) -> pd.DataFrame:
    """
    Applies a temporal shift to exogenous input features (OA_TEMP, RA_TEMP, SA_TEMPSPT)
    while keeping timestamps and target u in place.
    Breaks contemporaneous physical causality.
    """
    df_shifted = df.copy()
    shift_steps = shift_hours * 60  # 1-minute steps
    for col in ["OA_TEMP", "RA_TEMP", "SA_TEMPSPT"]:
        if col in df_shifted.columns:
            df_shifted[col] = np.roll(df_shifted[col].values, shift_steps)
    return df_shifted


def apply_negative_control_permutation(
    df: pd.DataFrame,
    seed: int = 42
) -> pd.DataFrame:
    """
    Permutes exogenous feature rows randomly with fixed seed.
    Completely destroys feature-target relationship.
    """
    df_perm = df.copy()
    rng = np.random.RandomState(seed)
    cols_to_permute = [c for c in df_perm.columns if c not in ["CHWC_VLV_DM", "SA_TEMP", "SF_SPD_DM"]]
    perm_indices = rng.permutation(len(df_perm))
    for c in cols_to_permute:
        df_perm[c] = df_perm[c].values[perm_indices]
    return df_perm
