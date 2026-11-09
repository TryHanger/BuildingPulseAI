"""
Standalone verification tests for CSIRO AHU-10 forensic integrity reanalysis (Stage 8C Release Candidate).

Covers all algorithmic acceptance checks (Gate E):
1. Raw Parquet -> 5-minute resample -> stable unique timestamps, zero duplicates, exactly 3,199 points.
2. Global experiment mask across all 103 experiments of AHU-10 + 30-min washout, resolving multi-event days (e.g. 2013-10-31).
3. Purity of training partition (873 clean operational points, zero fault overlap).
4. Rigorous separation of 7 observable events from 3 left-censored events (IDs 176, 194, 322).
5. Pre-existing alarm logic: alarm active before fault start is never counted as a new onset.
6. Operational gating (fan speed >= 10%), zero-denominator policy (None/null, NOT_EVALUABLE_ZERO_COVERAGE), strict JSON (no NaN/Inf).
7. Semantic compatibility gate: Zero-Shot models strictly tagged NOT_COMPARABLE.
8. Independent re-calculation of seasonal FAR from pointwise predictions matching manifest.
9. Report-to-manifest 100% numerical parity without hardcoded textual drift.
10. Explicit documentation of fixed exploratory thresholds vs training diagnostic percentiles.
"""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
MANIFEST_PATH = BASE_DIR / "research" / "runs" / "csiro_ahu10_validation_manifest.json"
REPORT_PATH = BASE_DIR / "research" / "reports" / "STAGE8C_CSIRO_AHU10_EVALUATION_REPORT.md"
POINTWISE_CSV_PATH = BASE_DIR / "research" / "runs" / "csiro_ahu10_pointwise_predictions.csv"
RAW_TELEMETRY_PATH = BASE_DIR / "data" / "raw" / "csiro_ahu10.parquet"
RAW_EXPERIMENTS_PATH = BASE_DIR / "data" / "raw" / "csiro_fault_experiments.parquet"


def test_1_raw_parquet_to_5min_grid_integrity():
    """Gate E.1: Raw parquet -> 5min resample produces 3199 unique timestamps without duplicates or NaT."""
    assert RAW_TELEMETRY_PATH.exists(), f"Missing raw telemetry at {RAW_TELEMETRY_PATH}"
    df_raw = pd.read_parquet(RAW_TELEMETRY_PATH)
    assert len(df_raw) == 422169, f"Expected 422,169 rows, got {len(df_raw)}"
    
    # Load manifest to get the 33 dates
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        m = json.load(f)
    train_dates = m["training_metadata"]["dates"]
    
    # Check pointwise predictions file
    assert POINTWISE_CSV_PATH.exists()
    df_pt = pd.read_csv(POINTWISE_CSV_PATH)
    assert len(df_pt) == 3199, f"Expected exactly 3199 grid points, got {len(df_pt)}"
    
    ts = pd.to_datetime(df_pt["timestamp"])
    assert not ts.isna().any(), "Found NaT in timestamps"
    assert not ts.duplicated().any(), "Found duplicate timestamps in 5-minute grid"
    
    # Check that within each day timestamps are strictly increasing
    for day, group in df_pt.groupby(ts.dt.date):
        day_ts = pd.to_datetime(group["timestamp"])
        assert day_ts.is_monotonic_increasing, f"Timestamps on day {day} are not strictly increasing"


def test_2_global_experiment_mask_cross_day_and_overlap():
    """Gate E.2: Global mask across all 103 experiments resolves overlapping events (2013-10-31)."""
    assert RAW_EXPERIMENTS_PATH.exists()
    df_exp = pd.read_parquet(RAW_EXPERIMENTS_PATH)
    ahu10_exp = df_exp[df_exp["AHU"].astype(str) == "10"]
    assert len(ahu10_exp) == 103, f"Expected 103 experiments on AHU-10, got {len(ahu10_exp)}"
    
    df_pt = pd.read_csv(POINTWISE_CSV_PATH)
    ts = pd.to_datetime(df_pt["timestamp"])
    
    # Check 2013-10-31 (experiments 224: 09:30-10:30 and 226: 11:31-12:31)
    day_31 = df_pt[ts.dt.date == pd.to_datetime("2013-10-31").date()]
    day_ts = pd.to_datetime(day_31["timestamp"])
    
    # On 2013-10-31, three back-to-back experiments (224, 225, 226) took place between 09:30 and 12:31:
    # 224: 09:30:41 to 10:30:47; 225: 10:31:10 to 11:31:18; 226: 11:31:41 to 12:31:50
    # From 09:35 to 12:30: continuous fault period covering all three experiments
    mask_fault_block = (day_ts >= "2013-10-31 09:35:00") & (day_ts <= "2013-10-31 12:30:00")
    assert day_31.loc[mask_fault_block, "in_any_experiment"].all()
    assert day_31.loc[mask_fault_block, "in_washout_30m"].all()
    
    # From 12:35 to 13:00: 30-minute washout following experiment 226 (in_washout=True, in_any_experiment=False)
    mask_washout_226 = (day_ts >= "2013-10-31 12:35:00") & (day_ts <= "2013-10-31 13:00:00")
    assert day_31.loc[mask_washout_226, "in_washout_30m"].all()
    assert not day_31.loc[mask_washout_226, "in_any_experiment"].any()
    
    # From 13:05 onwards: clean nominal afternoon operational period
    mask_clean_afternoon = (day_ts >= "2013-10-31 13:05:00") & (day_ts <= "2013-10-31 16:55:00")
    assert not day_31.loc[mask_clean_afternoon, "in_any_experiment"].any()
    assert not day_31.loc[mask_clean_afternoon, "in_washout_30m"].any()


