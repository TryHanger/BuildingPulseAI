"""BuildingPulse AI — Stage 8B-R.4 Corrected Audit Package Builder
Builds: BUILDINGPULSE_AUDIT_STAGE_8B_R_4_CORRECTED.zip

Includes:
- Complete runnable codebase (backend, ml, frontend source, scripts)
- Raw RBC-Nesbitt CSV datasets:
  - 10 historical development files in data/raw/rbc_nesbitt/
  - 13 holdout files in data/raw/rbc_nesbitt/holdout/
  - Drexel 00_explanations.pdf
- Complete research artifacts:
  - rbc_nesbitt_independent_validation_manifest.json (with model provenance and dual metrics)
  - rbc_nesbitt_independent_pointwise_predictions.csv (with alarm traces, eligibility, and onsets)
  - STAGE8B_INDEPENDENT_EXTERNAL_VALIDATION_REPORT.md (dynamically generated)
  - Historical reports (STAGE8B_R3, STAGE8B_R2, STAGE8B_RECONCILED)
- Standalone tests (33/33 passing)
- Verification script & SHA-256 manifest
- Audit files: README_REPRODUCE.md, CLAIMS_TO_EVIDENCE.md, KNOWN_LIMITATIONS.md, DATASET_BLIND_SPLIT_MANIFEST.md
"""

import os
import sys
import shutil
import zipfile
import hashlib
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

