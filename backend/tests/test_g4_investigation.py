
import pytest

from backend.app.services import g3_incidents, g4_investigation, investigator_v1 as runtime
from contracts.evidence_v1 import validate_schema
from scripts.build_g4_demo import build

DEMO = "demo-g4-mat"
ANNUAL = "ds_8e5b1ddfdd14"
URL = "/api/v1/investigation"
CONFIRMED = "2018-01-02T11:15:00"


def report(client, **query):
    response = client.get(URL, params=query)
    assert response.status_code == 200, response.text
    result = response.json()
    validate_schema(result, "RuntimeG4Investigation")
    payload = dict(result)
    payload.pop("run_sha256")
    assert g4_investigation.with_run_hash(payload) == result
    return result


def test_real_window_and_full_source_coverage(client):
    query = {"dataset_id": ANNUAL, "start": "2018-01-02T11:08:00"}
    result = report(client, **query)
    assert result["provenance"] == "SIMULATED_BENCHMARK"
    assert result["result_origin"] == "VERIFIED_RUNTIME"
    assert result["source_coverage"] == dict(samples=525540, evaluated=187192, not_evaluable=338348, violated=0)
    assert result["source_confirmed_episodes"] == 0
    assert result["status"] == "NO_SYMPTOMS_ON_EVALUATED_WINDOWS"
    assert result["evidence_status"] == "NOT_DETECTED"
    assert result["cause_state"] == "NOT_ASSESSED"
    assert result["events"] == []
    for format in ("json", "html"):
        params = {**query, "format": format}
        first = client.get(URL, params=params)
        assert first.content == client.get(URL, params=params).content
        assert result["run_sha256"].encode() in first.content
        assert result["source_sha256"].encode() in first.content
    assert "Zero confirmed symptoms does not establish zero faults." in first.text


def test_demo_evidence_matches_series_and_direct_seek(client):
    listing = client.get("/api/v1/datasets", params={"demo": True}).json()
    validate_schema(listing, "RuntimeDatasetList")
    assert [item["dataset_id"] for item in listing["items"]] == [DEMO]
    assert DEMO not in [item["dataset_id"] for item in client.get("/api/v1/datasets").json()["items"]]
    result = report(client, dataset_id=DEMO)
    assert result["provenance"] == result["result_origin"] == "DEMO_FIXTURE"
    assert result["status"] == "DETECTED_SYMPTOM"
    assert result["evidence_status"] == "CONFIRMED_SYMPTOM"
    assert result["time_quality"]["gaps"] == 1
    event, = result["events"]
    assert event["confirmed_at"] == CONFIRMED
    assert event["observation_count"] == 55
    assert event["sensor_root_count"] == 5
    roots = event["raw_lineage"]
    assert event["derived_fact"]["depends_on"] == [root["canonical_id"] for root in roots]
    series = client.get("/api/v1/series", params={
        "dataset_id": DEMO, "start": event["first_observed"], "limit": 11,
        "signal_ids": [root["canonical_id"] for root in roots],
    }).json()
    validate_schema(series, "RuntimeSeries")
    assert series["source_sha256"] == result["source_sha256"]
    assert series["result_origin"] == "DEMO_FIXTURE"
    values = {signal["canonical_id"]: signal["values"] for signal in series["signals"]}
    for root in roots:
        observations = root["observations"]
        assert len(observations) == 11
        assert [item["timestamp"] for item in observations] == series["timestamps"]
        assert all(item["source_sha256"] == result["source_sha256"] for item in observations)
        expected = [(item["value"] - 32) * 5 / 9 if item["unit"] == "degF" else item["value"]
                    for item in observations]
        assert values[root["canonical_id"]] == pytest.approx(expected)
    seek = report(client, dataset_id=DEMO, start="2018-01-02T11:17:00", limit=1, event_id=event["event_id"])
    assert seek["events"][0]["event_id"] == event["event_id"]
    assert seek["provenance"] == "DEMO_FIXTURE"
    preconfirmation = report(client, dataset_id=DEMO, start="2018-01-02T11:10:00", limit=1)
    assert preconfirmation["events"] == [] and preconfirmation["coverage"]["violated"] == 1
    gap = report(client, dataset_id=DEMO, start="2018-01-02T11:32:00", limit=1)
    assert gap["status"] == gap["evidence_status"] == "NOT_EVALUABLE"
    assert gap["time_quality"]["gaps"] == 1
    assert gap["cause_state"] == "NOT_ASSESSED" and not gap["events"]
    assert gap["not_evaluable_reasons"] == {"FAN_TRANSITION_HOLD": 1}
    assert client.get(URL, params=dict(dataset_id=DEMO, start=gap["first"], limit=1,
                                       event_id=event["event_id"])).status_code == 404
    for format in ("json", "html"):
        query = {"dataset_id": DEMO, "format": format}
        response = client.get(URL, params=query)
        assert response.content == client.get(URL, params=query).content
        assert result["run_sha256"].encode() in response.content


@pytest.mark.parametrize("parameter", ["oracle", "ground_truth", "fault_probability", "validated_discriminator",
                                       "root_cause_confirmed"])
