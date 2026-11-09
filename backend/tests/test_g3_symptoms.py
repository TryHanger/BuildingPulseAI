"""DEMO_FIXTURE negative/positive controls and official read-only runtime checks."""
import hashlib
import json
from datetime import datetime, timedelta

import pytest

from backend.app.services import g3_incidents, g3_symptom as rule, investigator_v1 as runtime
from backend.app.services.g2_mode import ModeContext
from contracts.evidence_v1 import ContractError, validate_schema
from scripts.build_g3_incident_index import analyze_source

BASE = {"OA_TEMP": 40, "RA_TEMP": 72, "MA_TEMP": 55, "SF_SPD_DM": 1, "SF_CS": 0.5}
ANNUAL = "ds_8e5b1ddfdd14"
START = datetime(2018, 1, 2)


@pytest.mark.parametrize(("changes", "mode", "predicate", "reason"), [
    ({"MA_TEMP": "bad"}, "RUNNING", "NOT_EVALUABLE", "REQUIRED_INPUT_QUALITY"),
    ({"OA_TEMP": float("inf")}, "RUNNING", "NOT_EVALUABLE", "REQUIRED_INPUT_QUALITY"),
    ({"RA_TEMP": None}, "RUNNING", "NOT_EVALUABLE", "REQUIRED_INPUT_QUALITY"),
    ({}, "OFF", "NOT_EVALUABLE", "FAN_OFF"),
    ({}, "UNKNOWN", "NOT_EVALUABLE", "FAN_STATUS_UNKNOWN"),
    ({}, "TRANSITION_HOLD", "NOT_EVALUABLE", "FAN_TRANSITION_HOLD"),
    ({"SF_CS": 0.01}, "RUNNING", "NOT_EVALUABLE", "FAN_COMMAND_TOO_LOW"),
    ({"OA_TEMP": 66, "MA_TEMP": 10}, "RUNNING", "NOT_EVALUABLE", "LOW_INLET_TEMPERATURE_SEPARATION"),
    ({"OA_TEMP": 72, "MA_TEMP": 10}, "RUNNING", "NOT_EVALUABLE", "LOW_INLET_TEMPERATURE_SEPARATION"),
    ({"MA_TEMP": 33}, "RUNNING", "NOT_VIOLATED", "EVALUATED"),
    ({"MA_TEMP": 32.99}, "RUNNING", "VIOLATED", "EVALUATED"),
    ({"OA_TEMP": 62, "MA_TEMP": 54.99}, "RUNNING", "VIOLATED", "EVALUATED"),
    ({"OA_TEMP": 33.8}, "RUNNING", "NOT_VIOLATED", "EVALUATED"),
    ({"OA_TEMP": 60}, "RUNNING", "NOT_VIOLATED", "EVALUATED"),
    ({"MA_TEMP": 83}, "RUNNING", "NOT_VIOLATED", "EVALUATED"),
])
def test_demo_fixture_rule_gate(changes, mode, predicate, reason):
    result = rule.evaluate({**BASE, **changes}, mode, rule.verified_bindings(runtime.SIGNALS))
    assert result.predicate == predicate and result.reason_code == reason


def test_only_distinct_documented_basic_points_and_one_evidence_family():
    bindings = {**runtime.SIGNALS, "RA_TEMP": {**runtime.SIGNALS["RA_TEMP"], "source_column": "OA_TEMP"}}
    assert not rule.verified_bindings(bindings)
    assert rule.evaluate(BASE, "RUNNING", False).reason_code == "UNVERIFIED_OR_DUPLICATE_BINDING"
    assert rule.evaluate({k: v for k, v in BASE.items() if k != "RA_TEMP"},
                         "RUNNING", True).reason_code == "REQUIRED_INPUT_MISSING"
    clean = rule.point_result(BASE, "RUNNING", runtime.SIGNALS, "a" * 64, START.isoformat())
    contaminated = {**BASE, "SYS_CTL": 1, "CHWC_VLV": 0, "source_label": "ORACLE", "SA_SP": float("inf"),
                    "fault_filename": "FAKE", "ground_truth_label": "FAULT"}
    assert rule.point_result(contaminated, "RUNNING", runtime.SIGNALS, "a" * 64, START.isoformat()) == clean
    source = {"sha256": "a" * 64}
    actual = runtime.evaluate_point(source, BASE, START.isoformat(), "BASIC", ModeContext("RUNNING"))
    tainted = runtime.evaluate_point({**source, "source_label": "ORACLE"}, contaminated,
                                     START.isoformat(), "BASIC", ModeContext("RUNNING"))
    assert tainted["symptom_evaluation"] == actual["symptom_evaluation"] == clean
    assert clean["rule"]["flow_proof"] == "UNAVAILABLE_IN_BASIC"
    assert {root["source_column"] for root in clean["raw_lineage"]} == set(BASE)
    assert len({root["evidence_id"] for root in clean["raw_lineage"]}) == len(BASE)
    assert clean["rule"]["method_id"] == "mat-below-mixing-envelope"
    assert "FC3_RETURN_FAN_HEAT_UNVERIFIED" in rule.INAPPLICABLE_CHECKS


