import argparse
import io
import os
import sys
import zipfile
from pathlib import Path
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
from backend.app.core.config import settings
from backend.app.db.session import SessionLocal, Base, engine
from backend.app.services.import_service import ImportService
from scripts.inspect_remote_zip import RemoteZipFile

LBNL_ZIP_URL = "https://fdddata.lbl.gov/data/Simulated_LBNL_FDD_Data_Sets_SDAHU/LBNL_FDD_Data_Sets_SDAHU.zip"

FAULT_METADATA_MAP = {
    "AHU_annual.csv": ("FAULT_FREE", "FAULT_FREE", "Эталонный симулированный год без неисправностей (Chicago TMY)"),
    "coi_stuck_025_annual.csv": ("COI_STUCK_025", "VALVE_STUCK", "Зависание клапана охлаждения на 25%"),
    "coi_stuck_050_annual.csv": ("COI_STUCK_050", "VALVE_STUCK", "Зависание клапана охлаждения на 50%"),
    "coi_leakage_025_annual.csv": ("COI_LEAK_025", "VALVE_LEAK", "Протечка клапана охлаждения 25%"),
    "damper_stuck_025_annual.csv": ("DAMPER_STUCK_025", "DAMPER_STUCK", "Зависание заслонки наружного воздуха на 25%"),
    "oa_bias_2_annual.csv": ("OA_BIAS_POS_2C", "SENSOR_BIAS", "Смещение датчика наружной температуры +2°C"),
    "coi_bias_2_annual.csv": ("COI_BIAS_POS_2C", "UNKNOWN", "Исходная метка имени CSV. Привязка к датчику не подтверждена")
}

def import_from_remote_zip(
    file_in_archive: str = "AHU_annual.csv",
    max_days: Optional[int] = 14
) -> dict:
    """
    Streams a slice of real LBNL simulation data from the remote archive using Range requests.
    """
    print(f"Connecting to remote LBNL archive: {LBNL_ZIP_URL}...")
    rz = RemoteZipFile(LBNL_ZIP_URL)
    zf = zipfile.ZipFile(rz)

    full_path_in_zip = f"LBNL_FDD_Dataset_SDAHU/{file_in_archive}"
    if full_path_in_zip not in zf.namelist():
        raise ValueError(f"Exact archive member {full_path_in_zip} not found")

    print(f"Streaming {full_path_in_zip}...")
    with zf.open(full_path_in_zip) as zf_file:
        # Read header + lines
        lines = []
        # Max minutes: e.g. 14 days = 14 * 1440 = 20,160 lines + header
        max_lines = (max_days * 1440 + 1) if max_days else 600000
        for i in range(max_lines):
            line = zf_file.readline()
            if not line:
                break
            lines.append(line)
            if i > 0 and i % 5000 == 0:
                print(f"  Streamed {i} minutes of historical simulation...")

    csv_bytes = io.BytesIO(b"".join(lines))

    fault_label, fault_type, desc = FAULT_METADATA_MAP.get(
        file_in_archive,
        ("UNKNOWN_FAULT", "UNKNOWN", f"Файл {file_in_archive}")
    )

    db = SessionLocal()
    try:
        filename = f"lbnl_{file_in_archive}"
        result = ImportService.process_csv_file(
            db=db,
            file_obj=csv_bytes,
            filename=filename,
            source_kind="SIMULATED_BENCHMARK",
            source_fault_label=fault_label,
            source_fault_label_type=fault_type,
            provenance_note=f"Официальный датасет LBNL Single Duct AHU (EnergyPlus / TMY Chicago). {desc}. Диапазон: первые {max_days or 'все'} дней."
        )
        return result
    finally:
        db.close()

def main():
    parser = argparse.ArgumentParser(description="Импорт сценариев LBNL SD-AHU в BuildingPulse AI")
    parser.add_argument("--remote-file", type=str, default="AHU_annual.csv", help="Имя CSV в архиве (например AHU_annual.csv или coi_stuck_025_annual.csv)")
    parser.add_argument("--days", type=int, default=14, help="Количество дней для импорта (по умолчанию 14 для быстрой загрузки; 0 для полного)")
    parser.add_argument("--local-file", type=str, default=None, help="Путь к локальному CSV или ZIP файлу")

    args = parser.parse_args()
    Base.metadata.create_all(bind=engine)

    if args.local_file:
        local_p = Path(args.local_file)
        if not local_p.exists():
            print(f"Error: local file {local_p} not found")
            sys.exit(1)
        with open(local_p, "rb") as f:
            content = f.read()
        db = SessionLocal()
        try:
            res = ImportService.process_csv_file(
                db=db,
                file_obj=io.BytesIO(content),
                filename=local_p.name,
                source_kind="SIMULATED_BENCHMARK",
                provenance_note=f"Импортирован из локального файла {local_p.name}"
            )
            print("Import result:", res)
        finally:
            db.close()
    else:
        days = args.days if args.days > 0 else None
        res = import_from_remote_zip(args.remote_file, max_days=days)
        print("Remote LBNL import result:", res)

if __name__ == "__main__":
    main()
