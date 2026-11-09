"""Pure BAS observation rules. No schedule, AHU identity or labels."""
from dataclasses import dataclass
from datetime import datetime, timedelta

RULE_VERSION = "bas-fan-observation@1.0.0"
STEP = timedelta(seconds=300)
CLOCK = "UNKNOWN_CLOCK_NAIVE_WORKBOOK_300S"
LINEAGE = "UNKNOWN_PHYSICAL_LINEAGE"
TAGS = (
    "logic__real_value__fan_fresh_air",
    "logic__real_value__fan_exahust_air",
    "logic__required_value__heater",
    "logic__required_value__chiller",
)


@dataclass(frozen=True)
class Tick:
    time: datetime
    supply: int | None
    exhaust: int | None
    heat: int | None
    cool: int | None


@dataclass(frozen=True)
class Evidence:
    tick: Tick
    supply_state: str
    paired_state: str


def binary(value):
    return int(value) if type(value) in (int, float, bool) and value in (0, 1) else None


def apply(tick):
    supply = {0: "OFF", 1: "ON"}.get(tick.supply, "INSUFFICIENT_DATA")
    pair = "INSUFFICIENT_DATA"
    if None not in (tick.supply, tick.exhaust, tick.heat, tick.cool):
        if (tick.heat, tick.cool) != (1, 0):
            pair = "NOT_APPLICABLE"
        elif tick.supply != tick.exhaust:
            pair = "DISAGREE"
        else:
            pair = supply
    return Evidence(tick, supply, pair)


def precontext(pre, field):
    states = [getattr(row, field) for row in pre]
    if len(states) < 2 or "INSUFFICIENT_DATA" in states:
        return "INSUFFICIENT_DATA"
    if states == ["ON", "ON"]:
        return "TWO_ON"
    if states == ["OFF", "OFF"]:
        return "TWO_OFF"
    return "NOT_APPLICABLE"


def summarize(pre, window, field, start):
    states = [getattr(row, field) for row in window]
    baseline = precontext(pre, field)
    known = {"ON", "OFF", "DISAGREE"}
    adjacent = any(a in known and b in known for a, b in zip(states, states[1:]))
    status = "OBSERVED" if adjacent else "INSUFFICIENT_DATA"
    if states and all(s == "NOT_APPLICABLE" for s in states):
        status = "NOT_APPLICABLE"
    off_run = longest = 0
    for state in states:
        off_run = off_run + 1 if state == "OFF" else 0
        longest = max(longest, off_run)
    result = {
        "status": status, "baseline": baseline,
        "change": "ABSTAIN" if status != "OBSERVED" or baseline != "TWO_ON" else "NO_OBSERVED_CHANGE",
        "off_ticks": states.count("OFF"), "known_ticks": sum(s in known for s in states),
        "longest_off_sample_span_seconds": max(0, longest - 1) * 300 if longest else None,
        "last_on_exclusive": None, "first_off_inclusive": None, "confirm_off": None,
        "first_off_from_log_start_seconds": None, "confirm_from_log_start_seconds": None,
    }
    if result["change"] != "NO_OBSERVED_CHANGE":
        return result
    prior = getattr(pre[-1], field)
    for index, (first, second) in enumerate(zip(states, states[1:])):
        if (prior, first, second) == ("ON", "OFF", "OFF"):
            first_time = window[index].tick.time
            confirm = window[index + 1].tick.time
            result.update(
                change="BAS_ON_TO_OFF_OBSERVED", last_on_exclusive=first_time - STEP,
                first_off_inclusive=first_time, confirm_off=confirm,
                first_off_from_log_start_seconds=int((first_time - start).total_seconds()),
                confirm_from_log_start_seconds=int((confirm - start).total_seconds()),
            )
            break
        prior = first
    return result
