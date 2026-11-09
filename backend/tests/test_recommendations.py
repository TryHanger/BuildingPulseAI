import pytest
import pandas as pd
import numpy as np
from ml.diagnostics.recommender import SensorRecommendationService, CandidateChannelScore

def test_recommender_basic_profile_recommends_chwc_vlv():
    res = SensorRecommendationService.recommend(
        scenario_id="sc_test",
        profile_id="BASIC",
        domain_status="VALIDATED",
        coverage_target=0.60
    )
    assert res.status == "RECOMMENDED"
    assert res.recommended_channel == "CHWC_VLV"
    assert len(res.candidate_scores) == 2
    top = res.candidate_scores[0]
    assert top.channel == "CHWC_VLV"
    assert top.delta_selective_risk_validation == 0.203
    assert top.decision == "RECOMMENDED"

def test_recommender_abstains_on_out_of_domain():
    res = SensorRecommendationService.recommend(
        scenario_id="sc_synthetic",
        profile_id="BASIC",
        domain_status="OUT_OF_DOMAIN",
        coverage_target=0.60
    )
    assert res.status == "OUT_OF_DOMAIN"
    assert res.recommended_channel is None
    assert any("Domain Guard" in lim for lim in res.limitations)

def test_recommender_profiles_exhausted_when_already_full():
    res = SensorRecommendationService.recommend(
        scenario_id="sc_test",
        profile_id="BASIC_PLUS_BOTH",
        domain_status="VALIDATED"
    )
    assert res.status == "PROFILES_EXHAUSTED"
    assert res.recommended_channel is None
    assert "уже включены" in res.reason

def test_recommender_fan_off_abstention():
    df_off = pd.DataFrame({"SF_SPD_DM": [0.0] * 15})
    res = SensorRecommendationService.recommend(
        scenario_id="sc_test",
        profile_id="BASIC",
        domain_status="VALIDATED",
        df_basic_window=df_off
    )
    assert res.status == "INSUFFICIENT_EXCITATION"
    assert res.recommended_channel is None

def test_recommendable_channels_list():
    items = SensorRecommendationService.get_recommendable_channels(profile_id="BASIC")
    assert len(items) == 2
    vlv = next(i for i in items if i["channel"] == "CHWC_VLV")
    assert vlv["is_recommendable"] is True
    assert vlv["already_present"] is False

    # For profile with valve:
    items_v = SensorRecommendationService.get_recommendable_channels(profile_id="BASIC_PLUS_VALVE")
    vlv_v = next(i for i in items_v if i["channel"] == "CHWC_VLV")
    assert vlv_v["is_recommendable"] is False
    assert vlv_v["already_present"] is True

def test_api_recommendable_channels():
    from fastapi.testclient import TestClient
    from backend.app.main import app
    client = TestClient(app)

    resp = client.get("/api/diagnostics/recommendable-channels?profile_id=BASIC")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2
    assert any(d["channel"] == "CHWC_VLV" for d in data)

def test_api_sensor_recommend_endpoint():
    from fastapi.testclient import TestClient
    from backend.app.main import app
    client = TestClient(app)

    payload = {
        "scenario_id": None,
        "profile_id": "BASIC",
        "coverage_target": 0.60
    }
    resp = client.post("/api/sensors/recommend", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "RECOMMENDED"
    assert data["recommended_channel"] == "CHWC_VLV"
    assert len(data["candidate_scores"]) == 2
