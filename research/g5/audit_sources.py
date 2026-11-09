"""Reconcile freshly read publisher bytes with RC2 and inventory the nominal split."""
import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timedelta
from math import isfinite
from pathlib import Path

import yaml

REGISTRY = Path(__file__).resolve().parents[1] / "g0-g1"
NOMINAL = "AHU_annual.csv"
CUTS = ("2018-05-01 00:00:00", "2018-07-01 00:00:00")
SPLITS = ("train", "calibration", "test_retrospective")
FEATURES = ("MA_TEMP", "OA_TEMP", "RA_TEMP", "SF_CS", "SA_TEMPSPT")
COMMAND = "CHWC_VLV_DM"
TARGET = "SA_TEMP"
GATE = "SF_SPD_DM"
EXTRAS = {"CHWC_VLV", "OA_DMPR", "OA_CFM", "RA_CFM", "SA_CFM"}
CONTEXT = {GATE}
BASIC = {*FEATURES, COMMAND, TARGET, *CONTEXT}


def source_map():
    return yaml.safe_load((REGISTRY / "SIGNAL_MAP_V1.yaml").read_text())["signals"]


def validate_features(features, panel, points):
    allowed = set(FEATURES) | {COMMAND}
    if panel == "EXTRA_SIMULATED":
        allowed |= EXTRAS
    elif panel != "BASIC":
        raise ValueError("Unknown or unverified panel")
    if len(set(features)) != len(features) or not set(features) <= allowed:
        raise ValueError("Duplicate, target, label or undeclared feature")
    for key in features:
        item = points[key]
        if item["source_column"] != key or item["basic_eligible"] != (key in BASIC):
            raise ValueError("False source role or panel provenance")
        if key in {COMMAND, "SF_CS"} and item["kind"] != "COMMAND":
            raise ValueError("Command cannot be relabeled as feedback")


def source_identity(member, release, *, local=None):
    name = Path(member["path"]).name
    payload = local or member
    family = name.split("_annual")[0]
    if name.startswith("coi_bias_"):
        label = "UNKNOWN_COI_BIAS_SA_BIAS_CROSSWALK"
    elif name.startswith(("oa_bias_", "coi_leakage_")):
        label = "EXCLUDED_DUPLICATE_SEVERITY"
    elif name.startswith(("damper_stuck_", "coi_stuck_")):
        label = "DOCUMENTED_SIMULATION_SCENARIO_ONLY"
    else:
        label = "PUBLISHER_NOMINAL_SCENARIO"
    return {
        **payload,
        "source_id": f"sha256:{payload['sha256']}",
        "campaign_key": f"{release}:{name}",
        "member_sha256": member["sha256"],
        "provenance": "SIMULATION",
        "profile": "LBNL_SDAHU",
        "label_status": label,
        "documented_scenario_name": family,
        "verified_onset": None,
        "pair_status": "PAIR_NOT_VERIFIED",
        "field_feedback": False,
    }


def local_inventory(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.reader(stream)
        columns = next(reader)
        first = last = next(reader)[0]
        rows = 1
        for row in reader:
            last = row[0]
            rows += 1
    return {"first": first, "last": last, "rows": rows, "columns": columns}


def nominal_support(path):
    """Count available rows only. This computes no predictions or residuals."""
    totals = {name: Counter() for name in SPLITS}
    status = {name: Counter() for name in SPLITS}
    cuts = tuple(datetime.fromisoformat(cut) for cut in CUTS)
    prior = previous_split = running_since = None
    with path.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            stamp = datetime.fromisoformat(row["Datetime"])
            split = SPLITS[sum(stamp >= cut for cut in cuts)]
            totals[split]["rows"] += 1
            value = float(row[GATE])
            status[split][str(value)] += 1
            if value != 1 or prior is None or stamp - prior != timedelta(minutes=1) or split != previous_split:
                running_since = stamp if value == 1 else None
            elif running_since is None:
                running_since = stamp
            prior, previous_split = stamp, split
            if running_since is None or stamp - running_since < timedelta(minutes=5):
                continue
            totals[split]["running_hold_pass"] += 1
            temperatures = [float(row[key]) for key in ("MA_TEMP", "OA_TEMP", "RA_TEMP", TARGET, "SA_TEMPSPT")]
            commands = [float(row[key]) for key in ("SF_CS", COMMAND)]
            if all(isfinite(x) and -100 <= x <= 200 for x in temperatures) and all(0 <= x <= 1 for x in commands):
                totals[split]["finite_common_panel"] += 1
    return {key: {
        **totals[key], "fan_status_counts": dict(sorted(status[key].items())),
        "has_both_binary_states": {"0.0", "1.0"} <= status[key].keys(),
    } for key in SPLITS}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("inventory", type=Path, help="Output of research/g0-g1/audit_lbnl.py")
    parser.add_argument("raw", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    observed = json.loads(args.inventory.read_text())
    frozen = json.loads((REGISTRY / "DATASET_MANIFEST.json").read_text())
    for key in ("archive", "pdf", "members", "duplicate_payload_groups"):
        assert observed[key] == frozen[key], key
    frozen_local = {item["path"]: item for item in frozen["local_slices"]}
    assert set(frozen_local) == {item["path"] for item in observed["local_slices"]}
    assert len(frozen_local) == 15
    release = observed["release_id"]
    published = {item["path"]: item for item in observed["members"] if "columns" in item}
    slices = []
    for item in observed["local_slices"]:
        original = frozen_local[item["path"]]
        assert item["exact_archive_prefix"] and all(original[key] == value for key, value in item.items())
        local = {**item, **local_inventory(args.raw / item["path"])}
        assert local["rows"] == original["rows"]
        slices.append(source_identity(published[item["archive_member"]], release, local=local))
    points = source_map()
    validate_features(FEATURES, "BASIC", points)
    validate_features((*FEATURES, COMMAND), "BASIC", points)
    validate_features((*FEATURES, COMMAND, *sorted(EXTRAS)), "EXTRA_SIMULATED", points)
    normal = next(item for item in slices if Path(item["archive_member"]).name == NOMINAL and item["sha256"] == item["member_sha256"])
    result = {
        "schema_version": 1, "release_id": release, "archive": observed["archive"], "pdf": observed["pdf"],
        "source_clock": "SOURCE_LOCAL_OFFSET_UNKNOWN",
        "crosswalk_coi_bias_sa_bias": "UNKNOWN",
        "members": [source_identity(item, release) for item in published.values()],
        "distinct_member_payloads": len({item["sha256"] for item in published.values()}),
        "duplicate_payload_groups": observed["duplicate_payload_groups"],
        "local_slices": slices,
        "nominal_source_id": normal["source_id"],
        "split_cuts": list(CUTS),
        "nominal_support": nominal_support(args.raw / normal["path"]),
        "source_map": {
            "basic": {key: points[key] for key in sorted(BASIC)},
            "extra_simulated": {key: points[key] for key in sorted(EXTRAS)},
            "baseline_features": list(FEATURES), "command_ablation_add": COMMAND,
            "target": TARGET, "eligibility_gate": GATE,
            "excluded": ["SYS_CTL", "fault_oracle", "source_label", "target_lags", "campaign_id"],
            "field_feedback": "NOT_VERIFIED",
        },
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(f"PASS {len(published)} official members, {len(slices)} verified slices, {result['distinct_member_payloads']} distinct payloads")
    print(json.dumps(result["nominal_support"], sort_keys=True))


if __name__ == "__main__":
    main()
