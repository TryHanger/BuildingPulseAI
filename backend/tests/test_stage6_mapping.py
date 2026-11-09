import json
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

from ml.virtual_sensor.features import fahrenheit_to_celsius, celsius_to_fahrenheit

def test_temperature_unit_conversions_deterministic():
    """Confirms exact deterministic Fahrenheit-to-Celsius arithmetic."""
    assert pytest.approx(fahrenheit_to_celsius(32.0), abs=1e-5) == 0.0
    assert pytest.approx(fahrenheit_to_celsius(212.0), abs=1e-5) == 100.0
    assert pytest.approx(fahrenheit_to_celsius(55.2), abs=1e-3) == 12.8888
    assert pytest.approx(celsius_to_fahrenheit(0.0), abs=1e-5) == 32.0
    assert pytest.approx(celsius_to_fahrenheit(100.0), abs=1e-5) == 212.0

def test_csiro_raw_data_integrity():
    """Validates existence, non-emptiness, and key columns of raw CSIRO telemetry."""
    raw_path = Path("data/raw/csiro_ahu9.parquet")
    if not raw_path.exists():
        pytest.skip("CSIRO raw parquet not available in test runner")

    df_raw = pd.read_parquet(raw_path)
    assert len(df_raw) > 10000
    expected_cols = [
        "AHU9ahuZoneTemp", "AHU9ahuCcValve", "AHU9ahuHcValve",
        "AHU9ahuMaTemp", "AHU9ahuOaDamper", "AHU9ahuOaTemp",
        "AHU9ahuRaDamper", "AHU9ahuRaTemp", "AHU9ahuSaTemp",
        "AHU9ahuSaTempSP", "AHU9ahuSaFanSpeed"
    ]
    for col in expected_cols:
        assert col in df_raw.columns, f"Expected column {col} missing in CSIRO parquet"

    # Verify audit finding: AHU9ahuMaTemp == AHU9ahuSaTemp
    diff = (df_raw["AHU9ahuMaTemp"] - df_raw["AHU9ahuSaTemp"]).dropna()
    assert (diff == 0.0).all(), "Audit fact violated: AHU9ahuMaTemp must be identical to AHU9ahuSaTemp in raw dataset"

def test_csiro_fault_experiments_structure():
    """Validates fault experiments metadata table."""
    exp_path = Path("data/raw/csiro_fault_experiments.parquet")
    if not exp_path.exists():
        pytest.skip("CSIRO fault experiments parquet not available in test runner")

    df_exp = pd.read_parquet(exp_path)
    assert len(df_exp) > 100
    assert "AHU" in df_exp.columns
    assert "Fault Type" in df_exp.columns
    assert "Start Datetime" in df_exp.columns
    assert "End Datetime" in df_exp.columns

    ahu9_exp = df_exp[df_exp["AHU"] == 9]
    assert len(ahu9_exp) >= 190, f"Expected >= 190 experiments for AHU9, found {len(ahu9_exp)}"

def test_reproduced_manifest_exists_and_valid():
    """Verifies that Stage 6 Gate 0 reproduction manifest is persisted and contains required keys."""
    manifest_path = Path("research/runs/stage6_zero_shot_reproduction.json")
    assert manifest_path.exists(), "stage6_zero_shot_reproduction.json must exist"

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["source_kind"] == "REAL_FIELD_BMS"
    assert data["ahu_target"] == "AHU9"
    assert "reproduced_metrics" in data
    rep = data["reproduced_metrics"]
    assert "overall_operating" in rep
    assert "normal_healthy_operating_points" in rep
    assert "fault_injected_operating_points" in rep

    overall = rep["overall_operating"]
    assert overall["count"] == 5735
    assert pytest.approx(overall["mae_degC"], abs=0.01) == 4.47
    assert pytest.approx(overall["rmse_degC"], abs=0.01) == 4.85
    assert pytest.approx(overall["mean_bias_degC"], abs=0.01) == 4.46
    assert overall["threshold_breach_rate"] > 0.98