def feed(accumulator, minute, mat=20, mode="RUNNING", seconds=0):
    stamp = START + timedelta(minutes=minute, seconds=seconds)
    accumulator.feed(stamp, rule.evaluate({**BASE, "MA_TEMP": mat}, mode, True))


def test_episode_confirmation_exact_boundary_and_future_free_snapshots():
    accumulator = rule.EpisodeAccumulator()
    for minute in range(11):
        feed(accumulator, minute)
    assert accumulator.confirmed == START + timedelta(minutes=10)
    feed(accumulator, 11)
    feed(accumulator, 12, mat=50)
    episodes = accumulator.finish()
    before = (START + timedelta(minutes=9)).isoformat()
    assert list(g3_incidents.incident_snapshots(episodes, START.isoformat(), before, "a" * 64)) == []
    confirm = (START + timedelta(minutes=10)).isoformat()
    at_confirm, = g3_incidents.incident_snapshots(episodes, confirm, confirm, "a" * 64)
    assert at_confirm["samples"] == 11 and at_confirm["last_seen"] == confirm
    assert at_confirm["gap_reason"] == "WINDOW_CUTOFF"
    assert len(at_confirm["raw_lineage"]) == 55
    assert len({root["evidence_id"] for root in at_confirm["raw_lineage"]}) == 55
    assert max(root["timestamp"] for root in at_confirm["raw_lineage"]) == confirm
    closure = (START + timedelta(minutes=12)).isoformat()
    after, = g3_incidents.incident_snapshots(episodes, closure, closure, "a" * 64)
    assert after["event_id"] == at_confirm["event_id"] and after["gap_reason"] == "PREDICATE_CLEARED"
    assert after["samples"] == 12 and after["last_seen"] < closure
    validate_schema(after, "RuntimeG3Incident")
    for field, value in (("fault_probability", 0.9), ("root_cause_confirmed", True)):
        with pytest.raises(ContractError):
            validate_schema({**after, field: value}, "RuntimeG3Incident")


@pytest.mark.parametrize(("break_reason", "stamp_minute", "seconds", "mode", "mat"), [
    ("FAN_OFF", 11, 0, "OFF", 20),
    ("FAN_STATUS_UNKNOWN", 11, 0, "UNKNOWN", 20),
    ("FAN_TRANSITION_HOLD", 11, 0, "TRANSITION_HOLD", 20),
    ("REQUIRED_INPUT_QUALITY", 11, 0, "RUNNING", "bad"),
    ("TIME_GAP", 551, 0, "RUNNING", 20),
    ("OFF_GRID_STEP", 11, 30, "RUNNING", 20),
])
def test_night_gap_unknown_hold_bad_value_and_off_grid_break_episode(break_reason, stamp_minute, seconds, mode, mat):
    accumulator = rule.EpisodeAccumulator()
    for minute in range(11):
        feed(accumulator, minute)
    feed(accumulator, stamp_minute, mat, mode, seconds)
    event, = accumulator.finish()
    assert event["last_seen"] == (START + timedelta(minutes=10)).isoformat()
    assert event["gap_reason"] == break_reason


def get_incidents(client, **query):
    response = client.get("/api/v1/incidents", params=query)
    assert response.status_code == 200, response.text
    result = response.json()
    validate_schema(result, "RuntimeG3Incidents")
    return result


