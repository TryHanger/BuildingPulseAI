"""
BuildingPulse AI — Automated Standalone Package Builder for Stage 8C Forensic Integrity Repair.
Creates: BUILDINGPULSE_AUDIT_STAGE_8C_FORENSIC_FIXED.zip with SHA256SUMS.txt.
Ensures:
1. csiro_ahu10.parquet is included (7.5 MB raw telemetry).
2. csiro_fault_experiments.parquet is included.
3. All 23 rbc_nesbitt raw CSV files are included.
4. evaluate_rbc_nesbitt_reconciled.py and all test dependencies are included.
5. run_csiro_validation.py has valid syntax and compiles cleanly.
6. 40/40 tests pass in an isolated unpacked temporary directory.
"""

import hashlib
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ZIP_OUT_PATH = BASE_DIR / "BUILDINGPULSE_AUDIT_STAGE_8C_FORENSIC_FIXED.zip"

INCLUDED_ITEMS = [
    # Top-level docs
    "AGENTS.md",
    "README.md",
    "README_REPRODUCE.md",
    "requirements.txt",
    "BUILDINGPULSE_STAGE_8C_INDEPENDENT_AUDIT.md",
    "BUILDINGPULSE_STAGE_8C_AGENT_CORRECTION_REQUEST.md",
    # Research Protocols & Reports
    "research/protocols/CSIRO_AHU10_VALIDATION_PROTOCOL.md",
    "research/reports/STAGE8C_CSIRO_AHU10_EVALUATION_REPORT.md",
    "research/reports/STAGE8B_INDEPENDENT_EXTERNAL_VALIDATION_REPORT.md",
    "research/runs/csiro_ahu10_validation_manifest.json",
    "research/runs/csiro_ahu10_pointwise_predictions.csv",
    "research/runs/rbc_nesbitt_independent_validation_manifest.json",
    "research/runs/rbc_nesbitt_independent_pointwise_predictions.csv",
    # Raw Data
    "data/raw/csiro_ahu10.parquet",
    "data/raw/csiro_fault_experiments.parquet",
    # Source Code
    "scripts/evaluate_csiro_ahu10_validation.py",
    "scripts/evaluate_rbc_nesbitt_reconciled.py",
    "scripts/evaluate_rbc_nesbitt_independent_validation.py",
    "ml/diagnostics/time_aware_fdd.py",
    # Tests
    "tests/test_csiro_ahu10_validation.py",
    "tests/test_domain_guard.py",
    "tests/test_domain_guard_nan_and_gap_policy.py",
    "tests/test_event_onset_and_preexisting_alarms.py",
    "tests/test_independent_holdout_validation.py",
    "tests/test_independent_temporal_integrity.py",
    "tests/test_m2_causal_ablation.py",
    "tests/test_report_manifest_consistency.py",
    "tests/test_stage8b_r2_scientific_integrity.py",
    "tests/test_time_aware_scoring.py",
    # Docs
    "docs/STATE.md",
    "docs/DECISIONS.md",
    "docs/NEXT_STEPS.md"
]

# Add all raw RBC-Nesbitt files
RBC_FILES = [
    "data/raw/rbc_nesbitt/00_explanations.pdf",
    "data/raw/rbc_nesbitt/20160601_Baseline.csv",
    "data/raw/rbc_nesbitt/20160712_Baseline.csv",
    "data/raw/rbc_nesbitt/20170618_Baseline.csv",
    "data/raw/rbc_nesbitt/20170702_Baseline.csv",
    "data/raw/rbc_nesbitt/20170714_Baseline.csv",
    "data/raw/rbc_nesbitt/20170718_OADamStuck_100.csv",
    "data/raw/rbc_nesbitt/20170729_Baseline.csv",
    "data/raw/rbc_nesbitt/20170811_CooCoiValStuck_100.csv",
    "data/raw/rbc_nesbitt/20180710_OADamStuck_30.csv",
    "data/raw/rbc_nesbitt/20180711_CooCoiValStuck_80.csv",
    "data/raw/rbc_nesbitt/holdout/20160722_Baseline.csv",
    "data/raw/rbc_nesbitt/holdout/20160803_Baseline.csv",
    "data/raw/rbc_nesbitt/holdout/20160819_Baseline.csv",
    "data/raw/rbc_nesbitt/holdout/20160831_Baseline.csv",
    "data/raw/rbc_nesbitt/holdout/20161201_OADamStuck_90.csv",
    "data/raw/rbc_nesbitt/holdout/20161205_Baseline.csv",
    "data/raw/rbc_nesbitt/holdout/20170103_OADamStuck_80.csv",
    "data/raw/rbc_nesbitt/holdout/20170115_Baseline.csv",
    "data/raw/rbc_nesbitt/holdout/20170215_Baseline.csv",
    "data/raw/rbc_nesbitt/holdout/20170317_Baseline.csv",
    "data/raw/rbc_nesbitt/holdout/20170711_OADamStuck_90.csv",
    "data/raw/rbc_nesbitt/holdout/20180709_TSup_m3.5.csv",
    "data/raw/rbc_nesbitt/holdout/20180718_OADamStuck_60.csv"
]


def sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main():
    print("=" * 70)
    print("BUILDINGPULSE AI — BUILDING STAGE 8C FORENSIC FIXED ARCHIVE")
    print("=" * 70)
    
    file_map = {}
    total_items = INCLUDED_ITEMS + RBC_FILES
    
    for item in total_items:
        p = BASE_DIR / item
        if not p.exists():
            raise FileNotFoundError(f"Missing required file for standalone bundle: {p}")
        rel = p.relative_to(BASE_DIR).as_posix()
        file_map[rel] = p
        
    print(f"Total files to bundle: {len(file_map)}")
    
    # Standalone runner content with guaranteed correct string literal syntax
    runner_code = (
        "# Standalone runner for CSIRO AHU-10 forensic validation\n"
        "import subprocess\n"
        "import sys\n\n"
        "print(\"Running Pytest suite (40 tests)...\")\n"
        "r1 = subprocess.run([sys.executable, \"-m\", \"pytest\", \"tests\", \"-v\"])\n"
        "if r1.returncode != 0:\n"
        "    sys.exit(r1.returncode)\n\n"
        "print(\"\\nRunning CSIRO AHU-10 forensic validation pipeline...\")\n"
        "r2 = subprocess.run([sys.executable, \"scripts/evaluate_csiro_ahu10_validation.py\"])\n"
        "sys.exit(r2.returncode)\n"
    )
    
    # Calculate file hashes
    hashes = {}
    for rel_path, fpath in file_map.items():
        data = fpath.read_bytes()
        hashes[rel_path] = sha256_of_bytes(data)
        
    # Also hash the runner
    hashes["run_csiro_validation.py"] = sha256_of_bytes(runner_code.encode("utf-8"))
    
    # Generate SHA256SUMS.txt
    sums_lines = [f"{h}  {path}" for path, h in sorted(hashes.items())]
    sums_content = "\n".join(sums_lines) + "\n"
    
    # Write ZIP
    print(f"\nWriting archive to {ZIP_OUT_PATH}...")
    with zipfile.ZipFile(ZIP_OUT_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("SHA256SUMS.txt", sums_content)
        zf.writestr("run_csiro_validation.py", runner_code)
        for rel_path, fpath in file_map.items():
            zf.write(fpath, arcname=rel_path)
            
    zip_bytes = ZIP_OUT_PATH.read_bytes()
    zip_sha = sha256_of_bytes(zip_bytes)
    zip_size_mb = len(zip_bytes) / (1024 * 1024)
    print(f"Archive built successfully!")
    print(f"  Path: {ZIP_OUT_PATH}")
    print(f"  Size: {zip_size_mb:.2f} MB")
    print(f"  SHA-256: {zip_sha}")
    print(f"  Total archive entries: {len(hashes) + 1}")
    
    # Verification in isolated temporary directory
    print("\nVerifying archive in isolated temporary directory...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        with zipfile.ZipFile(ZIP_OUT_PATH, "r") as zf:
            zf.extractall(tmp_path)
            
        # 1. Compile check on runner
        runner_file = tmp_path / "run_csiro_validation.py"
        r_comp = subprocess.run([sys.executable, "-m", "py_compile", str(runner_file)], capture_output=True, text=True)
        if r_comp.returncode != 0:
            print("FAILED: run_csiro_validation.py failed compilation:")
            print(r_comp.stderr)
            sys.exit(1)
        print("  py_compile run_csiro_validation.py: PASS")
        
        # 2. Run pytest suite inside tmpdir
        r_test = subprocess.run([sys.executable, "-m", "pytest", str(tmp_path / "tests"), "-v"], capture_output=True, text=True)
        if r_test.returncode != 0:
            print("FAILED: pytest in isolated directory failed:")
            print(r_test.stdout)
            print(r_test.stderr)
            sys.exit(1)
        lines = [l for l in r_test.stdout.splitlines() if "passed" in l]
        print(f"  pytest tests (isolated): PASS ({lines[-1] if lines else 'OK'})")
        
        # 3. Run evaluation script inside tmpdir
        script_file = tmp_path / "scripts" / "evaluate_csiro_ahu10_validation.py"
        r_exec = subprocess.run([sys.executable, str(script_file)], capture_output=True, text=True, cwd=str(tmp_path))
        if r_exec.returncode != 0:
            print("FAILED: execution of evaluation script in isolated directory failed:")
            print(r_exec.stderr)
            sys.exit(1)
        print("  execution of evaluate_csiro_ahu10_validation.py (isolated): PASS (exit code 0)")
        
    print("\nAll standalone isolation checks passed 100%!")


if __name__ == "__main__":
    main()
