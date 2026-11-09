import pytest
from httpx import AsyncClient, ASGITransport
import pandas as pd
import numpy as np

from backend.app.main import app
from ml.virtual_sensor.features import fahrenheit_to_celsius, BASIC_FEATURE_COLUMNS, FeatureTransformer
from ml.virtual_sensor.splits import BlockTemporalSplit
from ml.virtual_sensor.scoring import apply_persistence_filter, PersistenceFilterConfig

@pytest.mark.asyncio
async def test_ml_list_models():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/ml/models")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        model_ids = [m["model_id"] for m in data]
        assert "vs-sa-temp-v1" in model_ids

@pytest.mark.asyncio
async def test_ml_get_model_metadata():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Valid model
        resp = await client.get("/api/ml/models/vs-sa-temp-v1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["model_id"] == "vs-sa-temp-v1"
        assert data["target"] == "SA_TEMP"
        assert data["target_unit"] == "degC"
        assert "MA_TEMP" in data["features"]
        assert "SA_TEMP" not in data["features"]  # Leakage guard!
        assert "thresholds" in data
        assert data["thresholds"]["three_sigma"] > 0

        # Non-existent model
        resp_404 = await client.get("/api/ml/models/non_existent_model_xyz")
        assert resp_404.status_code == 404

@pytest.mark.asyncio
async def test_ml_predictions_and_detect():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Get scenarios first
        sc_resp = await client.get("/api/scenarios")
        assert sc_resp.status_code == 200
        sc_data = sc_resp.json()
        scenarios = sc_data.get("items", [])
        if not scenarios:
            pytest.skip("No scenarios available in test db")

        sc_id = scenarios[0]["id"]

        # Predictions endpoint
        pred_resp = await client.get(f"/api/ml/predictions?scenario_id={sc_id}&model_id=vs-sa-temp-v1&max_points=50")
        assert pred_resp.status_code == 200
        pdata = pred_resp.json()
        assert pdata["scenario_id"] == sc_id
        assert pdata["model_id"] == "vs-sa-temp-v1"
        assert len(pdata["points"]) > 0
        first_pt = pdata["points"][0]
        assert "predicted" in first_pt
        assert "residual_abs" in first_pt

        # Detect endpoint
        det_resp = await client.post("/api/ml/detect", json={
            "scenario_id": sc_id,
            "model_id": "vs-sa-temp-v1",
            "threshold_policy": "three_sigma"
        })
        assert det_resp.status_code == 200
        events = det_resp.json()
        assert isinstance(events, list)
        for ev in events:
            assert ev["conclusion_type"] == "VIRTUAL_SENSOR_RESIDUAL"
            assert "evidence_json" in ev

def test_unit_conversion():
    # 32°F == 0°C, 212°F == 100°C, 68°F == 20°C
    assert abs(fahrenheit_to_celsius(32.0) - 0.0) < 1e-4
    assert abs(fahrenheit_to_celsius(212.0) - 100.0) < 1e-4
    assert abs(fahrenheit_to_celsius(68.0) - 20.0) < 1e-4

def test_target_leakage_prohibition():
    assert "SA_TEMP" not in BASIC_FEATURE_COLUMNS
    for feat in BASIC_FEATURE_COLUMNS:
        assert not feat.startswith("SA_TEMP_")

def test_block_temporal_split_disjointness():
    dummy_df = pd.DataFrame({"val": range(20160)})
    splitter = BlockTemporalSplit(train_days=9, val_days=2)
    df_train, df_val, df_test = splitter.split(dummy_df)

    # Check non-empty
    assert len(df_train) == 9 * 1440
    assert len(df_val) == 2 * 1440
    assert len(df_test) == 20160 - (11 * 1440)

    # Check exact indices disjointness
    train_idx = set(df_train.index)
    val_idx = set(df_val.index)
    test_idx = set(df_test.index)

    assert len(train_idx.intersection(val_idx)) == 0
    assert len(train_idx.intersection(test_idx)) == 0
    assert len(val_idx.intersection(test_idx)) == 0

def test_causal_persistence_filter():
    # Residuals exceeding threshold at steps 10..24 (15 points)
    res = pd.Series([0.1]*10 + [2.5]*15 + [0.1]*10)
    op = pd.Series([True]*35)
    config = PersistenceFilterConfig(k=10, n=15)

    alarms = apply_persistence_filter(res, threshold=1.0, operating_mask=op, config=config)

    # Alarm should turn on ONLY after at least 10 points (step 19 onwards), not before!
    assert not alarms.iloc[9]
    assert not alarms.iloc[18]
    assert alarms.iloc[19]  # 10th consecutive point
    assert alarms.iloc[24]
    # When dropping back below threshold, alarm drops after window clears
