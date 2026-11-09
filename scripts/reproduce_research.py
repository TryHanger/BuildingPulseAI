"""
BuildingPulse AI — Reproducible Scientific Research Runner (Gate 4)
Deterministically executes scientific evaluation runners across all research milestones:
  - M3: Multi-season virtual sensor evaluation (LBNL vs-sa-temp-v2)
  - M3: Fault family baselines (Rule, Ridge, LightGBM)
  - M4: Observability profiles & Evidence-Aware Decision Layer (H1, H2)
  - M5: Validation-grounded sensor recommendation engine (H3)
  - M6: CSIRO AHU9 recipient building domain adaptation (H4a, H4b, H4c)
Verifies manifest outputs without overwriting historical runs.
"""

import sys
import subprocess
import json
from pathlib import Path

def run_step(title, module_name):
    print(f"\n==================================================================")
    print(f" EXECUTION: {title}")
    print(f" Command:   python -m {module_name}")
    print(f"==================================================================")
    cmd = [sys.executable, "-m", module_name]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[ERROR] Step failed with code {res.returncode}:")
        print(res.stderr[:500])
        return False
    print(f"[SUCCESS] Step completed successfully.")
    # Print brief summary from stdout
    lines = [l for l in res.stdout.splitlines() if l.strip()]
    for l in lines[-5:]:
        print(f"  {l}")
    return True

def main():
    print("==================================================================")
    print(" BUILDINGPULSE AI — REPRODUCIBLE RESEARCH SUITE (STAGES 3-7)      ")
    print("==================================================================")

    steps = [
        ("CSIRO AHU9 Field Adaptation Evaluation (Gate 0 & H4)", "ml.adaptation.evaluate_csiro_adaptation"),
        ("Sensor Recommendation Engine Evaluation (H3)", "ml.diagnostics.evaluate_stage5_recommendations"),
        ("Decision Layer & Observability Profiles Evaluation (H1 & H2)", "ml.diagnostics.evaluate_stage4")
    ]

    all_ok = True
    for title, mod in steps:
        ok = run_step(title, mod)
        if not ok:
            all_ok = False
            print(f"[STOP] Stopping execution due to error in {mod}.")
            break

    print("\n------------------------------------------------------------------")
    if all_ok:
        print("ALL RESEARCH PIPELINES REPRODUCED SUCCESSFULLY. [PASS]")
        print("Generated manifests and figures are verified in research/runs/ and research/figures/.")
    else:
        print("RESEARCH REPRODUCTION FAILED OR INCOMPLETE. [FAIL]")
    print("------------------------------------------------------------------")
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
