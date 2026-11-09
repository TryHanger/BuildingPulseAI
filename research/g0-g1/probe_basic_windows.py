"""Find candidate replay windows for reviewer inspection, without emitting diagnoses."""
import argparse
import json
import zipfile
from collections import deque
from datetime import datetime

COLUMNS = ("OA_TEMP", "SF_SPD_DM", "CHWC_VLV_DM", "SA_TEMP", "SA_TEMPSPT")
MEMBERS = ("AHU_annual.csv", "coi_stuck_025_annual.csv")

def probe(archive, member):
    path = f"LBNL_FDD_Dataset_SDAHU/{member}"
    context = deque(maxlen=20)
    examples = {}
    previous = None
    with archive.open(path) as stream:
        header = stream.readline().decode().strip().split(",")
        indices = [header.index(column) for column in COLUMNS]
        for line in stream:
            cells = line.split(b",")
            timestamp = datetime.fromisoformat(cells[0].decode())
            oat, fan, command, sat, sp = [float(cells[index]) for index in indices]
            # Screen one unambiguous temperature band; mode eligibility is a G2 decision.
            if previous is not None and (timestamp - previous).total_seconds() != 60:
                context.clear()
            previous = timestamp
            if not (oat > 60 and fan == 1 and 0 < command <= 1):
                context.clear()
                continue
            context.append(dict(timestamp=str(timestamp), oat=oat, sat=sat, sp=sp, command=command))
            if len(context) != 20:
                continue
            last_ten = list(context)[-10:]
            if all(abs(point["sat"] - point["sp"]) > 5 for point in last_ten):
                examples.setdefault("sat_delta_over_5_degF", list(context))
            if all(point["command"] >= 0.99 for point in last_ten):
                examples.setdefault("cooling_command_at_least_0_99", list(context))
            if len(examples) == 2:
                break
    return examples

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("zip")
    args = parser.parse_args()
    with zipfile.ZipFile(args.zip) as archive:
        print(json.dumps({name: probe(archive, name) for name in MEMBERS}, indent=2, allow_nan=False))

if __name__ == "__main__":
    main()
