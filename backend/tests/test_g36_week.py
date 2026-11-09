import csv
import hashlib
import io

import pytest

from backend.app.services import g36_benchmark, g36_week as week, g36_week_benchmark
from contracts.evidence_v1 import validate_schema


def payload(rows, *, sat_header=None, omit=None):
    header = ["time (s)", *week.BASIC.values(), *week.WEATHER, g36_benchmark.ORACLE, "ground_truth"]
    if sat_header:
        header[1] = sat_header
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    positions = [i for i, name in enumerate(header) if name != omit]
    writer.writerow([header[i] for i in positions])
    for row in rows:
        writer.writerow([row[i] for i in positions])
    return buffer.getvalue().encode()


def row(time, *, sat=300, fan=1, dry=299, wet=295, oracle=0, truth="A"):
    return [time, sat, 290, 298, fan, .9, 0, dry, wet, oracle, truth]


def test_projector_rejects_missing_and_wrong_unit():
    sample = [row(week.FIRST)]
    for raw in [payload(sample, omit=week.WEATHER[0]), payload(sample, sat_header="AHU Supply Air Temperature (C)")]:
        with pytest.raises(ValueError, match="BASIC/weather"):
            list(week.project_samples(raw))


def test_minute_hold_gap_nan_weather_and_fan_transition():
    rows = [row(60*i) for i in range(11)]
    rows += [row(720), row(780, sat="NaN"), row(840, fan=0), row(900, dry="NaN"), row(960, dry=290, wet=300)]
    trace = list(week.score(week.project_samples(payload(rows))))
    assert [point["time_s"] for point in trace if point["confirmed"]] == [600]
    assert trace[10]["confirmed_start"]
    assert [p["reason"] for p in trace[-5:]] == [
        "APPLICABLE", "INVALID_INPUT", "FAN_OFF", "UNKNOWN_WEATHER_CONTEXT", "UNKNOWN_WEATHER_CONTEXT"
    ]


def test_oracle_and_truth_are_outside_projection_and_score():
    rows = [row(60*i) for i in range(12)]
    altered = [row(60*i, oracle=1, truth="ALTERED") for i in range(12)]
    assert list(week.project_samples(payload(rows))) == list(week.project_samples(payload(altered)))
    assert list(week.score(week.project_samples(payload(rows)))) == list(week.score(week.project_samples(payload(altered))))


@pytest.mark.parametrize("mode", ["NaN", "4", "999"])
def test_optional_mode_and_coil_channels_are_outside_basic(mode):
    raw = payload([row(week.FIRST)])
    header, values = list(csv.reader(io.StringIO(raw.decode())))
    # A falsely named coil value reuses SAT, pressure has the wrong unit, and the mode is untrusted.
    header += ["Cooling Mode Control Signal (1: free cooling , 2: partial mechanical, 3: full mechanical, 4: off)",
               "Cooling Coil Discharge Air Temperature (°K)",
               "Chilled Water Flow Rate of the Chilled Water Loop into the Cooling Coil (kg/s)",
               "Cooling Coil Heat Transfer Rate (W)", "Measured AHU Supply Air Duct Static Pressure (psi)"]
    values += [mode, values[1], "0.7", "500", "2"]
    buffer = io.StringIO(newline="")
    csv.writer(buffer).writerows([header, values])
    projected = list(week.project_samples(buffer.getvalue().encode()))
    assert projected == list(week.project_samples(raw))  # Missing supplemental fields are allowed.
    assert set(projected[0]) == {"time_s", "weather_known", *week.BASIC}
    assert list(week.score(projected)) == list(week.score(week.project_samples(raw)))


def test_api_direct_seek_and_last_two_ticks(client, tmp_path, monkeypatch):
    monkeypatch.setattr(g36_benchmark.runtime.settings, "DATA_ROOT", tmp_path)
    directory = tmp_path/"g36-1wk"
    directory.mkdir()
    path = directory/"CooCoiValStuck_0.csv"
    url = "/api/v1/g36-benchmark"
    params = {"dataset": "g36-1wk"}
    assert client.get(url, params=params).status_code == 404
    n = 13
    raw = payload([row(week.FIRST+i*60, oracle=int(i >= n-2)) for i in range(n)])
    path.write_bytes(raw)
    monkeypatch.setattr(week, "TICKS", n)
    monkeypatch.setattr(week, "LAST", week.FIRST+(n-1)*60)
    monkeypatch.setitem(week.SOURCES, path.name, hashlib.sha256(raw).hexdigest())
    other_release = client.get(url, params={**params, "start": week.LAST - 60, "panel": "EXTRA_SIMULATED"}).json()
    assert [point["reference_oracle"] for point in other_release["points"]] == [1, 1]
    assert all("source_oracle_status" not in point for point in other_release["points"])
    monkeypatch.setitem(g36_week_benchmark.ORACLE_EXCEPTIONS, ("VALVE_CLOSED", week.SOURCES[path.name]),
                        frozenset({week.LAST - 60, week.LAST}))
    with monkeypatch.context() as basic_guard:
        def forbidden(*_):
            pytest.fail("BASIC must never call the oracle reader")
        basic_guard.setattr(g36_week_benchmark, "read_oracle", forbidden)
        full = client.get(url, params=params).json()
    assert (full["paired_causal_gate"], full["unpaired_descriptive_gate"], full["runs_per_scenario"]) == ("STOP", "PASS", 1)
    assert full["cooling_enable"] == "UNKNOWN" and full["cause_status"] == "NOT_ASSESSED"
    validate_schema(full, "G36BenchmarkWindow")
    assert full["summaries"][0]["samples"] == n
    direct = client.get(url, params={**params,"start":week.FIRST+600,"limit":3}).json()
    assert direct["points"] == full["points"][10:]
    assert direct["points"][0]["confirmed_start"]
    assert all(p["reference_oracle"] is None for p in direct["points"])
    extra = client.get(url, params={**params,"start":week.LAST-60,"panel":"EXTRA_SIMULATED"}).json()
    assert [p["reference_oracle"] for p in extra["points"]] == [1,1]
    validate_schema(extra, "G36BenchmarkWindow")
    assert all("source_oracle_status" not in p for p in full["points"])
    assert [p["source_oracle_status"] for p in extra["points"]] == ["SOURCE_ORACLE_EXCEPTION"] * 2
    extra_basic = [{**p, "reference_oracle": None} for p in extra["points"]]
    for point in extra_basic:
        point.pop("source_oracle_status")
    assert extra_basic == full["points"][-2:]
    assert client.get(url, params={**params,"label":"fake"}).status_code == 422
    assert client.get(url, params={**params,"scenario":"DUCT_LEAK"}).status_code == 422
    with pytest.raises(ValueError, match="Unregistered"):
        week.verified_payload(directory/"renamed.csv")
    (directory/"BaselineSystem.csv").write_bytes(raw)
    assert client.get(url, params={**params,"scenario":"NOMINAL"}).status_code == 409
    path.write_bytes(raw.replace(b",0,A",b",1,A",1))
    assert client.get(url, params=params).status_code == 409
