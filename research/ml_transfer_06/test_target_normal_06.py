"""Negative controls and a non-predictive integration check on the pinned reference."""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.ml_transfer_05.contract import ContractError, load_protocol
from research.ml_transfer_06 import target_normal_06 as normal


@pytest.fixture
def protocol():
    return load_protocol()


@pytest.fixture
def receipt():
    return {
        "train_support_degF": {"MA_TEMP": [60, 90], "OA_TEMP": [60, 90], "RA_TEMP": [60, 90]},
        "calibration": {method: {"center": 0.5, "scale": 0.5} for method in normal.METHODS},
    }


class ModelStub:
    calls = 0

    def predict(self, x, *, validate_features, num_threads):
        self.calls += 1
        assert tuple(x) == normal.FEATURES
        assert validate_features and num_threads == 1
        return np.full(len(x), 56.0)


RIDGE_STUB = np.zeros(3), np.ones(3), np.zeros(3), 55.5


def synthetic(size=1440):
    seconds = 17625600 + 60 * np.arange(size)
    labels = pd.Series(np.arange(size) // 1440)
    frame = pd.DataFrame({"MA_TEMP": 70 + np.arange(size) % 3 / 3,
                          "OA_TEMP": 75 + np.arange(size) % 7 / 7, "RA_TEMP": 72,
                          "SA_TEMP": 55, "SA_TEMPSPT": 55, "SF_STATUS": 1})
    return seconds, labels, frame, pd.Series([3] * size), pd.Series([False] * size)


@pytest.mark.parametrize("role", ["target_probe", "fault", "source", "target_normal", ""])
def test_reject_role_before_any_files(role, tmp_path, monkeypatch):
    def unexpected(*_args, **_kwargs):
        pytest.fail("file path was accessed for an unauthorized role")

    monkeypatch.setattr(normal, "checked", unexpected)
    with pytest.raises(ContractError, match="STOP_ROLE_NOT_AUTHORIZED"):
        normal.run(role, tmp_path, tmp_path, tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("name", list(normal.PINNED))
def test_sha_tamper(name, tmp_path):
    path = tmp_path / name
    path.write_bytes(b"wrong")
    with pytest.raises(ContractError, match="STOP_SHA_MISMATCH"):
        normal.checked(path, name, read_bytes=name != normal.SOURCE)


def test_symlink_to_unapproved_basename_not_opened(tmp_path, monkeypatch):
    forbidden = tmp_path / "CooCoiValStuck_0.csv"
    normal_path = tmp_path / normal.NORMAL
    normal_path.symlink_to(forbidden)
    monkeypatch.setattr(Path, "read_bytes", lambda _path: pytest.fail("symlink was opened"))
    with pytest.raises(ContractError, match="STOP_SHA_MISMATCH.*NOT_REGULAR"):
        normal.checked(normal_path, normal.NORMAL)


def test_fixed_basenames_no_discovery(tmp_path, monkeypatch):
    seen = []

    def inspect(path, name, read_bytes=True):
        assert path.name == name
        seen.append(name)
        return b"" if read_bytes else None

    monkeypatch.setattr(normal, "checked", inspect)
    normal.verify_inputs(normal.ROLE, tmp_path, tmp_path)
    assert set(seen) == set(normal.PINNED) and len(seen) == 6


@pytest.mark.parametrize("mutation", ["shift", "duplicate", "missing", "late_boundary", "early_boundary", "fractional"])
def test_clock_grid_and_boundary(protocol, mutation):
    expected = 17625600 + 60 * np.arange(10081)
    raw = expected.astype(float)
    if mutation == "shift":
        raw += 60
    elif mutation == "duplicate":
        raw[1] = raw[0]
    elif mutation == "missing":
        raw = np.delete(raw, 5)
    elif mutation == "late_boundary":
        raw[-1] += 60
    elif mutation == "early_boundary":
        raw[-1] -= 60
    else:
        raw[-1] += 0.5
    with pytest.raises(ContractError, match="CLOCK_OR_BLOCK_BOUNDARY"):
        normal.clock_blocks(pd.Series(raw), protocol)
    clock, block = normal.clock_blocks(pd.Series(expected), protocol)
    assert len(clock) == 10080 and clock[-1] == 18230340
    assert block.value_counts().sort_index().tolist() == [1440] * 7


@pytest.mark.parametrize("field", ["SAT", "future", "unit", "fan_role", "threshold", "calibration", "support"])
def test_receipt_and_semantic_guards(protocol, field):
    receipt = {
        "scope": "SOURCE_NORMAL_ONLY", "protocol_sha256": normal.PROTOCOL_SHA,
        "source_sha256": normal.PINNED[normal.SOURCE], "feature_order": list(normal.FEATURES),
        "artifacts": {name: normal.PINNED[name] for name in (normal.NATIVE, normal.RIDGE)},
        "train_support_degF": {name: [50, 100] for name in normal.FEATURES},
        "calibration": {method: {"center": 0.5, "scale": 0.5, "days": 53} for method in normal.METHODS},
    }
    normal.checked_receipt(protocol, receipt)
    if field in {"SAT", "future"}:
        protocol["feature_order"][0] = "SA_TEMP" if field == "SAT" else "MA_TEMP_t_plus_1"
    elif field == "unit":
        protocol["bindings"]["MA_TEMP"]["target_unit"] = "degF"
    elif field == "fan_role":
        protocol["bindings"]["SF_STATUS"]["role"] = "FAN_SPEED_COMMAND"
    elif field == "threshold":
        protocol["calibration"]["alarm_z"] = 4
    elif field == "calibration":
        receipt["calibration"]["lightgbm_reduced"]["scale"] = 0
    else:
        receipt["train_support_degF"]["MA_TEMP"] = [100, 60]
    with pytest.raises(ContractError):
        normal.checked_receipt(protocol, receipt)


def test_ridge_dimensions_and_order():
    row = {"feature_order": list(normal.FEATURES), "mean": [1, 2, 3], "scale": [1, 1, 1],
           "coefficient": [1, 1, 1], "intercept": 1}
    normal.load_ridge(json.dumps(row))
    row["scale"] = [1, 1]
    with pytest.raises(ContractError, match="DIMENSIONS"):
        normal.load_ridge(json.dumps(row))
    row["feature_order"].reverse()
    with pytest.raises(ContractError, match="FEATURE_ORDER"):
        normal.load_ridge(json.dumps(row))


@pytest.mark.parametrize("missing", ["fan", "oat", "mode", "unit"])
def test_technical_observability_stop(protocol, receipt, missing):
    data = synthetic()
    if missing == "fan":
        data[2].loc[23, "SF_STATUS"] = np.nan
    elif missing == "oat":
        data[2].loc[23, "OA_TEMP"] = np.nan
    elif missing == "mode":
        data[3].loc[23] = np.nan
    else:
        data[4].loc[23] = True
    model = ModelStub()
    trace, rows, technical = normal.evaluate_normal(data, model, RIDGE_STUB, receipt, protocol)
    assert technical and model.calls == 0 and not trace.ELIGIBLE.any()
    assert trace.loc[23, "ABSTAIN_REASON"] == {
        "fan": "UNKNOWN_FAN", "oat": "UNKNOWN_OAT", "mode": "UNKNOWN_PLANT_MODE", "unit": "INVALID_UNIT_OR_RANGE",
    }[missing]
    assert normal.window_summary(trace, rows, technical, protocol)["gate"] == normal.STOP


def test_sat_mat_alias_and_bad_kelvin(protocol, receipt):
    data = synthetic()
    data[2]["MA_TEMP"] = data[2]["SA_TEMP"] = 71
    with pytest.raises(ContractError, match="SAT_ALIAS"):
        normal.evaluate_normal(data, ModelStub(), RIDGE_STUB, receipt, protocol)
    frame = pd.DataFrame({name: [68.0, 293.15] for name in normal.TEMPERATURES})
    converted = normal.temperatures(frame, False, protocol)
    assert converted.iloc[0].isna().all()
    assert converted.iloc[1].tolist() == pytest.approx([68.0] * len(normal.TEMPERATURES))


def test_one_minute_never_scores_a_block(protocol, receipt):
    data = synthetic()
    data[2]["SF_STATUS"] = 0
    data[2].loc[:5, "SF_STATUS"] = 1
    model = ModelStub()
    trace, rows, technical = normal.evaluate_normal(data, model, RIDGE_STUB, receipt, protocol)
    assert not technical and model.calls == 0 and trace.MINUTE_ELIGIBLE.sum() == 1
    assert rows[0]["status"] == "ABSTAIN" and rows[0]["lightgbm_reduced_decision"] == "ABSTAIN"


def test_shared_mask_source_calibration_and_no_fault_transition(protocol, receipt):
    data = synthetic(3 * 1440)
    data[2].loc[25, "MA_TEMP"] = 100
    model = ModelStub()
    trace, rows, technical = normal.evaluate_normal(data, model, RIDGE_STUB, receipt, protocol)
    assert model.calls == 1 and not technical
    assert trace.loc[25, "ABSTAIN_REASON"] == "OUTSIDE_SOURCE_SUPPORT"
    for column in normal.RESIDUAL_COLUMNS.values():
        assert trace[column].notna().equals(trace.ELIGIBLE)
    assert rows[0]["lightgbm_reduced_z"] == 1.0
    assert rows[0]["ridge_reduced_z"] == 0.0 and rows[0]["sat_minus_sp_z"] == -1.0
    assert normal.window_summary(trace, rows, technical, protocol)["gate"] == normal.PASS
    receipt["calibration"]["lightgbm_reduced"] = {"center": 0.25, "scale": 0.25}
    rows = normal.summaries(trace, [{"warm_running_minutes": row["warm_running_minutes"],
                                    "usable_minutes": row["eligible_before_block_gate"],
                                    "longest_run": row["max_contiguous_candidate_minutes"]} for row in rows], receipt, protocol)
    assert rows[0]["lightgbm_reduced_z"] == 3.0 and rows[0]["lightgbm_reduced_decision"] == "NO_ALERT"


def test_pinned_reference_integration_without_inference(monkeypatch):
    inputs, artifacts = os.environ.get("BP06_INPUTS"), os.environ.get("BP06_ARTIFACTS")
    if not inputs or not artifacts:
        pytest.skip("provide the six pinned files for the integration check")
    actual_reads = []
    read_bytes = Path.read_bytes

    def guard(path):
        assert path.name in normal.PINNED
        actual_reads.append(path.name)
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", guard)
    content = normal.verify_inputs(normal.ROLE, Path(inputs), Path(artifacts))
    protocol, receipt = (json.loads(content[name]) for name in (normal.PROTOCOL.name, normal.FIT))
    normal.checked_receipt(protocol, receipt)
    decoded = normal.read_normal(content[normal.NORMAL], protocol)
    assert len(decoded[0]) == 10080
    assert set(actual_reads) == set(normal.PINNED) - {normal.SOURCE}
    normal.load_ridge(content[normal.RIDGE])
    assert tuple(normal.load_native(content[normal.NATIVE]).feature_name()) == normal.FEATURES
