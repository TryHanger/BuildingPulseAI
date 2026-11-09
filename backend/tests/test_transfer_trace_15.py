import json
from pathlib import Path

import pytest

from backend.app.api.endpoints import transfer_trace_15

URL = "/api/research/transfer-trace-15"
ROOT = Path(__file__).resolve().parents[2]


def test_fixed_trace_contract(client):
    response = client.get(URL)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.content == transfer_trace_15.BUNDLE.read_bytes()
    trace = transfer_trace_15.TransferTrace.model_validate(response.json())
    assert [point.model_seconds for point in trace.points] == list(range(17645700, 17649300, 60))
    assert all((point.prediction_deg_f is not None) == point.eligible for point in trace.points)
    assert all(block.decision == "ALERT" for block in trace.blocks)
    assert (trace.eligible_minutes, trace.calendar_minutes, trace.independent_normal_runs) == (5425, 10080, 1)


@pytest.mark.parametrize("suffix", ["?start=17647500", "?case=other", "?model=alternative"])
def test_rejects_unfrozen_queries(client, suffix):
    response = client.get(URL + suffix)
    assert response.status_code == 422
    assert response.json() == {"detail": "FROZEN_TRACE_ONLY"}


def test_read_only_and_existing_contracts(client):
    assert client.post(URL, json={}).status_code == 405
    baseline = json.loads((ROOT / "research/evidence/field_evidence_10/evidence/openapi-18060.json").read_bytes())
    observed = client.get("/openapi.json").json()
    assert set(observed["paths"]) - set(baseline["paths"]) == {URL}
    assert observed["paths"].pop(URL).keys() == {"get"}
    assert observed["paths"] == baseline["paths"]
    added = set(observed["components"]["schemas"]) - set(baseline["components"]["schemas"])
    assert added == {"TransferTrace", "TransferTraceBlock", "TransferTracePoint", "TransferTraceProvenance"}
    for name in added:
        del observed["components"]["schemas"][name]
    assert observed == baseline


@pytest.mark.parametrize("damage", ["missing", "changed"])
def test_source_failure_withholds_observations(client, monkeypatch, tmp_path, damage):
    artifact = tmp_path / "frozen.json"
    if damage == "changed":
        artifact.write_bytes(transfer_trace_15.BUNDLE.read_bytes() + b"\n")
    monkeypatch.setattr(transfer_trace_15, "BUNDLE", artifact)
    response = client.get(URL)
    assert response.status_code == 503
    assert response.json() == {"detail": "SOURCE_PROVENANCE_UNVERIFIED"}
