"""Compare the audited baseline and current read-only results over disposable data."""
import argparse
import hashlib
import json
from types import ModuleType
from zipfile import ZipFile

import yaml

from backend.app.services import investigator_v1 as current

parser = argparse.ArgumentParser()
parser.add_argument("baseline_zip")
args = parser.parse_args()
with open(args.baseline_zip, "rb") as archive:
    baseline_sha = hashlib.file_digest(archive, "sha256").hexdigest()
if baseline_sha != "05dbbe6eb08f445542fe798a93d3d5a0d9d445e960e12188b684f5e608d1a883":
    parser.error("Expected the exact audited G0/G1 handoff ZIP")
baseline = ModuleType("baseline_investigator")
with ZipFile(args.baseline_zip) as source:
    prefix = "BuildingPulse_G0_G1/"
    service = source.read(prefix + "backend/app/services/investigator_v1.py")
    exec(compile(service, "audited-baseline/investigator_v1.py", "exec"), baseline.__dict__)
    registry = yaml.safe_load(source.read(prefix + "research/g0-g1/SIGNAL_MAP_V1.yaml"))
    baseline.SIGNALS = {key: spec for key, spec in registry["signals"].items() if key != "SYS_CTL"}

key = "ds_8e5b1ddfdd14"
timestamp = "2018-01-01T01:00:00"
pressures = ["SA_SP", "SA_SPSPT"]


def capture(runtime, annual_limit):
    source, frame = runtime.dataset_data(key, **annual_limit)
    catalog = {item["canonical_id"]: item for item in runtime.signal_catalog(frame, "BASIC")}
    series = runtime.series_window(frame, "BASIC", pressures, None, 1)
    assert series["timestamps"] == [timestamp]
    signals = {}
    for item in series["signals"]:
        name = item["canonical_id"]
        signals[name] = {"value": item["values"][0], "unit": catalog[name]["unit"],
                         "value_status": item.get("value_status"), "warning": item.get("warning_code")}
    commands = {}
    for fan, command in ((0, 1.5), (1, 1.0), (1, 1.5)):
        result = runtime.evaluate_point(source, {"SF_SPD_DM": fan, "CHWC_VLV_DM": command}, timestamp, "BASIC")
        commands[f"fan={fan}, command={command}"] = {
            "anomaly": result["anomaly_status"], "cause": result["cause_status"],
            "issue_class": result.get("issue_class"), "predicate": result["methods"][0]["predicate"],
        }
    return {"pressure": signals, "command_range": commands}


before = capture(baseline, {})
after = capture(current, {"limit": 1})
for name, raw in (("SA_SP", 402.07953), ("SA_SPSPT", 1.60746)):
    assert before["pressure"][name] == {"value": raw, "unit": "inH2O", "value_status": None, "warning": None}
    assert after["pressure"][name] == {"value": raw, "unit": None, "value_status": "UNVERIFIED_UNIT",
                                      "warning": "SEMANTICS_UNVERIFIED"}
assert all(item["cause"] == "UNEXPLAINED" for item in before["command_range"].values())
assert all(item["cause"] == "NOT_ASSESSED" for item in after["command_range"].values())
assert before["command_range"]["fan=1, command=1.5"]["issue_class"] is None
assert after["command_range"]["fan=1, command=1.5"]["issue_class"] == "SIGNAL_RANGE_VIOLATION"
assert after["command_range"]["fan=1, command=1.0"]["issue_class"] is None
print(json.dumps({"status": "PASS", "before": before, "after": after}, indent=2))
