import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)

def test_get_adaptation_datasets():
    response = client.get("/api/adaptation/datasets")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    ahu9 = next((d for d in data if d["target_id"] == "CSIRO_AHU9"), None)
    assert ahu9 is not None
    assert ahu9["source_kind"] == "REAL_FIELD_BMS"
    assert ahu9["status"] == "LOCALLY_EVALUATED"

def test_get_adaptation_models():
    response = client.get("/api/adaptation/models?target=CSIRO_AHU9")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 5
    codes = [m["strategy_code"] for m in data]
    assert "Z0" in codes
    assert "C1" in codes
    assert "C2" in codes
    assert "A1" in codes
    assert "L1" in codes
    assert "L2" in codes

def test_get_adaptation_summary():
    response = client.get("/api/adaptation/summary?target=CSIRO_AHU9")
    assert response.status_code == 200
    data = response.json()
    assert data["target_domain"] == "CSIRO_AHU9"
    assert "models_comparison" in data
    assert len(data["models_comparison"]) >= 6
    assert data["mae_reduction_pct"] > 50.0  # Must exceed 50% target
    assert data["best_adapted_model_id"] == "csiro-ahu9-affine-v1"

def test_get_adaptation_predictions():
    response = client.get("/api/adaptation/predictions?target=CSIRO_AHU9&model_id=csiro-ahu9-affine-v1&max_points=200")
    assert response.status_code == 200
    data = response.json()
    assert data["target_domain"] == "CSIRO_AHU9"
    assert data["model_id"] == "csiro-ahu9-affine-v1"
    assert "points" in data
    assert len(data["points"]) > 0
    p0 = data["points"][0]
    assert "datetime" in p0
    assert "actual_sa_temp" in p0
    assert "source_pred_sa_temp" in p0
    assert "adapted_pred_sa_temp" in p0
    assert "source_residual" in p0
    assert "adapted_residual" in p0
    assert "is_fault" in p0

def test_get_adaptation_runs():
    response = client.get("/api/adaptation/runs/stage6_train_csiro_adaptation")
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data or "evaluation_name" in data
