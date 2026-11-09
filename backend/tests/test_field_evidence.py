import json

import pytest

from backend.app.api.endpoints import field_evidence as endpoint

API = "/api/research/field-evidence"


def test_serve_verified_bundle(client):
    response = client.get(API)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.content == endpoint.BUNDLE.read_bytes()
    evidence = endpoint.FieldEvidence.model_validate_json(response.content, strict=True)
    assert len(evidence.cases) == 12
    assert all(len(case.observations) == 20 for case in evidence.cases)
    assert set(client.get("/openapi.json").json()["paths"][API]) == {"get"}
    assert API not in client.get("/api/v1/openapi.json").json()["paths"]


@pytest.mark.parametrize("attack", [
    "missing", "invalid-json", "source-hash", "native-time", "duplicate-time",
    "off-grid", "end-tick", "missing-fan", "fault-label", "schedule",
    "missing-control", "unknown-clock-replaced",
])
def test_altered_evidence_is_withheld(client, monkeypatch, tmp_path, attack):
    bundle = json.loads(endpoint.BUNDLE.read_bytes())
    case = bundle["cases"][0]
    tick = case["observations"][2]
    if attack == "source-hash":
        bundle["provenance"]["files"]["AHU1.xlsx"]["publisher_sha256"] = "0" * 64
    elif attack == "native-time":
        tick["native_time"] = "2019-03-01 13:99:00"
    elif attack == "duplicate-time":
        tick["native_time"] = case["observations"][1]["native_time"]
    elif attack == "off-grid":
        tick["native_time"] = "2019-03-01 13:31:00"
    elif attack == "end-tick":
        case["observations"][-1]["native_time"] = case["end_exclusive"]
    elif attack == "missing-fan":
        del tick["supply"]
    elif attack == "fault-label":
        tick["fault"] = "Fault 12"
    elif attack == "schedule":
        tick["schedule"] = case["evaluation_metadata"]
    elif attack == "missing-control":
        bundle["cases"].pop()
    elif attack == "unknown-clock-replaced":
        bundle["provenance"]["clock"] = "UTC"
        tick["native_time"] += "+00:00"

    replacement = tmp_path / "untrusted.json"
    if attack != "missing":
        replacement.write_text("{" if attack == "invalid-json" else json.dumps(bundle))
    monkeypatch.setattr(endpoint, "BUNDLE", replacement)
    response = client.get(API)
    assert response.status_code == 503
    assert response.json() == {"detail": "SOURCE_PROVENANCE_UNVERIFIED"}


@pytest.mark.parametrize("query", [
    {"ahu": "AHU99"}, {"path": "../../buildingpulse.db"}, {"url": "https://example.org"},
    {"time_zone": "UTC"}, {"schedule": "Fault 12"},
])
def test_no_client_configurable_source_or_selection(client, query):
    response = client.get(API, params=query)
    assert response.status_code == 422
    assert response.json() == {"detail": "FROZEN_COLLECTION_ONLY"}


def test_read_only_and_no_incident_write(client):
    params = {"dataset_id": "ds_8e5b1ddfdd14", "start": "2018-01-02T11:08:00", "limit": 1}
    before = client.get("/api/v1/incidents", params=params)
    assert before.status_code == 200
    assert client.get(API + "/AHU99").status_code == 404
    assert client.get(API).status_code == 200
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        assert client.request(method, API, json={"type": "MODEL_ANOMALY"}).status_code == 405
    assert client.post("/api/v1/incidents", params=params, json={"type": "MODEL_ANOMALY"}).status_code == 405
    assert client.get("/api/v1/incidents", params=params).content == before.content
