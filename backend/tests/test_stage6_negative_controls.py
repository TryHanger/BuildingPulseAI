import hashlib
from pathlib import Path
import pytest
import numpy as np
import pandas as pd

from ml.adaptation.calibrators import (
    ConstantBiasCalibrator,
    AffineCalibrator,
    ResidualRidgeCalibrator,
    LocalRidgeModel
)
from ml.adaptation.metrics import compute_regression_metrics, compute_fdd_metrics
from ml.adaptation.data import extract_adaptation_matrices
from ml.adaptation.splits import CSIROTemporalSplitter

def test_source_model_immutability():
    """Confirms that vs-sa-temp-v2.joblib binary is byte-for-byte identical to baseline (not overwritten)."""
    p = Path("models/vs-sa-temp-v2.joblib")
    assert p.exists()
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    expected_stage5_hash = "9fd340dd28b137e90d37dc4195dc8309e9766130091b82c31082928819c6e48d"
    assert h == expected_stage5_hash, "CRITICAL ERROR: Original LBNL model vs-sa-temp-v2 was modified!"

def test_missing_essential_feature_raises():
    """Negative control: Removing a required adaptation feature must raise ValueError, not invent zeros."""
    df_dummy = pd.DataFrame({
        "OA_TEMP": [20.0, 21.0],
        "RA_TEMP": [24.0, 24.5],
        "SA_TEMP": [18.0, 18.5]
        # Missing SA_TEMPSPT, CHWC_VLV_DM, etc.
    })
    with pytest.raises(ValueError, match="Required adaptation feature"):
        extract_adaptation_matrices(df_dummy)

def test_empty_or_zero_division_handled_cleanly():
    """Negative control: Empty or zero-variance inputs must produce None/nan, never fake 0.0 or crash."""
    empty_true = np.array([])
    empty_pred = np.array([])
    met = compute_regression_metrics(empty_true, empty_pred)
    assert met["count"] == 0
    assert met["mae_degC"] is None
    assert met["r2"] is None

    # Zero variance target (ss_tot == 0)
    flat_true = np.array([20.0, 20.0, 20.0])
    flat_pred = np.array([19.0, 19.5, 19.2])
    met_flat = compute_regression_metrics(flat_true, flat_pred)
    assert met_flat["r2"] is None  # Must not crash with ZeroDivisionError

def test_unfitted_model_inference_guard():
    """Negative control: Calling predict() on unfitted calibrators must raise RuntimeError."""
    c1 = ConstantBiasCalibrator()
    with pytest.raises(RuntimeError, match="not fitted"):
        c1.predict(np.array([15.0]))

    c2 = AffineCalibrator()
    with pytest.raises(RuntimeError, match="not fitted"):
        c2.predict(np.array([15.0]))

    a1 = ResidualRidgeCalibrator()
    with pytest.raises(RuntimeError, match="not fitted"):
        a1.predict(pd.DataFrame({"OA_TEMP": [20.0]}), np.array([15.0]))

    l1 = LocalRidgeModel()
    with pytest.raises(RuntimeError, match="not fitted"):
        l1.predict(pd.DataFrame({"OA_TEMP": [20.0]}))

def test_fault_contamination_injection_detected():
    """Negative control: Synthetic contamination of clean train indices with fault point must fail validation."""
    splitter = CSIROTemporalSplitter(embargo_minutes=60)
    df_mock = pd.DataFrame({
        "Datetime": pd.date_range("2013-10-28 09:00", periods=10, freq="1min"),
        "SF_SPD_DM": [1.0] * 10
    })
    df_exp_mock = pd.DataFrame([{
        "AHU": 9,
        "Fault Type": "Synthetic Fault",
        "Start Datetime": "2013-10-28 09:03",
        "End Datetime": "2013-10-28 09:05"
    }])

    raw_mask, emb_mask = splitter.build_fault_masks(df_mock, df_exp_mock)
    # Minutes 3, 4, 5 must be flagged raw
    assert raw_mask[3] and raw_mask[4] and raw_mask[5]
    # And embargo must cover adjacent points
    assert emb_mask[0] and emb_mask[9]

def test_temporal_split_chronological_integrity():
    """Negative control: Train after Val must raise ValueError on initialization."""
    with pytest.raises(ValueError, match="strictly earlier"):
        CSIROTemporalSplitter(
            train_end="2013-11-05",
            val_start="2013-11-04"  # Inverted!
        )
