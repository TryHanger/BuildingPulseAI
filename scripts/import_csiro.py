"""
Import adapter for CSIRO Operational AHU Dataset (Newcastle, Australia).
Maps real-world field BMS telemetry to BuildingPulse AI canonical schema,
preserves raw immutable Parquet provenance, resamples to 1-minute resolution,
and registers scenario with source_kind="REAL_FIELD_BMS" and Domain Guard protection.
"""

import argparse
import io
import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.db.session import SessionLocal, engine, Base
from backend.app.services.import_service import ImportService

def import_csiro_ahu9_scenario(
    raw_file_path: str = "data/raw/csiro_ahu9.parquet",
    start_date: str = "2013-10-28 00:00:00",
    end_date: str = "2013-11-12 23:59:00",
    output_filename: str = "csiro_ahu9_real_bms_field_faults.csv"
):
    raw_path = Path(raw_file_path)
    if not raw_path.exists():
        raise FileNotFoundError(f"Raw CSIRO file '{raw_path}' not found. Please download first.")

    print(f"Loading raw CSIRO telemetry from '{raw_path}'...")
    df_raw = pd.read_parquet(raw_path)

    print(f"Filtering date slice: {start_date} to {end_date}...")
    df_slice = df_raw.loc[start_date:end_date].copy()
    if df_slice.empty:
        raise ValueError(f"No records found in range {start_date} to {end_date}")

    print(f"  Raw 30-second rows in slice: {len(df_slice)}")

    # 1. Resample from 30s to 1-minute (mean aggregation)
    # Drop completely empty off-hours (nights/weekends when BMS was offline)
    df_1m = df_slice.resample("1min").mean().dropna(how="all")
    print(f"  Resampled 1-minute rows with telemetry: {len(df_1m)}")

    # 2. Canonical Channel Mapping (use .values to prevent Pandas index mismatch)
    df_canonical = pd.DataFrame(index=df_1m.index)
    df_canonical["OA_TEMP"] = df_1m["AHU9ahuOaTemp"].values.round(2)
    df_canonical["RA_TEMP"] = df_1m["AHU9ahuRaTemp"].values.round(2)
    df_canonical["MA_TEMP"] = df_1m["AHU9ahuMaTemp"].values.round(2)
    df_canonical["SA_TEMP"] = df_1m["AHU9ahuSaTemp"].values.round(2)
    df_canonical["SA_TEMPSPT"] = df_1m["AHU9ahuSaTempSP"].values.round(2)

    # Actuators (convert 0..100% to fraction 0..1)
    df_canonical["CHWC_VLV_DM"] = np.clip(df_1m["AHU9ahuCcValve"].values / 100.0, 0.0, 1.0).round(4)
    df_canonical["OA_DMPR_DM"] = np.clip(df_1m["AHU9ahuOaDamper"].values / 100.0, 0.0, 1.0).round(4)
    df_canonical["RA_DMPR_DM"] = np.clip(df_1m["AHU9ahuRaDamper"].values / 100.0, 0.0, 1.0).round(4)

    # Fan Command and Speed
    fan_spd = df_1m["AHU9ahuSaFanSpeed"].values
    df_canonical["SF_SPD_DM"] = (fan_spd > 5.0).astype(float)
    df_canonical["SF_CS"] = np.clip(fan_spd / 100.0, 0.0, 1.0).round(4)

    # Static Pressure: Pa to in. w.g. (1 Pa = 0.00401463 in. w.g.)
    df_canonical["SA_SP"] = (df_1m["AHU9ahuSaPressure"].values * 0.00401463).round(3)

    # Zone Temperatures
    df_canonical["ZONE_TEMP_1"] = df_1m["AHU9ahuZoneTemp"].values.round(2)
    df_canonical["ZONE_TEMP_2"] = df_1m["AHU9ahuZoneTemp.1"].values.round(2)
    df_canonical["ZONE_TEMP_3"] = df_1m["AHU9ahuZoneTemp.2"].values.round(2)

    # Add Datetime column from DatetimeIndex
    df_canonical.reset_index(inplace=True)
    df_canonical.rename(columns={df_canonical.columns[0]: "Datetime"}, inplace=True)
    df_canonical["Datetime"] = df_canonical["Datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")

    # Convert to CSV buffer for ImportService
    csv_buf = io.StringIO()
    df_canonical.to_csv(csv_buf, index=False)
    csv_bytes = io.BytesIO(csv_buf.getvalue().encode("utf-8"))

    # Register in DB via ImportService
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        print("Registering scenario in BuildingPulse AI database...")
        res = ImportService.process_csv_file(
            db=db,
            file_obj=csv_bytes,
            filename=output_filename,
            source_kind="REAL_FIELD_BMS",
            source_fault_label="CHW_VALVE_PROXY_STUCK_AND_DAMPER",
            source_fault_label_type="FIELD_INJECTED_FAULT",
            provenance_note=(
                "CSIRO Operational AHU Dataset (Newcastle, Australia). "
                "Реальные полевые измерения BMS Schneider Electric TAC Vista офисного здания Energy Centre. "
                "Экспериментально введённые дефекты клапана охлаждения и заслонок (31.10.2013 и 11.11.2013). "
                "Тип данных: REAL_FIELD_BMS с активным доменным барьером Domain Guard."
            )
        )
        print("Import successfully finished!")
        print(f"  Scenario ID: {res.get('scenario_id')}")
        print(f"  Rows count:  {res.get('total_rows', res.get('row_count'))}")
        print(f"  Channels:    {len(res.get('channels', []))}")
        return res
    finally:
        db.close()

def main():
    parser = argparse.ArgumentParser(description="Импорт реального набора CSIRO AHU9 в BuildingPulse AI")
    parser.add_argument("--raw-file", type=str, default="data/raw/csiro_ahu9.parquet")
    parser.add_argument("--start-date", type=str, default="2013-10-28 00:00:00")
    parser.add_argument("--end-date", type=str, default="2013-11-12 23:59:00")
    args = parser.parse_args()

    import_csiro_ahu9_scenario(
        raw_file_path=args.raw_file,
        start_date=args.start_date,
        end_date=args.end_date
    )

if __name__ == "__main__":
    main()
