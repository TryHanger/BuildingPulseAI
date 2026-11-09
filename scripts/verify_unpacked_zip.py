"""
BuildingPulse AI — Independent Unpacked ZIP Verification for Stage 8B-R.3
Unpacks BUILDINGPULSE_AUDIT_STAGE_8B_R_3.zip in an isolated temporary directory,
verifies every checksum in audit/MANIFEST.json, runs pytest tests -v,
and re-executes python scripts/evaluate_rbc_nesbitt_reconciled.py.
"""

import sys
import shutil
import zipfile
import hashlib
import json
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
ZIP_PATH = ROOT_DIR / "BUILDINGPULSE_AUDIT_STAGE_8B_R_3.zip"
VERIFY_DIR = ROOT_DIR / "temp_verify_zip_r3"


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main():
    print("==================================================================")
    print(" VERIFYING UNPACKED ZIP: BUILDINGPULSE_AUDIT_STAGE_8B_R_3.zip")
    print("==================================================================")
    
    assert ZIP_PATH.exists(), f"ZIP not found: {ZIP_PATH}"
    print(f"ZIP Size:   {ZIP_PATH.stat().st_size:,} bytes")
    print(f"ZIP SHA256: {compute_sha256(ZIP_PATH)}")
    
    if VERIFY_DIR.exists():
        shutil.rmtree(VERIFY_DIR)
    VERIFY_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Unpack
    print("\n1. Unpacking ZIP into isolated directory...")
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        zf.extractall(VERIFY_DIR)
    print("Unpacked successfully.")
    
    # 2. Checksum validation against audit/MANIFEST.json
    print("\n2. Checking manifest SHA-256 for all unpacked files...")
    manifest_file = VERIFY_DIR / "audit" / "MANIFEST.json"
    assert manifest_file.exists(), "audit/MANIFEST.json missing in unpacked ZIP"
    with open(manifest_file, "r", encoding="utf-8") as f:
        catalog = json.load(f)
        
    mismatches = 0
    checked = 0
    for entry in catalog:
        rel_p = entry["path"]
        expected_sha = entry["sha256"]
        expected_size = entry["size_bytes"]
        target = VERIFY_DIR / rel_p
        assert target.exists(), f"Missing file: {rel_p}"
        actual_size = target.stat().st_size
        actual_sha = compute_sha256(target)
        if actual_size != expected_size or actual_sha != expected_sha:
            print(f"MISMATCH: {rel_p} (expected {expected_sha[:8]}, got {actual_sha[:8]})")
            mismatches += 1
        checked += 1
        
    print(f"Checked {checked}/{len(catalog)} files: {mismatches} mismatches.")
    assert mismatches == 0, f"{mismatches} checksum mismatches found!"
    
    # 3. Run standalone tests in unpacked directory
    print("\n3. Running pytest tests -v inside unpacked directory...")
    proc_test = subprocess.run(["pytest", "tests", "-v"], cwd=str(VERIFY_DIR), capture_output=True, text=True)
    print(proc_test.stdout)
    if proc_test.returncode != 0:
        print(proc_test.stderr)
        raise RuntimeError(f"Tests failed with code {proc_test.returncode}")
        
    # 4. Run reconciled runner in unpacked directory
    print("\n4. Running python scripts/evaluate_rbc_nesbitt_reconciled.py inside unpacked directory...")
    proc_runner = subprocess.run([sys.executable, "scripts/evaluate_rbc_nesbitt_reconciled.py"], cwd=str(VERIFY_DIR), capture_output=True, text=True)
    print(proc_runner.stdout)
    if proc_runner.returncode != 0:
        print(proc_runner.stderr)
        raise RuntimeError(f"Runner failed with code {proc_runner.returncode}")
        
    # 5. Clean up
    shutil.rmtree(VERIFY_DIR)
    print("Cleaned up verify directory.")
    print("\n==================================================================")
    print(" ALL VERIFICATIONS PASSED 100%! ZIP IS REPRODUCIBLE AND CLEAN!")
    print("==================================================================")


if __name__ == "__main__":
    main()
