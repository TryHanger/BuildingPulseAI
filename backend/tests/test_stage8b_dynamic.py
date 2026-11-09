"""
Unit and Regression Tests for Stage 8B: Dynamic Control-Aware Fault Detection.

Verifies:
1. Gap-aware dynamic lags reset across overnight shutdowns (>120s).
2. Fan state transitions reset lag memory.
3. Zero leakage: MA_TEMP duplicate and current u_t strictly banned.
4. Physical regime partitioning correctness.
5. Causal K-of-N persistence filter gap resets.
6. Robust regime scaler normalization.
7. Physical fault episode consolidation.
8. Negative control permutation validity.
9. Clean embargoed partition on AHU-10.
10. Stage 8B evaluation manifest integrity and scientific reproducibility.
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from ml.control_aware.dynamic_features import (
    compute_gap_aware_lags,
    classify_operating_regime,
    extract_dynamic_features
)
from ml.control_aware.dynamic_models import (
    DynamicRidgeControlModel,
    RobustRegimeScaler
)
from ml.control_aware.evaluate_stage8b import (
    extract_physical_fault_episodes,
    score_physical_episodes,
    split_clean_ahu
)
from ml.adaptation.splits import CSIROTemporalSplitter
from ml.control_aware.alarm_policy import apply_causal_k_of_n_filter


def test_dynamic_lags_reset_on_overnight_gap():
    """Verify that lag features NEVER jump across gaps > 120s (e.g. 16h overnight)."""
    # Create artificial telemetry with an overnight gap
    times = [
        "2013-11-01 16:58:00",
        "2013-11-01 16:59:00",
        "2013-11-01 17:00:00",
        # 16-hour overnight gap
        "2013-11-02 09:00:00",
        "2013-11-02 09:01:00",
        "2013-11-02 09:02:00"
    ]
    df = pd.DataFrame({
        "OA_TEMP": [15.0, 15.2, 15.4, 25.0, 25.5, 26.0],
        "SF_SPD_DM": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    }, index=pd.to_datetime(times))

    df_lags = compute_gap_aware_lags(df, columns=["OA_TEMP"], lags=[1], max_gap_seconds=120.0)

    # Point at 09:00:00 MUST NOT use 17:00:00 value (15.4), it must be clamped to current segment start (25.0)
    assert df_lags.loc["2013-11-02 09:00:00", "OA_TEMP_lag1"] == 25.0
    # Next point at 09:01:00 should normally lag 09:00:00 (25.0)
    assert df_lags.loc["2013-11-02 09:01:00", "OA_TEMP_lag1"] == 25.0
    assert df_lags.loc["2013-11-02 09:02:00", "OA_TEMP_lag1"] == 25.5


def test_dynamic_lags_reset_on_fan_start():
    """Verify that when fan turns on after being off, dynamic state resets."""
    times = [
        "2013-11-01 09:00:00",
        "2013-11-01 09:01:00",
        "2013-11-01 09:02:00",
        "2013-11-01 09:03:00"
    ]
    df = pd.DataFrame({
        "OA_TEMP": [10.0, 10.0, 30.0, 31.0],
        "SF_SPD_DM": [0.0, 0.0, 1.0, 1.0] # Fan turns on at step 2
    }, index=pd.to_datetime(times))

    df_lags = compute_gap_aware_lags(df, columns=["OA_TEMP"], lags=[1], max_gap_seconds=120.0)
    # At step 2 (fan on), lag should be reset to current 30.0, NOT 10.0 from fan-off
    assert df_lags.iloc[2]["OA_TEMP_lag1"] == 30.0
    assert df_lags.iloc[3]["OA_TEMP_lag1"] == 30.0


def test_feature_leakage_prohibits_banned_columns():
    """Verify that extract_dynamic_features enforces strict bans."""
    df = pd.DataFrame({
        "OA_TEMP": [20.0],
        "RA_TEMP": [22.0],
        "SA_TEMPSPT": [18.0],
        "CHWC_VLV_DM": [0.5],
        "SF_SPD_DM": [1.0],
        "MA_TEMP": [20.0] # Duplicate
    }, index=pd.to_datetime(["2013-11-01 10:00:00"]))

    X, u = extract_dynamic_features(df, include_controller_state=False)
    # MA_TEMP must not be in X
    assert "MA_TEMP" not in X.columns
    # Target u must not be in X
    assert "CHWC_VLV_DM" not in X.columns
    assert u.iloc[0] == 0.5


def test_regime_classification_boundaries():
    """Verify correct physical regime tagging."""
    df = pd.DataFrame({
        "OA_TEMP": [25.0, 15.0, 20.0],
        "SA_TEMPSPT": [18.0, 18.0, 18.0],
        "CHWC_VLV_DM": [0.40, 0.00, 0.02]
    })
    regimes = classify_operating_regime(df)
    assert regimes.iloc[0] == "COOLING"          # OA > SPT + 1.0 and Valve > 5%
    assert regimes.iloc[1] == "ECONOMIZER_VENT"  # OA <= SPT and Valve <= 5%
    assert regimes.iloc[2] == "TRANSITION_UNKNOWN"


def test_robust_regime_scaler():
    """Verify regime-specific scaling prevents scale collapse."""
    residuals = np.array([0.1, 0.2, 0.15, 0.9, 1.1, 1.0])
    regimes = pd.Series(["ECONOMIZER_VENT"] * 3 + ["COOLING"] * 3)

    scaler = RobustRegimeScaler(min_samples=3)
    scaler.fit(residuals, regimes)

    z = scaler.transform(residuals, regimes)
    assert len(z) == 6
    assert np.all(z >= 0)
    assert np.all(np.isfinite(z))


def test_physical_episode_grouping():
    """Verify that simultaneous fault rows are consolidated into 1 physical episode."""
    exp_df = pd.DataFrame({
        "AHU": [9, 9, 9],
        "Start Datetime": ["2013-11-08 14:32:34", "2013-11-08 14:32:34", "2013-11-08 14:32:46"],
        "End Datetime":   ["2013-11-08 15:32:42", "2013-11-08 15:32:43", "2013-11-08 15:32:50"],
        "Fault Type":     ["OA Damper Stuck Open", "Zone Average Temp Drift", "OA Damper Stuck Open"]
    }, index=[287, 288, 289])

    phys_df = extract_physical_fault_episodes(exp_df, ahu_id=9, test_start="2013-11-08 00:00:00", test_end="2013-11-08 23:59:00")
    # All 3 simultaneous rows MUST be merged into exactly 1 consolidated physical episode
    assert len(phys_df) == 1
    assert set(phys_df.iloc[0]["fault_row_ids"]) == {287, 288, 289}
    assert len(phys_df.iloc[0]["fault_types"]) == 2 # 2 unique fault types


def test_causal_persistence_filter_with_gap():
    """Verify K-of-N persistence filter breaks on time gaps."""
    times = pd.date_range("2013-11-01 10:00:00", periods=20, freq="1min")
    scores = pd.Series(10.0, index=times) # High scores

    # Insert gap at index 12
    times_with_gap = list(times[:12]) + list(pd.date_range("2013-11-01 11:00:00", periods=8, freq="1min"))
    scores_with_gap = pd.Series(10.0, index=pd.to_datetime(times_with_gap))

    alarms = apply_causal_k_of_n_filter(scores_with_gap, threshold=5.0, k=10, n=15, max_gap_minutes=5.0)
    # Before gap, alarm is True at index 9 (10 consecutive)
    assert alarms.iloc[9] == True
    # Immediately after 1-hour gap at index 12, alarm MUST be False because causal history is broken
    assert alarms.iloc[12] == False


def test_ahu10_clean_split_embargo_isolation():
    """Verify that split_clean_ahu removes fault experiments and embargo from AHU-10."""
    exp_path = Path("data/raw/csiro_fault_experiments.parquet")
    df_exp = pd.read_parquet(exp_path)

    df_ahu10 = pd.read_parquet("data/raw/csiro_ahu10.parquet")
    df_slice = df_ahu10.loc["2013-10-28 00:00:00":"2013-11-12 23:59:59"].copy()

    splitter = CSIROTemporalSplitter(embargo_minutes=60)
    splits = split_clean_ahu(splitter, df_slice, df_exp, ahu_id=10)

    train_indices = splits["train"]["clean_operating_indices"]
    val_indices = splits["val"]["clean_operating_indices"]

    # Ensure train and val have valid clean points
    assert len(train_indices) > 1000
    assert len(val_indices) > 500

    # Ensure zero overlap
    assert len(set(train_indices).intersection(set(val_indices))) == 0


def test_stage8b_manifest_integrity():
    """Verify that stage8b_dynamic_results.json exists, is valid, and reproduces key findings."""
    manifest_path = Path("research/runs/stage8b_dynamic_results.json")
    assert manifest_path.exists(), "Manifest research/runs/stage8b_dynamic_results.json must exist"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert "hypotheses_verdicts" in manifest
    assert "ahu9" in manifest
    assert "ahu10" in manifest

    # Check that M1 baseline exists on both
    assert "M1_T_ONLY_STATIC" in manifest["ahu9"]["methods"]
    assert "M1_T_ONLY_STATIC" in manifest["ahu10"]["methods"]
    assert manifest["ahu9"]["methods"]["M1_T_ONLY_STATIC"]["row_events"]["detected"] == 6
    assert manifest["ahu10"]["methods"]["M1_T_ONLY_STATIC"]["row_events"]["detected"] == 6

    # Verify that M4 dynamic model was evaluated on both
    assert "M4_U_DYN_EXO" in manifest["ahu9"]["methods"]
    assert "M4_U_DYN_EXO" in manifest["ahu10"]["methods"]
    assert "M4_U_DYN_EXO_STRICT" in manifest["ahu9"]["methods"]
    assert "M4_U_DYN_EXO_STRICT" in manifest["ahu10"]["methods"]

    # Verify reconciled verdicts
    assert manifest["hypotheses_verdicts"]["H8B.3_regime_specific_fusion"]["status"] == "REFUTED_FAR_BUDGET_EXCEEDED"
    assert manifest["hypotheses_verdicts"]["H8B.1_dynamic_vs_static"]["status"] == "REFUTED_VALIDATION_OVERFITTING"


def test_rbc_nesbitt_external_manifest():
    """Verify that rbc_nesbitt_fdd_results.json exists, is valid, and reproduces key findings."""
    manifest_path = Path("research/runs/rbc_nesbitt_fdd_results.json")
    assert manifest_path.exists(), "Manifest research/runs/rbc_nesbitt_fdd_results.json must exist"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert "gate_0_audit" in manifest
    assert manifest["gate_0_audit"]["gate_0_verdict"] == "PASSED_WITH_QUALIFICATIONS"
    assert manifest["gate_0_audit"]["total_columns"] == 540

    # Verify M2 (U_ONLY_STRICT_3_5) detected 3 of 4 physical episodes with FAR <= 5%
    m2 = manifest["methods_summary"]["M2_U_ONLY_STRICT_3_5"]
    assert m2["detected_physical_episodes"] == 3
    assert m2["total_physical_episodes"] == 4
    assert m2["pointwise_far"] <= 0.05
    assert m2["far_budget_met"] == True

    # Verify M1 (T_ONLY) detected 0 episodes due to closed-loop override
    m1 = manifest["methods_summary"]["M1_T_ONLY"]
    assert m1["detected_physical_episodes"] == 0

    # Verify signal lineage CSV exists
    lineage_path = Path("research/tables/rbc_nesbitt_signal_lineage.csv")
    assert lineage_path.exists()
    df_lineage = pd.read_csv(lineage_path)
    assert len(df_lineage) > 20
    assert "physical_channel" in df_lineage.columns


def test_rbc_nesbitt_reconciled_manifest():
    """Verify that Stage 8B-R reconciled manifest and predictions exist and are valid."""
    manifest_path = Path("research/runs/rbc_nesbitt_reconciled_manifest.json")
    assert manifest_path.exists(), "Reconciled manifest must exist"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["manifest_version"] in [
        "2.0-reconciled",
        "2.1-scientific-integrity-reconciled",
        "2.2-scientific-evidence-reconciled",
        "2.3-scientific-evidence-reconciled"
    ]
    assert manifest["dataset_metadata"]["columns_total"] == 540

    res_all = manifest["reconciled_results"]["evaluation_all_4_scenarios"]
    res_val = manifest["reconciled_results"]["evaluation_valid_3_scenarios_excluding_unresolved"]

    # Verify M3 strict 4.0
    m3_strict = res_all["M3_T_PLUS_U_STRICT_4_0"]
    assert m3_strict["detected_physical_episodes"] == 3
    assert m3_strict["total_physical_episodes"] == 4
    assert m3_strict["pointwise_far"] == 0.025
    assert m3_strict["far_budget_met"] == True

    # Verify M2 strict 3.5
    m2_strict = res_all["M2_U_ONLY_STRICT_3_5"]
    assert m2_strict["detected_physical_episodes"] == 3
    assert m2_strict["total_physical_episodes"] == 4
    assert m2_strict["pointwise_far"] == 0.0441
    assert m2_strict["far_budget_met"] == True

    # Verify M1 T_ONLY is 0 recall
    m1 = res_all["M1_T_ONLY"]
    assert m1["detected_physical_episodes"] == 0

    # Verify N=3 metrics
    m3_val = res_val["M3_T_PLUS_U_STRICT_4_0"]
    assert m3_val["detected_physical_episodes"] == 2
    assert m3_val["total_physical_episodes"] == 3
    assert m3_val["pointwise_far"] == 0.0156

    # Verify pointwise predictions CSV
    pt_csv = Path("research/runs/rbc_nesbitt_pointwise_predictions.csv")
    assert pt_csv.exists()
    df_pt = pd.read_csv(pt_csv)
    assert len(df_pt) == 1152 # 4 test days * 288 points
    assert "z_m1_t_only" in df_pt.columns
    assert "z_m2_u_only" in df_pt.columns
    assert "z_m3_fusion" in df_pt.columns
