"""Independent arithmetic and archived BASIC parity for G5.7."""
import argparse
from collections import Counter
import csv
from decimal import Decimal
import io
import json
from pathlib import Path
from zipfile import ZipFile

NAMES = ("BaselineSystem", "CooCoiValStuck_0", "OADamStuck_100", "SupDucLea_20",
         "BaselineSystem", "CooCoiValStuck_0")
PHASES = {"PRE": "pre", "WINDOW": "active", "POST": "post"}


def checked(data, outputs, earlier):
    result = json.loads((outputs / "g57-observations.json").read_text())
    with ZipFile(earlier / "BUILDINGPULSE_G5_3_GATE_REVIEW.zip") as archive:
        accepted_5wk = json.loads(archive.read("outputs/CROSS_SCENARIO_INDEPENDENT_RESULTS.json"))["scenario_results"]
    with ZipFile(earlier / "BUILDINGPULSE_G5_4_GATE_REVIEW.zip") as archive:
        accepted_1wk = {
            name: list(csv.DictReader(io.StringIO(archive.read(f"outputs/{name}-trace.csv").decode())))
            for name in NAMES[-2:]
        }
    for index, (key, name) in enumerate(zip("ABCDEF", NAMES, strict=True)):
        profile = "5wk" if index < 4 else "1wk"
        with (data / f"g36-{profile}" / f"{name}.csv").open(encoding="utf-8-sig", newline="") as src, (
            outputs / f"trace-{key}.csv"
        ).open(encoding="utf-8", newline="") as out:
            reader = csv.reader(src)
            next(reader)
            traces = list(csv.DictReader(out))
            counts = Counter()
            for i, (fields, trace) in enumerate(zip(reader, traces, strict=True)):
                time = int(Decimal(fields[0]))
                assert int(trace["time_s"]) == time
                sat, sp, mat, coil = (Decimal(fields[col - 1]) for col in (47, 48, 51, 53))
                assert abs(Decimal(trace["sat_minus_coil_k"]) - (sat - coil)) < Decimal("1e-12")
                assert abs(Decimal(trace["mat_minus_coil_k"]) - (mat - coil)) < Decimal("1e-12")
                assert abs(Decimal(trace["coil_minus_sat_sp_k"]) - (coil - sp)) < Decimal("1e-12")
                assert trace["cooling_enable"] == "UNKNOWN" and trace["cause"] == "AMBIGUOUS"
                assert trace["common_mask"] == str(trace["basic_reason"] == "APPLICABLE")
                phase = ("PRE" if time < 16_354_800 else "WINDOW" if time < 18_730_800 else "POST") if profile == "5wk" else "FULL"
                assert trace["period"] == phase
                counts[phase, "samples"] += 1
                counts[phase, "applicable"] += trace["basic_reason"] == "APPLICABLE"
                counts[phase, "point_exceedances"] += trace["basic_point_exceeds"] == "True"
                counts[phase, "confirmed_samples"] += trace["basic_confirmed_period"] == "True"
                if profile == "1wk":
                    old = accepted_1wk[name][i]
                    for current, previous in {
                        "time_s": "time_s", "basic_reason": "reason", "fan_mode": "fan_mode",
                        "sat_minus_sp_k": "residual_k", "basic_point_exceeds": "point_exceeds",
                        "basic_confirmed_period": "confirmed", "basic_confirmed_timeline": "confirmed",
                    }.items():
                        assert trace[current] == old[previous], (key, time, current)
                if trace["basic_confirmed_period"] == "True":
                    position = "ABOVE_SP_AT_BOTH" if coil > sp else "CROSSES_SP_DOWNSTREAM"
                    assert trace["position_vs_sat_sp"] == position
                    counts[phase, position] += 1
            for phase, period in result["runs"][key]["periods"].items():
                if profile == "5wk":
                    for metric in ("samples", "applicable", "point_exceedances", "confirmed_samples"):
                        assert counts[phase, metric] == accepted_5wk[name][PHASES[phase]][metric]
                for position in ("ABOVE_SP_AT_BOTH", "CROSSES_SP_DOWNSTREAM"):
                    assert counts[phase, position] == period["positions_confirmed"].get(position, 0)
                assert counts[phase, "samples"] == period["total_ticks"]
            assert len(traces) == 10_081
        print(f"PASS {key}: 10081 Decimal differences, mask, geometry and archived BASIC parity")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("data", "outputs", "earlier"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    checked(args.data, args.outputs, args.earlier)


if __name__ == "__main__":
    main()
