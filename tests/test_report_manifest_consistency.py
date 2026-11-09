import json
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT_DIR / "research" / "runs" / "rbc_nesbitt_independent_validation_manifest.json"
REPORT_PATH = ROOT_DIR / "research" / "reports" / "STAGE8B_INDEPENDENT_EXTERNAL_VALIDATION_REPORT.md"
POINTWISE_CSV = ROOT_DIR / "research" / "runs" / "rbc_nesbitt_independent_pointwise_predictions.csv"

def test_manifest_and_report_files_exist():
    assert MANIFEST_PATH.exists(), "Validation manifest must exist"
    assert REPORT_PATH.exists(), "Scientific report must exist"
    assert POINTWISE_CSV.exists(), "Pointwise predictions CSV must exist"

def test_strict_json_no_nan_literals():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        text = f.read()
    assert "NaN" not in text, "Manifest must not contain unquoted NaN literals"
    assert "Infinity" not in text, "Manifest must not contain Infinity literals"
    data = json.loads(text)
    assert data["protocol_status"] == "POST_HOC_FORENSIC_REANALYSIS_TEST_EXPOSED"

def test_no_false_positive_summer_claims():
    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        report_text = f.read()
    # P0-01 Audit Requirement: Report must NOT contain hardcoded false positive claims
    assert "Recall = 100%" not in report_text, "Report must not claim 100% summer detection"
    assert "(3/3)" not in report_text, "Report must not claim (3/3) summer detection"
    assert "3 из 3" not in report_text, "Report must not claim 3 of 3 summer detection"
    assert "New Onset Recall = 0.0% (0/3)" in report_text, "Report must explicitly state 0.0% (0/3) summer recall"

def test_numeric_parity_between_manifest_and_report():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        report_text = f.read()
        
    slices = manifest["evaluation_slices"]
    
    # 1. Summer M2 Exp350 onset recall (must be 0.0%)
    m2_sum_onset = slices["summer_in_domain"]["M2_Control_Exp350"]["episode_recall_onset"]
    assert m2_sum_onset == 0.0
    
    # 2. All seasons M2 Mat400 onset recall (must be 20.0%, 1/5)
    m2_all_onset = slices["all_seasons_combined"]["M2_Control_Mat400"]["episode_recall_onset"]
    assert m2_all_onset == 0.2
    assert "New Onset Recall M2 $\\tau=4.00$ по всем 5 сценариям составляет **20.0% (1/5)**" in report_text
    
    # 3. All seasons M6 Damper BAS onset recall (must be 40.0%, 2/5)
    m6_all_onset = slices["all_seasons_combined"]["M6_Direct_Damper_BAS400"]["episode_recall_onset"]
    assert m6_all_onset == 0.4
    assert "M6 составляет **40.0% (2/5)**" in report_text
    
    # 4. Winter M6 FAR (must match 66.27%)
    m6_win_far = slices["winter_out_of_domain"]["M6_Direct_Damper_BAS400"]["pointwise_far"]
    assert m6_win_far == 0.6627
    assert "FAR = 66.27%" in report_text
    
    # 5. DomainGuard winter coverage (must match 0.0%)
    dg_win_cov = slices["winter_out_of_domain"]["M2_Control_Exp350_DomainGuard"]["normal_coverage_pct"]
    assert dg_win_cov == 0.0
    assert "охват нормы и аварий составляет **0.0%**" in report_text
