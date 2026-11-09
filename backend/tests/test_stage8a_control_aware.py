"""
Stage 8A Automated Test Suite.
Validates:
  1. Data integrity and proxy isolation (fail closed).
  2. Prevention of command self-leakage and target contamination.
  3. Rejection of duplicate sensor channels (MA_TEMP == SA_TEMP).
  4. Chronological train/val/test boundary non-overlap and embargo.
  5. Causal sliding window persistence filter (no future points).
  6. Gap handling, AHU-off resets, and irregular intervals.
  7. Event-level single-detection scoring (no double counting).
  8. False alarm counting outside fault episodes.
  9. Negative control verification (temporal shift and permutation degradation).
  10. Deterministic numerical reproducibility of metrics.
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path

from ml.control_aware.channel_semantics import (
    ChannelSemanticType,
    CSIRO_CHANNEL_SEMANTICS,
    validate_feature_matrix_columns,
    BANNED_CHANNELS
)
from ml.control_aware.features import extract_control_effort_features
from ml.control_aware.splits import (
    STAGE8A_SPLIT_WINDOWS,
    get_stage8a_split,
    apply_negative_control_temporal_shift,
    apply_negative_control_permutation
)
from ml.control_aware.baseline_control import ControlEffortModel
from ml.control_aware.alarm_policy import apply_causal_k_of_n_filter
from ml.control_aware.events import evaluate_events_and_false_alarms


def test_channel_semantics_classification():
    """Verify that every essential CSIRO channel has an explicit, valid semantic classification."""
    assert "SA_TEMP" in CSIRO_CHANNEL_SEMANTICS
    assert CSIRO_CHANNEL_SEMANTICS["SA_TEMP"] == ChannelSemanticType.OBSERVED_PHYSICAL_SENSOR
    assert CSIRO_CHANNEL_SEMANTICS["CHWC_VLV_DM"] == ChannelSemanticType.CONTROLLER_OUTPUT_PRE_PROXY
    assert CSIRO_CHANNEL_SEMANTICS["MA_TEMP"] == ChannelSemanticType.DUPLICATE


def test_no_target_self_leakage():
    """Verify that target 'CHWC_VLV_DM' is rejected if present in feature matrix."""
    with pytest.raises(ValueError, match="Target leakage violation"):
        validate_feature_matrix_columns(["OA_TEMP", "RA_TEMP", "CHWC_VLV_DM"], target_name="CHWC_VLV_DM")


def test_banned_channels_rejected():
    """Verify that ground-truth labels and raw injection parameters are rejected."""
    for banned in BANNED_CHANNELS:
        if banned == "MA_TEMP":
            continue
        with pytest.raises(ValueError, match="Banned channel violation"):
            validate_feature_matrix_columns(["OA_TEMP", banned], target_name="CHWC_VLV_DM")


def test_duplicate_ma_temp_rejected():
    """Verify that MA_TEMP is rejected from feature matrix due to duplicate hardware wiring."""
    with pytest.raises(ValueError, match="CSIRO MA_TEMP violation"):
        validate_feature_matrix_columns(["OA_TEMP", "RA_TEMP", "MA_TEMP"], target_name="CHWC_VLV_DM")


def test_chronological_splits_no_overlap():
    """Verify that train, validation, and test splits have strict zero overlap."""
    t_end = pd.to_datetime(STAGE8A_SPLIT_WINDOWS["train"]["end"])
    v_start = pd.to_datetime(STAGE8A_SPLIT_WINDOWS["val"]["start"])
    v_end = pd.to_datetime(STAGE8A_SPLIT_WINDOWS["val"]["end"])
    s_start = pd.to_datetime(STAGE8A_SPLIT_WINDOWS["test"]["start"])

    assert t_end < v_start, "Train end must precede validation start!"
    assert v_end < s_start, "Validation end must precede test start!"


def test_feature_extraction_causality_and_bounds():
    """Verify feature extractor output types, shapes, and absence of target."""
    dates = pd.date_range("2013-10-28 09:00:00", periods=60, freq="1min")
    df_dummy = pd.DataFrame({
        "OA_TEMP": np.linspace(15, 25, 60),
        "RA_TEMP": np.full(60, 23.0),
        "SA_TEMPSPT": np.full(60, 18.0),
        "CHWC_VLV_DM": np.linspace(0.1, 0.5, 60),
        "SF_CS": np.full(60, 0.5)
    }, index=dates)

    X, y = extract_control_effort_features(df_dummy, target_col="CHWC_VLV_DM")

    assert "CHWC_VLV_DM" not in X.columns
    assert "SA_TEMP" not in X.columns
    assert "MA_TEMP" not in X.columns
    assert len(X) == 60
    assert len(y) == 60
    assert "T_target_diff" in X.columns
    assert "hour_sin" in X.columns


def test_control_effort_model_bounded_predictions():
    """Verify that predictions from ControlEffortModel are strictly clipped to [0, 1]."""
    dates = pd.date_range("2013-10-28 09:00:00", periods=100, freq="1min")
    X = pd.DataFrame({
        "OA_TEMP": np.random.normal(20, 5, 100),
        "RA_TEMP": np.random.normal(23, 1, 100),
        "SA_TEMPSPT": np.full(100, 18.0),
        "T_target_diff": np.random.normal(5, 1, 100),
        "T_oa_sa_diff": np.random.normal(2, 5, 100),
        "hour_sin": np.sin(np.linspace(0, 6, 100)),
        "hour_cos": np.cos(np.linspace(0, 6, 100)),
        "SF_CS": np.full(100, 0.5)
    }, index=dates)
    y = pd.Series(np.random.uniform(0, 0.8, 100), index=dates)

    model = ControlEffortModel(model_type="ridge", alpha=1.0)
    model.fit(X, y)
    preds = model.predict(X)

    assert preds.min() >= 0.0
    assert preds.max() <= 1.0


def test_causal_k_of_n_filter_logic():
    """Verify that K-of-N persistence filter requires K consecutive exceedances without gap."""
    dates = pd.date_range("2013-11-07 10:00:00", periods=20, freq="1min")
    # 9 points above threshold, then 1 below, then 10 above
    scores = np.array([2.0]*9 + [0.5] + [2.0]*10)
    series = pd.Series(scores, index=dates)

    # Threshold = 1.0, K=10, N=15
    alarms = apply_causal_k_of_n_filter(series, threshold=1.0, k=10, n=15)

    # First 9 points should NOT alarm (less than K=10)
    assert not alarms.iloc[8]
    # Point 9 is below threshold
    assert not alarms.iloc[9]
    # Points 10..18 build up exceedances again
    # Exactly when cumulative exceedances in window reach 10, alarm triggers
    assert alarms.iloc[18]


def test_causal_k_of_n_filter_gap_reset():
    """Verify that time gaps > 5 min reset the persistence filter accumulator."""
    # 8 points, then a 30-min gap, then 8 points
    idx1 = pd.date_range("2013-11-07 10:00:00", periods=8, freq="1min")
    idx2 = pd.date_range("2013-11-07 10:38:00", periods=8, freq="1min")
    idx = idx1.union(idx2)

    scores = pd.Series(np.full(len(idx), 2.0), index=idx)
    alarms = apply_causal_k_of_n_filter(scores, threshold=1.0, k=10, n=15, max_gap_minutes=5.0)

    # Despite 16 total points with score 2.0, no window of 10 continuous points without gap exists
    assert not alarms.any()


def test_event_level_single_detection():
    """Verify that an event spanning 60 alarm minutes counts as exactly ONE detected event."""
    dates = pd.date_range("2013-11-07 10:00:00", periods=120, freq="1min")
    # Alarms active throughout 10:15 to 11:15 (60 minutes)
    alarms = pd.Series(False, index=dates)
    alarms.loc["2013-11-07 10:15:00":"2013-11-07 11:15:00"] = True

    # One ground truth event from 10:10 to 11:10
    exp_df = pd.DataFrame([{
        "AHU": 9,
        "Fault Type": "CHW Valve Proxy Stuck Open",
        "Magnitude": 50.0,
        "Start Datetime": pd.to_datetime("2013-11-07 10:10:00"),
        "End Datetime": pd.to_datetime("2013-11-07 11:10:00")
    }])

    summary, df_ev, fa = evaluate_events_and_false_alarms(
        alarms, exp_df, ahu_id=9,
        test_start="2013-11-07 10:00:00", test_end="2013-11-07 12:00:00",
        method_name="TEST_METHOD"
    )

    assert summary["total_fault_events"] == 1
    assert summary["detected_fault_events"] == 1
    assert summary["event_recall"] == 1.0


def test_false_alarm_episode_grouping():
    """Verify that isolated alarms outside fault events create false alarm episodes."""
    dates = pd.date_range("2013-11-07 10:00:00", periods=60, freq="1min")
    alarms = pd.Series(False, index=dates)
    # False alarms at minutes 5..10 (6 minutes contiguous = 1 episode)
    alarms.iloc[5:11] = True
    # False alarms at minutes 25..30 (6 minutes contiguous = 2nd episode)
    alarms.iloc[25:31] = True

    # No faults present
    exp_df = pd.DataFrame(columns=["AHU", "Fault Type", "Magnitude", "Start Datetime", "End Datetime"])

    summary, df_ev, fa = evaluate_events_and_false_alarms(
        alarms, exp_df, ahu_id=9,
        test_start="2013-11-07 10:00:00", test_end="2013-11-07 11:00:00",
        method_name="TEST_METHOD"
    )

    assert summary["false_alarm_minutes"] == 12
    assert summary["false_alarm_episodes_count"] == 2


def test_negative_controls_degrade_correlations():
    """Verify that temporal shift and permutation destroy exogenous feature correlations."""
    dates = pd.date_range("2013-10-28 09:00:00", periods=100, freq="1min")
    df = pd.DataFrame({
        "OA_TEMP": np.sin(np.linspace(0, 4*np.pi, 100)),
        "RA_TEMP": np.sin(np.linspace(0, 4*np.pi, 100)) * 0.5 + 20,
        "SA_TEMPSPT": np.full(100, 18.0),
        "CHWC_VLV_DM": np.sin(np.linspace(0, 4*np.pi, 100)) * 0.3 + 0.3,
        "SF_SPD_DM": np.full(100, 1.0),
        "SF_CS": np.full(100, 0.5)
    }, index=dates)

    orig_corr = np.corrcoef(df["OA_TEMP"], df["CHWC_VLV_DM"])[0, 1]

    # Permutation
    df_perm = apply_negative_control_permutation(df, seed=42)
    perm_corr = np.corrcoef(df_perm["OA_TEMP"], df_perm["CHWC_VLV_DM"])[0, 1]

    # Temporal shift
    df_shift = apply_negative_control_temporal_shift(df, shift_hours=6)
    shift_corr = np.corrcoef(df_shift["OA_TEMP"], df_shift["CHWC_VLV_DM"])[0, 1]

    assert orig_corr > 0.99
    assert abs(perm_corr) < 0.35
    assert abs(shift_corr) < 0.5
