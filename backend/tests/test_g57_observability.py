import csv
import io

import pytest

from backend.app.services.g36_policy import BASIC, WEATHER, evaluate
from research.g57 import observe


def fixture(coils, *, times=None, coil_header=observe.COIL, swap=False, extras=("label", "oracle")):
    header = [f"unused-{i}" for i in range(114)]
    names = [observe.TIME, *(v for k, v in BASIC.items() if k != "sat_k"), *WEATHER, *extras]
    header[:len(names)] = names
    header[46], header[52] = observe.SAT, coil_header
    if swap:
        header[46], header[52] = header[52], header[46]
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(header)
    for i, coil in enumerate(coils):
        row = [""] * 114
        row[:10] = [i * 60 if times is None else times[i], 290, 300, 1, .8, 0, 299, 296, "TRUE", 1]
        row[46], row[52] = 299, coil
        writer.writerow(row)
    return buffer.getvalue().encode()


@pytest.mark.parametrize("options", [{"coil_header": "unknown"}, {"coil_header": "Cooling Coil Discharge Air Temperature (°C)"}, {"swap": True}])
def test_invalid_header_and_order(options):
    with pytest.raises(ValueError, match="header|column order"):
        observe.project(fixture([296], **options), "1wk", (0, 0, 60))


@pytest.mark.parametrize("times", [[60, 120, 180], [0, 120, 180], [0, 120, 60], [0, 60, 60]])
def test_clock_shift_gap_reorder_and_duplicate(times):
    with pytest.raises(ValueError, match="model time"):
        observe.project(fixture([295, 297, 296], times=times), "1wk", (0, 120, 60))


def test_shifted_extra_on_same_clock_fails_source_identity():
    original = fixture([295, 296, 297])
    shifted = fixture([297, 295, 296])
    with pytest.raises(ValueError, match="hash mismatch"):
        observe.verify(shifted, observe.digest(original))


def test_alias_abstention_no_recomputation_and_no_oracle():
    grid = (0, 720, 60)
    basic, coils = observe.project(fixture([299] * 13), "1wk", grid)
    with pytest.raises(ValueError, match="aliases SAT"):
        observe.require_non_alias(basic, coils)
    original = [296] * 10 + ["NaN", 289, 300]
    samples, coils = observe.project(fixture(original), "1wk", grid)
    assert samples == basic
    assert set(samples[0]) == {"time_s", "weather_known", *BASIC}
    evaluation = list(evaluate(samples, step=60))
    points = list(observe.trace(samples, coils, 60, evaluation, topology=False))
    assert points[10]["basic_confirmed_period"] and not points[10]["common_mask"]
    assert points[10]["position_vs_sat_sp"] == "AMBIGUOUS"
    assert points[11]["position_vs_sat_sp"] == "CROSSES_SP_DOWNSTREAM"
    assert points[12]["position_vs_sat_sp"] == "ABOVE_SP_AT_BOTH"
    assert all(p["cause"] == "AMBIGUOUS" and p["cooling_enable"] == "UNKNOWN" for p in points)
    assert all(p["mat_minus_coil_k"] is None for p in points)
    assert observe.unavailable(points, "coil_valid_k", 60) == {
        "ticks": 1, "duration_tick_seconds": 60, "blocks": [{"first_s": 600, "last_s": 600, "ticks": 1}],
    }
