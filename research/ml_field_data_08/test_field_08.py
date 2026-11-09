"""Qualification and additive guard controls. No prediction or new G36 data."""
import json
import os
from pathlib import Path
from collections import Counter

from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from research.ml_field_data_08 import inspect_08 as field
from research.ml_domain_shift_07.test_applicability import BASE, MATCH


def test_original_hashes_when_files_available():
    source = os.environ.get("BP08_RAW")
    if source is None:
        pytest.skip("Set BP08_RAW to the verified Mendeley download directory")
    pinned = json.loads(field.MANIFEST.read_text())
    verified = field.qualify_source(Path(source), pinned)
    assert len(verified) == 8
    assert all(entry["verified_sha256"] == entry["publisher_sha256"] for entry in verified.values())


def test_missing_source_stops_before_parsing(tmp_path):
    with pytest.raises(field.QualificationError, match="STOP_SOURCE_UNAVAILABLE"):
        field.qualify_source(tmp_path, {"files": {"AHU1.xlsx": {"bytes": 4, "publisher_sha256": "0" * 64}}})


def test_modified_bytes_stop(tmp_path):
    (tmp_path / "AHU1.xlsx").write_bytes(b"fake")
    with pytest.raises(field.QualificationError, match="STOP_SOURCE_SHA_MISMATCH"):
        field.qualify_source(tmp_path, {"files": {"AHU1.xlsx": {"bytes": 4, "publisher_sha256": "0" * 64}}})


@pytest.mark.parametrize("deltas,duplicates,reversed_count,expected", [
    ({60: 5}, 0, 0, "MINUTE_GRID_ONLY_OTHER_GATES_REQUIRED"),
    ({300: 5}, 0, 0, "STOP_NON_MINUTE_CADENCE"),
    ({60: 4, 300: 1}, 0, 0, "STOP_NON_MINUTE_CADENCE"),
    ({60: 5}, 1, 0, "STOP_UNQUALIFIED_CLOCK"),
    ({-60: 1, 60: 4}, 0, 1, "STOP_UNQUALIFIED_CLOCK"),
    ({}, 0, 0, "STOP_UNQUALIFIED_CLOCK"),
])
def test_grid_and_duplicate_controls(deltas, duplicates, reversed_count, expected):
    assert field.sampling_status(Counter(deltas), duplicates, reversed_count) == expected


def test_physical_roles_and_label_boundary():
    assert field.roles(field.EXHAUST_SP)[1] == "BAS_SETPOINT_EXHAUST"
    assert field.roles("air_temperature__max__supply_air_outlet")[1] == "BAS_LIMIT"
    assert field.roles("signal__required_value__fan_fresh_air")[1] == "BAS_COMMAND"
    assert field.roles(field.FAN)[1] == "BAS_STATUS_UNVERIFIED_RUN_PROOF"
    assert field.roles("water_temperature__real_value__chiller_behind")[0] != "SAT"
    assert field.roles("fault")[1] == "ANNOTATION_EXCLUDED_FROM_INPUT"
    assert field.normalize_label(None) == "UNKNOWN"
    assert field.normalize_label(" no fault ") == "no fault"


@pytest.mark.parametrize("features", [
    {"MA_TEMP": 105, "OA_TEMP": 65, "RA_TEMP": 70},
    {"MA_TEMP": "105", "OA_TEMP": "65", "RA_TEMP": "70"},
])
def test_match_is_self_attested_1d_only_even_when_implausible(features):
    client = TestClient(app)
    result = client.post(BASE + "/applicability", json={**MATCH, "features": features})
    assert result.status_code == 200
    payload = result.json()
    assert payload["status"] == "SOURCE_REGIME_MATCH_ONLY"
    assert payload["self_attested_metadata_only"] is True
    assert payload["one_dimensional_feature_ranges_only"] is True
    assert payload["fan_duration_verified"] is False
    assert not any(payload[key] for key in ("inference_authorized", "deployment_eligible", "incident_eligible"))
    assert client.post(BASE + "/applicability", json={**MATCH, "fan_duration_verified": True}).status_code == 422


def test_oracle_forbidden_and_negative_gate_visible():
    client = TestClient(app)
    result = client.get(BASE).json()
    assert result["transfer_normal_gate"] == "STOP_OOD_HEALTHY"
    assert result["historical_normal_evidence"]["lightgbm_alarm_blocks"] == 7
    assert result["self_attested_metadata_only"] is result["one_dimensional_feature_ranges_only"] is True
    assert result["fan_duration_verified"] is False
    assert client.post(BASE + "/applicability", json={**MATCH, "fault": "Fault 12"}).status_code == 422
    assert client.post(BASE + "/applicability", json={**MATCH, "features": {**MATCH["features"], "oracle": 0}}).status_code == 422