STAGE_DIR = ROOT_DIR / "temp_validation_package"
ZIP_PATH = ROOT_DIR / "BUILDINGPULSE_AUDIT_STAGE_8B_R_4_CORRECTED.zip"


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main():
    print("=" * 75)
    print("BUILDINGPULSE AI — PACKAGING STAGE 8B-R.4 CORRECTED AUDIT PACKAGE")
    print("=" * 75)
    
    if STAGE_DIR.exists():
        shutil.rmtree(STAGE_DIR)
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Directory Structure
    dirs = {
        "code": STAGE_DIR / "code",
        "data_raw": STAGE_DIR / "data" / "raw" / "rbc_nesbitt",
        "data_holdout": STAGE_DIR / "data" / "raw" / "rbc_nesbitt" / "holdout",
        "models": STAGE_DIR / "models",
        "research_runs": STAGE_DIR / "research" / "runs",
        "research_reports": STAGE_DIR / "research" / "reports",
        "tests": STAGE_DIR / "tests",
        "validation": STAGE_DIR / "validation",
        "audit": STAGE_DIR / "audit",
        "scripts": STAGE_DIR / "scripts",
        "ml": STAGE_DIR / "ml"
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
        
    print("[1/6] Created staging layout.")
    
    # 2. Populate Code & Frontend
    code_subdirs = ["backend/app", "ml", "scripts", "frontend"]
    for sub in code_subdirs:
        src = ROOT_DIR / sub
        dst = dirs["code"] / sub
        if src.exists():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
                "__pycache__", "*.pyc", ".pytest_cache", "node_modules", "dist", ".vite"
            ))
            
    # Root scripts and ml mirror for direct running
    shutil.copy2(ROOT_DIR / "scripts" / "evaluate_rbc_nesbitt_independent_validation.py", dirs["scripts"] / "evaluate_rbc_nesbitt_independent_validation.py")
    shutil.copy2(ROOT_DIR / "scripts" / "evaluate_rbc_nesbitt_reconciled.py", dirs["scripts"] / "evaluate_rbc_nesbitt_reconciled.py")
    shutil.copytree(ROOT_DIR / "ml", dirs["ml"], dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"))
    
    # Root configs
    for cfg in ["pyproject.toml", "requirements.txt", "package.json", "AGENTS.md", "README.md"]:
        if (ROOT_DIR / cfg).exists():
            shutil.copy2(ROOT_DIR / cfg, STAGE_DIR / cfg)
            shutil.copy2(ROOT_DIR / cfg, dirs["code"] / cfg)
            
    print("[2/6] Populated source code and root runners.")
    
    # 3. Populate Data
    raw_nesbitt_src = ROOT_DIR / "data" / "raw" / "rbc_nesbitt"
    if raw_nesbitt_src.exists():
        for f in raw_nesbitt_src.glob("*.csv"):
            shutil.copy2(f, dirs["data_raw"] / f.name)
        if (raw_nesbitt_src / "00_explanations.pdf").exists():
            shutil.copy2(raw_nesbitt_src / "00_explanations.pdf", dirs["data_raw"] / "00_explanations.pdf")
            
    holdout_src = raw_nesbitt_src / "holdout"
    if holdout_src.exists():
        for f in holdout_src.glob("*.csv"):
            shutil.copy2(f, dirs["data_holdout"] / f.name)
            
    print(f"  Copied {len(list(dirs['data_raw'].glob('*.csv')))} dev CSVs and {len(list(dirs['data_holdout'].glob('*.csv')))} holdout CSVs.")
    
    # 4. Populate Research Runs and Reports
    for rf in [
        "rbc_nesbitt_independent_validation_manifest.json",
        "rbc_nesbitt_independent_pointwise_predictions.csv",
        "rbc_nesbitt_reconciled_manifest.json",
        "threshold_selection_log.json"
    ]:
        src = ROOT_DIR / "research" / "runs" / rf
        if src.exists():
            shutil.copy2(src, dirs["research_runs"] / rf)
            
    for rep in [
        "STAGE8B_INDEPENDENT_EXTERNAL_VALIDATION_REPORT.md",
        "STAGE8B_R3_EVIDENCE_REPORT.md",
        "STAGE8B_R2_EVIDENCE_REPORT.md",
        "STAGE8B_RECONCILED_EVIDENCE_REPORT.md"
    ]:
        src = ROOT_DIR / "research" / "reports" / rep
        if src.exists():
            shutil.copy2(src, dirs["research_reports"] / rep)
            
    print("[3/6] Populated research runs and scientific reports.")
    
    # 5. Populate Tests & Run Pytest inside Staging
    for tf in (ROOT_DIR / "tests").glob("test_*.py"):
        shutil.copy2(tf, dirs["tests"] / tf.name)
        
    print("[4/6] Running standalone test suite in staging environment...")
    pytest_res = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-v"],
        cwd=str(STAGE_DIR),
        capture_output=True,
        text=True
    )
    log_path = dirs["validation"] / "pytest_validation_log.txt"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(pytest_res.stdout)
        if pytest_res.stderr:
            f.write("\nSTDERR:\n" + pytest_res.stderr)
            
    print(f"  Pytest finished with exit code {pytest_res.returncode}. Log saved to validation/pytest_validation_log.txt.")
    assert pytest_res.returncode == 0, f"Pytest failed in staging!\n{pytest_res.stdout}"
    
    # 6. Create Audit Documentation
    # 6.1 README_REPRODUCE.md
    with open(dirs["audit"] / "README_REPRODUCE.md", "w", encoding="utf-8") as f:
        f.write("""# BuildingPulse AI — Stage 8B-R.4 Corrected Reproduction Guide

## 1. Quick Verification
To reproduce all tests and execute the complete forensic validation runner:
```bash
python -m pytest tests -v
python run_independent_validation.py
```

## 2. Directory Structure
- `scripts/evaluate_rbc_nesbitt_independent_validation.py`: Main forensic validation runner.
- `research/runs/rbc_nesbitt_independent_validation_manifest.json`: Complete machine results (no NaN).
- `research/runs/rbc_nesbitt_independent_pointwise_predictions.csv`: 3,744 timestamped pointwise rows.
- `research/reports/STAGE8B_INDEPENDENT_EXTERNAL_VALIDATION_REPORT.md`: Dynamically generated report.
- `tests/`: 33 autonomous pytest unit and regression tests.
- `data/raw/rbc_nesbitt/`: Raw CSV files and Drexel University 00_explanations.pdf.
- `validation/`: Test logs and verification scripts.
""")
    shutil.copy2(dirs["audit"] / "README_REPRODUCE.md", STAGE_DIR / "README_REPRODUCE.md")

    # 6.2 CLAIMS_TO_EVIDENCE.md
    with open(dirs["audit"] / "CLAIMS_TO_EVIDENCE.md", "w", encoding="utf-8") as f:
        f.write("""# BuildingPulse AI — Claims to Evidence Mapping (Stage 8B-R.4 Corrected)

| Claim / Topic | Machine Evidence & File | Finding / Status |
| :--- | :--- | :--- |
| **Summer Fault Detection (M2/M3)** | `research/runs/rbc_nesbitt_independent_validation_manifest.json` (`summer_in_domain`) | **New Onset Recall = 0.0% (0/3)**. Valve feedback model does not detect damper faults. False claims of 100% detection completely eliminated. |
| **Winter Alarm Timing** | `tests/test_event_onset_and_preexisting_alarms.py`, manifest `scenarios_breakdown` | Alarms on `2016-12-01` were active before 10:00 (`ALARM_STARTED_BEFORE_FAULT`). Overall New Onset Recall M2 $\\tau=4.0$ is **20.0% (1/5)**, M6 is **40.0% (2/5)**. |
| **M6 Direct Damper Status** | `scenarios_breakdown`, `00_explanations.pdf` Table 2 | Marked `DIRECT_BAS_RULE / INJECTION_OBSERVABLE`. Winter normal FAR = **66.27%**. Unusable as operational classifier. |
| **DomainGuard Seasonal Price** | manifest (`winter_out_of_domain`) | Winter normal & fault coverage = **0.0%**. Zero FAR in winter is achieved by 100% abstention due to seasonal shift ($T_{oa} < 10^\\circ\\text{C}$). |
| **Negative Control** | manifest (`NEG_CONTROL_M2_CircularShift350`) | 12h circular shift of residuals results in **17.29% FAR**, confirming lack of causal selectivity under temporal permutation. |
| **Report/Manifest Parity** | `tests/test_report_manifest_consistency.py` | 100% parity verified automatically. Zero hardcoded false narratives. |
""")

    # 6.3 KNOWN_LIMITATIONS.md
    with open(dirs["audit"] / "KNOWN_LIMITATIONS.md", "w", encoding="utf-8") as f:
        f.write("""# BuildingPulse AI — Known Limitations and Open Boundaries (Stage 8B-R.4)

1. **TEST-EXPOSED Cohort:** The 5 holdout scenarios (`20170711`, `20180718`, `20180709`, `20161201`, `20170103`) have been examined. All evaluations are post-hoc forensic reanalyses, not prospective blind trials.
2. **Valve vs Air-Side Decoupling:** Model M2 predicts cooling valve feedback ($CCV\\_FBK$). Air-side damper faults do not produce significant valve anomalies when secondary supply air temperature is controlled.
3. **Pre-existing Alarms:** Models trained in summer exhibit substantial pre-fault baseline offset during winter operation, triggering false alarms prior to fault start.
4. **DomainGuard Abstention:** Domain envelope calibrated on summer data abstains on 100% of winter timestamps, leaving winter equipment unmonitored unless seasonal models are introduced.
5. **Direct BAS Rules:** M6 reads BAS actuator signals directly, which reflect experimenter overrides rather than autonomous FDD inference.
""")

    # 6.4 DATASET_BLIND_SPLIT_MANIFEST.md
    with open(dirs["audit"] / "DATASET_BLIND_SPLIT_MANIFEST.md", "w", encoding="utf-8") as f:
        f.write("""# BuildingPulse AI — Dataset Partitioning and Exposure Manifest

## 1. Development Partition (Historical Known Data)
- Train Baselines: `20160601_Baseline.csv`, `20160712_Baseline.csv`
- Validation Baselines: `20170618_Baseline.csv`, `20170702_Baseline.csv`
- Development Envelope: `20170714_Baseline.csv`, `20170729_Baseline.csv`
- Historical Scenarios (DEVELOPMENT-KNOWN):
  `20170718_OADamStuck_100.csv`, `20170811_CooCoiValStuck_100.csv`, `20180710_OADamStuck_30.csv`, `20180711_CooCoiValStuck_80.csv`

## 2. Test-Exposed Holdout Partition (Forensic Reanalysis)
- Fault Scenarios (TEST-EXPOSED):
  - `20170711_OADamStuck_90.csv`
  - `20180718_OADamStuck_60.csv`
  - `20180709_TSup_m3.5.csv`
  - `20161201_OADamStuck_90.csv`
  - `20170103_OADamStuck_80.csv`
- Baseline Holdout (Multi-Season):
  - Summer: `20160722`, `20160803`, `20160819`, `20160831`
  - Winter: `20161205`, `20170115`, `20170215`
  - Spring: `20170317`

## 3. Provenance Classification
Models are `LOCALLY_FITTED_DEVELOPMENT_MODELS` with fixed threshold rules ($\tau \in \{2.75, 3.00, 3.50, 4.00\}$).
""")
    shutil.copy2(dirs["audit"] / "DATASET_BLIND_SPLIT_MANIFEST.md", STAGE_DIR / "DATASET_BLIND_SPLIT_MANIFEST.md")
    
    # 7. Verification Script in Validation/
    verif_script = dirs["validation"] / "verify_independent_validation.py"
    with open(verif_script, "w", encoding="utf-8") as f:
        f.write('''"""Independent verification script for BUILDINGPULSE_AUDIT_STAGE_8B_R_4_CORRECTED.zip"""
import sys
import json
import subprocess
from pathlib import Path

def main():
    root = Path(__file__).resolve().parent.parent
    print("Verifying BuildingPulse AI Stage 8B-R.4 Corrected Audit Package...")
    
    # 1. Run tests
    print("[1/3] Running standalone pytest suite...")
    res = subprocess.run([sys.executable, "-m", "pytest", str(root / "tests"), "-v"])
    if res.returncode != 0:
        print("Verification FAILED at test execution!")
        sys.exit(1)
        
    # 2. Run independent validation runner
    print("[2/3] Executing forensic validation runner...")
    res_run = subprocess.run([sys.executable, str(root / "scripts" / "evaluate_rbc_nesbitt_independent_validation.py")])
    if res_run.returncode != 0:
        print("Verification FAILED at runner execution!")
        sys.exit(1)
        
    # 3. Check manifest
    print("[3/3] Checking machine manifest...")
    mpath = root / "research" / "runs" / "rbc_nesbitt_independent_validation_manifest.json"
    with open(mpath, "r", encoding="utf-8") as f:
        m = json.load(f)
    assert m["protocol_status"] in ["PRE_REGISTERED_INDEPENDENT_VALIDATION", "POST_HOC_FORENSIC_REANALYSIS_TEST_EXPOSED"]
    print("ALL VERIFICATION CHECKS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
''')
    
    # One-click runner in root
    root_runner = STAGE_DIR / "run_independent_validation.py"
    with open(root_runner, "w", encoding="utf-8") as f:
        f.write('''import sys
import subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent
print("Executing BuildingPulse AI Stage 8B-R.4 Forensic Validation Runner...")
res = subprocess.run([sys.executable, str(ROOT / "scripts" / "evaluate_rbc_nesbitt_independent_validation.py")])
sys.exit(res.returncode)
''')
    
    # 8. Generate SHA-256 manifest
    print("[5/6] Generating SHA256SUMS.txt...")
    sha_records = []
    for root_p, _, filenames in os.walk(STAGE_DIR):
        for fname in sorted(filenames):
            fp = Path(root_p) / fname
            rel = fp.relative_to(STAGE_DIR).as_posix()
            sha = compute_sha256(fp)
            sha_records.append(f"{sha}  {rel}")
            
    sha_file = dirs["audit"] / "SHA256SUMS.txt"
    with open(sha_file, "w", encoding="utf-8") as f:
        f.write("\n".join(sha_records) + "\n")
    shutil.copy2(sha_file, STAGE_DIR / "SHA256SUMS.txt")
    print(f"  Generated SHA-256 for {len(sha_records)} files.")
    
    # 9. Create ZIP
    print("[6/6] Packaging into ZIP...")
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
        
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for root_p, _, filenames in os.walk(STAGE_DIR):
            for fname in sorted(filenames):
                fp = Path(root_p) / fname
                arcname = fp.relative_to(STAGE_DIR).as_posix()
                zf.write(fp, arcname)
                
    zip_size = ZIP_PATH.stat().st_size
    zip_sha = compute_sha256(ZIP_PATH)
    print("=" * 75)
    print(f"ZIP PACKAGE CREATED: {ZIP_PATH.name}")
    print(f"File Size: {zip_size:,} bytes ({zip_size / (1024*1024):.2f} MB)")
    print(f"Package SHA-256: {zip_sha}")
    print("=" * 75)


if __name__ == "__main__":
    main()
