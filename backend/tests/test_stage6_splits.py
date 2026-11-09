import pytest
import pandas as pd
import numpy as np
from pathlib import Path

from ml.adaptation.splits import CSIROTemporalSplitter
from ml.adaptation.data import (
    load_csiro_dataset,
    extract_adaptation_matrices,
    estimate_physical_mixed_air_temp,
    LOCAL_ADAPTATION_FEATURES
)

@pytest.fixture(scope="module")
def csiro_data():
    df, df_exp = load_csiro_dataset()
    return df, df_exp

def test_temporal_split_no_overlap(csiro_data):
    """Verifies that Train, Validation, and Test index sets have strictly zero overlap."""
    df, df_exp = csiro_data
    splitter = CSIROTemporalSplitter()
    splits = splitter.split(df, df_exp)

    train_set = set(splits["train"]["all_indices"])
    val_set = set(splits["val"]["all_indices"])
    test_set = set(splits["test"]["all_indices"])

    assert len(train_set.intersection(val_set)) == 0, "Train and Val must not overlap"
    assert len(val_set.intersection(test_set)) == 0, "Val and Test must not overlap"
    assert len(train_set.intersection(test_set)) == 0, "Train and Test must not overlap"

def test_temporal_split_strictly_chronological(csiro_data):
    """Verifies that max(Train) < min(Val) < min(Test) (no future information leakage)."""
    df, df_exp = csiro_data
    splitter = CSIROTemporalSplitter()
    splits = splitter.split(df, df_exp)

    dt = pd.to_datetime(df["Datetime"])
    train_max = dt.iloc[splits["train"]["all_indices"]].max()
    val_min = dt.iloc[splits["val"]["all_indices"]].min()
    val_max = dt.iloc[splits["val"]["all_indices"]].max()
    test_min = dt.iloc[splits["test"]["all_indices"]].min()

    assert train_max < val_min, f"Train max ({train_max}) must precede Val min ({val_min})"
    assert val_max < test_min, f"Val max ({val_max}) must precede Test min ({test_min})"

def test_no_fault_contamination_in_train_and_val(csiro_data):
    """Verifies that clean operating indices for Train and Val contain 0 fault or embargo points."""
    df, df_exp = csiro_data
    splitter = CSIROTemporalSplitter(embargo_minutes=60)
    splits = splitter.split(df, df_exp)

    is_fault_raw = splits["masks"]["is_fault_raw"]
    is_fault_emb = splits["masks"]["is_fault_embargo"]

    train_clean = splits["train"]["clean_operating_indices"]
    val_clean = splits["val"]["clean_operating_indices"]

    assert len(train_clean) > 1000, "Must have sufficient healthy train points"
    assert len(val_clean) > 500, "Must have sufficient healthy val points"

    assert not is_fault_raw[train_clean].any(), "Train clean must have 0 raw fault points"
    assert not is_fault_emb[train_clean].any(), "Train clean must have 0 embargoed points"
    assert not is_fault_raw[val_clean].any(), "Val clean must have 0 raw fault points"
    assert not is_fault_emb[val_clean].any(), "Val clean must have 0 embargoed points"

def test_feature_sanitization_and_no_target_leakage(csiro_data):
    """Verifies that SA_TEMP and fault labels cannot be included as input features."""
    df, _ = csiro_data

    # Valid extraction
    X, y, op_mask = extract_adaptation_matrices(df)
    assert "SA_TEMP" not in X.columns
    assert "MA_TEMP_EST" in X.columns
    assert y is not None
    assert len(X) == len(df)

    # Attempting to request target as feature must raise ValueError
    with pytest.raises(ValueError, match="CRITICAL VIOLATION"):
        extract_adaptation_matrices(df, feature_cols=["OA_TEMP", "SA_TEMP"])

    # Attempting to request fault labels as feature must raise ValueError
    with pytest.raises(ValueError, match="CRITICAL VIOLATION"):
        extract_adaptation_matrices(df, feature_cols=["OA_TEMP", "source_fault_label"])

def test_physical_mixed_air_estimation(csiro_data):
    """Verifies that MA_TEMP_EST is bounded between min(OA, RA) and max(OA, RA)."""
    df, _ = csiro_data
    ma_est = estimate_physical_mixed_air_temp(df)
    oa = df["OA_TEMP"]
    ra = df["RA_TEMP"]

    min_bound = np.minimum(oa, ra)
    max_bound = np.maximum(oa, ra)

    assert (ma_est >= min_bound - 1e-4).all()
    assert (ma_est <= max_bound + 1e-4).all()
