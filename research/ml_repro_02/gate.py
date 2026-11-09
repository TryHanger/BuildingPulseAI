"""Verify pinned inputs and rebuild the v1 cache from the publisher archive."""
import argparse
import json
from pathlib import Path

from research.ml_reproduction.sources import audit, sha

SOURCE_SHA = "8295fcf0f55bc955937cb4ec0198512c28e5ede32e6bbf735257b0df55426471"
TTL_SHA = "7dbd8403cc85d49c047173f910aae8a85a297d02f9b7ddb779de7a1887d3aa93"
V1_SHA = "50e4fbf3e84cdbed3edd2eccd9fecdb49ce2eaeb219206d02fd624d1b18a966c"


def check(path, expected):
    if sha(path) != expected:
        raise ValueError(f"D0 SHA mismatch: {path.name}")


def main(archive, ttl, accepted, output):
    check(archive, SOURCE_SHA)
    check(ttl, TTL_SHA)
    check(Path(__file__).parents[1] / "ml_reproduction/FROZEN_PROTOCOL.yaml", V1_SHA)
    prior = json.loads(accepted.read_text())
    if prior["archive_sha256"] != SOURCE_SHA or not prior["structural_pass"]:
        raise ValueError("Invalid prior source receipt")
    audit(archive, output / "cache", output)
    current = json.loads((output / "source-audit.json").read_text())
    if current != prior:
        raise ValueError("D0 source inventory differs from accepted v1")
    receipt = {"status": "PASS", "source_sha256": SOURCE_SHA, "ttl_sha256": TTL_SHA,
               "protocol_v1_sha256": V1_SHA, "members": len(current["members"]),
               "accepted_receipt_sha256": sha(accepted),
               "cache": {path.name: sha(path) for path in sorted((output / "cache").glob("*.parquet"))}}
    (output / "verified.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("PASS pinned archive, TTL, protocol, all 21 CSV and reconstructed cache")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("archive", "ttl", "accepted", "output"):
        parser.add_argument(name, type=Path)
    main(**vars(parser.parse_args()))
