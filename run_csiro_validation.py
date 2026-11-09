"""
BuildingPulse AI — Standalone Orchestration Entrypoint for CSIRO AHU-10 Forensic Reanalysis.

Usage:
    python run_csiro_validation.py

Executes:
1. scripts/evaluate_csiro_ahu10_validation.py (raw telemetry -> models -> manifest & report)
2. pytest tests -v (full standalone regression test suite)
3. Direct numerical parity assertion across data, manifest, and report
"""

import json
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def main():
    print("=" * 80)
    print("BUILDINGPULSE AI — CSIRO AHU-10 ORCHESTRATION PIPELINE (STAGE 8C)")
    print("=" * 80)

    # 1. Run evaluation pipeline
    print("\n[Step 1/3] Executing CSIRO AHU-10 forensic evaluation pipeline...")
    script_path = BASE_DIR / "scripts" / "evaluate_csiro_ahu10_validation.py"
    r_eval = subprocess.run([sys.executable, str(script_path)], cwd=str(BASE_DIR))
    if r_eval.returncode != 0:
        print(f"FAILED: evaluate_csiro_ahu10_validation.py exited with code {r_eval.returncode}")
        sys.exit(r_eval.returncode)

    # 2. Run pytest suite
    print("\n[Step 2/3] Executing full Pytest test suite...")
    r_test = subprocess.run([sys.executable, "-m", "pytest", "tests", "-v"], cwd=str(BASE_DIR))
    if r_test.returncode != 0:
        print(f"FAILED: pytest test suite exited with code {r_test.returncode}")
        sys.exit(r_test.returncode)

    # 3. Verify manifest and report parity
    print("\n[Step 3/3] Verifying machine manifest and scientific report parity...")
    manifest_file = BASE_DIR / "research" / "runs" / "csiro_ahu10_validation_manifest.json"
    report_file = BASE_DIR / "research" / "reports" / "STAGE8C_CSIRO_AHU10_EVALUATION_REPORT.md"
    
    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    with open(report_file, "r", encoding="utf-8") as f:
        report = f.read()

    # Check key forensic assertions
    m2_tot_far = manifest["false_alarm_slices"]["all_operational_norm_combined"]["M2_Control_Local_Tau400"]["pointwise_far"]
    assert m2_tot_far == 0.403, f"Unexpected M2 total FAR: {m2_tot_far}"
    assert "750/1861 (40.30%)" in report, "Report missing exact M2 total FAR string"
    assert "979/1861 (52.61%)" in report, "Report missing exact M1 total FAR string"
    assert "4/7" in report, "Report missing 4/7 primary observable recall string"
    assert "2/7" in report, "Report missing 2/7 primary observable recall string"

    print("  Report and manifest parity verified: PASS")
    print("\n" + "=" * 80)
    print("ALL STANDALONE CHECKS COMPLETED SUCCESSFULLY WITH EXIT CODE 0")
    print("=" * 80)


if __name__ == "__main__":
    main()
