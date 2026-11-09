"""Verify publisher inventory, accepted review payloads and unmodified app copy."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

ACCEPTED = (
    ("Stage09", "e06ba4b8e837b2bd47d49f3bcd8b7f2dc7fb56eb187a51d038b394a348815db8", 49),
    ("Stage10", "34249855caf429d7dde74e96b3d0343d87ecfcb78a6de7c9a38d8cb7ac966fca", 38),
)
FROZEN = "cfd6df405d4e99324457a9cfa744e6c5bd4d994b21b9a87f10dd5f43f45726b9"


def digest(payload):
    return sha256(payload).hexdigest()


def verify(path, expected, count):
    assert digest(path.read_bytes()) == expected, path
    with ZipFile(path) as archive:
        hashes = archive.read("SHA256SUMS").decode().splitlines()
        assert len(hashes) == count
        names = []
        for line in hashes:
            expected_hash, name = line.split("  ", 1)
            name = name.removeprefix("./")
            names.append(name)
            assert digest(archive.read(name)) == expected_hash, name
        assert len(set(names)) == count
        assert set(names) | {"SHA256SUMS"} == {name for name in archive.namelist() if not name.endswith("/")}
    return count


def app_hashes(root):
    for folder in ("backend/app", "backend/tests", "frontend/src", "contracts", "ml", "models", "data", "research"):
        for file in sorted((root / folder).rglob("*")):
            if file.is_file() and "__pycache__" not in file.parts and ".pytest_cache" not in file.parts:
                yield file.relative_to(root), digest(file.read_bytes())


def main(stage09, stage10, listing, app=None, accepted_app=None):
    publisher = json.loads(listing.read_text())
    frozen_manifest = json.loads(Path(__file__).with_name("PUBLISHER_FILES_V1.json").read_text())
    assert {row["filename"] for row in publisher} == frozen_manifest["files"].keys()
    for row in publisher:
        expected = frozen_manifest["files"][row["filename"]]
        assert (row["id"], row["size"], row["content_details"]["sha256_hash"]) == (
            expected["file_id"], expected["bytes"], expected["publisher_sha256"])
    print("PASS publisher V1 listing vs manifest: eight IDs, sizes and digests")
    for path, (name, expected, count) in zip((stage09, stage10), ACCEPTED):
        print(f"PASS {name} review ZIP identity and {verify(path, expected, count)} payload hashes")
    with ZipFile(stage10) as archive:
        frozen = archive.read("frozen-data/field_evidence_10.json")
    assert digest(frozen) == FROZEN
    print("PASS frozen Stage09-derived JSON SHA-256", FROZEN)
    if app is not None:
        assert accepted_app is not None
        assert (app / "backend/app/research_data/field_evidence_10.json").read_bytes() == frozen
        actual, accepted = dict(app_hashes(app)), dict(app_hashes(accepted_app))
        assert actual == accepted, [str(path) for path in actual.keys() | accepted.keys()
                                    if actual.get(path) != accepted.get(path)]
        print(f"PASS {len(actual)} Stage10 application/source/model files byte-identical before/after research-only task")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage09", type=Path)
    parser.add_argument("stage10", type=Path)
    parser.add_argument("listing", type=Path)
    parser.add_argument("--app", type=Path)
    parser.add_argument("--accepted-app", type=Path)
    main(**vars(parser.parse_args()))
