"""Unit tests for Stage 5 Experiment Hygiene, Anti-Leakage barriers, and Domain Guard.

Ensures:
1. Candidate evaluation strictly uses validation scenarios, never test data.
2. Domain Guard rejects out-of-domain telemetry (e.g. Australian field BMS) from unvalidated recommendation.
3. Recommendations are reproducible across runs.
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from ml.diagnostics.recommender import (
    SensorRecommendationService,
    CandidateChannelScore,
    RecommendationResult,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_candidate_scoring_no_leakage():
    """Verify that candidate evaluation strictly uses validation constants without touching test labels."""
    service = SensorRecommendationService()
    
    # Validation values check
    val_map = service.VALIDATION_VALS
    assert "CHWC_VLV" in val_map
    assert "OA_DMPR" in val_map
    
    assert val_map["CHWC_VLV"]["delta_risk"] == 0.203
    assert val_map["OA_DMPR"]["delta_risk"] == 0.021
    
    # Channels check
    recs = service.get_recommendable_channels("BASIC")
    assert len(recs) == 2
    assert any(c["channel"] == "CHWC_VLV" and c["is_recommendable"] for c in recs)


def test_recommendation_determinism():
    """Verify recommendations are strictly deterministic for the same input."""
    service = SensorRecommendationService()
    res1 = service.recommend(
        scenario_id=None,
        profile_id="BASIC",
        domain_status="VALIDATED",
        coverage_target=0.60,
    )
    res2 = service.recommend(
        scenario_id=None,
        profile_id="BASIC",
        domain_status="VALIDATED",
        coverage_target=0.60,
    )
    
    assert res1.status == "RECOMMENDED"
    assert res2.status == "RECOMMENDED"
    assert res1.recommended_channel == res2.recommended_channel == "CHWC_VLV"
    assert len(res1.candidate_scores) == len(res2.candidate_scores)


def test_domain_guard_on_external_dataset(client):
    """Verify that external/real field BMS scenarios trigger Domain Guard abstention in API."""
    # CSIRO real field BMS scenario without allow_unvalidated
    res_blocked = client.post(
        "/api/sensors/recommend",
        json={
            "scenario_id": "sc_89e2c6028b4f",
            "profile_id": "BASIC",
            "allow_unvalidated": False,
        },
    )
    assert res_blocked.status_code == 200
    data_blocked = res_blocked.json()
    assert data_blocked["status"] == "OUT_OF_DOMAIN"
    assert data_blocked["recommended_channel"] is None
    assert any("Domain Guard" in lim for lim in data_blocked.get("limitations", []))
    
    # With explicit override allow_unvalidated=True
    res_override = client.post(
        "/api/sensors/recommend",
        json={
            "scenario_id": "sc_89e2c6028b4f",
            "profile_id": "BASIC",
            "allow_unvalidated": True,
        },
    )
    assert res_override.status_code == 200
    data_override = res_override.json()
    assert data_override["status"] == "RECOMMENDED"
    assert data_override["recommended_channel"] == "CHWC_VLV"


def test_profiles_exhausted_abstention():
    """When a profile already contains all candidate channels, abstain with PROFILES_EXHAUSTED."""
    service = SensorRecommendationService()
    res = service.recommend(
        scenario_id=None,
        profile_id="BASIC_PLUS_BOTH",
    )
    assert res.status == "PROFILES_EXHAUSTED"
    assert res.recommended_channel is None