def test_investigation_rejects_caller_supplied_diagnostics(client, parameter):
    assert client.get(URL, params={"dataset_id": DEMO, parameter: "true"}).status_code == 422


@pytest.mark.parametrize(("filename", "code"), [("mixing-demo.csv", "SOURCE_INTEGRITY"),
                                               ("incidents.json", "INCIDENT_INDEX_INTEGRITY")])
def test_demo_integrity_never_falls_back(client, tmp_path, monkeypatch, filename, code):
    build(tmp_path)
    monkeypatch.setattr(runtime, "DEMO_DIR", tmp_path)
    assert client.get(URL, params={"dataset_id": DEMO}).status_code == 200
    with (tmp_path / filename).open("ab") as stream:
        stream.write(b"tampered")
    response = client.get(URL, params={"dataset_id": DEMO})
    assert response.status_code == 409 and response.json()["detail"]["code"] == code


def test_live_bad_index_sha(client, tmp_path, monkeypatch):
    path = tmp_path / "bad.sha256"
    path.write_text("0" * 64)
    monkeypatch.setattr(g3_incidents, "INDEX_SHA", path)
    for url in (URL, "/api/v1/incidents"):
        response = client.get(url, params={"dataset_id": ANNUAL})
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "INCIDENT_INDEX_INTEGRITY"


def test_html_escapes_source_metadata(client, monkeypatch):
    attack = '<img src=x onerror="alert(1)"><script>alert(2)</script>'
    manifest = {**runtime.demo_manifest(), "name": attack}
    monkeypatch.setattr(runtime, "demo_manifest", lambda: manifest)
    response = client.get(URL, params={"dataset_id": DEMO, "format": "html"})
    assert response.status_code == 200
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert attack not in response.text and "<script>" not in response.text
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in response.text


def test_fixture_rebuild(tmp_path):
    build(tmp_path)
    for name in ("manifest.json", "incidents.json", "mixing-demo.csv"):
        assert (tmp_path / name).read_bytes() == (runtime.DEMO_DIR / name).read_bytes()


def test_missing_demo_manifest_keeps_live_sources_available(client, tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "DEMO_DIR", tmp_path)
    assert client.get(URL, params={"dataset_id": DEMO}).status_code == 409
    assert client.get(URL, params={"dataset_id": ANNUAL}).status_code == 200


@pytest.mark.parametrize(("limit", "unconfirmed", "confirmed"), [(10, 10, 0), (11, 0, 1)])
def test_window_distinguishes_violated_samples_from_confirmation(client, limit, unconfirmed, confirmed):
    result = report(client, dataset_id=DEMO, start="2018-01-02T11:05:00", limit=limit)
    assert result["coverage"]["evaluated"] == result["coverage"]["violated"] == limit
    assert result["unconfirmed_violated_samples"] == unconfirmed
    assert result["confirmation_state"] == ("PENDING" if unconfirmed else "CONFIRMED")
    assert len(result["events"]) == confirmed


def test_missing_mixed_air_sensor_is_unassessed(client, tmp_path, monkeypatch):
    build(tmp_path, omit_mat=True)
    monkeypatch.setattr(runtime, "DEMO_DIR", tmp_path)
    result = report(client, dataset_id=DEMO, start=CONFIRMED, limit=1)
    assert result["status"] == result["evidence_status"] == "NOT_EVALUABLE"
    assert result["cause_state"] == "NOT_ASSESSED"
    assert result["unconfirmed_violated_samples"] == 0 and not result["events"]
    assert result["not_evaluable_reasons"] == {"REQUIRED_INPUT_MISSING": 1}
    assert next(item for item in result["inputs"] if item["canonical_id"] == "MA_TEMP")["available"] is False


def test_pending_is_window_local_and_does_not_replace_legacy_status(client):
    pending = report(client, dataset_id=DEMO, start="2018-01-02T11:05:00", limit=10)
    assert pending["status"] == "NO_SYMPTOMS_ON_EVALUATED_WINDOWS"
    assert pending["evidence_status"] == "NOT_DETECTED"
    assert pending["confirmation_state"] == "PENDING"
    assert pending["last"] == "2018-01-02T11:14:00"
    html = client.get(URL, params={"dataset_id": DEMO, "start": pending["first"], "limit": 10, "format": "html"})
    assert "Window confirmation state: PENDING" in html.text
    assert "Later samples can change confirmation." in html.text
    following = report(client, dataset_id=DEMO, start=pending["first"], limit=11)
    assert following["events"][0]["confirmed_at"] == "2018-01-02T11:15:00"


def test_ended_short_run_is_unconfirmed_without_pending(client, tmp_path, monkeypatch):
    build(tmp_path, violation_minutes=10)
    monkeypatch.setattr(runtime, "DEMO_DIR", tmp_path)
    result = report(client, dataset_id=DEMO, start="2018-01-02T11:05:00", limit=11)
    assert result["confirmation_state"] == "UNCONFIRMED"
    assert result["unconfirmed_violated_samples"] == 10 and not result["events"]
