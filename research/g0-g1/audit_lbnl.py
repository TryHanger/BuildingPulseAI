"""Audit the published files in place using only Python's standard library."""
import argparse
import csv
import hashlib
import json
import statistics
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from itertools import zip_longest

BASE = "https://fdddata.lbl.gov/data/Simulated_LBNL_FDD_Data_Sets_SDAHU/"
STEM = "LBNL_FDD_Data_Sets_SDAHU"

def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def csv_inventory(archive, member):
    digest = hashlib.sha256()
    with archive.open(member) as stream:
        line = stream.readline()
        digest.update(line)
        header = next(csv.reader([line.decode("utf-8-sig")]))
        first = last = None
        rows = gaps = non_increasing = 0
        for line in stream:
            digest.update(line)
            timestamp = datetime.fromisoformat(line.split(b",", 1)[0].decode("ascii"))
            if last is None:
                first = timestamp
            else:
                seconds = (timestamp - last).total_seconds()
                gaps += seconds > 60
                non_increasing += seconds <= 0
            last = timestamp
            rows += 1
    return dict(columns=header, rows=rows, first=str(first), last=str(last),
                gaps_over_one_minute=gaps, non_increasing=non_increasing,
                sha256=digest.hexdigest())

def compare_bias(archive, healthy, bias):
    offsets = defaultdict(list)
    selected = ("SA_TEMP", "OA_TEMP", "RA_TEMP", "CHWC_VLV_DM")
    mismatched_time = 0
    fan_off = fan_on = fan_mismatch = 0
    with archive.open(healthy) as left, archive.open(bias) as right:
        header = left.readline().decode().strip().split(",")
        assert header == right.readline().decode().strip().split(",")
        indices = {key: header.index(key) for key in (*selected, "SF_SPD_DM")}
        for normal, biased in zip_longest(left, right):
            if normal is None or biased is None:
                mismatched_time += 1
                continue
            a, b = normal.split(b","), biased.split(b",")
            if a[0] != b[0]:
                mismatched_time += 1
                continue
            i = indices["SF_SPD_DM"]
            if float(a[i]) != float(b[i]):
                fan_mismatch += 1
                continue
            group = "both_fan_on" if float(a[i]) == 1 else "both_fan_off"
            fan_on += group == "both_fan_on"
            fan_off += group == "both_fan_off"
            for key in selected:
                i = indices[key]
                offsets[group, key].append(float(b[i]) - float(a[i]))
    return {
        "baseline": healthy, "comparison": bias, "timestamp_mismatches": mismatched_time,
        "both_fan_on": fan_on, "both_fan_off": fan_off, "fan_status_mismatches": fan_mismatch,
        "deltas": {f"{group}/{key}": dict(n=len(values), mean=statistics.fmean(values),
                    median=statistics.median(values), min=min(values), max=max(values))
                   for (group, key), values in offsets.items()},
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("zip", type=Path)
    parser.add_argument("--local-raw", type=Path)
    args = parser.parse_args()
    files = []
    duplicates = defaultdict(list)
    with zipfile.ZipFile(args.zip) as archive:
        members = {Path(member.filename).name: member.filename for member in archive.infolist()
                   if not member.is_dir()}
        assert len(members) == sum(not member.is_dir() for member in archive.infolist())
        for member in archive.infolist():
            row = dict(path=member.filename, bytes=member.file_size, compressed_bytes=member.compress_size,
                       crc32=f"{member.CRC:08x}", zip_timestamp=list(member.date_time))
            if member.filename.lower().endswith(".csv"):
                row.update(csv_inventory(archive, member))
                duplicates[row["sha256"]].append(member.filename)
            elif not member.is_dir():
                with archive.open(member) as stream:
                    row["sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
            files.append(row)
        bias = compare_bias(archive, members["AHU_annual.csv"], members["coi_bias_2_annual.csv"])
        local = []
        if args.local_raw:
            for path in sorted(args.local_raw.glob("ds_*_lbnl_*.csv")):
                name = path.name.split("_lbnl_", 1)[1]
                member = members.get(name)
                sha256 = digest(path)
                prefix_match = False
                if member:
                    with archive.open(member) as remote, path.open("rb") as stream:
                        prefix_match = all(remote.read(len(block)) == block
                                           for block in iter(lambda: stream.read(1024 * 1024), b""))
                local.append(dict(path=path.name, bytes=path.stat().st_size, sha256=sha256,
                                  archive_member=member, exact_archive_prefix=prefix_match))
    result = dict(source_type="SIMULATION", release_id="sha256:" + digest(args.zip),
                  pdf=dict(url=BASE + STEM + ".pdf", bytes=args.pdf.stat().st_size, sha256=digest(args.pdf)),
                  archive=dict(url=BASE + STEM + ".zip", bytes=args.zip.stat().st_size,
                               sha256=digest(args.zip), entries=len(files),
                               csv_count=sum("columns" in file for file in files)),
                  members=files, duplicate_payload_groups=[group for group in duplicates.values() if len(group) > 1],
                  bias_byte_comparison=bias, local_slices=local)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))

if __name__ == "__main__":
    main()
