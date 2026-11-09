import numpy as np
import pandas as pd

from research.g51.qualify_interventions import (
    COMMON, REFERENCE_STATUS, bounds, clusters, features, interval_profile, overlap, point_lineage, valid_telemetry,
)


def test_publisher_half_open_bounds_and_unannotated_clock():
    index = pd.date_range("2013-10-31 09:00", periods=5, freq="30s")
    first, last = bounds(index, index[1], index[3])
    assert list(index[first:last]) == [index[1], index[2]]
    assert REFERENCE_STATUS == "UNKNOWN_UNANNOTATED"
    assert bounds(index, index[0] - pd.Timedelta(hours=2), index[0]) == (0, 0)


def test_overlap_and_whole_day_clusters_across_ahu_and_midnight():
    stamps = pd.date_range("2013-10-31 23:30", periods=5, freq="15min")
    assert not overlap(stamps[0], stamps[1], stamps[1], stamps[2])
    assert overlap(stamps[0], stamps[2], stamps[1], stamps[3])
    grouped = clusters([
        {"valid_interval": True, "ahu": 9, "start": stamps[0], "end": stamps[1]},
        {"valid_interval": True, "ahu": 10, "start": stamps[3], "end": stamps[4]},
    ])
    assert grouped[stamps[0].normalize()] == grouped[stamps[4].normalize()]


def test_missing_and_gap_exclude_window():
    index = pd.DatetimeIndex(["2013-10-31 09:00:00", "2013-10-31 09:00:30", "2013-10-31 09:01:30"])
    frame = pd.DataFrame({"SAT": [10, np.nan, 12]}, index=index)
    profile = interval_profile(frame, index[0], index[-1]+pd.Timedelta(seconds=30), pd.Timedelta(seconds=30))
    assert profile["boundary_pass"]
    assert profile["missing_cells"] == profile["gap_steps"] == 1
    assert not valid_telemetry(profile)


def test_labels_commands_and_duplicate_sensor_are_excluded():
    data = {f"AHU9ahu{key}": [1., 2.] for key in (*COMMON, "MaTemp", "CcValve", "ZoneTemp")}
    frame = pd.DataFrame({**data, "fault_type": ["F", "F"], "start": [0, 1], "magnitude": [10, 20]})
    assert list(features(frame, 9)) == [f"AHU9ahu{key}" for key in COMMON]
    role = {row["native_point"]: row for row in point_lineage(9, pd.DataFrame(data))}
    assert role["AHU9ahuCcValve"]["independent_feedback"] == "UNKNOWN"
    assert role["AHU9ahuCcValve"]["use"] == "EXCLUDED_POTENTIAL_INJECTION_PATH"
    assert role["AHU9ahuMaTemp"]["use"] == "EXCLUDED_DUPLICATE"
    assert role["magnitude"]["use"] == "EXCLUDED_FROM_FEATURES"
