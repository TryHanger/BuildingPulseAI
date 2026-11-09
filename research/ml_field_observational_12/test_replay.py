"""Adversarial checks of research qualification. No fixtures enter the analysis."""
import csv
from datetime import date, datetime, time, timedelta
import json
import os
from pathlib import Path
from shutil import copy2

import pytest

import replay

ARTIFACTS = Path(os.environ.get("STAGE12_ARTIFACTS", "."))
DAY = date(2019, 3, 8)
OTHER = DAY - timedelta(days=7)


@pytest.fixture
def protocol():
    return replay.load_protocol(ARTIFACTS)


def masks_for(day, protocol):
    return {stamp: (True, True) for stamps in replay.expected_ticks(day, protocol).values() for stamp in stamps}


def schedule_event(day, start, end, ahu="AHU1"):
    return replay.Event(47, ahu, day, datetime.combine(day, start), datetime.combine(day, end), "Fault 9",
                        "PUBLISHER_ANNOTATION", "")


def test_half_open_ticks_and_no_gap_filling(protocol):
    ticks = replay.expected_ticks(DAY, protocol)
    assert [len(ticks[k]) for k in replay.PARTS] == [6, 24, 6]
    assert ticks["PRE"][-1].time() == time(8, 55)
    assert ticks["WINDOW"][0].time() == time(9)
    assert ticks["WINDOW"][-1].time() == time(10, 55)
    assert ticks["POST"][0].time() == time(11)
    assert ticks["POST"][-1].time() == time(11, 25)
    masks = masks_for(DAY, protocol)
    del masks[ticks["POST"][-1]]
    masks[datetime.combine(DAY, time(11, 30))] = (True, True)
    row = replay.qualify(DAY, protocol, [], masks, primary=True)
    assert row["POST_missing_ticks"] == 1 and row["reasons"] == "GRID_INCOMPLETE"


@pytest.mark.parametrize("value", [None, float("nan"), float("inf"), "", "20.0", True])
def test_invalid_sat_excludes_even_post(value, protocol):
    masks = masks_for(OTHER, protocol)
    stamp = datetime.combine(OTHER, time(11, 5))
    masks[stamp] = (replay.finite(value), True)
    row = replay.qualify(OTHER, protocol, [], masks)
    assert row["POST_sat_missing"] == 1 and not row["eligible"]
    assert row["reasons"] == "SAT_NOT_FINITE"


def test_excludes_site_buffer_and_ahu_overlap_with_exact_bounds(protocol):
    masks = masks_for(OTHER, protocol)
    adjacent = schedule_event(OTHER + timedelta(days=1), time(12), time(14), "AHU24")
    overlap = schedule_event(OTHER, time(11, 25), time(11, 40))
    row = replay.qualify(OTHER, protocol, [adjacent, overlap], masks)
    assert row["reasons"] == "SITE_EVENT_DAY_OR_BUFFER|AHU_SCHEDULE_OVERLAP"
    assert row["site_blocking_dates"] == f"{OTHER}|{OTHER + timedelta(days=1)}"
    for boundary in (schedule_event(OTHER, time(8), time(8, 30)),
                     schedule_event(OTHER, time(11, 30), time(12, 30))):
        assert replay.qualify(OTHER, protocol, [boundary], masks)["ahu_overlap_rows"] == ""


def test_context_switch_only_blocks_pre_or_window(protocol):
    masks = masks_for(OTHER, protocol)
    masks[datetime.combine(OTHER, time(11))] = (True, False)
    assert replay.qualify(OTHER, protocol, [], masks)["eligible"]
    masks[datetime.combine(OTHER, time(10, 55))] = (True, False)
    row = replay.qualify(OTHER, protocol, [], masks)
    assert row["WINDOW_context_mismatch"] == 1
    assert row["reasons"] == "COMMAND_CONTEXT_MISMATCH"