def test_demo_fixture_api_pages_match_whole_and_preserve_id_on_direct_seek(client, monkeypatch, tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    source_file = raw / "demo.csv"
    rows = 1000
    source_file.write_text("Datetime,OA_TEMP,RA_TEMP,MA_TEMP,SF_SPD_DM,SF_CS\n" + "".join(
        f"{(START + timedelta(minutes=i)).isoformat()},40,72,{20 if 465 <= i < 480 or 600 <= i < 970 else 55},1,0.5\n"
        for i in range(rows)
    ))
    key = "DEMO_FIXTURE_G3"
    source = {"path": source_file.name, "rows": rows, "sha256": hashlib.sha256(source_file.read_bytes()).hexdigest()}
    monkeypatch.setattr(runtime.settings, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(runtime, "SOURCES", {key: source})
    index = tmp_path / "index.json"
    digest = index.with_suffix(".sha256")
    index.write_text(json.dumps({"index_version": 1, "rule_fingerprint": rule.RULE_FINGERPRINT,
                                 "datasets": {key: analyze_source(source)}}))
    digest.write_text(hashlib.sha256(index.read_bytes()).hexdigest())
    monkeypatch.setattr(g3_incidents, "INDEX", index)
    monkeypatch.setattr(g3_incidents, "INDEX_SHA", digest)
    whole = get_incidents(client, dataset_id=key, limit=1000)
    assert len(whole["events"]) == 2
    first = get_incidents(client, dataset_id=key, limit=480)
    second = get_incidents(client, dataset_id=key, start=first["next_start"], limit=480)
    third = get_incidents(client, dataset_id=key, start=second["next_start"], limit=480)
    assert first["events"][0]["gap_reason"] == "WINDOW_CUTOFF"
    assert second["events"][0]["gap_reason"] == "PREDICATE_CLEARED"
    merged = {event["event_id"]: event for page in (first, second, third) for event in page["events"]}
    assert list(merged.values()) == whole["events"]
    assert sum(page["coverage"]["evaluated"] for page in (first, second, third)) == whole["coverage"]["evaluated"]
    seek = (START + timedelta(minutes=900)).isoformat()
    direct = get_incidents(client, dataset_id=key, start=seek, limit=1)
    assert direct["events"][0]["event_id"] == whole["events"][1]["event_id"]
    assert direct["events"][0]["last_seen"] == seek
    index.write_text("{}")
    corrupt = client.get("/api/v1/incidents", params={"dataset_id": key})
    assert corrupt.status_code == 409 and corrupt.json()["detail"]["code"] == "INCIDENT_INDEX_INTEGRITY"


def test_official_valid_empty_window_and_independent_pressure_warning(client, monkeypatch):
    def reject_csv(*args, **kwargs):
        pytest.fail("Annual incident window attempted a full or sequential CSV read")

    monkeypatch.setattr(runtime, "read_verified", reject_csv)
    monkeypatch.setattr(runtime, "annual_csv_window", reject_csv)
    timestamp = "2018-01-02T11:08:00"
    window = get_incidents(client, dataset_id=ANNUAL, start=timestamp, limit=1440)
    assert window["coverage"]["samples"] == 1440 and window["coverage"]["evaluated"] > 0
    assert window["coverage"]["violated"] == 0 and window["events"] == []
    response = client.get("/api/v1/diagnostics", params={"dataset_id": ANNUAL, "at": timestamp})
    payload = response.json()
    validate_schema(payload, "RuntimeDiagnostics")
    assert payload["data_status"] == "DEGRADED"
    assert payload["symptom_evaluation"]["predicate"] == "NOT_VIOLATED"
    assert payload["methods"][2]["reason_code"] == "PANEL_EXCLUDES_SIGNAL"
    assert next(item for item in payload["signal_quality"] if item["canonical_id"] == "SA_SP")["flags"] == [
        "SEMANTICS_UNVERIFIED"
    ]


def test_extra_fraction_flags_differ_from_command_range_and_do_not_change_basic_rule(client, monkeypatch, tmp_path):
    (tmp_path / "raw").mkdir()
    path = tmp_path / "raw/demo.csv"
    path.write_text("Datetime,OA_TEMP,RA_TEMP,MA_TEMP,SF_SPD_DM,SF_CS,CHWC_VLV,CHWC_VLV_DM\n" + "".join(
        f"{(START + timedelta(minutes=i)).isoformat()},40,72,55,1,0.5,1.5,1.5\n" for i in range(6)
    ))
    key = "DEMO_FIXTURE_G3"
    monkeypatch.setattr(runtime.settings, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(runtime, "SOURCES", {key: {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}})
    params = {"dataset_id": key, "at": (START + timedelta(minutes=5)).isoformat()}
    basic = client.get("/api/v1/diagnostics", params=params).json()
    extra = client.get("/api/v1/diagnostics", params={**params, "panel": "EXTRA"}).json()
    quality = {item["canonical_id"]: item["flags"] for item in extra["signal_quality"]}
    assert quality["CHWC_VLV"] == ["MEASUREMENT_FRACTION_OUT_OF_RANGE"]
    assert quality["CHWC_VLV_DM"] == ["COMMAND_OUT_OF_RANGE"]
    assert basic["symptom_evaluation"] == extra["symptom_evaluation"]
    assert extra["symptom_evaluation"]["predicate"] == "NOT_VIOLATED"


@pytest.mark.parametrize("query", [
    {"limit": 1441}, {"limit": 0}, {"start": "2018-01-02T12:00:00Z"},
    {"fault_probability": 0.9}, {"ground_truth_label": "FAULT"}, {"validated_discriminator": "invented"},
])
def test_incident_api_rejects_unbounded_or_oracle_requests(client, query):
    response = client.get("/api/v1/incidents", params={"dataset_id": ANNUAL, **query})
    assert response.status_code == 422
    validate_schema(response.json(), "RuntimeError")
