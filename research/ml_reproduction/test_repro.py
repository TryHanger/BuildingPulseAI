from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from backend.app.services.g2_mode import evaluate_modes
from research.ml_reproduction.brick import derive
from research.ml_reproduction.run import MODES, calibration, daily, fan_running, plans, split, summarize, zscore
from research.ml_reproduction.sources import BASELINE, CASES


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = yaml.safe_load((ROOT / "research/g0-g1/SIGNAL_MAP_V1.yaml").read_text())["signals"]
TTL = ROOT / "research/g0-g1/logs/LBNL_FDD_Data_Sets_SDAHU_ttl.ttl"


def test_graph_target_exclusion_and_both_sys_ctl_channels():
    targets, path = derive(TTL, list(REGISTRY))
    assert path == "BRICK_GRAPH"
    assert set(targets) == {"SA_TEMP", "MA_TEMP", "RA_TEMP", *(f"ZONE_TEMP_{i}" for i in range(1, 6))}
    assert all(target not in names for target, names in targets.items())
    assert "OA_TEMP" in targets["SA_TEMP"] and "RA_DMPR" in targets["SA_TEMP"]
    paper, _, _ = plans(targets, list(REGISTRY), REGISTRY, MODES[0])
    assert {"SYS_CTL", "occupancy"} <= set(paper["SA_TEMP"])
    for mode in MODES[1:]:
        features, raw, counts = plans(targets, [*REGISTRY, "fault_label", "severity", "oracle", "Datetime"], REGISTRY, mode)
        forbidden = {"SYS_CTL", "occupancy", "fault_label", "severity", "oracle", "Datetime"}
        assert not (forbidden & set(raw))
        assert all(not (forbidden & set(names)) and target not in names for target, names in features.items())
        if mode.startswith("PRODUCT_BASIC"):
            assert min(counts.values()) >= 3
            assert not ({"CHWC_VLV", "OA_DMPR", "RA_DMPR", "SA_SP", "SA_SPSPT"} & set(raw))
        if mode == MODES[-1]:
            assert not any(REGISTRY[name]["kind"] == "COMMAND" for name in raw)
    unsupported, _, _ = plans({"SA_TEMP": ["OA_TEMP", "OA_DMPR", "SYS_CTL"]}, list(REGISTRY), REGISTRY, MODES[2])
    assert unsupported == {}


def test_fallback_uses_only_nonexogenous_targets(tmp_path):
    path = tmp_path / "empty.ttl"
    path.write_text("")
    targets, method = derive(path, ["FCU_MAT", "FCU_OA_TEMP", "FCU_DAT_SPT", "pump"])
    assert method == "ALGORITHM_1_FALLBACK" and list(targets) == ["FCU_MAT"]
    assert "FCU_MAT" not in targets["FCU_MAT"]


def test_mode_is_causal_and_matches_runtime():
    times = pd.date_range("2018-10-02", periods=15, freq="min").delete(7)
    fan = [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
    result = evaluate_modes((time, {"SF_SPD_DM": status, "OA_TEMP": 68.0}) for time, status in zip(times, fan, strict=True))
    assert fan_running(times, fan).tolist() == [row.fan_state == "RUNNING" for row in result]
    assert not fan_running(times[:5], fan[:5]).any()


def test_dates_and_cutoffs_are_disjoint_for_strict():
    times = pd.date_range("2018-01-01", periods=20, freq="12h")
    frame = pd.DataFrame(index=times)
    mask = np.arange(len(times)) % 2 == 1
    first, second = split(frame, mask, False)
    assert (first, second) == (pd.Timestamp("2018-01-07"), pd.Timestamp("2018-01-09"))
    cutoff, negative_cutoff = split(frame, mask, True)
    assert cutoff == negative_cutoff == times[17]
    assert not set(times[times < first].date) & set(times[(times >= first) & (times < second)].date)


def test_absolute_residual_daily_mean_then_max_and_threshold():
    abs_error = np.abs(np.array([-1, 3, -5, 7]))
    center, scale = calibration(abs_error)
    assert center == 4 and scale == pytest.approx(np.sqrt(5))
    assert calibration(np.ones(8)) == (1.0, None)
    assert np.isnan(zscore([1, 1], 1, None)).all()
    index = pd.DatetimeIndex(["2018-01-01 01:00", "2018-01-01 01:01", "2018-01-02 01:00"])
    per_target = daily({"A": [0, 8, 3], "B": [6, 0, 2]}, index)
    assert per_target.max(axis=1).tolist() == [4, 3]
    negative = pd.DataFrame({"raw": [3], "z": [3]}, index=per_target.index[:1])
    positive = pd.DataFrame({"raw": [4], "z": [4]}, index=per_target.index[1:])
    assert summarize(negative, positive)["auc"] == 1.0
    assert summarize(negative, positive)["fp"] == 0


def test_table2_has_twelve_distinct_scenario_members():
    assert len(CASES) == 12 and BASELINE in CASES
    assert not any(name.startswith("oa_bias") or name.endswith("_short.csv") for name in CASES)
    assert sum("leakage" in name for name in CASES) == 1
    assert sum("coi_bias" in name for name in CASES) == 4
