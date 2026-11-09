"""Frozen G36 SAT symptom policy and BAS channel bindings."""

from math import isfinite

STEP = 300
HOLD = 600
THRESHOLD_K = 2
POLICY = "g36-sat-high@1.0.0"
BASIC = {
    "sat_k": "AHU Supply Air Temperature (°K)",
    "setpoint_k": "AHU Supply Air Temperature Setpoint (°K)",
    "mat_k": "AHU Mixed Air Temperature (°K)",
    "fan_status": "AHU Supply Air Fan Status (0: off, 1: on)",
    "cooling_command": "Control Signal for AHU Cooling Coil Valve from BAS (fraction, 0: valve should be fully closed to 1: valve should be fully open)",
    "heating_command": "Control Signal for AHU Heating Coil Valve (fraction, 0: valve should be fully closed to 1: valve should be fully open)",
}
WEATHER = ("AHU Outdoor Air Dry Bulb Temperature (°K)", "AHU Outdoor Air Wet Bulb Temperature (°K)")


def evaluate(samples, *, step=STEP):
    """Check weather availability, then score only timestamped BASIC inputs."""
    first_violation = previous = None
    for row in samples:
        time = row["time_s"]
        temperatures = [row[key] for key in ("sat_k", "setpoint_k", "mat_k")]
        fan, cooling, heating = (row[key] for key in ("fan_status", "cooling_command", "heating_command"))
        weather_known = row.get("weather_known") is True
        reason = "APPLICABLE"
        if not weather_known:
            reason = "UNKNOWN_WEATHER_CONTEXT"
        elif (not all(value is not None and 230 <= value <= 340 for value in temperatures)
                or fan not in (0, 1) or any(value is None or not 0 <= value <= 1 for value in (cooling, heating))):
            reason = "INVALID_INPUT"
        elif fan == 0:
            reason = "FAN_OFF"
        elif cooling < 0.20:
            reason = "LOW_COOLING_COMMAND"
        elif heating > 0.01:
            reason = "HEATING_COMMAND"
        elif row["mat_k"] - row["setpoint_k"] < 2:
            reason = "LOW_TEMPERATURE_LIFT"
        residual = row["sat_k"] - row["setpoint_k"] if reason == "APPLICABLE" else None
        exceeds = residual is not None and residual > THRESHOLD_K
        if not exceeds:
            first_violation = None
        elif first_violation is None or time - previous != step:
            first_violation = time
        method_status = ("APPLICABLE" if reason == "APPLICABLE" else
                         "INCONCLUSIVE" if reason in {"INVALID_INPUT", "UNKNOWN_WEATHER_CONTEXT"} else "INAPPLICABLE")
        yield {
            "weather_status": "OBSERVED" if weather_known else "UNKNOWN",
            "fan_mode": "FAN_ON" if fan == 1 else "FAN_OFF" if fan == 0 else "UNKNOWN",
            "method_status": method_status,
            "predicate": "INDETERMINATE" if residual is None else "VIOLATED" if exceeds else "NOT_VIOLATED",
            "reason": reason, "residual_k": residual, "point_exceeds": exceeds,
            "confirmed": first_violation is not None and time - first_violation >= HOLD,
        }
        previous = time


def number(value):
    try:
        parsed = float(value)
    except (ValueError, TypeError):
        return None
    return parsed if isfinite(parsed) else None
