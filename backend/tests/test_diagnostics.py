import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db.session import SessionLocal
from backend.app.db.models import Scenario, Dataset
from ml.diagnostics.features import extract_diagnostic_features, BASIC_OBSERVATION_COLUMNS
import pandas as pd
import numpy as np

client = TestClient(app)

def test_diagnostics_summary_lbnl():
    db = SessionLocal()
    # Find any LBNL benchmark scenario
    sc = db.query(Scenario).join(Dataset).filter(Dataset.source_kind == "SIMULATED_BENCHMARK").first()
    db.close()
    assert sc is not None, "Need at least one LBNL benchmark scenario"

    response = client.get(f"/api/diagnostics/summary?scenario_id={sc.id}&model_id=vs-sa-temp-v2")
    assert response.status_code == 200
    data = response.json()
    assert data["scenario_id"] == sc.id
    assert data["model_domain_status"] == "VALIDATED_ON_LBNL"
    assert data["profile_id"] == "BASIC"
    assert "detection" in data
    assert "localization" in data
    assert "provenance" in data
    assert data["detection"]["status"] in ["NORMAL", "ANOMALY", "INSUFFICIENT_DATA"]

def test_domain_guard_on_synthetic_demo():
    db = SessionLocal()
    sc = db.query(Scenario).join(Dataset).filter(Dataset.source_kind == "SYNTHETIC_DEMO").first()
    db.close()
    if not sc:
        pytest.skip("Synthetic demo scenario not present in DB")

    # Default request without allow_unvalidated should trigger Domain Guard
    response = client.get(f"/api/diagnostics/summary?scenario_id={sc.id}&model_id=vs-sa-temp-v2&allow_unvalidated=false")
    assert response.status_code == 200
    data = response.json()
    assert data["model_domain_status"] == "OUT_OF_DOMAIN_UNVALIDATED"
    assert data["detection"]["status"] == "OUT_OF_DOMAIN"
    assert data["localization"]["status"] == "NOT_EVALUATED"
    assert "не валидирована" in (data["domain_warning"] or "")

    # When allow_unvalidated=true, exploratory mode is enabled with prominent warning
    resp_unval = client.get(f"/api/diagnostics/summary?scenario_id={sc.id}&model_id=vs-sa-temp-v2&allow_unvalidated=true")
    assert resp_unval.status_code == 200
    data_unval = resp_unval.json()
    assert data_unval["model_domain_status"] == "OUT_OF_DOMAIN_UNVALIDATED"
    assert data_unval["domain_warning"] is not None

def test_diagnostics_events_endpoint():
    db = SessionLocal()
    sc = db.query(Scenario).first()
    db.close()
    assert sc is not None

    response = client.get(f"/api/diagnostics/events?scenario_id={sc.id}")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_diagnostic_features_safety():
    # Verify no actual actuator feedback in Basic observations
    assert "CHWC_VLV" not in BASIC_OBSERVATION_COLUMNS
    assert "OA_DMPR" not in BASIC_OBSERVATION_COLUMNS

    # Synthetic test frame
    n = 30
    df = pd.DataFrame({
        "MA_TEMP": np.full(n, 20.0),
        "OA_TEMP": np.full(n, 10.0),
        "RA_TEMP": np.full(n, 22.0),
        "SA_TEMP": np.full(n, 14.0),
        "CHWC_VLV_DM": np.full(n, 0.2),
        "OA_DMPR_DM": np.full(n, 0.3),
        "SF_SPD_DM": np.full(n, 1.0),
        "SA_TEMPSPT": np.full(n, 13.0)
    })
    vs_pred = np.full(n, 13.8)
    op = pd.Series(True, index=df.index)

    feats = extract_diagnostic_features(df, vs_pred, op)
    assert len(feats) == n
    assert "res_sa_signed" in feats.columns
    assert "delta_t_chwc" in feats.columns
    # Check that residual is 14.0 - 13.8 = 0.2
    assert pytest.approx(feats["res_sa_signed"].iloc[-1], 0.01) == 0.2

def test_diagnostics_profiles_endpoint():
    response = client.get("/api/diagnostics/profiles")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 5
    profile_ids = [p["id"] for p in data]
    assert "BASIC" in profile_ids
    assert "BASIC_PLUS_VALVE" in profile_ids
    assert "FULL" in profile_ids

def test_diagnostics_summary_profile_switch():
    db = SessionLocal()
    sc = db.query(Scenario).join(Dataset).filter(Dataset.source_kind == "SIMULATED_BENCHMARK").first()
    db.close()
    assert sc is not None

    # Request BASIC profile
    res_b = client.get(f"/api/diagnostics/summary?scenario_id={sc.id}&profile_id=BASIC")
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert data_b["profile_id"] == "BASIC"
    assert data_b["profile_info"]["has_valve_feedback"] is False

    # Request BASIC_PLUS_VALVE profile
    res_v = client.get(f"/api/diagnostics/summary?scenario_id={sc.id}&profile_id=BASIC_PLUS_VALVE")
    assert res_v.status_code == 200
    data_v = res_v.json()
    assert data_v["profile_id"] == "BASIC_PLUS_VALVE"
    assert data_v["profile_info"]["has_valve_feedback"] is True

def test_stage4_experiments_summary_endpoint():
    response = client.get("/api/experiments/stage4/summary")
    assert response.status_code == 200
    data = response.json()
    assert "decision_layer_eval" in data
    assert "observability_eval" in data