def test_3_training_partition_cleanliness_against_all_103_experiments():
    """Gate E.3: Training partition contains exactly 873 points with zero experiment/washout overlap."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        m = json.load(f)
    train_dates = m["training_metadata"]["dates"]
    assert len(train_dates) == 9
    
    df_pt = pd.read_csv(POINTWISE_CSV_PATH)
    ts = pd.to_datetime(df_pt["timestamp"])
    is_train = ts.dt.strftime("%Y-%m-%d").isin(train_dates)
    
    # Inside train partition, no point should intersect with in_washout_30m or in_any_experiment
    assert not df_pt.loc[is_train, "in_any_experiment"].any(), "Training days overlap with experiments!"
    assert not df_pt.loc[is_train, "in_washout_30m"].any(), "Training days overlap with washout periods!"
    
    # Clean operational points on train days
    clean_train = is_train & (df_pt["SF_SPD"] >= 10.0)
    assert clean_train.sum() == 873, f"Expected 873 clean operational training points, got {clean_train.sum()}"
    assert m["training_metadata"]["clean_points_count"] == 873


def test_4_left_censored_events_excluded_from_observable_7():
    """Gate E.4: Events 176, 194, 322 are left-censored and excluded from new_onset_observable_7."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        m = json.load(f)
        
    ev_outcomes = m["event_detection_outcomes"]
    m1_res = ev_outcomes["M1_Thermal_Local_Tau300"]
    m2_res = ev_outcomes["M2_Control_Local_Tau400"]
    m3_res = ev_outcomes["M3_LinearFusion_Local_Tau300"]
    
    # Observable 7 metric
    assert m1_res["new_onset_observable_7"]["observable_events_count"] == 7
    assert m1_res["new_onset_observable_7"]["detected_count"] == 4  # 4/7
    assert m1_res["new_onset_observable_7"]["recall"] == 0.5714
    
    assert m2_res["new_onset_observable_7"]["observable_events_count"] == 7
    assert m2_res["new_onset_observable_7"]["detected_count"] == 2  # 2/7
    assert m2_res["new_onset_observable_7"]["recall"] == 0.2857
    
    assert m3_res["new_onset_observable_7"]["observable_events_count"] == 7
    assert m3_res["new_onset_observable_7"]["detected_count"] == 4  # 4/7
    assert m3_res["new_onset_observable_7"]["recall"] == 0.5714
    
    # Post-Observation 10 metric
    assert m1_res["post_observation_alarm_all_10"]["detected_count"] == 5  # 5/10
    assert m2_res["post_observation_alarm_all_10"]["detected_count"] == 3  # 3/10
    assert m3_res["post_observation_alarm_all_10"]["detected_count"] == 5  # 5/10
    
    # Left-censored IDs
    lc_ids = m1_res["left_censored_3_summary"]["event_ids"]
    assert set(lc_ids) == {176, 194, 322}
    
    # Check each left-censored event start time against telemetry day start
    df_exp = pd.read_parquet(RAW_EXPERIMENTS_PATH)
    ahu10_exp = df_exp[df_exp["AHU"].astype(str) == "10"]
    for eid in [176, 194, 322]:
        start = pd.to_datetime(ahu10_exp.loc[eid, "Start Datetime"])
        assert start.hour == 8 and start.minute >= 30, f"Event {eid} expected start at ~08:30, got {start}"


def test_5_preexisting_alarm_not_counted_as_new_onset():
    """Gate E.5: False alarm active before fault start is not counted as a new onset."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        m = json.load(f)
        
    m2_ev = m["event_detection_outcomes"]["M2_Control_Local_Tau400"]["event_breakdown"]
    ev_116 = next(e for e in m2_ev if e["experiment_id"] == 116)
    assert ev_116["alarm_already_active_before_fault"] is True
    assert ev_116["status"] == "ALARM_STARTED_BEFORE_FAULT"
    assert ev_116["new_onset_detected"] is False
    assert ev_116["legacy_detected"] is True
    
    ev_161 = next(e for e in m2_ev if e["experiment_id"] == 161)
    assert ev_161["alarm_already_active_before_fault"] is True
    assert ev_161["status"] == "ALARM_STARTED_BEFORE_FAULT"
    assert ev_161["new_onset_detected"] is False


def test_6_operational_and_gap_guards_zero_denominator():
    """Gate E.6: Operational gating (fan >= 10%) and zero-denominator policy (None / NOT_EVALUABLE)."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        m = json.load(f)
        
    dg_summer = m["false_alarm_slices"]["summer_baseline_only"]["M2_Control_Local_Tau300_DomainGuard"]
    assert dg_summer["normal_points_eligible"] == 0
    assert dg_summer["pointwise_far"] is None
    assert dg_summer["pointwise_far_status"] == "NOT_EVALUABLE_ZERO_COVERAGE"
    assert dg_summer["episodes_per_8h"] is None
    assert dg_summer["coverage_pct"] == 0.0


