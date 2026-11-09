# REPRODUCIBILITY GUIDE — Stage 8C Release Candidate

This guide provides end-to-end instructions for reproducing all Stage 8C scientific results, model fits, pointwise predictions, manifests, reports, and tests from raw Parquet telemetry in an isolated environment.

---

## 1. System Requirements

- **Python:** 3.11+ (tested on Python 3.11.6 x86_64)
- **Disk Space:** ~50 MB (excluding virtualenv)
- **RAM:** Minimum 2 GB
- **OS:** Windows 10/11, Ubuntu 22.04+, macOS 13+

---

## 2. Environment Setup

```bash
# 1. Create a fresh virtual environment
python -m venv venv_reproduce

# 2. Activate environment
# On Linux / macOS:
source venv_reproduce/bin/activate
# On Windows PowerShell:
.\venv_reproduce\Scripts\Activate.ps1

# 3. Install core dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 3. Verification of Raw Artifacts (SHA-256)

Verify raw input files before running the pipeline:

```bash
# On Linux / macOS:
sha256sum -c SHA256SUMS.txt

# Or via Python on any platform:
python -c "
import hashlib, sys
lines = open('SHA256SUMS.txt').read().splitlines()
all_ok = True
for l in lines:
    if not l.strip() or l.startswith('#'): continue
    parts = l.split()
    h, path = parts[0], parts[1].replace('\\\\', '/')
    data = open(path, 'rb').read()
    ch = hashlib.sha256(data).hexdigest()
    if ch != h:
        print(f'FAIL: {path}'); all_ok = False
if all_ok: print('All checksums match 100%')
"
```

Expected raw file hashes:
- `data/raw/csiro_ahu10.parquet`: `f789b7efc5a0ec9857d5126137f727b94ad0895b63ff9b2170dd5651b26d3610`
- `data/raw/csiro_fault_experiments.parquet`: `b7ebad8a25baa8da7740186eb52a1eb62d0602c82dcc394ed0527ea5c6fd65f2`

---

## 4. Execution: Raw Parquet to Scientific Report

### Single Command Orchestration:

```bash
python run_csiro_validation.py
```

This runs:
1. `scripts/evaluate_csiro_ahu10_validation.py`: Resamples raw 30-second telemetry to 5 minutes across 33 selected days (3,199 points), constructs global fault masks from 103 experiments, fits local models on 873 clean operational training points, predicts residuals, evaluates 10 experiments (separating 7 observable from 3 left-censored), computes pure seasonal FAR slices (1861 baseline points), and dynamically exports manifest and report.
2. `pytest tests -v`: Runs the 43 standalone regression and forensic tests.
3. Asserts exact parity between the generated JSON manifest and Markdown report.

### Step-by-Step Execution:

```bash
# Step A: Compile scripts to check syntax
python -m py_compile run_csiro_validation.py scripts/evaluate_csiro_ahu10_validation.py

# Step B: Run evaluation pipeline
python scripts/evaluate_csiro_ahu10_validation.py

# Step C: Run test suite
pytest tests -v
```

---

## 5. Expected Primary Scientific Outputs

| Metric | Target / Model | Exact Value | Float Tolerance |
| :--- | :--- | :---: | :---: |
| **Grid Total Points** | 33 selected days | **3,199** | Exact integer |
| **Clean Train Points** | Sept 2–12, 2013 | **873** | Exact integer |
| **Clean Normal Points** | 15 baselines + 9 exp days | **1,861** | Exact integer |
| **Observable Events** | Observable Physical Onset | **7** | Exact integer |
| **Left-Censored Events** | Pre-09:00 Onset (176, 194, 322) | **3** | Exact integer |
| **M1 $\tau=3.00$ Observable Recall** | Thermal Local | **4/7 (57.14%)** | $\pm 0.001$ |
| **M2 $\tau=4.00$ Observable Recall** | Control Local | **2/7 (28.57%)** | $\pm 0.001$ |
| **M3 $\tau=3.00$ Observable Recall** | Linear Fusion Local | **4/7 (57.14%)** | $\pm 0.001$ |
| **M2 $\tau=4.00$ Total FAR** | Normal Baseline (N=1861) | **750/1861 (40.30%)** | $\pm 0.001$ |
| **M2 $\tau=4.00$ Summer FAR** | Summer Baseline (N=485) | **220/485 (45.36%)** | $\pm 0.001$ |
| **M1 $\tau=3.00$ Total FAR** | Normal Baseline (N=1861) | **979/1861 (52.61%)** | $\pm 0.001$ |
| **M1 $\tau=3.00$ Summer FAR** | Summer Baseline (N=485) | **480/485 (98.97%)** | $\pm 0.001$ |
| **Zero-Shot M2 $\tau=4.00$ Status** | RBC-Nesbitt to CSIRO | **`NOT_COMPARABLE`** | Exact string |
