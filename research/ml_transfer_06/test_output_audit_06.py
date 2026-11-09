"""Exercise the post-write checksum fix using dummy files and no model."""
import json
from pathlib import Path
import subprocess
import sys


def test_guard_allows_result_checksum_and_denies_other_csv(tmp_path):
    program = r'''
from pathlib import Path
import sys
from research.ml_transfer_06 import audit_execute_06 as audit

root = Path(sys.argv[1])
blocked = root / "unapproved_dummy.csv"
blocked.write_text("dummy")
out = root / "outputs"

def stub(role, inputs, artifacts, output):
    output.mkdir()
    summary = output / "TARGET_NORMAL_06_BLOCKS.csv"
    summary.write_text("block\n")
    assert summary.read_text() == "block\n"
    try:
        blocked.read_bytes()
    except PermissionError:
        pass
    else:
        raise AssertionError("unapproved CSV read was accepted")

audit.scorer.run = stub
audit.main("target_reference", root, root, out, root / "audit.json")
'''
    subprocess.run([sys.executable, "-c", program, str(tmp_path)], check=True)
    evidence = json.loads((tmp_path / "audit.json").read_text())
    assert evidence["approved_inputs_read"] == {}
    assert evidence["expected_outputs_written"] == {"TARGET_NORMAL_06_BLOCKS.csv": 1}
