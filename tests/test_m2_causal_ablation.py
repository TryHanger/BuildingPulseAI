"""
Unit Tests for M2 Causal Ablations and Negative Shift Controls
Demonstrates resolution of findings P1-F and Gate 6/7.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import Ridge

from ml.diagnostics.time_aware_fdd import (
    apply_time_aware_causal_k_of_n,
    count_calendar_time_episodes
)
from scripts.evaluate_rbc_nesbitt_reconciled import load_clean_nesbitt, FAULT_SPECS, RAW_DIR


@pytest.fixture(scope="module")
def ablation_context():
    b3_files = [
        RAW_DIR / "20160601_Baseline.csv",
        RAW_DIR / "20160712_Baseline.csv",
        RAW_DIR / "20170714_Baseline.csv"
    ]
    val_file = RAW_DIR / "20170729_Baseline.csv"
    df_train = pd.concat([load_clean_nesbitt(p) for p in b3_files])
    df_val = load_clean_nesbitt(val_file)
    
    f_full = ["OA_TEMP", "RA_TEMP", "MA_TEMP", "SA_TEMP_SPT", "SF_SPD"]
    f_noma = ["OA_TEMP", "RA_TEMP", "SA_TEMP_SPT", "SF_SPD"]
    
    m_full = Ridge(alpha=10.0).fit(df_train[f_full], df_train["CCV_FBK"])
    m_noma = Ridge(alpha=10.0).fit(df_train[f_noma], df_train["CCV_FBK"])
    
    sig_full = float(np.std(np.abs(df_val["CCV_FBK"] - m_full.predict(df_val[f_full])), ddof=1))
    sig_noma = float(np.std(np.abs(df_val["CCV_FBK"] - m_noma.predict(df_val[f_noma])), ddof=1))
    
    test_dfs = {fname: load_clean_nesbitt(RAW_DIR / fname) for fname in FAULT_SPECS}
    
    return {
        "m_full": m_full,
        "m_noma": m_noma,
        "f_full": f_full,
        "f_noma": f_noma,
        "sig_full": sig_full,
        "sig_noma": sig_noma,
        "test_dfs": test_dfs
    }


def test_removing_ma_temp_eliminates_all_negative_predictions(ablation_context):
    """Gate 6: Prove that without MA_TEMP, M2 predicts zero negative valve commands on 2017-07-18."""
    ctx = ablation_context
    df17 = ctx["test_dfs"]["20170718_OADamStuck_100.csv"]
    is_f = (df17["raw_time_hhmm"] >= 1100) & (df17["raw_time_hhmm"] <= 2000)
    
    preds_full = ctx["m_full"].predict(df17[is_f][ctx["f_full"]])
    preds_noma = ctx["m_noma"].predict(df17[is_f][ctx["f_noma"]])
    
    assert (preds_full < 0.0).sum() == 25, "Full model must have 25 negative predictions"
    assert (preds_noma < 0.0).sum() == 0, "No-MA model must have ZERO negative predictions"
    assert preds_noma.min() >= 37.0, f"Expected min >= 37%, got {preds_noma.min()}"


def test_no_ma_temp_drops_oa_damper_detection_on_20170718(ablation_context):
    """Gate 6: Prove that without MA_TEMP, M2 misses the 2017-07-18 damper fault at tau=3.5."""
    ctx = ablation_context
    df17 = ctx["test_dfs"]["20170718_OADamStuck_100.csv"]
    is_f = (df17["raw_time_hhmm"] >= 1100) & (df17["raw_time_hhmm"] <= 2000)
    
    pred_full = ctx["m_full"].predict(df17[ctx["f_full"]])
    pred_noma = ctx["m_noma"].predict(df17[ctx["f_noma"]])
    
    z_full = np.abs(df17["CCV_FBK"] - pred_full) / ctx["sig_full"]
    z_noma = np.abs(df17["CCV_FBK"] - pred_noma) / ctx["sig_noma"]
    
    al_full = apply_time_aware_causal_k_of_n(df17["timestamp"], z_full.values, threshold=3.5, k=2, n=3)
    al_noma = apply_time_aware_causal_k_of_n(df17["timestamp"], z_noma.values, threshold=3.5, k=2, n=3)
    
    assert np.any(al_full[is_f]), "Full model must detect 20170718 fault"
    assert not np.any(al_noma[is_f]), "No-MA model must MISS 20170718 fault, proving reliance on MA_TEMP OOD"


def test_circular_shift_control_destroys_fdd_budget(ablation_context):
    """Gate 7: Prove that circular block shift blows up normal FAR to > 30%."""
    ctx = ablation_context
    test_dfs = ctx["test_dfs"]
    
    for seed in [42, 123, 999]:
        rng = np.random.RandomState(seed)
        total_norm = 0
        total_fa = 0
        for fname, df_t in test_dfs.items():
            spec = FAULT_SPECS[fname]
            is_f = (df_t["raw_time_hhmm"] >= spec["official_start_hhmm"]) & (df_t["raw_time_hhmm"] <= spec["official_end_hhmm"])
            z = np.abs(df_t["CCV_FBK"] - ctx["m_full"].predict(df_t[ctx["f_full"]])) / ctx["sig_full"]
            
            # Shift by between 2h and 22h
            shift = rng.randint(24, len(z) - 24)
            z_shifted = np.roll(z.values, shift)
            
            al = apply_time_aware_causal_k_of_n(df_t["timestamp"], z_shifted, threshold=3.5, k=2, n=3)
            total_norm += int((~is_f).sum())
            total_fa += int(al[~is_f].sum())
            
        shifted_far = total_fa / total_norm
        assert shifted_far > 0.30, f"Seed {seed}: Expected FAR > 30%, got {shifted_far*100:.2f}%"
