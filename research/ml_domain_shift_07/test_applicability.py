"""Prospective unit/HTTP checks with synthetic metadata and no scoring."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.domain_shift_07 import ApplicabilityRequest, FEATURE_SUPPORT, assess

BASE = "/api/research/domain-shift-07"
MATCH = {
    "active_setpoint": "55.184006", "setpoint_exact": True, "temperature_unit": "degF",
    "physical_roles_verified": True, "origin": "VERIFIED_BAS", "control_mode": "RUNNING_WARM",
    "features": {"MA_TEMP": 70, "OA_TEMP": 72, "RA_TEMP": 73},
}
CASES = [
    ({}, "SOURCE_REGIME_MATCH_ONLY", "EXACT_SOURCE_SUPPORT_MATCH", "MATCH"),
    ({"active_setpoint": None}, "ABSTAIN_DOMAIN_SHIFT", "UNKNOWN_SETPOINT", "UNKNOWN"),
    ({"setpoint_exact": False}, "ABSTAIN_DOMAIN_SHIFT", "UNKNOWN_SETPOINT", "UNKNOWN"),
    ({"active_setpoint": "53.2765195"}, "NOT_APPLICABLE_CONTROL_REGIME", "SETPOINT_OUTSIDE_SOURCE_SUPPORT", "OUTSIDE"),
    ({"active_setpoint": "55.18400601"}, "NOT_APPLICABLE_CONTROL_REGIME", "SETPOINT_OUTSIDE_SOURCE_SUPPORT", "OUTSIDE"),
    ({"temperature_unit": "K"}, "ABSTAIN_DOMAIN_SHIFT", "UNKNOWN_OR_WRONG_TEMPERATURE_UNIT", "UNKNOWN"),
    ({"temperature_unit": None}, "ABSTAIN_DOMAIN_SHIFT", "UNKNOWN_OR_WRONG_TEMPERATURE_UNIT", "UNKNOWN"),
    ({"control_mode": "UNKNOWN"}, "ABSTAIN_DOMAIN_SHIFT", "UNKNOWN_CONTROL_MODE", "MATCH"),
    ({"control_mode": "OFF"}, "NOT_APPLICABLE_CONTROL_REGIME", "OUTSIDE_CONTROL_MODE", "MATCH"),
    ({"physical_roles_verified": False}, "ABSTAIN_DOMAIN_SHIFT", "UNVERIFIED_PHYSICAL_ROLES", "UNKNOWN"),
    ({"origin": "UNKNOWN"}, "ABSTAIN_DOMAIN_SHIFT", "UNVERIFIED_PHYSICAL_ROLES", "UNKNOWN"),
    ({"features": {"MA_TEMP": 70}}, "ABSTAIN_DOMAIN_SHIFT", "MISSING_REQUIRED_FEATURE", "MATCH"),
    ({"features": {**MATCH["features"], "RA_TEMP": 118}}, "ABSTAIN_DOMAIN_SHIFT", "OUTSIDE_SOURCE_FEATURE_SUPPORT", "MATCH"),
]


def verify(response, status, reason, support):
    assert response == {
        "status": status, "reason": reason, "source_setpoint_support": support,
        "inference_authorized": False, "deployment_eligible": False, "incident_eligible": False,
        "self_attested_metadata_only": True, "one_dimensional_feature_ranges_only": True,
        "fan_duration_verified": False,
    }


@pytest.mark.parametrize("patch,status,reason,support", CASES)
def test_unit_guard(patch, status, reason, support):
    result = assess(ApplicabilityRequest.model_validate({**MATCH, **patch}))
    verify(result.model_dump(), status, reason, support)


@pytest.mark.parametrize("patch,status,reason,support", CASES)
def test_http_guard(patch, status, reason, support):
    response = TestClient(app).post(BASE + "/applicability", json={**MATCH, **patch})
    assert response.status_code == 200
    verify(response.json(), status, reason, support)


@pytest.mark.parametrize("patch", [
    {"oracle": 0}, {"features": {**MATCH["features"], "TRUE_VALVE_POSITION": 0}},
    {"features": {**MATCH["features"], "SA_TEMP": 53}}, {"origin": "SIMULATOR_INTERNAL"},
    {"physical_roles_verified": "true"}, {"active_setpoint": "NaN"},
    {"features": {**MATCH["features"], "RA_TEMP": "Infinity"}},
])
def test_http_rejects_oracles_and_untyped_evidence(patch):
    assert TestClient(app).post(BASE + "/applicability", json={**MATCH, **patch}).status_code == 422


def test_registry_matches_audit_and_leaves_stop_gate():
    receipt = json.loads(Path(__file__).with_name("DOMAIN_SHIFT_07_REGISTER.json").read_text())
    registry = TestClient(app).get(BASE).json()
    for key in ("candidate", "source_calibration_domain", "training_setpoint_support", "setpoint_used_as_feature",
                "transfer_normal_gate", "target_fault_eval_allowed", "external_field_validation", "deployment_eligible"):
        assert registry[key] == receipt[key]
    audit = receipt["saved_target_trace_audit"]
    evidence = registry["historical_normal_evidence"]
    assert (evidence["independent_runs"], evidence["eligible_minutes"], evidence["calendar_minutes"]) == (1, 5425, 10080)
    assert evidence["lightgbm_alarm_blocks"] == audit["methods"]["lightgbm_reduced"]["alarm_blocks"] == 7
    assert evidence["stage06_archive_sha256"] == receipt["sha256"]["accepted_stage_06_zip"]
    assert audit["mode_4_eligible_count"] == 6 and audit["last_block_minutes_without_mode_4"] == 769
    assert all(method["audit_only_last_block"]["without_mode_4_would_exceed_frozen_threshold"]
               for method in audit["methods"].values())
    for key, (low, high) in FEATURE_SUPPORT.items():
        values = receipt["source_training_audit"]["features"]["summary_degF"][key]
        assert (low, high) == (values["min"], values["max"])
    assert not receipt["target_raw_opened"] and not receipt["model_loaded"] and receipt["prediction_calls"] == 0


def test_research_post_does_not_change_fdd_feed():
    client = TestClient(app)
    params = {"dataset_id": "ds_8e5b1ddfdd14", "start": "2018-01-02T11:08:00", "limit": 1}
    before = client.get("/api/v1/incidents", params=params)
    assert before.status_code == 200
    for patch in ({}, {"active_setpoint": "53"}, {"active_setpoint": None}):
        status = client.post(BASE + "/applicability", json={**MATCH, **patch}).json()
        assert not status["incident_eligible"] and status["status"] not in ("MODEL_ANOMALY", "NORMAL")
        assert client.post("/api/v1/incidents", params=params, json=status).status_code == 405
    after = client.get("/api/v1/incidents", params=params)
    assert after.content == before.content
