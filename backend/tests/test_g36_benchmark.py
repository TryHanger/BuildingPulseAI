import csv
import hashlib

from backend.app.services import g36_benchmark as g36
from contracts.evidence_v1 import validate_schema

URL = "/api/v1/g36-benchmark"


def point(time, **changes):
    return {**dict(time_s=time, sat_k=302, setpoint_k=295, mat_k=301, fan_status=1, weather_known=True,
                   cooling_command=0.8, heating_command=0), **changes}


def test_threshold_persistence_and_abstention():
    rows = [point(0, sat_k=297), point(300), point(600), point(900), point(1500),
            point(1800), point(2100, fan_status=0), point(2400, mat_k=None)]
    result = list(g36.evaluate(rows))
    assert [item["confirmed"] for item in result] == [False, False, False, True, False, False, False, False]
    assert not result[0]["point_exceeds"]
    assert result[-2]["reason"] == "FAN_OFF"
    assert result[-1]["reason"] == "INVALID_INPUT"
    assert result[-1]["residual_k"] is None


def test_label_and_oracle_cannot_change_baseline():
    rows = [point(time) for time in (0, 300, 600)]
    altered = [{**row, "reference_oracle": 0.0, "label": "SIMULATED_VALVE_CLOSURE_INTERVAL"} for row in rows]
    assert list(g36.evaluate(rows)) == list(g36.evaluate(altered))


def test_api_windows_and_explicit_oracle(client, monkeypatch, tmp_path):
    monkeypatch.setattr(g36.runtime.settings, "DATA_ROOT", tmp_path)
    assert client.get(URL).status_code == 404
    directory = tmp_path / "g36-5wk"
    directory.mkdir()
    filename = g36.SOURCES["VALVE_CLOSED"][0]
    raw = directory / filename
    with raw.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["time (s)", *g36.BASIC.values(), g36.ORACLE, *g36.WEATHER])
        for stamp in [g36.START - g36.STEP, g36.START, g36.START + g36.STEP, g36.START + 2*g36.STEP]:
            sample = point(stamp)
            writer.writerow([stamp, *(sample[key] for key in g36.BASIC), 0.25, 300, 295])
    monkeypatch.setitem(g36.SOURCES, "VALVE_CLOSED", (filename, hashlib.sha256(raw.read_bytes()).hexdigest()))
    basic = client.get(URL).json()
    extra = client.get(URL, params={"panel": "EXTRA_SIMULATED"}).json()
    validate_schema(basic, "G36BenchmarkWindow")
    validate_schema(extra, "G36BenchmarkWindow")
    assert basic["provenance"] == "SIMULATED_BENCHMARK"
    assert [row["confirmed"] for row in basic["points"]] == [False, True, True]
    assert [row["reference_oracle"] for row in basic["points"]] == [None]*3
    assert [row["reference_oracle"] for row in extra["points"]] == [0.25]*3
    assert [{**row, "reference_oracle": None} for row in extra["points"]] == basic["points"]
    # A summary starts the 600 s rule afresh at the documented period boundary.
    assert basic["summaries"][1]["confirmed_samples"] == 1
    assert client.get(URL, params={"source_label": "fake"}).status_code == 422
    assert client.get(URL, params={"limit": 289}).status_code == 422
    raw.write_bytes(raw.read_bytes().replace(b",0.25,", b",0.75,", 1))
    assert client.get(URL).status_code == 409


def test_persistence_uses_elapsed_seconds_and_resets_across_both_grids():
    for step in (60, 300):
        samples = [point(i*step) for i in range(600//step + 1)]
        assert [row["confirmed"] for row in g36.evaluate(samples, step=step)] == [False]*(600//step) + [True]
        gap = samples + [point(600+step*2)]
        assert not list(g36.evaluate(gap, step=step))[-1]["confirmed"]


def test_valid_mode_and_weather_intersection_resets_unstable_symptom():
    rows = [point(0), point(300, weather_known=False), point(600), point(900, fan_status=None), point(1200),
            point(1500, sat_k=297), point(1800), point(2100, fan_status=0)]
    result = list(g36.evaluate(rows))
    assert [item["method_status"] for item in result] == [
        "APPLICABLE", "INCONCLUSIVE", "APPLICABLE", "INCONCLUSIVE",
        "APPLICABLE", "APPLICABLE", "APPLICABLE", "INAPPLICABLE",
    ]
    assert result[1]["weather_status"] == result[3]["fan_mode"] == "UNKNOWN"
    assert result[1]["predicate"] == result[3]["predicate"] == "INDETERMINATE"
    assert all(not item["confirmed"] for item in result)
    summary = g36.summarize("PLACEBO", rows)
    assert summary["applicable"] == 5
    assert summary["point_exceedances"] == 4
    assert summary["symptom_starts"] == 0


def test_comparison_fails_closed_without_all_files(client, monkeypatch, tmp_path):
    monkeypatch.setattr(g36.runtime.settings, "DATA_ROOT", tmp_path)
    assert client.get(URL + "/comparison").status_code == 404
    assert client.get(URL + "/comparison", params={"reference_oracle": 0.5}).status_code == 422
