"""Pinned, model-free reader for the transfer design. It exposes no target scorer."""
from dataclasses import dataclass
from hashlib import file_digest, sha256
import json
from pathlib import Path

import numpy as np
import pandas as pd

PROTOCOL_SHA = "7efbb52918b8ffb004318bf538fbe58774600aeefebe93cdaebc7ab72fee0fd0"
CHANNELS = {"SA_TEMP": "MEASURED_TARGET", "MA_TEMP": "MEASUREMENT", "OA_TEMP": "MEASUREMENT",
            "RA_TEMP": "MEASUREMENT", "SA_TEMPSPT": "ACTIVE_SETPOINT", "SF_STATUS": "SUPPLY_FAN_STATUS"}
FEATURES = ("MA_TEMP", "OA_TEMP", "RA_TEMP")
TEMPERATURES = tuple(key for key in CHANNELS if key != "SF_STATUS")


class ContractError(ValueError):
    pass


def sha(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def load_protocol():
    path = Path(__file__).with_name("TRANSFER_05_PROTOCOL.json")
    if sha(path) != PROTOCOL_SHA:
        raise ContractError("PROTOCOL_SHA_MISMATCH")
    protocol = json.loads(path.read_text())
    validate_bindings(protocol)
    return protocol


def validate_bindings(protocol):
    if tuple(protocol["feature_order"]) != FEATURES:
        raise ContractError("FORBIDDEN_OR_REORDERED_FEATURE")
    bindings = protocol["bindings"]
    if {key: val["role"] for key, val in bindings.items()} != CHANNELS:
        raise ContractError("SEMANTIC_STOP_UNVERIFIED_CHANNEL_ROLE")
    for side in ("source", "target"):
        headers = [binding[side] for binding in bindings.values()]
        if len(set(headers)) != len(headers) or any("true value" in item.lower() for item in headers):
            raise ContractError("SEMANTIC_STOP_DUPLICATE_OR_ORACLE")
        expected = {"source": "degF", "target": "K"}[side]
        if any(bindings[key][side + "_unit"] != expected for key in TEMPERATURES):
            raise ContractError("SEMANTIC_STOP_WRONG_UNITS")
        if bindings["SF_STATUS"][side + "_unit"] != "binary":
            raise ContractError("SEMANTIC_STOP_WRONG_FAN_UNIT")


@dataclass(frozen=True)
class Input:
    role: str
    clock: pd.Series
    channels: pd.DataFrame
    context: pd.DataFrame
    header_sha256: str


def check_clock(clock, spec, step, source):
    if source:
        clock = pd.to_datetime(clock, format="%Y-%m-%d %H:%M:%S", errors="raise")
        numeric = clock.to_numpy(dtype="datetime64[s]").astype("int64")
        bounds = str(clock.iloc[0]), str(clock.iloc[-1])
    else:
        clock = pd.to_numeric(clock, errors="raise")
        numeric = clock.to_numpy()
        bounds = clock.iloc[0], clock.iloc[-1]
    if (len(clock) != spec["rows"] or bounds != (spec["first"], spec["last"])
            or not np.isfinite(numeric).all() or not np.all(np.diff(numeric) == step)):
        raise ContractError("UNQUALIFIED_CLOCK")
    return clock


def temperatures(frame, source, protocol):
    values = frame.loc[:, list(TEMPERATURES)]
    if not source:
        values = (values - 273.15) * 1.8 + 32
    lo, hi = protocol["units"]["valid_temperature_degF"]
    return values.where(values.ge(lo) & values.le(hi))


def reject_alias(frame, observed=None):
    """Catch exact SAT duplicates and explicit one-minute SAT shifts within observed rows."""
    for feature in FEATURES:
        for shift in (0, -1, 1):
            pair = pd.concat([frame[feature], frame["SA_TEMP"].shift(shift)], axis=1)
            pair = (pair if observed is None else pair.loc[observed]).dropna()
            if len(pair) >= 2 and np.allclose(pair.iloc[:, 0], pair.iloc[:, 1], atol=1e-9, rtol=0):
                raise ContractError(f"SEMANTIC_STOP_SAT_ALIAS:{feature}:{shift}")


def read_input(directory, role):
    protocol = load_protocol()
    source = role == "source"
    side = "source" if source else "target"
    spec = protocol["files"][role]
    path = directory / spec["name"]
    if sha(path) != spec["sha256"]:
        raise ContractError(f"INPUT_SHA_MISMATCH:{role}")
    with path.open("rb") as stream:
        header = stream.readline()
    bindings = {mapping[side]: channel for channel, mapping in protocol["bindings"].items()}
    mode = protocol["audit_only"]["target_cooling_mode"]["header"]
    context = [] if source else [mode, *protocol["audit_only"]["target_pair_quality_columns"]]
    required = [spec["clock"], *bindings, *context]
    available = pd.read_csv(path, nrows=0).columns
    missing = sorted(set(required) - set(available))
    if missing:
        raise ContractError("SEMANTIC_STOP_MISSING:" + ", ".join(missing))
    raw = pd.read_csv(path, usecols=required, float_precision="round_trip")
    clock = check_clock(raw[spec["clock"]], spec, protocol["mask"]["step_s"], source)
    channels = raw[list(bindings)].rename(columns=bindings).apply(pd.to_numeric, errors="coerce")
    channels[list(TEMPERATURES)] = temperatures(channels, source, protocol)
    channels["SF_STATUS"] = channels["SF_STATUS"].where(channels["SF_STATUS"].isin([0, 1]))
    reject_alias(channels)
    return Input(role, clock, channels, raw[context], sha256(header).hexdigest())


def consecutive_true(values):
    position = np.arange(len(values))
    return np.where(values, position - np.maximum.accumulate(np.where(values, -1, position)), 0)


def mode_valid(context, protocol):
    mode = protocol["audit_only"]["target_cooling_mode"]
    if mode["header"] not in context:
        raise ContractError("SEMANTIC_STOP_UNAVAILABLE_COOLING_MODE")
    return context[mode["header"]].isin(mode["known_codes"]).to_numpy()


def masks(data, protocol):
    mask = protocol["mask"]
    hold_observations = mask["fan_hold_s"] // mask["step_s"] + 1
    fan = data.channels.SF_STATUS.eq(1).to_numpy()
    running = consecutive_true(fan) >= hold_observations
    warm = data.channels.OA_TEMP.gt(protocol["audit_only"]["source_bands"]["warm_above_degF"]).to_numpy()
    denominator = running & warm
    available = np.isfinite(data.channels).all(axis=1).to_numpy()
    if data.role != "source":
        available &= mode_valid(data.context, protocol)
    eligible = denominator & available
    reject_alias(data.channels, eligible)
    return denominator, eligible


def input_support(frame, limits):
    eligible = np.ones(len(frame), dtype=bool)
    for feature in FEATURES:
        lo, hi = limits[feature]
        eligible &= frame[feature].between(lo, hi).to_numpy()
    return eligible


def blocks(data, protocol):
    mask = protocol["mask"]
    if data.role == "source":
        return data.clock.dt.strftime("%Y-%m-%d")
    seconds = data.clock - mask["target_block_anchor_model_s"]
    return (seconds // (mask["step_s"] * mask["minutes_per_block"])).astype(int)


def block_rows(labels, denominator, eligible, protocol):
    rule = protocol["mask"]
    for label, positions in labels.groupby(labels, sort=True).indices.items():
        if len(positions) != rule["minutes_per_block"]:
            continue
        usable = eligible[positions]
        total = int(denominator[positions].sum())
        count = int(usable.sum())
        contiguous = int(consecutive_true(usable).max())
        evaluated = (count >= rule["minimum_minutes"] and contiguous >= rule["minimum_contiguous_minutes"]
                     and total > 0 and count / total >= rule["minimum_coverage"])
        yield label, positions[usable], {"block": str(label), "warm_running_minutes": total,
                                         "usable_minutes": count, "longest_run": contiguous,
                                         "status": "EVALUABLE" if evaluated else "ABSTAIN"}


def healthy_gate(evaluated, usable, denominator, alarms, unknown_denominator, protocol):
    rule = protocol["healthy_gate"]
    if (evaluated < rule["minimum_evaluated_blocks"] or not denominator
            or usable / denominator < rule["minimum_coverage"]
            or alarms > rule["maximum_lightgbm_alarm_blocks"]
            or (rule["require_complete_fan_and_oat"] and unknown_denominator)):
        return "STOP_OOD_HEALTHY"
    return "GO_FAULT_EVAL_DESCRIPTIVE"