def test_stop_and_deterministic_comparator_tie():
    event = {"eligible": True, "date": str(DAY)}
    chosen, status = replay.select(event, [{"eligible": False}], 3)
    assert chosen == [(str(DAY), "event")] and status == "STOP_NO_COMPARATOR"
    assert replay.select({**event, "eligible": False}, [], 3) == ([], "STOP_PRIMARY_INELIGIBLE")
    candidate = lambda weeks: {"eligible": True, "relative_weeks": weeks,
                               "date": str(DAY + timedelta(weeks=weeks))}
    chosen, status = replay.select(event, [candidate(1), candidate(-2), candidate(-1)], 3)
    assert status == "DESCRIPTIVE_OBSERVED"
    assert chosen == [(str(DAY), "event"), (str(OTHER), "comparison"),
                      (str(DAY + timedelta(weeks=1)), "negative_control_1"),
                      (str(DAY - timedelta(weeks=2)), "negative_control_2")]


def test_source_missing_and_wrong_sha(tmp_path, protocol):
    manifest = json.loads((ARTIFACTS / "evidence/SOURCE_PROVENANCE_11.json").read_text())
    with pytest.raises(replay.Stop, match="STOP_SOURCE_UNAVAILABLE AHU1.xlsx"):
        replay.verify_sources(tmp_path, ARTIFACTS, protocol)
    with (tmp_path / "AHU1.xlsx").open("wb") as bad:
        bad.truncate(manifest["files"]["AHU1.xlsx"]["bytes"])
    with pytest.raises(replay.Stop, match="STOP_SOURCE_SHA_MISMATCH AHU1.xlsx"):
        replay.verify_sources(tmp_path, ARTIFACTS, protocol)


def test_reject_required_value_as_a_sensor(protocol):
    with pytest.raises(replay.Stop, match="STOP_CHANNEL_ROLE_MISMATCH"):
        replay.signal_columns({**protocol, "sat": protocol["sat"].replace("real_value", "required_value")})
    with pytest.raises(replay.Stop, match="STOP_CHANNEL_ROLE_MISMATCH"):
        replay.signal_columns({**protocol, "secondary": [protocol["commands"][0]]})


def test_mask_telemetry_never_reads_annotations(monkeypatch, protocol):
    def cells(raw, config, fields):
        assert fields == (protocol["sat"], *protocol["required_context"])
        yield datetime.combine(DAY, time(9)), 21.0, 1, 0, 1

    monkeypatch.setattr(replay, "telemetry", cells)
    _, _, masks = replay.read_masks(None, protocol)
    assert list(masks.values()) == [(True, True)]


def test_labels_cannot_change_numbers_and_no_comparison_has_no_contrast(tmp_path, protocol):
    for name in replay.PREPARED_FILES:
        copy2(ARTIFACTS / name, tmp_path / name)

    def reseal():
        (tmp_path / "PREPARED_12.sha256").write_text(
            "".join(f"{replay.digest(tmp_path / name)}  {name}\n" for name in replay.PREPARED_FILES))

    reseal()
    replay.calculate(tmp_path, protocol)
    original = (tmp_path / "DESCRIPTIVE_12.csv").read_bytes()
    (tmp_path / "PUBLISHER_ANNOTATIONS_12.csv").write_text("corrupt_labels\nnever_a_feature\n")
    with pytest.raises(replay.Stop, match="STOP_PREPARATION_SHA_MISMATCH"):
        replay.calculate(tmp_path, protocol)
    reseal()
    replay.calculate(tmp_path, protocol)
    assert (tmp_path / "DESCRIPTIVE_12.csv").read_bytes() == original
    selection_file = tmp_path / "SELECTION_12.json"
    selection = json.loads(selection_file.read_text())
    replay.dump(selection_file, {**selection, "selected": {str(DAY): "event"}, "status": "STOP_NO_COMPARATOR"})
    slice_path = tmp_path / "RAW_SLICE_12.csv"
    with slice_path.open() as stream:
        events = [row for row in csv.DictReader(stream) if row["window_id"] == "event"]
    replay.table(slice_path, events)
    reseal()
    replay.calculate(tmp_path, protocol)
    no_comparison = json.loads((tmp_path / "RESULT_12.json").read_text())
    assert no_comparison["status"] == "STOP_NO_COMPARATOR"
    assert no_comparison["event_minus_comparison_change_C"] is None
    assert set(no_comparison["sat_window_minus_pre_C"]) == {"event"}
