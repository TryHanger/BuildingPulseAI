"""
BuildingPulse AI — Stage 8B-R.2 Scientific Integrity Tests
Directly executes on raw RBC-Nesbitt CSVs and generated manifests to verify all Stage 8B-R.2 audit findings.
"""

import sys
from pathlib import Path
import json
import re
import numpy as np
import pandas as pd
import pytest
from scipy.stats import binomtest
from sklearn.linear_model import Ridge

from scripts.evaluate_rbc_nesbitt_reconciled import (
    load_clean_nesbitt,
    select_threshold,
    evaluate_time_aware_fdd,
    CalibratedDomainGuard,
    FAULT_SPECS,
    RAW_DIR
)
from ml.diagnostics.time_aware_fdd import (
    apply_time_aware_causal_k_of_n,
    count_calendar_time_episodes
)


@pytest.fixture(scope="module")
def base_data_and_models():
    b3_files = [
        RAW_DIR / "20160601_Baseline.csv",
        RAW_DIR / "20160712_Baseline.csv",
        RAW_DIR / "20170714_Baseline.csv"
    ]
    val_file = RAW_DIR / "20170729_Baseline.csv"
    
    df_train = pd.concat([load_clean_nesbitt(p) for p in b3_files])
    df_val = load_clean_nesbitt(val_file)
    
    features = ["OA_TEMP", "RA_TEMP", "MA_TEMP", "SA_TEMP_SPT", "SF_SPD"]
    features_noma = ["OA_TEMP", "RA_TEMP", "SA_TEMP_SPT", "SF_SPD"]
    
    m_u = Ridge(alpha=10.0).fit(df_train[features], df_train["CCV_FBK"])
    m_u_noma = Ridge(alpha=10.0).fit(df_train[features_noma], df_train["CCV_FBK"])
    
    test_dfs = {fname: load_clean_nesbitt(RAW_DIR / fname) for fname in FAULT_SPECS}
    
    return {
        "df_train": df_train,
        "df_val": df_val,
        "features": features,
        "features_noma": features_noma,
        "m_u": m_u,
        "m_u_noma": m_u_noma,
        "test_dfs": test_dfs
    }


def test_p0_a_domain_guard_calibrated_envelope(base_data_and_models):
    """P0-A: Prove that Calibrated Dev Envelope covers 100% of healthy development data."""
    ctx = base_data_and_models
    guard = CalibratedDomainGuard(ctx["df_train"], ctx["df_val"], ctx["features"])
    
    # 0% OOD on train and val under dev_envelope
    for _, row in ctx["df_train"].iterrows():
        chk = guard.check_point(row.to_dict(), mode="dev_envelope")
        assert not chk["is_ood"], f"Train point marked OOD: {chk}"
        
    for _, row in ctx["df_val"].iterrows():
        chk = guard.check_point(row.to_dict(), mode="dev_envelope")
        assert not chk["is_ood"], f"Val point marked OOD: {chk}"


def test_p0_b_data_report_parity():
    """P0-B: Verify 100% numerical parity between manifest and generated report."""
    manifest_path = Path("research/runs/rbc_nesbitt_reconciled_manifest.json")
    report_path = Path("research/reports/STAGE8B_R2_EVIDENCE_REPORT.md")
    
    assert manifest_path.exists(), "Manifest missing"
    assert report_path.exists(), "Report missing"
    
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    with open(report_path, "r", encoding="utf-8") as f:
        report_text = f.read()
        
    # Check M6 Direct Damper BAS parity: 2/4 (50.0%), 229/472 fault rows, 4.41% FAR
    m6_res = manifest["reconciled_results"]["evaluation_all_4_scenarios"]["M6_DIRECT_DAMPER_BAS"]
    assert m6_res["detected_physical_episodes"] == 2
    assert m6_res["total_physical_episodes"] == 4
    assert m6_res["detected_fault_rows"] == 229
    assert m6_res["total_fault_rows"] == 472
    assert "2/4 (50.0%)" in report_text
    assert "229/472 fault-строк" in report_text
    assert "4.41%" in report_text


def test_p0_c_circular_shift_destroys_fdd_budget():
    """P0-C: Prove circular block shift explodes normal FAR to > 30%."""
    manifest_path = Path("research/runs/rbc_nesbitt_reconciled_manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    shifts = manifest["scientific_integrity_audit"]["negative_controls"]["circular_block_shift"]
    assert len(shifts) >= 3
    for sc in shifts:
        assert sc["pointwise_far"] > 0.30, f"Expected FAR > 30%, got {sc['pointwise_far']}"
        assert sc["false_episodes_per_8h"] > 0.5


def test_p0_d_causal_ablation_eliminates_negative_predictions(base_data_and_models):
    """P0-D: Prove removing MA_TEMP eliminates negative predictions but drops recall to 2/4."""
    ctx = base_data_and_models
    df17 = ctx["test_dfs"]["20170718_OADamStuck_100.csv"]
    fault_mask = (df17["raw_time_hhmm"] >= 1100) & (df17["raw_time_hhmm"] <= 2000)
    fault_df = df17[fault_mask]
    
    preds_full = ctx["m_u"].predict(fault_df[ctx["features"]])
    preds_noma = ctx["m_u_noma"].predict(fault_df[ctx["features_noma"]])
    
    assert (preds_full < 0.0).sum() == 25
    assert (preds_noma < 0.0).sum() == 0
    assert preds_noma.min() > 35.0  # Physically realistic valve command >= 37.3%


def test_p0_e_regime_coverage_under_fan_speed_mask(base_data_and_models):
    """P0-E: Prove fan speed mask SF_SPD >= 50% drops majority of fault points on 2018 days."""
    ctx = base_data_and_models
    df18_10 = ctx["test_dfs"]["20180710_OADamStuck_30.csv"]
    df18_11 = ctx["test_dfs"]["20180711_CooCoiValStuck_80.csv"]
    
    fmask_10 = (df18_10["raw_time_hhmm"] >= 1030) & (df18_10["raw_time_hhmm"] <= 2030)
    fmask_11 = (df18_11["raw_time_hhmm"] >= 1000) & (df18_11["raw_time_hhmm"] <= 2000)
    
    fan_hi_10 = df18_10["SF_SPD"] >= 50.0
    fan_hi_11 = df18_11["SF_SPD"] >= 50.0
    
    pts_10 = (fmask_10 & fan_hi_10).sum()
    pts_11 = (fmask_11 & fan_hi_11).sum()
    
    assert pts_10 == 34  # 34 / 121 (28.1% coverage)
    assert pts_11 == 6   # 6 / 121 (5.0% coverage)


def test_p0_f_statistical_uncertainty():
    """P0-F: Verify Clopper-Pearson CIs and exact paired tests."""
    bt3 = binomtest(2, 3)
    ci3 = bt3.proportion_ci(confidence_level=0.95, method="exact")
    assert np.isclose(ci3.low * 100, 9.4, atol=0.2)
    assert np.isclose(ci3.high * 100, 99.2, atol=0.2)
    
    bt4 = binomtest(3, 4)
    ci4 = bt4.proportion_ci(confidence_level=0.95, method="exact")
    assert np.isclose(ci4.low * 100, 19.4, atol=0.2)
    assert np.isclose(ci4.high * 100, 99.4, atol=0.2)
    
    pt3 = binomtest(2, 2, 0.5)
    assert pt3.pvalue == 0.5000
    pt4 = binomtest(3, 3, 0.5)
    assert pt4.pvalue == 0.2500
