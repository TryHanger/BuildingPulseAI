"""
BuildingPulse AI — Stage 8B-R.1 Scientific Integrity Tests
Directly executes on raw RBC-Nesbitt CSVs to verify all 10 audit findings.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import numpy as np
import pandas as pd
import pytest
from scipy.stats import binomtest
from sklearn.linear_model import Ridge

from scripts.evaluate_rbc_nesbitt_reconciled import (
    load_clean_nesbitt,
    select_threshold,
    apply_causal_k_of_n,
    evaluate_causal_fdd,
    DomainGuard,
    FAULT_SPECS,
    RAW_DIR
)


@pytest.fixture(scope="module")
def trained_models_and_data():
    b3_files = [
        RAW_DIR / "20160601_Baseline.csv",
        RAW_DIR / "20160712_Baseline.csv",
        RAW_DIR / "20170714_Baseline.csv"
    ]
    val_file = RAW_DIR / "20170729_Baseline.csv"
    
    df_train = pd.concat([load_clean_nesbitt(p) for p in b3_files])
    df_val = load_clean_nesbitt(val_file)
    
    features = ["OA_TEMP", "RA_TEMP", "MA_TEMP", "SA_TEMP_SPT", "SF_SPD"]
    domain_guard = DomainGuard(df_train, features)
    
    m_T = Ridge(alpha=10.0).fit(df_train[features], df_train["SA_TEMP"])
    m_u = Ridge(alpha=10.0).fit(df_train[features], df_train["CCV_FBK"])
    
    # Validation scales
    res_val_T = np.abs(df_val["SA_TEMP"].values - m_T.predict(df_val[features]))
    sigma_T_abs = float(np.std(res_val_T, ddof=1))
    sigma_T_signed = float(np.std(df_val["SA_TEMP"].values - m_T.predict(df_val[features]), ddof=1))
    z_val_T = res_val_T / sigma_T_abs
    
    res_val_u = np.abs(df_val["CCV_FBK"].values - m_u.predict(df_val[features]))
    sigma_u_abs = float(np.std(res_val_u, ddof=1))
    sigma_u_signed = float(np.std(df_val["CCV_FBK"].values - m_u.predict(df_val[features]), ddof=1))
    z_val_u = res_val_u / sigma_u_abs
    
    z_val_fus = np.maximum(z_val_T, z_val_u)
    
    test_dfs = {fname: load_clean_nesbitt(RAW_DIR / fname) for fname in FAULT_SPECS}
    
    return {
        "df_train": df_train,
        "df_val": df_val,
        "features": features,
        "domain_guard": domain_guard,
        "m_T": m_T,
        "m_u": m_u,
        "sigma_T_abs": sigma_T_abs,
        "sigma_T_signed": sigma_T_signed,
        "sigma_u_abs": sigma_u_abs,
        "sigma_u_signed": sigma_u_signed,
        "z_val_T": z_val_T,
        "z_val_u": z_val_u,
        "z_val_fus": z_val_fus,
        "test_dfs": test_dfs
    }


def test_automated_threshold_selection_rule(trained_models_and_data):
    """P0-1: Prove that validation-only rule selects tau=3.0 for M2 and tau=3.25 for M3."""
    ctx = trained_models_and_data
    candidate_grid = [1.5, 2.0, 2.5, 2.75, 3.0, 3.25, 3.5, 3.75, 4.0]
    
    sel_u = select_threshold(pd.Series(ctx["z_val_u"]), budget_far=0.03, candidate_grid=candidate_grid)
    sel_fus = select_threshold(pd.Series(ctx["z_val_fus"]), budget_far=0.03, candidate_grid=candidate_grid)
    
    # At 3% budget on clean validation baseline:
    # M2 reaches 2.43% at tau=3.00 (<= 3%)
    assert sel_u["selected_threshold"] == 3.00, f"Expected tau=3.00 for M2, got {sel_u['selected_threshold']}"
    
    # M3 reaches 4.17% at tau=3.00 (>3%), and 0.00% at tau=3.25 (<= 3%)
    assert sel_fus["selected_threshold"] == 3.25, f"Expected tau=3.25 for M3, got {sel_fus['selected_threshold']}"
    
    # Disclose that tau=3.5 and tau=4.0 were post-hoc / exploratory choices
    assert sel_u["selected_threshold"] != 3.50
    assert sel_fus["selected_threshold"] != 4.00


def test_m2_dominates_m3_at_matched_thresholds(trained_models_and_data):
    """P0-2: Prove that across all candidate thresholds, M3 never beats M2 and has higher FAR."""
    ctx = trained_models_and_data
    m_T = ctx["m_T"]
    m_u = ctx["m_u"]
    features = ctx["features"]
    test_dfs = ctx["test_dfs"]
    
    z_test_u = {}
    z_test_fus = {}
    for fname, df_f in test_dfs.items():
        zt = np.abs(df_f["SA_TEMP"].values - m_T.predict(df_f[features])) / ctx["sigma_T_abs"]
        zu = np.abs(df_f["CCV_FBK"].values - m_u.predict(df_f[features])) / ctx["sigma_u_abs"]
        z_test_u[fname] = zu
        z_test_fus[fname] = np.maximum(zt, zu)
        
    for tau in [2.5, 3.0, 3.25, 3.5, 3.75, 4.0, 4.25, 4.5]:
        res_m2 = evaluate_causal_fdd(z_test_u, test_dfs, tau, exclude_unresolved=False)
        res_m3 = evaluate_causal_fdd(z_test_fus, test_dfs, tau, exclude_unresolved=False)
        
        # M3 NEVER detects more episodes than M2
        assert res_m3["detected_episodes"] == res_m2["detected_episodes"], f"At tau={tau}, recall differed!"
        
        # At thresholds where thermal noise triggers alarms, M3 has strictly higher FAR
        if tau <= 4.0:
            assert res_m3["pointwise_far"] > res_m2["pointwise_far"], f"At tau={tau}, M3 FAR not higher!"
            
    # Specifically at matched tau=4.00:
    res_m2_40 = evaluate_causal_fdd(z_test_u, test_dfs, 4.00, exclude_unresolved=False)
    res_m3_40 = evaluate_causal_fdd(z_test_fus, test_dfs, 4.00, exclude_unresolved=False)
    assert res_m2_40["detected_episodes"] == 3
    assert res_m3_40["detected_episodes"] == 3
    assert np.isclose(res_m2_40["pointwise_far"], 0.0191, atol=1e-4)
    assert np.isclose(res_m3_40["pointwise_far"], 0.0250, atol=1e-4)
    assert round(res_m2_40["false_episodes_per_8h"], 2) == 0.28
    assert round(res_m3_40["false_episodes_per_8h"], 2) == 0.56


def test_post_fault_damper_override_lingering():
    """P0-3: Verify that Relief/Return Dampers remain at 100% until 22:25 on 20170718."""
    df17 = pd.read_csv(RAW_DIR / "20170718_OADamStuck_100.csv", encoding="latin1")
    times = df17.iloc[:, 1].values
    c73 = df17.iloc[:, 73].values # Relief Air Damper
    c74 = df17.iloc[:, 74].values # Return Air Damper
    
    # Points between 2005 and 2225 (after official 20:00 label end)
    lingering_mask = (times >= 2005) & (times <= 2225)
    assert np.all(c73[lingering_mask] == 100.0), "Relief Damper should be 100% until 22:25"
    assert np.all(c74[lingering_mask] == 100.0), "Return Damper should be 100% until 22:25"
    
    # At 2230 they finally return to baseline 15%
    at_2230 = (times == 2230)
    assert c73[at_2230][0] == 15.0
    assert c74[at_2230][0] == 15.0
    
    # In 20180710, 30% override starts at 1025 and ends at 2035
    df18 = pd.read_csv(RAW_DIR / "20180710_OADamStuck_30.csv", encoding="latin1")
    t18 = df18.iloc[:, 1].values
    c73_18 = df18.iloc[:, 73].values
    assert c73_18[t18 == 1025][0] == 30.0 # Started before official 10:30
    assert c73_18[t18 == 2035][0] == 30.0 # Remained after official 20:30
    assert c73_18[t18 == 2040][0] == 15.0 # Reset at 20:40


def test_ood_negative_predictions_and_causal_path(trained_models_and_data):
    """P0-5: Verify negative valve predictions on 20170718 and MA_TEMP causal entanglement."""
    ctx = trained_models_and_data
    m_u = ctx["m_u"]
    features = ctx["features"]
    df_train = ctx["df_train"]
    df17 = ctx["test_dfs"]["20170718_OADamStuck_100.csv"]
    
    fault_mask = (df17["raw_time_hhmm"] >= 1100) & (df17["raw_time_hhmm"] <= 2000)
    fault_df = df17[fault_mask]
    
    preds = m_u.predict(fault_df[features])
    neg_count = (preds < 0.0).sum()
    
    # Verify exactly 25 of 109 predictions are negative
    assert neg_count == 25, f"Expected 25 negative predictions, got {neg_count}"
    assert np.isclose(preds.min(), -9.2595, atol=1e-3)
    
    # Verify MA_TEMP is out of training range for 108 of 109 observations
    train_ma_min = df_train["MA_TEMP"].min()
    train_ma_max = df_train["MA_TEMP"].max()
    ma_ood_count = ((fault_df["MA_TEMP"] < train_ma_min) | (fault_df["MA_TEMP"] > train_ma_max)).sum()
    assert ma_ood_count == 108, f"Expected 108 MA_TEMP OOD points, got {ma_ood_count}"
    
    # Verify DomainGuard flags them
    guard = ctx["domain_guard"]
    ood_checks = [guard.check_point({f: row[f] for f in features})["is_ood"] for _, row in fault_df.iterrows()]
    assert sum(ood_checks) >= 108


def test_direct_damper_override_telemetry_detects_30_percent_fault():
    """P0-6: Verify that the 30% damper fault is directly visible in BAS telemetry."""
    df18 = pd.read_csv(RAW_DIR / "20180710_OADamStuck_30.csv", encoding="latin1")
    times = df18.iloc[:, 1].values
    c73 = df18.iloc[:, 73].values # Relief Air Damper
    c74 = df18.iloc[:, 74].values # Return Air Damper
    
    is_fault = (times >= 1030) & (times <= 2030)
    damper_override_detected = (c73[is_fault] > 20.0) | (c74[is_fault] > 20.0)
    
    # Directly detects 121/121 points
    assert damper_override_detected.sum() == 121
    assert damper_override_detected.mean() == 1.0


def test_disaggregated_far_and_fan_speed_mask(trained_models_and_data):
    """P0-4: Verify daily FAR divergence and effect of SF_SPD >= 50% mask."""
    ctx = trained_models_and_data
    m_u = ctx["m_u"]
    features = ctx["features"]
    test_dfs = ctx["test_dfs"]
    
    z_test_u = {fname: np.abs(df_f["CCV_FBK"].values - m_u.predict(df_f[features])) / ctx["sigma_u_abs"]
                for fname, df_f in test_dfs.items()}
                
    # Unmasked evaluation at tau=3.5
    res_unmasked = evaluate_causal_fdd(z_test_u, test_dfs, 3.50, exclude_unresolved=False)
    bd = res_unmasked["scenarios_breakdown"]
    
    # 2017 days have low FAR (<= 1.5%)
    assert bd["20170718_OADamStuck_100.csv"]["pointwise_far"] == 0.0112 # 2/179
    assert bd["20170811_CooCoiValStuck_100.csv"]["pointwise_far"] == 0.0000 # 0/167
    
    # 2018 days violate 5% budget in unmasked mode
    assert bd["20180710_OADamStuck_30.csv"]["pointwise_far"] == 0.0659 # 11/167
    assert bd["20180711_CooCoiValStuck_80.csv"]["pointwise_far"] == 0.1018 # 17/167
    
    # Masked evaluation (SF_SPD >= 50%)
    res_masked = evaluate_causal_fdd(z_test_u, test_dfs, 3.50, exclude_unresolved=False, op_mask_fan_ge_50=True)
    bd_masked = res_masked["scenarios_breakdown"]
    
    # On both 2018 days, masked FAR is exactly 0.00%
    assert bd_masked["20180710_OADamStuck_30.csv"]["false_alarm_points"] == 0
    assert bd_masked["20180711_CooCoiValStuck_80.csv"]["false_alarm_points"] == 0


def test_statistical_uncertainty_and_paired_test():
    """P1-8: Verify Clopper-Pearson CI and paired exact test p-values."""
    # N=3: 2 out of 3
    bt3 = binomtest(2, 3)
    ci3 = bt3.proportion_ci(confidence_level=0.95, method="exact")
    assert np.isclose(ci3.low * 100, 9.4, atol=0.2)
    assert np.isclose(ci3.high * 100, 99.2, atol=0.2)
    
    # N=4: 3 out of 4
    bt4 = binomtest(3, 4)
    ci4 = bt4.proportion_ci(confidence_level=0.95, method="exact")
    assert np.isclose(ci4.low * 100, 19.4, atol=0.2)
    assert np.isclose(ci4.high * 100, 99.4, atol=0.2)
    
    # Paired exact test: M2 detects 2, M1 detects 0 (discordant pairs = 2)
    pt3 = binomtest(2, 2, 0.5)
    assert pt3.pvalue == 0.5000, f"Expected p=0.5000, got {pt3.pvalue}"
    
    # Paired exact test for N=4: discordant pairs = 3
    pt4 = binomtest(3, 3, 0.5)
    assert pt4.pvalue == 0.2500, f"Expected p=0.2500, got {pt4.pvalue}"
