"""Read-only source/feature qualification, including BASIC missing-channel abstention."""
import argparse
import csv
import json
from pathlib import Path

import yaml

from research.ml_reproduction.brick import derive
from research.ml_reproduction.run import MODES, ROOT, plans
from research.ml_reproduction.sources import BASELINE


def inventory(receipt, ttl, output, missing):
    columns = json.loads(receipt.read_text())["members"][BASELINE]["columns"][1:]
    registry = yaml.safe_load((ROOT / "research/g0-g1/SIGNAL_MAP_V1.yaml").read_text())["signals"]
    graph, derivation = derive(ttl, columns)
    observed = [column for column in columns if column not in missing]
    plan, basic, counts = plans(graph, observed, registry, MODES[2])
    status = {target: {"status": "BASIC_ALLOWED" if target in plan else "NOT_EVALUABLE",
                       "reason": None if target in plan else "BLOCKED_INSUFFICIENT_INPUTS",
                       "target_present": target in observed, "neighbors": counts[target]}
              for target in graph}
    output.mkdir(parents=True, exist_ok=True)
    (output / "basic-qualification.json").write_text(json.dumps({
        "derivation": derivation, "missing": missing, "targets": status, "permitted_basic_fields": basic,
        "virtual_sensor_service": "NOT_INTEGRATED",
    }, indent=2) + "\n")
    with (output / "SIGNAL_ELIGIBILITY_MATRIX.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["id", "source", "unit", "registry_role", "provenance", "paper_role", "basic_role", "alias_or_limitation"])
        for name in columns:
            config = registry[name]
            field_type = config["kind"]
            writer.writerow([name, "official LBNL SD-AHU CSV and TTL", config["source_unit"], field_type,
                             "SIMULATED_BENCHMARK", "TARGET_AND_OTHER_MODELS_FEATURE" if name in graph else
                             "OCCUPANCY_MASK_AND_FEATURE" if name == "SYS_CTL" else "FEATURE",
                             "BASIC_ALLOWED" if name in basic else "SIM_ONLY" if name in {
                                 "SYS_CTL", "CHWC_VLV", "OA_DMPR", "RA_DMPR", "SF_SPD", "RF_SPD"} else "UNKNOWN"
                             if config["source_unit"] is None else "EXCLUDED_EXTRA",
                             "SA_TEMP is never a feature of SA_TEMP; source clocks have no verified UTC offset"
                             if name == "SA_TEMP" else config.get("semantics", config.get("origin", ""))])
        for name, unit in (("hour", "hour"), ("month", "month"), ("day_of_week", "0–6"), ("occupancy", "binary")):
            writer.writerow([name, "derived from source-local clock or SYS_CTL", unit, "DERIVED",
                             "SIMULATED_BENCHMARK", "FEATURE", "SIM_ONLY" if name == "occupancy" else "BASIC_ALLOWED",
                             "same numeric occupancy as raw SYS_CTL on eligible minutes" if name == "occupancy" else "calendar context only"])
        writer.writerow(["scenario", "publisher inventory", "none", "LABEL", "SIMULATED_BENCHMARK",
                         "EVALUATION_ONLY", "FORBIDDEN", "never a feature"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("receipt", "ttl", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--missing", nargs="*", default=[])
    inventory(**vars(parser.parse_args()))
