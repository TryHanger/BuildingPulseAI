import io
import os
import sys
import time
import zipfile
from pathlib import Path
from typing import Optional, List, Dict

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
from backend.app.core.config import settings
from backend.app.db.session import SessionLocal, Base, engine
from backend.app.services.import_service import ImportService
from scripts.inspect_remote_zip import RemoteZipFile

LBNL_ZIP_URL = "https://fdddata.lbl.gov/data/Simulated_LBNL_FDD_Data_Sets_SDAHU/LBNL_FDD_Data_Sets_SDAHU.zip"

LBNL_ALL_FAULT_METADATA: Dict[str, tuple] = {
    "AHU_annual.csv": (
        "FAULT_FREE",
        "FAULT_FREE",
        "Эталонный симулированный год без неисправностей (Chicago TMY)"
    ),
    "coi_bias_-4_annual.csv": (
        "SENSOR_BIAS_NEG_4C",
        "SENSOR_BIAS_SA",
        "Смещение датчика притока -4°C"
    ),
    "coi_bias_-2_annual.csv": (
        "SENSOR_BIAS_NEG_2C",
        "SENSOR_BIAS_SA",
        "Смещение датчика притока -2°C"
    ),
    "coi_bias_2_annual.csv": (
        "SENSOR_BIAS_POS_2C",
        "SENSOR_BIAS_SA",
        "Смещение датчика притока +2°C"
    ),
    "coi_bias_4_annual.csv": (
        "SENSOR_BIAS_POS_4C",
        "SENSOR_BIAS_SA",
        "Смещение датчика притока +4°C"
    ),
    "coi_stuck_010_annual.csv": (
        "COI_STUCK_010",
        "COOLING_VALVE_STUCK",
        "Заклинивание клапана охлаждения на 10%"
    ),
    "coi_stuck_025_annual.csv": (
        "COI_STUCK_025",
        "COOLING_VALVE_STUCK",
        "Заклинивание клапана охлаждения на 25%"
    ),
    "coi_stuck_050_annual.csv": (
        "COI_STUCK_050",
        "COOLING_VALVE_STUCK",
        "Заклинивание клапана охлаждения на 50%"
    ),
    "coi_stuck_075_annual.csv": (
        "COI_STUCK_075",
        "COOLING_VALVE_STUCK",
        "Заклинивание клапана охлаждения на 75%"
    ),
    "damper_stuck_010_annual.csv": (
        "DAMPER_STUCK_010",
        "OUTDOOR_DAMPER_STUCK",
        "Заклинивание заслонки на 10%"
    ),
    "damper_stuck_025_annual.csv": (
        "DAMPER_STUCK_025",
        "OUTDOOR_DAMPER_STUCK",
        "Заклинивание заслонки на 25%"
    ),
    "damper_stuck_075_annual.csv": (
        "DAMPER_STUCK_075",
        "OUTDOOR_DAMPER_STUCK",
        "Заклинивание заслонки на 75%"
    ),
    "damper_stuck_100_annual_short.csv": (
        "DAMPER_STUCK_100",
        "OUTDOOR_DAMPER_STUCK",
        "Заклинивание заслонки на 100% (короткий прогон с апреля)"
    )
}

def stream_and_import_scenario(
    zf: zipfile.ZipFile,
    file_name: str,
    max_days: Optional[int] = 14
) -> dict:
    full_zip_path = f"LBNL_FDD_Dataset_SDAHU/{file_name}"
    print(f"Streaming {file_name} (first {max_days or 'all'} days)...")
    t0 = time.time()
    
    with zf.open(full_zip_path) as zf_file:
        lines = []
        max_lines = (max_days * 1440 + 1) if max_days else 600000
        for i in range(max_lines):
            line = zf_file.readline().decode("utf-8", errors="ignore")
            if not line:
                break
            lines.append(line)
            if i > 0 and i % 100000 == 0:
                print(f"  Streamed {i} records in {time.time() - t0:.1f}s...")
                
    elapsed = time.time() - t0
    print(f"  Completed reading {len(lines) - 1} records in {elapsed:.2f}s")
    
    csv_text = "".join(lines)
    csv_bytes = io.BytesIO(csv_text.encode("utf-8"))
    
    label, label_type, desc = LBNL_ALL_FAULT_METADATA.get(
        file_name,
        ("UNKNOWN_FAULT", "UNKNOWN", file_name)
    )
    
    db = SessionLocal()
    try:
        filename = f"lbnl_{file_name}"
        result = ImportService.process_csv_file(
            db=db,
            file_obj=csv_bytes,
            filename=filename,
            source_kind="SIMULATED_BENCHMARK",
            source_fault_label=label,
            source_fault_label_type=label_type,
            provenance_note=f"LBNL Single Duct AHU benchmark. {desc}. Интервал: {len(lines)-1} минут.",
            max_size=None
        )
        return result
    finally:
        db.close()

def main():
    Base.metadata.create_all(bind=engine)
    print("Connecting to remote LBNL archive...")
    rz = RemoteZipFile(LBNL_ZIP_URL)
    zf = zipfile.ZipFile(rz)
    print("Connected successfully. Starting Stage 3 datasets import...")

    results = {}
    for filename in LBNL_ALL_FAULT_METADATA.keys():
        try:
            # For AHU_annual.csv, import full year (max_days=None) to have complete seasonal data!
            days = None if filename == "AHU_annual.csv" else 14
            res = stream_and_import_scenario(zf, filename, max_days=days)
            results[filename] = res
            print(f"  -> Imported {filename}: status={res.get('status')}, scenario_id={res.get('scenario_id')}")
        except Exception as e:
            print(f"  -> ERROR importing {filename}: {e}")
            results[filename] = {"status": "ERROR", "error": str(e)}

    print("\n--- Import Summary ---")
    for k, v in results.items():
        print(f"  {k}: {v.get('status', 'OK')} (scenario={v.get('scenario_id')})")

if __name__ == "__main__":
    main()
