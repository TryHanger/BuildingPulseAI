"""Data-quality checks for the verified simulation panel."""
from math import isfinite

import pandas as pd

SAMPLE_SECONDS = 60
# Broad screening limits for this AHU profile. They do not diagnose a sensor fault.
TEMPERATURE_SCREEN_DEGF = (-100, 200)


def sample_number(value):
    if pd.isna(value):
        return None, "MISSING_VALUE"
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None, "NON_NUMERIC_OR_NON_FINITE"
    if not isfinite(number):
        return None, "NON_NUMERIC_OR_NON_FINITE"
    return number, None


def signal_quality(row, catalog):
    result = []
    for signal in catalog:
        column = signal["source_column"]
        flags = []
        if column not in row:
            flags.append("MISSING_COLUMN")
        else:
            number, error = sample_number(row[column])
            if error:
                flags.append(error)
            elif signal["source_unit"] == "binary" and number not in (0, 1):
                flags.append("NON_BINARY_STATUS")
            elif signal["source_unit"] == "fraction" and not 0 <= number <= 1:
                if signal["kind"] == "COMMAND":
                    flags.append("COMMAND_OUT_OF_RANGE")
                elif signal["kind"] == "MEASUREMENT":
                    flags.append("MEASUREMENT_FRACTION_OUT_OF_RANGE")
            elif signal["source_unit"] == "degF" and not TEMPERATURE_SCREEN_DEGF[0] <= number <= TEMPERATURE_SCREEN_DEGF[1]:
                flags.append("SUSPECT_TEMPERATURE")
        if signal["value_status"] == "UNVERIFIED_UNIT":
            flags.append("SEMANTICS_UNVERIFIED")
        result.append({
            "canonical_id": signal["canonical_id"], "source_column": column, "origin": signal["origin"],
            "value_status": signal["value_status"], "flags": flags,
        })
    return result


def time_quality(previous, current):
    elapsed = (current - previous).total_seconds() if previous is not None else None
    off_grid = elapsed is not None and elapsed % SAMPLE_SECONDS != 0
    gap = elapsed is not None and elapsed > SAMPLE_SECONDS
    return {
        "elapsed_seconds": elapsed,
        "gap_before": gap,
        "off_grid_before": off_grid,
        "missing_samples_before": int(elapsed / SAMPLE_SECONDS) - 1 if gap and not off_grid else 0,
    }
