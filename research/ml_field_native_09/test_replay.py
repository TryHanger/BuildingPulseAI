from datetime import datetime, timedelta
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient
from openpyxl import Workbook
import pytest

from backend.app.main import app
from research.ml_field_native_09 import replay
from research.ml_field_native_09.rules import TAGS, Tick, apply, summarize


ORIGIN = datetime(2019, 3, 1)


def at(n, supply=1, exhaust=1, heat=1, cool=0):
    return apply(Tick(ORIGIN + timedelta(minutes=5 * n), supply, exhaust, heat, cool))


@pytest.mark.parametrize("seconds,reason", [
    (0, "DUPLICATE_OR_REVERSED"), (-300, "DUPLICATE_OR_REVERSED"),
    (60, "NOT_NATIVE_300S"), (600, "NOT_NATIVE_300S"),
])
def test_bad_clock(seconds, reason):
    with pytest.raises(replay.Stop, match=reason):
        replay.verify_clock(ORIGIN, ORIGIN + timedelta(seconds=seconds))


def test_half_open_off_grid_and_open_interval():
    rows = [at(n) for n in range(5)]
    times = [row.tick.time for row in rows]
    reason, pre, window = replay.window_at(times, rows, ORIGIN + timedelta(minutes=7), times[4])
    assert (reason, pre, window) == ("", rows[:2], rows[2:4])
    assert replay.window_at(times, rows, ORIGIN, None)[0] == "UNKNOWN_CLOCK_OPEN_OR_INVALID_INTERVAL"
    assert replay.window_at(times, rows, ORIGIN - replay.STEP, times[4])[0] == "UNKNOWN_CLOCK_OUT_OF_GRID"


def test_baseline_off_missing_and_inapplicable():
    off = [at(n, 0, 0) for n in range(4)]
    result = summarize(off[:2], off[2:], "paired_state", ORIGIN)
    assert (result["status"], result["baseline"], result["change"]) == ("OBSERVED", "TWO_OFF", "ABSTAIN")
    for row, status in [(at(2, None, None), "INSUFFICIENT_DATA"), (at(2, 0, 0, 0), "NOT_APPLICABLE")]:
        result = summarize(off[:2], [row, row], "paired_state", ORIGIN)
        assert (result["status"], result["change"]) == (status, "ABSTAIN")


def test_two_consecutive_and_transition_bound():
    pre = [at(0), at(1)]
    off = [at(2, 0, 0), at(3, 0, 0)]
    result = summarize(pre, off, "paired_state", off[0].tick.time)
    assert result["change"] == "BAS_ON_TO_OFF_OBSERVED"
    assert (result["last_on_exclusive"], result["first_off_inclusive"], result["confirm_off"]) == (
        pre[-1].tick.time, off[0].tick.time, off[1].tick.time)
    assert result["longest_off_sample_span_seconds"] == 300
    assert summarize(pre, off[:1], "paired_state", ORIGIN)["change"] == "ABSTAIN"
    separated = [off[0], at(3, None), at(4, 0, 0)]
    assert summarize(pre, separated, "paired_state", ORIGIN)["change"] == "ABSTAIN"
    assert at(2, 0, 1).paired_state == "DISAGREE"


def test_command_and_fault_removed_or_present_do_not_change_inputs(tmp_path, monkeypatch):
    monkeypatch.setattr(replay, "END", ORIGIN + replay.STEP)
    # Two-row adversarial sheets intentionally fail the production row-count
    # gate, but recorded Tick inputs must agree before that gate.
    streams = []
    for label_header in (True, False):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Sheet1"
        header = ["Time", "signal__required_value__fan_fresh_air", *TAGS[1:]]
        if label_header:
            header.append("fault")
        sheet.append(header)
        for n in range(2):
            sheet.append([ORIGIN + n * replay.STEP, 0, 0, 1, 0] + (["Fault 12"] if label_header else []))
        path = tmp_path / f"{label_header}.xlsx"
        workbook.save(path)
        captured = []

        def capture(tick):
            captured.append(tick)
            return apply(tick)

        monkeypatch.setattr(replay, "apply", capture)
        with pytest.raises(replay.Stop, match="ROW_COUNT"):
            replay.read_fans(path)
        streams.append(captured)
    assert streams[0] == streams[1]
    assert [tick.supply for tick in streams[0]] == [None, None]
    assert all(apply(tick).paired_state == "INSUFFICIENT_DATA" for tick in streams[0])


@pytest.mark.parametrize("exists", [False, True])
def test_missing_or_altered_publisher_original(tmp_path, exists):
    base = Path(__file__).parents[1] / "ml_field_data_08"
    protocol = tmp_path / "protocol"
    ledger = tmp_path / "ledger"
    protocol.write_text("frozen")
    ledger.write_text("frozen")
    from unittest.mock import patch
    manifest = base / "PUBLISHER_FILES_V1.json"
    if exists:
        import json
        first = next(iter(json.loads(manifest.read_text())["files"]))
        with ZipFile(tmp_path / first, "w") as workbook:
            workbook.writestr("not original", "changed")
    with patch.object(replay, "PROTOCOL_SHA", replay.source.sha(protocol)), patch.object(
        replay, "LEDGER_SHA", replay.source.sha(ledger)
    ):
        with pytest.raises(replay.Stop, match="STOP_SOURCE_PROVENANCE"):
            replay.run(tmp_path, tmp_path / "paper", ledger, protocol, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_site_wide_intervention_and_next_day():
    intervention = ORIGIN.date()
    assert replay.excluded_day(intervention, {intervention})
    assert replay.excluded_day(intervention + timedelta(days=1), {intervention})
    assert not replay.excluded_day(intervention + timedelta(days=2), {intervention})


def test_no_research_replay_route_or_incident_authorization():
    client = TestClient(app)
    assert client.get("/research/field-data").status_code == 404
    assert not any("field-native" in p or "field-data" in p for p in app.openapi()["paths"])
    from research.ml_domain_shift_07.test_applicability import BASE, MATCH
    response = client.post(BASE + "/applicability", json=MATCH)
    assert response.status_code == 200
    result = response.json()
    assert not any(result[key] for key in ("incident_eligible", "inference_authorized", "deployment_eligible"))
