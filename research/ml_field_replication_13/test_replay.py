"""Adversarial fixtures exercise qualification only. They are never analysis inputs."""
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
from shutil import copy2

import pytest

from research.ml_field_observational_12 import replay as base
from research.ml_field_replication_13 import replay

ARTIFACTS = Path(os.environ.get("STAGE13_ARTIFACTS", "."))


@pytest.fixture
def config():
    return replay.protocol_from(ARTIFACTS)


def event(start, end, number=29, ahu="AHU23", label="Fault 6"):
    return base.Event(number, ahu, start.date(), start, end, label, "evaluation-only", "")


@pytest.mark.parametrize("minutes", [30, 120])
def test_native_half_open_bounds(config, minutes):
    start = datetime(2019, 3, 15, 11, 30)
    end = start + timedelta(minutes=minutes)
    info = replay.event_protocol(config, event(start, end))
    ticks = base.expected_ticks(start.date(), info)
    assert [len(ticks[p]) for p in base.PARTS] == [6, minutes // 5, 6]
    assert ticks["PRE"][-1] == start - timedelta(minutes=5)
    assert ticks["WINDOW"][0] == start
    assert ticks["WINDOW"][-1] == end - timedelta(minutes=5)
    assert ticks["POST"][0] == end
    assert ticks["POST"][-1] == end + timedelta(minutes=25)


def test_overlap_boundary_and_labels(config):
    start = datetime(2019, 3, 15, 11, 30)
    end = start + timedelta(minutes=30)
    target = event(start, end)
    info = replay.event_protocol(config, target)
    stamps = base.expected_ticks(start.date(), info)
    masks = {tick: (True, True) for ticks in stamps.values() for tick in ticks}
    adjacent = event(end + timedelta(minutes=30), end + timedelta(minutes=35), 88)
    overlaps = event(end + timedelta(minutes=25), end + timedelta(minutes=35), 89)
    assert base.qualify(target.day, info, [target, adjacent], masks, primary=True)["eligible"]
    result = base.qualify(target.day, info, [target, overlaps], masks, primary=True)
    assert result["reasons"] == "AHU_SCHEDULE_OVERLAP"
    assert result == base.qualify(target.day, info, [event(start, end, label="changed annotation"),
                                                  overlaps], masks, primary=True)


def test_clock_and_numeric_mask_columns_exclude_labels(config, monkeypatch):
    item = event(datetime(2019, 3, 15, 11, 30), datetime(2019, 3, 15, 12))
    info = replay.event_protocol(config, item)

    def read(raw, protocol, columns):
        assert columns == (config["sat"], *config["required_context"])
        yield item.start, 0, 1, 0, 1
        yield item.start + timedelta(minutes=5), float("nan"), 1, 0, 1
        yield item.start + timedelta(minutes=10), 20, 1, 0, 0

    monkeypatch.setattr(base, "telemetry", read)
    _, _, flags = base.read_masks(None, info)
    assert list(flags.values()) == [(True, True), (False, True), (True, False)]


def test_role_checks(config):
    for mutation in ({"sat": "signal__required_value__heater_valve"},
                     {"status": "logic__required_value__fan_fresh_air"},
                     {"commands": [config["sat"]]}):
        with pytest.raises(base.Stop, match="STOP_CHANNEL_ROLE_MISMATCH"):
            base.signal_columns({**config, **mutation})


def test_choose_comparator_is_outcome_blind_and_earlier_breaks_tie():
    eligible = [{"date": "2019-03-22", "relative_weeks": 1, "eligible": True},
                {"date": "2019-03-08", "relative_weeks": -1, "eligible": True}]
    assert replay.choose_comparison(eligible)[1] == "2019-03-08"
    assert replay.choose_comparison([{**row, "eligible": False} for row in eligible])[1] is None


def test_same_site_counts_unique_ahu_per_type_and_excludes_short_and_comparison():
    def sample(ahu, fault, *, sign="negative", cohort="main_120m", kind="event"):
        return {"ahu": ahu, "fault": f"Fault {fault}", "sign": sign, "cohort": cohort, "kind": kind}

    rows = [sample("AHU1", 4)] * 2 + [sample("AHU18", 4, kind="comparison"), sample("AHU1", 6),
                                     sample("AHU23", 6, cohort="short_30m"), sample("AHU24", 6)]
    assert replay.decision_from(rows)[0] == "STOP_INSUFFICIENT_NATIVE_DATA"
    assert replay.decision_from(rows + [sample("AHU18", 4)])[0] == "DESCRIPTIVE_MULTI_AHU_OBSERVED"
    for sign in ("positive", "zero"):
        assert replay.decision_from(rows + [sample("AHU18", 4, sign=sign)])[0] == "HETEROGENEOUS_OBSERVATIONS"
    assert {"SAME_SITE_TWO_DATES", "NOT_INDEPENDENT_BUILDING_VALIDATION"} <= set(replay.LIMITS)


def test_mislabeled_post_tick_changes_neither_numeric_results_nor_selection(tmp_path, config):
    for name in replay.FILES:
        copy2(ARTIFACTS / name, tmp_path / name)
    replay.seal(tmp_path)
    replay.calculate(tmp_path, config)
    selected = (tmp_path / replay.SELECTION).read_bytes()
    metrics = (tmp_path / "DESCRIPTIVE_EPISODES_13.csv").read_bytes()
    annotations = replay.read_csv(tmp_path / replay.ANN)
    row = next(r for r in annotations if r["kind"] == "event" and r["partition"] == "POST")
    row["publisher_fault_evaluation_only"] = "deliberately conflicting publication label"
    base.table(tmp_path / replay.ANN, annotations)
    with pytest.raises(base.Stop, match="STOP_SOURCE_PREPARATION_SHA"):
        replay.calculate(tmp_path, config)
    replay.seal(tmp_path)
    replay.calculate(tmp_path, config)
    assert (tmp_path / replay.SELECTION).read_bytes() == selected
    assert (tmp_path / "DESCRIPTIVE_EPISODES_13.csv").read_bytes() == metrics


def test_originals_missing_and_checksum_error(tmp_path, config):
    first, meta = next(iter(json.loads((ARTIFACTS / "evidence/SOURCE_PROVENANCE_11.json").read_text())["files"].items()))
    with pytest.raises(base.Stop, match="STOP_SOURCE_UNAVAILABLE"):
        base.verify_sources(tmp_path, ARTIFACTS, config)
    with (tmp_path / first).open("wb") as stream:
        stream.truncate(meta["bytes"])
    with pytest.raises(base.Stop, match="STOP_SOURCE_SHA_MISMATCH"):
        base.verify_sources(tmp_path, ARTIFACTS, config)
