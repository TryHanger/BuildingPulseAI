"""Counterexamples for the pinned design and its source-only fit boundary."""
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from research.ml_transfer_05 import contract
from research.ml_transfer_05.fit_source import score_source, source_partition


@pytest.fixture
def protocol():
    return contract.load_protocol()


@pytest.mark.parametrize("mutation,expected", [
    ("target", "FORBIDDEN_OR_REORDERED_FEATURE"), ("future", "FORBIDDEN_OR_REORDERED_FEATURE"),
    ("fan", "UNVERIFIED_CHANNEL_ROLE"), ("unit", "WRONG_UNITS"), ("oracle", "DUPLICATE_OR_ORACLE"),
    ("same_tag", "DUPLICATE_OR_ORACLE"),
])
def test_semantic_stop(protocol, mutation, expected):
    bindings = protocol["bindings"]
    if mutation in {"target", "future"}:
        protocol["feature_order"][0] = "SA_TEMP" if mutation == "target" else "MA_TEMP_t_plus_1"
    elif mutation == "fan":
        bindings["SF_STATUS"]["role"] = "FAN_SPEED_COMMAND"
    elif mutation == "unit":
        bindings["MA_TEMP"]["target_unit"] = "degC"
    else:
        bindings["MA_TEMP"]["target"] = (
            "True Value for Cooling Coil" if mutation == "oracle" else bindings["SA_TEMP"]["target"])
    with pytest.raises(contract.ContractError, match=expected):
        contract.validate_bindings(protocol)


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_current_and_shifted_sat_alias(offset):
    sat = pd.Series([51, 62, 58, 47, 64])
    frame = pd.DataFrame({"SA_TEMP": sat, "MA_TEMP": sat.shift(offset),
                          "OA_TEMP": [61, 68, 59, 60, 54], "RA_TEMP": [61, 69, 57, 64, 57]})
    with pytest.raises(contract.ContractError, match="SAT_ALIAS"):
        contract.reject_alias(frame)


@pytest.mark.parametrize("times", [[60, 120, 180], [0, 120, 120], [0, 30, 120]])
def test_shifted_or_broken_clock(times):
    with pytest.raises(contract.ContractError, match="UNQUALIFIED_CLOCK"):
        contract.check_clock(pd.Series(times), {"rows": 3, "first": 0, "last": 120}, 60, False)


def test_missing_channel(tmp_path, protocol, monkeypatch):
    name = protocol["files"]["source"]["name"]
    (tmp_path / name).write_text("Datetime,SA_TEMP\n2018-01-01 01:00:00,55\n")
    protocol["files"]["source"]["sha256"] = contract.sha(tmp_path / name)
    monkeypatch.setattr(contract, "load_protocol", lambda: protocol)
    with pytest.raises(contract.ContractError, match="SEMANTIC_STOP_MISSING"):
        contract.read_input(tmp_path, "source")


def test_target_bytes_cannot_enter_fit_input(tmp_path, protocol):
    (tmp_path / protocol["files"]["source"]["name"]).write_text("time (s),AHU Supply Air Temperature (°K)\n")
    with pytest.raises(contract.ContractError, match="INPUT_SHA_MISMATCH:source"):
        contract.read_input(tmp_path, "source")


def test_wrong_numeric_units_reject_temperature(protocol):
    frame = pd.DataFrame({key: [293.15, 68.0] for key in contract.TEMPERATURES})
    values = contract.temperatures(frame, False, protocol)
    assert values.iloc[0].tolist() == pytest.approx([68] * len(contract.TEMPERATURES))
    assert values.iloc[1].isna().all()


def test_no_cooling_mode_is_not_zero(protocol):
    with pytest.raises(contract.ContractError, match="UNAVAILABLE_COOLING_MODE"):
        contract.mode_valid(pd.DataFrame(), protocol)
    header = protocol["audit_only"]["target_cooling_mode"]["header"]
    assert contract.mode_valid(pd.DataFrame({header: [1, np.nan, 4, 0]}), protocol).tolist() == [True, False, True, False]


def test_fan_hold_and_unknown_reset(protocol):
    frame = pd.DataFrame({
        "SA_TEMP": [54] * 13, "MA_TEMP": [68] * 13, "OA_TEMP": [73] * 13,
        "RA_TEMP": [71] * 13, "SA_TEMPSPT": [55] * 13, "SF_STATUS": [1] * 6 + [np.nan] + [1] * 6,
    })
    data = contract.Input("source", pd.Series(range(13)), frame, pd.DataFrame(), "")
    denominator, eligible = contract.masks(data, protocol)
    assert np.flatnonzero(denominator).tolist() == np.flatnonzero(eligible).tolist() == [5, 12]
    with pytest.raises(contract.ContractError, match="SOURCE_ONLY_SCORING"):
        score_source(replace(data, role="target_reference"), {}, None, None, None, None, protocol)


def test_healthy_ood_stop_and_mask(protocol):
    limits = {name: [50, 80] for name in contract.FEATURES}
    frame = pd.DataFrame({name: [55, 81] for name in contract.FEATURES})
    assert contract.input_support(frame, limits).tolist() == [True, False]
    assert contract.healthy_gate(3, 79, 100, 0, 0, protocol) == "STOP_OOD_HEALTHY"
    assert contract.healthy_gate(3, 90, 100, 1, 0, protocol) == "STOP_OOD_HEALTHY"
    assert contract.healthy_gate(3, 90, 100, 0, 1, protocol) == "STOP_OOD_HEALTHY"
    assert contract.healthy_gate(3, 80, 100, 0, 0, protocol) == "GO_FAULT_EVAL_DESCRIPTIVE"


def test_calendar_split_is_disjoint(protocol):
    clocks = pd.Series(pd.to_datetime(["2018-08-07 23:59", "2018-08-08", "2018-10-20", "2019-01-01"], format="mixed"))
    partitions = source_partition(clocks, protocol["partition"])
    assert np.vstack(list(partitions.values())).sum(axis=0).tolist() == [1, 1, 1, 0]


def test_coverage_floor_and_fragmentation(protocol):
    labels = pd.Series([0] * 1440)
    denominator = np.zeros(len(labels), dtype=bool)
    denominator[:150] = True
    usable = denominator.copy()
    usable[120:] = False
    assert next(contract.block_rows(labels, denominator, usable, protocol))[2]["status"] == "EVALUABLE"
    usable[119] = False
    assert next(contract.block_rows(labels, denominator, usable, protocol))[2]["status"] == "ABSTAIN"
    usable[:] = False
    usable[::2] = True
    assert next(contract.block_rows(labels, np.ones(1440, dtype=bool), usable, protocol))[2]["status"] == "ABSTAIN"
