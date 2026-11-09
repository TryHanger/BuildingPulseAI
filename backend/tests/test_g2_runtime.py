import hashlib
from datetime import datetime, timedelta

import pytest

from backend.app.services import investigator_v1 as runtime
from contracts.evidence_v1 import ContractError, validate_schema

ANNUAL = "ds_8e5b1ddfdd14"


def register(monkeypatch, tmp_path, text):
    raw = tmp_path / "raw"
    raw.mkdir()
    content = text.encode()
    (raw / "test.csv").write_bytes(content)
    source = {"path": "test.csv", "archive_member": "test.csv", "sha256": hashlib.sha256(content).hexdigest()}
    monkeypatch.setattr(runtime.settings, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(runtime, "SOURCES", {"test": source})
    return source


def at(client, timestamp, panel="BASIC", dataset_id="test"):
    response = client.get("/api/v1/diagnostics", params={"dataset_id": dataset_id, "at": timestamp, "panel": panel})
    assert response.status_code == 200, response.text
    result = response.json()
    validate_schema(result, "RuntimeDiagnostics")
    return result


def modes(client, start=None, dataset_id="test", limit=480):
    query = {"dataset_id": dataset_id, "limit": limit}
    if start is not None:
        query["start"] = start
    response = client.get("/api/v1/modes", params=query)
    assert response.status_code == 200, response.text
    result = response.json()
    validate_schema(result, "RuntimeModes")
    return result


def test_transitions_quality_applicability_and_basic_boundary(client, monkeypatch, tmp_path):
    header = "Datetime,SF_SPD_DM,OA_TEMP,SA_TEMP,SA_TEMPSPT,CHWC_VLV_DM,SA_SP,CHWC_VLV,SYS_CTL,SF_CS\n"
    start = datetime(2018, 1, 1, 22)
    rows = [
        "2018-01-01 21:59:00,0,50,55,55,0,402,1,1,1",
        *[
            f"{start + timedelta(minutes=i)},1,{oat},{sat},55,{command},402,0.7,0,1"
            for i, (oat, sat, command) in enumerate([
                *[(50, 55, 1)] * 5, (33.8, 55, 1), (60, 55, 1), (50, "inf", 1.5), (500, 55, 1),
            ])
        ],
        "2018-01-01 22:09:00,0.5,50,55,55,1,402,0,1,1",
        "2018-01-01 22:10:00,1,50,55,55,,402,0,1,1",
        "2018-01-02 07:10:00,1,50,55,55,1,402,0,1,1",
        "2018-01-02 07:11:00,0,50,55,55,1,402,0,1,1",
        "2018-01-02 07:12:30,0,50,55,55,1,402,0,1,1",
    ]
    source = register(monkeypatch, tmp_path, header + "\n".join(rows) + "\n")

    initial = at(client, "2018-01-01T21:59:00")
    assert initial["mode"] == "OFF" and initial["fan_on"] is False
    assert initial["methods"][0]["reason_code"] == "FAN_OFF"  # SF_CS=1 must not drive the mode.
    holding = at(client, "2018-01-01T22:04:00")
    assert holding["mode"] == "TRANSITION_HOLD" and holding["fan_on"] is True
    assert holding["methods"][0]["method_status"] == "APPLICABLE"
    assert holding["methods"][1]["reason_code"] == "FAN_TRANSITION_HOLD"
    assert holding["methods"][2]["reason_code"] == "PANEL_EXCLUDES_SIGNAL"
    assert holding["mode_policy"]["hold_seconds"] == 300

    for minute in (5, 6):
        point = at(client, f"2018-01-01T22:0{minute}:00")
        assert point["mode"] == "RUNNING" and point["weather_context"] == "BOUNDARY_UNVERIFIED"
        assert point["methods"][1]["reason_code"] == "COOLING_ENABLE_UNOBSERVED"

    anomaly = at(client, "2018-01-01T22:07:00")
    assert anomaly["weather_context"] == "WITHIN_DOCUMENTED_OAT_BAND"
    assert anomaly["physical_context"]["economizer_state"] == "UNKNOWN"
    assert anomaly["physical_context"]["mechanical_cooling_enable"] == "UNKNOWN"
    assert anomaly["source_sha256"] == source["sha256"]
    assert anomaly["issue_class"] == "SIGNAL_RANGE_VIOLATION"
    assert anomaly["cause_status"] == "NOT_ASSESSED" and anomaly["data_status"] == "DEGRADED"
    assert anomaly["methods"][0]["predicate"] == "VIOLATED"
    assert anomaly["methods"][1]["reason_code"] == "METHOD_INPUT_QUALITY"
    assert anomaly["methods"][1]["invalid_signal_ids"] == ["SA_TEMP"]
    quality = {item["canonical_id"]: item for item in anomaly["signal_quality"]}
    assert quality["SA_TEMP"]["flags"] == ["NON_NUMERIC_OR_NON_FINITE"]
    assert quality["CHWC_VLV_DM"]["flags"] == ["COMMAND_OUT_OF_RANGE"]
    assert quality["SA_SP"]["flags"] == ["SEMANTICS_UNVERIFIED"]
    assert quality["MA_TEMP"]["flags"] == ["MISSING_COLUMN"]
    assert "CHWC_VLV" not in quality and "SYS_CTL" not in quality
    assert all(root["canonical_id"] not in {"CHWC_VLV", "SYS_CTL"}
               for method in anomaly["methods"] for root in method["roots"])
    extra = at(client, "2018-01-01T22:07:00", "EXTRA")
    extra_quality = {item["canonical_id"]: item for item in extra["signal_quality"]}
    assert extra_quality["CHWC_VLV"]["origin"] == "EXTRA_SIMULATED" and "SYS_CTL" not in extra_quality
    assert extra["mode"] == anomaly["mode"] and extra["physical_context"] == anomaly["physical_context"]

    suspect = at(client, "2018-01-01T22:08:00")
    assert suspect["weather_context"] == "UNASSESSED"
    assert next(item for item in suspect["signal_quality"] if item["canonical_id"] == "OA_TEMP")["flags"] == [
        "SUSPECT_TEMPERATURE"
    ]
    assert suspect["anomaly_status"] == "NOT_DETECTED_IN_EVALUATED_TESTS"

    unknown = at(client, "2018-01-01T22:09:00")
    assert unknown["mode"] == "UNKNOWN" and unknown["fan_on"] is None
    assert unknown["methods"][0]["reason_code"] == "FAN_STATUS_INVALID"
    assert next(item for item in unknown["signal_quality"] if item["canonical_id"] == "SF_SPD_DM")["flags"] == [
        "NON_BINARY_STATUS"
    ]
    missing = at(client, "2018-01-01T22:10:00")
    assert missing["methods"][0]["reason_code"] == "COMMAND_VALUE_INVALID"
    assert next(item for item in missing["signal_quality"] if item["canonical_id"] == "CHWC_VLV_DM")["flags"] == [
        "MISSING_VALUE"
    ]
    gap = at(client, "2018-01-02T07:10:00")
    assert gap["mode"] == "TRANSITION_HOLD"
    assert gap["time_quality"] == {"elapsed_seconds": 32400, "gap_before": True,
                                  "off_grid_before": False, "missing_samples_before": 539}
    night = modes(client, "2018-01-02T07:10:00")
    assert [segment["mode"] for segment in night["segments"]] == ["TRANSITION_HOLD", "OFF", "OFF"]
    assert night["time_quality"] == {"samples": 3, "gaps": 2, "off_grid_steps": 1, "missing_samples": 539}
    assert night["segments"][0]["gap_before"] and night["segments"][-1]["off_grid_before"]


def test_real_annual_seek_uses_prehistory_and_agrees_with_enclosing_window(client, monkeypatch):
    def reject_full_csv(*_):
        pytest.fail("Annual modes fell back to a full raw DataFrame")

    monkeypatch.setattr(runtime, "read_verified", reject_full_csv)
    timestamp = "2018-07-03T12:00:00"
    point = at(client, timestamp, dataset_id=ANNUAL)
    direct = modes(client, timestamp, ANNUAL, limit=1)
    surrounding = modes(client, "2018-07-03T11:45:00", ANNUAL, limit=30)
    match = next(segment for segment in surrounding["segments"] if segment["first"] <= timestamp <= segment["last"])
    assert point["mode"] == direct["segments"][0]["mode"] == match["mode"] == "RUNNING"
    assert direct["segments"][0]["weather_context"] == point["weather_context"] == match["weather_context"]
    assert direct["next_start"] == "2018-07-03T12:01:00"
    assert point["time_quality"]["elapsed_seconds"] == 60
    assert point["methods"][0]["method_status"] == "APPLICABLE"
    assert point["methods"][1]["reason_code"] == "COOLING_ENABLE_UNOBSERVED"
    assert at(client, timestamp, "EXTRA", ANNUAL)["methods"][2]["reason_code"] == "VALVE_TRACKING_UNVALIDATED"
    assert at(client, "2018-01-02T11:08:00", dataset_id=ANNUAL)["mode"] == "RUNNING"  # Parquet boundary.
    assert at(client, "2018-07-02T12:00:00", dataset_id=ANNUAL)["mode"] == "OFF"  # Observed status.


@pytest.mark.parametrize(("timestamps", "code"), [
    (["2018-01-01T00:00:00", "2018-01-01T00:00:00"], "DUPLICATE_TIMESTAMP"),
    (["2018-01-01T00:01:00", "2018-01-01T00:00:00"], "OUT_OF_ORDER_TIMESTAMP"),
    (["2018-01-01T00:00:00", "nonsense"], "INVALID_TIMESTAMP"),
    (["2018-01-01T00:00:00Z", "2018-01-01T00:01:00Z"], "SOURCE_CLOCK_MISMATCH"),
])
def test_invalid_source_time_fails_closed(client, monkeypatch, tmp_path, timestamps, code):
    register(monkeypatch, tmp_path,
             "Datetime,SF_SPD_DM\n" + "".join(f"{stamp},1\n" for stamp in timestamps))
    response = client.get("/api/v1/modes", params={"dataset_id": "test"})
    assert response.status_code in (409, 422)
    validate_schema(response.json(), "RuntimeError")
    assert response.json()["detail"]["code"] == code


def test_contract_rejects_confirmed_physical_context_and_bad_method_claim(client):
    point = at(client, "2018-07-03T12:00:00", dataset_id=ANNUAL)
    point["physical_context"]["economizer_state"] = "CONFIRMED"
    with pytest.raises(ContractError, match="SCHEMA"):
        validate_schema(point, "RuntimeDiagnostics")
    point["physical_context"]["economizer_state"] = "UNKNOWN"
    point["methods"][1]["method_status"] = "APPLICABLE"
    point["methods"][1]["predicate"] = "VIOLATED"
    with pytest.raises(ContractError, match="SCHEMA"):
        validate_schema(point, "RuntimeDiagnostics")


def test_modes_reject_offset_and_return_empty_past_year_end(client):
    response = client.get("/api/v1/modes", params={"dataset_id": ANNUAL, "start": "2018-07-03T12:00:00Z"})
    assert response.status_code == 422
    validate_schema(response.json(), "RuntimeError")
    injection = client.get("/api/v1/modes", params={"dataset_id": ANNUAL, "SYS_CTL": 1, "mode": "COOLING"})
    assert injection.status_code == 422 and injection.json()["detail"]["code"] == "UNKNOWN_MODES_PARAMETER"
    empty = modes(client, "2019-01-01T00:00:00", ANNUAL)
    assert empty["segments"] == [] and empty["next_start"] is None
    assert empty["time_quality"]["samples"] == 0


def test_valid_calendar_bounds_outside_pandas_range(client):
    early = modes(client, "0001-01-01T00:00:00", ANNUAL, limit=1)
    assert early["segments"][0]["first"] == "2018-01-01T01:00:00"
    late = modes(client, "9999-12-31T23:59:59", ANNUAL)
    assert late["segments"] == []
    response = client.get("/api/v1/diagnostics", params={"dataset_id": ANNUAL, "at": "0001-01-01T00:00:00"})
    assert response.status_code == 404 and response.json()["detail"]["code"] == "NO_SAMPLE"


def test_missing_time_column_fails_closed(client, monkeypatch, tmp_path):
    register(monkeypatch, tmp_path, "SF_SPD_DM,OA_TEMP\n1,50\n")
    response = client.get("/api/v1/modes", params={"dataset_id": "test"})
    assert response.status_code == 422 and response.json()["detail"]["code"] == "MISSING_TIME_COLUMN"
    validate_schema(response.json(), "RuntimeError")
