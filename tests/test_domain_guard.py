"""
Unit Tests for Three-State DomainGuard and Abstention Policy
Demonstrates resolution of finding P0-A (Gate 2).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import pytest

from ml.diagnostics.time_aware_fdd import CalibratedDomainGuard
from scripts.evaluate_rbc_nesbitt_reconciled import load_clean_nesbitt, FAULT_SPECS, RAW_DIR


@pytest.fixture(scope="module")
def guard_context():
    b3_files = [
        RAW_DIR / "20160601_Baseline.csv",
        RAW_DIR / "20160712_Baseline.csv",
        RAW_DIR / "20170714_Baseline.csv"
    ]
    val_file = RAW_DIR / "20170729_Baseline.csv"
    df_train = pd.concat([load_clean_nesbitt(p) for p in b3_files])
    df_val = load_clean_nesbitt(val_file)
    features = ["OA_TEMP", "RA_TEMP", "MA_TEMP", "SA_TEMP_SPT", "SF_SPD"]
    guard = CalibratedDomainGuard(df_train, df_val, features)
    return {
        "df_train": df_train,
        "df_val": df_val,
        "features": features,
        "guard": guard
    }


def test_validation_strict_min_max_flags_expected_ood_rate(guard_context):
    """Verify that strict min-max flags exactly 95 of 288 points on clean validation baseline."""
    ctx = guard_context
    guard = ctx["guard"]
    df_val = ctx["df_val"]
    features = ctx["features"]
    
    val_checks = [guard.check_point(row, mode="strict_train")["is_ood"] for _, row in df_val[features].iterrows()]
    assert sum(val_checks) == 95, f"Expected 95 OOD points on validation baseline, got {sum(val_checks)}"
    assert np.isclose(sum(val_checks) / 288.0, 0.3298, atol=1e-3)


def test_calibrated_dev_envelope_covers_all_healthy_development_data(guard_context):
    """Verify that the calibrated development envelope has 0% OOD on both train and validation."""
    ctx = guard_context
    guard = ctx["guard"]
    df_val = ctx["df_val"]
    df_train = ctx["df_train"]
    features = ctx["features"]
    
    val_checks = [guard.check_point(row, mode="dev_envelope")["is_ood"] for _, row in df_val[features].iterrows()]
    assert sum(val_checks) == 0, f"Expected 0 OOD points under dev envelope on validation, got {sum(val_checks)}"
    
    train_checks = [guard.check_point(row, mode="dev_envelope")["is_ood"] for _, row in df_train[features].iterrows()]
    assert sum(train_checks) == 0, "Expected 0 OOD points under dev envelope on training"


def test_20170718_ma_temp_is_predominantly_ood_under_all_guards(guard_context):
    """Verify that on 2017-07-18, MA_TEMP is OOD for 108 of 109 fault points under both guards."""
    ctx = guard_context
    guard = ctx["guard"]
    features = ctx["features"]
    df17 = load_clean_nesbitt(RAW_DIR / "20170718_OADamStuck_100.csv")
    is_f = (df17["raw_time_hhmm"] >= 1100) & (df17["raw_time_hhmm"] <= 2000)
    fault_df = df17[is_f]
    
    ood_strict = [guard.check_point(row, mode="strict_train")["is_ood"] for _, row in fault_df[features].iterrows()]
    ood_dev = [guard.check_point(row, mode="dev_envelope")["is_ood"] for _, row in fault_df[features].iterrows()]
    
    assert sum(ood_strict) == 108
    assert sum(ood_dev) == 108
    
    # Verify that MA_TEMP is specifically the OOD feature
    ma_ood = [("MA_TEMP" in guard.check_point(row, mode="dev_envelope")["ood_features"]) for _, row in fault_df[features].iterrows()]
    assert sum(ma_ood) == 108