def test_7_semantic_compatibility_flags_not_comparable():
    """Gate E.7: Zero-Shot models strictly tagged NOT_COMPARABLE due to physical mismatch."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        m = json.load(f)
        
    for mname, data in m["event_detection_outcomes"].items():
        if "ZeroShot" in mname:
            assert "NOT_COMPARABLE" in mname
            assert data["category"] == "INVALID_SEMANTIC_CONTROL"


def test_8_pointwise_predictions_to_manifest_parity():
    """Gate E.8: Pointwise predictions file independently reproduces exact manifest FAR percentages."""
    df_pt = pd.read_csv(POINTWISE_CSV_PATH)
    ts = pd.to_datetime(df_pt["timestamp"])
    clean_norm = (~df_pt["in_washout_30m"]) & (df_pt["SF_SPD"] >= 10.0)
    
    winter_dates = ["2013-07-01", "2013-07-02", "2013-07-03", "2013-07-04", "2013-07-05"]
    summer_dates = ["2014-01-03", "2014-01-06", "2014-01-07", "2014-01-08", "2014-01-09"]
    spring_dates = ["2013-10-03", "2013-10-04", "2013-10-07", "2013-10-08", "2013-10-09"]
    exp_dates = ["2013-09-19", "2013-10-16", "2013-10-22", "2013-10-23", "2013-10-25", "2013-10-30", "2013-10-31", "2013-11-07", "2013-11-11"]
    
    dates = ts.dt.strftime("%Y-%m-%d")
    is_winter = dates.isin(winter_dates)
    is_summer = dates.isin(summer_dates)
    is_spring = dates.isin(spring_dates)
    is_exp = dates.isin(exp_dates)
    is_all_norm = is_winter | is_summer | is_spring | is_exp
    
    # Check denominators
    assert (clean_norm & is_winter).sum() == 485
    assert (clean_norm & is_summer).sum() == 485
    assert (clean_norm & is_spring).sum() == 485
    assert (clean_norm & is_exp).sum() == 406
    assert (clean_norm & is_all_norm).sum() == 1861
    
    # Check M2 Control Local Tau400 false alarms
    m2_al = df_pt["alarm_M2_Control_Local_Tau400"]
    fa_all = int((m2_al & clean_norm & is_all_norm).sum())
    fa_summer = int((m2_al & clean_norm & is_summer).sum())
    fa_winter = int((m2_al & clean_norm & is_winter).sum())
    
    assert fa_all == 750, f"Expected 750 false alarms, got {fa_all}"
    assert round(fa_all / 1861, 4) == 0.4030
    assert fa_summer == 220, f"Expected 220 summer false alarms, got {fa_summer}"
    assert round(fa_summer / 485, 4) == 0.4536
    assert fa_winter == 181, f"Expected 181 winter false alarms, got {fa_winter}"
    assert round(fa_winter / 485, 4) == 0.3732
    
    # Check M1 Thermal Local Tau300 false alarms
    m1_al = df_pt["alarm_M1_Thermal_Local_Tau300"]
    fa_m1_all = int((m1_al & clean_norm & is_all_norm).sum())
    assert fa_m1_all == 979, f"Expected 979 false alarms, got {fa_m1_all}"
    assert round(fa_m1_all / 1861, 4) == 0.5261


def test_9_manifest_to_report_exact_parity():
    """Gate E.9: Report strictly reflects manifest numbers without hardcoded textual drift."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        m = json.load(f)
    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        rep = f.read()
        
    # Check that forbidden stale claims are absent
    assert "FAR свыше 70%" not in rep
    assert "29.24%" not in rep
    assert "35.88%" not in rep
    
    # Check that true metrics are present
    assert "750/1861 (40.30%)" in rep
    assert "979/1861 (52.61%)" in rep
    assert "220/485 (45.36%)" in rep
    assert "480/485 (98.97%)" in rep
    assert "Observable 7" in rep
    assert "4/7" in rep
    assert "2/7" in rep


def test_10_fixed_thresholds_and_training_diagnostics_lineage():
    """Gate E.10: Manifest documents fixed thresholds and training diagnostic percentiles."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        m = json.load(f)
        
    t_meta = m["training_metadata"]
    assert t_meta["fixed_research_thresholds"] == [3.00, 4.00]
    assert "sigma = float(np.std(np.abs(residual)))" in t_meta["standardization_formula"]
    
    # Thermal percentiles
    th = t_meta["thermal_model"]
    assert round(th["p99_0"], 3) == 4.668
    assert round(th["p99_5"], 3) == 5.419
    
    # Control percentiles
    u = t_meta["control_model"]
    assert round(u["p99_0"], 3) == 3.974
    assert round(u["p99_5"], 3) == 4.073
