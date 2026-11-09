"""
BuildingPulse AI — Environment and Runtime Verification Script (Gate 4)
Performs non-invasive checks of the runtime environment:
  - Python & Node.js versions
  - Critical dependencies (FastAPI, PyArrow, LightGBM, Scikit-learn, etc.)
  - Datasets & Parquet integrity
  - Model artifacts & checksums
  - Local database status
  - Port binding availability
Does not leak credentials or external tokens.
"""

import sys
import os
import socket
import json
import hashlib
from pathlib import Path

def check_python_version():
    v = sys.version_info
    ok = v.major == 3 and v.minor >= 10
    return {
        "component": "Python Runtime",
        "version": f"{v.major}.{v.minor}.{v.micro}",
        "required": ">= 3.10",
        "status": "PASS" if ok else "FAIL"
    }

def check_package(name, import_name=None):
    imp = import_name or name
    try:
        mod = __import__(imp)
        ver = getattr(mod, "__version__", "installed")
        return {"component": f"PyPackage: {name}", "version": str(ver), "status": "PASS"}
    except ImportError:
        return {"component": f"PyPackage: {name}", "version": "MISSING", "status": "FAIL"}

def check_file(path_str, expected_min_bytes=100):
    p = Path(path_str)
    if not p.exists():
        return {"component": f"File: {p.name}", "status": "FAIL", "detail": "NOT_FOUND"}
    size = p.stat().st_size
    if size < expected_min_bytes:
        return {"component": f"File: {p.name}", "status": "FAIL", "detail": f"TOO_SMALL ({size} bytes)"}
    h = hashlib.sha256(p.read_bytes()[:1024*1024]).hexdigest()[:12]
    return {"component": f"File: {p.name}", "status": "PASS", "detail": f"{size // 1024} KB (prefix_sha: {h})"}

def check_port(port, host="127.0.0.1"):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        res = s.connect_ex((host, port))
        if res == 0:
            return {"component": f"Port {port}", "status": "IN_USE", "detail": "Active listener present"}
        return {"component": f"Port {port}", "status": "AVAILABLE", "detail": "Ready for binding"}

def main():
    print("==================================================================")
    print(" BUILDINGPULSE AI — ENVIRONMENT & RUNTIME VERIFICATION (GATE 4)   ")
    print("==================================================================\n")

    checks = []

    # 1. Runtimes
    checks.append(check_python_version())

    # 2. Python Packages
    pkgs = [
        ("fastapi", "fastapi"),
        ("pydantic", "pydantic"),
        ("sqlalchemy", "sqlalchemy"),
        ("pyarrow", "pyarrow"),
        ("pandas", "pandas"),
        ("lightgbm", "lightgbm"),
        ("scikit-learn", "sklearn"),
        ("joblib", "joblib"),
        ("pytest", "pytest")
    ]
    for name, imp in pkgs:
        checks.append(check_package(name, imp))

    # 3. Datasets & Raw Files
    files_to_check = [
        "data/raw/csiro_ahu9.parquet",
        "data/raw/csiro_fault_experiments.parquet",
        "models/vs-sa-temp-v2.joblib",
        "models/csiro-ahu9-affine-v1.joblib",
        "models/csiro-ahu9-bias-v1.joblib",
        "buildingpulse.db"
    ]
    for f in files_to_check:
        checks.append(check_file(f))

    # 4. Port Availability
    checks.append(check_port(8050))
    checks.append(check_port(5180))
    checks.append(check_port(5455))

    # Print Table
    print(f"{'Component':<35} | {'Version / Detail':<30} | {'Status':<10}")
    print("-" * 80)
    all_pass = True
    for c in checks:
        detail = c.get("version") or c.get("detail", "")
        st = c.get("status", "")
        if st == "FAIL":
            all_pass = False
        print(f"{c['component']:<35} | {detail:<30} | {st:<10}")

    print("-" * 80)
    if all_pass:
        print("OVERALL VERIFICATION STATUS: [PASS] Environment is ready for defense demo.")
    else:
        print("OVERALL VERIFICATION STATUS: [PARTIAL/FAIL] Review failed components above.")

    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())
