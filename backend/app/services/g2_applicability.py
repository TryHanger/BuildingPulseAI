"""Independent applicability decisions for the three read-only runtime methods."""
from dataclasses import dataclass

from backend.app.services.g2_quality import sample_number

METHODS = (
    ("running-command-range", ("SF_SPD_DM", "CHWC_VLV_DM")),
    ("sat-tracking", ("SF_SPD_DM", "SA_TEMP", "SA_TEMPSPT")),
    ("valve-tracking", ("SF_SPD_DM", "CHWC_VLV_DM", "CHWC_VLV")),
)


@dataclass(frozen=True)
class Applicability:
    status: str
    reason: str
    predicate: str = "INDETERMINATE"


def assess(method, row, mode, missing, excluded, invalid):
    if excluded:
        return Applicability("INAPPLICABLE", "PANEL_EXCLUDES_SIGNAL")
    if missing:
        return Applicability("INAPPLICABLE", "MISSING_SIGNAL")
    if mode.fan_on is False:
        return Applicability("INAPPLICABLE", "FAN_OFF")
    if mode.fan_on is None:
        return Applicability("INCONCLUSIVE", "FAN_STATUS_INVALID")
    if method == "running-command-range":
        command, error = sample_number(row["CHWC_VLV_DM"])
        if error:
            return Applicability("INCONCLUSIVE", "COMMAND_VALUE_INVALID")
        predicate = "NOT_VIOLATED" if 0 <= command <= 1 else "VIOLATED"
        return Applicability("APPLICABLE", "COMMAND_FRACTION_RANGE", predicate)
    if mode.fan_state == "TRANSITION_HOLD":
        return Applicability("INAPPLICABLE", "FAN_TRANSITION_HOLD")
    if invalid:
        return Applicability("INCONCLUSIVE", "METHOD_INPUT_QUALITY")
    if method == "sat-tracking":
        return Applicability("INCONCLUSIVE", "COOLING_ENABLE_UNOBSERVED")
    return Applicability("INCONCLUSIVE", "VALVE_TRACKING_UNVALIDATED")
