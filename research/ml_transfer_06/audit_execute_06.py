"""Run the evaluator with an extra Python file-open guard and record approved accesses."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys

from research.ml_transfer_06 import target_normal_06 as scorer


def main(role, inputs, artifacts, output, audit_log):
    approved = {
        scorer.PROTOCOL.absolute(), (inputs / scorer.SOURCE).absolute(), (inputs / scorer.NORMAL).absolute(),
        *((artifacts / name).absolute() for name in (scorer.NATIVE, scorer.RIDGE, scorer.FIT)),
    }
    permitted_outputs = {(output / name).absolute() for name in (
        "RUN_STARTED.json", "TARGET_NORMAL_06_MINUTE_TRACE.csv.gz",
        "TARGET_NORMAL_06_BLOCKS.csv", "TARGET_NORMAL_06_RECEIPT.json",
    )}
    reads, writes = Counter(), Counter()
    with audit_log.open("x") as log:
        def file_guard(event, args):
            if event != "open" or not isinstance(args[0], (str, bytes)):
                return
            path = Path(os.path.abspath(os.fsdecode(args[0])))
            write = bool(args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if write:
                if path not in permitted_outputs:
                    raise PermissionError(f"Denied write outside the four expected outputs: {path}")
                writes[path.name] += 1
            elif path in approved:
                reads[path.name] += 1
            elif path not in permitted_outputs and path.suffix.lower() in {".csv", ".parquet", ".db", ".sqlite"}:
                raise PermissionError(f"Denied data read: {path}")

        sys.addaudithook(file_guard)
        try:
            scorer.run(role, inputs, artifacts, output)
        finally:
            json.dump({"guard": "PYTHON_OPEN_AUDIT", "approved_inputs_read": reads,
                       "expected_outputs_written": writes}, log, indent=2)
            log.write("\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", required=True)
    for arg in ("inputs", "artifacts", "output", "audit_log"):
        parser.add_argument("--" + arg.replace("_", "-"), required=True, type=Path)
    try:
        main(**vars(parser.parse_args()))
    except scorer.ContractError as error:
        reason = str(error)
        gate = reason.split(":")[0] if reason.startswith("STOP_") else scorer.STOP
        parser.exit(2, json.dumps({"gate": gate, "reason": reason, "fault_phase_authorized": False}) + "\n")
