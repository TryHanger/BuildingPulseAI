"""Causal fan state and weather context for the LBNL SD-AHU signal profile."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Mapping

from backend.app.services.g2_quality import SAMPLE_SECONDS, TEMPERATURE_SCREEN_DEGF, sample_number

HOLD_SECONDS = 300
MODE_POLICY = {
    "policy_id": "lbnl-fan-hold",
    "version": "1.0.0",
    "hold_seconds": HOLD_SECONDS,
    "fan_status_signal": "SF_SPD_DM",
    "fan_status_semantics": "SIMULATED_FAN_STATUS",
    "weather_signal": "OA_TEMP",
    "weather_boundaries_deg_f": [33.8, 60],
}
PHYSICAL_CONTEXT = {
    "economizer_state": "UNKNOWN",
    "mechanical_cooling_enable": "UNKNOWN",
    "missing_observations": ["INDEPENDENT_ECONOMIZER_STATUS", "MECHANICAL_COOLING_ENABLE"],
}


@dataclass(frozen=True)
class ModeContext:
    fan_state: str
    economizer_band: str = "UNASSESSED"
    mechanical_cooling_enable: str = "UNOBSERVED"

    @property
    def fan_on(self):
        return {"OFF": False, "UNKNOWN": None, "TRANSITION_HOLD": True, "RUNNING": True}[self.fan_state]


def evaluate_modes(
    observations: Iterable[tuple[datetime, Mapping[str, float | None]]],
) -> list[ModeContext]:
    """Evaluate raw BASIC fan status and OAT using only current and preceding observations."""
    step = timedelta(seconds=SAMPLE_SECONDS)
    hold = timedelta(seconds=HOLD_SECONDS)
    previous = None
    running_since = None
    results = []
    for timestamp, row in observations:
        if timestamp.tzinfo is not None or (previous is not None and timestamp <= previous):
            raise ValueError("Expected strictly increasing source-local timestamps")
        if previous is None or timestamp - previous != step:
            running_since = None
        previous = timestamp
        fan, _ = sample_number(row.get("SF_SPD_DM"))
        if fan != 1:
            running_since = None
            results.append(ModeContext("OFF" if fan == 0 else "UNKNOWN"))
            continue
        if running_since is None:
            running_since = timestamp
        if timestamp - running_since < hold:
            results.append(ModeContext("TRANSITION_HOLD"))
            continue
        oat, _ = sample_number(row.get("OA_TEMP"))
        low, high = MODE_POLICY["weather_boundaries_deg_f"]
        if oat is None or not TEMPERATURE_SCREEN_DEGF[0] <= oat <= TEMPERATURE_SCREEN_DEGF[1]:
            band = "UNASSESSED"
        elif low < oat < high:
            band = "WITHIN_DOCUMENTED_OAT_BAND"
        elif oat in (low, high):
            band = "BOUNDARY_UNVERIFIED"
        else:
            band = "OUTSIDE_DOCUMENTED_OAT_BAND"
        results.append(ModeContext("RUNNING", band))
    return results
