"""Recover only approved members of the pinned Figshare v3 ZIP using byte ranges."""
import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryFile
from urllib.request import Request, urlopen
from zipfile import ZipFile

BASE = "https://api.figshare.com/v2/file/download/57268553"
SIZE = 928675992
RANGE_ETAG = "bcb61029cf69043da14c2279ef575db3-9"
PREFIX = "Public_ScientificData_AHUFaults/"


def fetch(first, last):
    request = Request(f"{BASE}?g52_range={first}-{last}", headers={"Range": f"bytes={first}-{last}"})
    with urlopen(request, timeout=60) as response:
        if (response.status != 206 or response.headers.get("Content-Range") != f"bytes {first}-{last}/{SIZE}"
                or response.headers.get("ETag", "").strip('"') != RANGE_ETAG):
            raise ValueError(f"Unverified publisher range {first}-{last}")
        data = response.read(last - first + 2)
        if len(data) != last - first + 1:
            raise ValueError(f"Unexpected byte count {first}-{last}")
        return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--one-week-probe", action="store_true", help="Fetch only the G36-1wk passport and cooling-season closed-valve CSV")
    modes.add_argument("--one-week-baseline", action="store_true", help="Fetch only the CoolingSeason nominal CSV")
    modes.add_argument("--directory-only", action="store_true", help="Record G36-1wk names from the directory only")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with TemporaryFile() as stream:
        tail = fetch(SIZE-131072, SIZE-1)
        stream.seek(SIZE-len(tail))
        stream.write(tail)
        with ZipFile(stream) as archive:
            directory = archive.infolist()
            if args.directory_only:
                result = [{"path": x.filename, "bytes": x.file_size, "crc32": f"{x.CRC:08x}"}
                          for x in directory if x.filename.startswith(PREFIX+"04_G36-1wk/") and not x.is_dir()]
            else:
                if args.one_week_baseline:
                    groups = [[archive.getinfo(PREFIX + "04_G36-1wk/CoolingSeason/BaselineSystem.csv")]]
                elif args.one_week_probe:
                    groups = [[archive.getinfo(PREFIX + "04_G36-1wk/" + name)] for name in (
                        "00_explanations.pdf", "CoolingSeason/CooCoiValStuck_0.csv",
                    )]
                else:
                    group = [x for x in directory if x.filename.startswith(PREFIX+"05_G36-5wk/") and not x.is_dir()]
                    assert len(group) == 5
                    groups = [group]
                result = []
                transferred = len(tail)
                for group in groups:
                    following = next(x for x in directory if x.header_offset > group[-1].header_offset)
                    first, last = group[0].header_offset, following.header_offset-1
                    payload = fetch(first, last)
                    transferred += len(payload)
                    stream.seek(first)
                    stream.write(payload)
                    for member in group:
                        data = archive.read(member)  # verifies member CRC
                        destination = args.output / Path(member.filename).name
                        destination.write_bytes(data)
                        destination.chmod(0o444)
                        result.append({"path": member.filename, "bytes": len(data), "compressed_bytes": member.compress_size,
                                       "sha256": hashlib.sha256(data).hexdigest(), "crc32": f"{member.CRC:08x}"})
                print(f"Transferred {transferred} bytes, validated {len(result)} members")
    (args.output/"member-receipt.json").write_text(json.dumps(result, indent=2)+"\n")


if __name__ == "__main__":
    main()
