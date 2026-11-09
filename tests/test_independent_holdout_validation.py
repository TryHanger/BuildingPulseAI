import json
from pathlib import Path
import pandas as pd
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT_DIR / "research" / "runs" / "rbc_nesbitt_independent_validation_manifest.json"
POINTWISE_CSV = ROOT_DIR / "research" / "runs" / "rbc_nesbitt_independent_pointwise_predictions.csv"
HOLDOUT_DIR = ROOT_DIR / "data" / "raw" / "rbc_nesbitt" / "holdout"

def test_manifest_existence_and_strict_json():
    assert MANIFEST_PATH.exists(), "Holdout manifest must exist"
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["protocol_status"] in [
        "PRE_REGISTERED_INDEPENDENT_VALIDATION",
        "POST_HOC_FORENSIC_REANALYSIS_TEST_EXPOSED"
    ]
    assert "evaluation_slices" in data
    assert "summer_in_domain" in data["evaluation_slices"]
    assert "winter_out_of_domain" in data["evaluation_slices"]
    assert "all_seasons_combined" in data["evaluation_slices"]

def test_development_holdout_disjointness():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    prov = data["holdout_data_provenance"]
    dev_days = set(prov["development_known_days"])
    holdout_faults = set(prov["holdout_fault_days"])
    holdout_baselines = set(prov["holdout_baseline_days"])

    # Assert strict zero overlap
    overlap_faults = dev_days.intersection(holdout_faults)
    overlap_baselines = dev_days.intersection(holdout_baselines)
    assert len(overlap_faults) == 0, f"Holdout faults must have 0 overlap with dev: {overlap_faults}"
    assert len(overlap_baselines) == 0, f"Holdout baselines must have 0 overlap with dev: {overlap_baselines}"

def test_pointwise_predictions_integrity():
    assert POINTWISE_CSV.exists(), "Pointwise predictions CSV must exist"
    df = pd.read_csv(POINTWISE_CSV)
    assert len(df) == 3744, "Expected exactly 3744 pointwise records (13 files * 288 steps)"
    assert set(df["domain_status"].unique()).issubset({"IN_DOMAIN", "OOD", "INVALID_INPUT"})
    assert df["timestamp"].notna().all()

def test_domain_guard_seasonal_ood_protection():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    win_m2_dg = data["evaluation_slices"]["winter_out_of_domain"]["M2_Control_Exp350_DomainGuard"]
    # In winter, outdoor temp drops to 0-10C while summer model envelope is >20C
    # DomainGuard must flag all winter normal points as OOD, resulting in 0% coverage and 0 false alarms
    assert win_m2_dg["normal_coverage_pct"] == 0.0
    assert win_m2_dg["false_alarm_points"] == 0
