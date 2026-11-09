import io
import math
import random
import sys
from pathlib import Path
from datetime import datetime, timedelta

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
from backend.app.db.session import SessionLocal, Base, engine
from backend.app.services.import_service import ImportService

def generate_synthetic_demo_csv() -> io.BytesIO:
    """
    Generates a physics-inspired 7-day AHU synthetic dataset.
    Explicitly labeled as SYNTHETIC_DEMO.
    Includes:
    - Diurnal outdoor temperature cycle (55°F - 85°F).
    - Occupied (06:00 - 22:00) vs unoccupied modes.
    - Economizer damper modulation and cooling coil response.
    - Injected fault: cooling coil valve stuck at 20% on day 5-7.
    - Injected data quality gap: 45 min missing data on day 3.
    """
    random.seed(42)
    start_time = datetime(2024, 6, 1, 0, 0, 0)
    records = []

    # 7 days * 24 * 60 = 10,080 minutes
    total_minutes = 7 * 24 * 60
    current_time = start_time

    for m in range(total_minutes):
        # Injected gap on day 3 between 14:00 and 14:45
        if m >= (2 * 24 * 60 + 14 * 60) and m < (2 * 24 * 60 + 14 * 60 + 45):
            current_time += timedelta(minutes=1)
            continue

        hour = current_time.hour
        is_occupied = 1.0 if (6 <= hour < 22) else 0.0

        # Outdoor air temp: diurnal sine wave
        time_fraction = (current_time.hour + current_time.minute / 60.0) / 24.0
        oa_base = 65.0 + 15.0 * math.sin(2 * math.pi * (time_fraction - 0.35))
        oa_noise = random.gauss(0, 0.4)
        oa_temp = round(oa_base + oa_noise, 2)

        # Return air temp (stable zone return around 72-74 degF)
        ra_temp = round(72.5 + 1.2 * math.sin(2 * math.pi * (time_fraction - 0.5)) + random.gauss(0, 0.2), 2)

        # Outdoor damper: 15% min in occupied, modulates up if OA is cool (economizer)
        if is_occupied > 0.5:
            if 55.0 <= oa_temp <= 65.0:
                oa_dmpr_cmd = round(min(1.0, max(0.15, (65.0 - oa_temp) / 10.0)), 3)
            else:
                oa_dmpr_cmd = 0.15
        else:
            oa_dmpr_cmd = 0.0

        # Mixed air temp follows mass balance
        alpha = oa_dmpr_cmd if is_occupied > 0.5 else 0.0
        ma_temp = round(alpha * oa_temp + (1.0 - alpha) * ra_temp + random.gauss(0, 0.15), 2)

        sa_temp_spt = 55.0

        # Day 5 onwards: simulate fault (cooling coil stuck at 0.18)
        is_fault_period = m >= (4 * 24 * 60)
        
        # Desired cooling
        cooling_demand = max(0.0, min(1.0, (ma_temp - sa_temp_spt) / 15.0)) if is_occupied > 0.5 else 0.0
        chwc_vlv_cmd = round(cooling_demand, 3)

        if is_fault_period:
            # Fault: actual valve stuck at 0.18 regardless of demand
            chwc_vlv_actual = 0.18
        else:
            chwc_vlv_actual = chwc_vlv_cmd

        # Supply air temp based on actual cooling coil position
        cooling_delivered = chwc_vlv_actual * max(0.0, ma_temp - 52.0)
        sa_temp = round(ma_temp - cooling_delivered + (1.2 if is_occupied > 0.5 else 0.0) + random.gauss(0, 0.2), 2)

        fan_cmd = 1.0 if is_occupied > 0.5 else 0.0
        fan_speed = 0.85 if is_occupied > 0.5 else 0.0
        fan_watts = round(fan_speed * 3200.0 + random.gauss(0, 20), 1) if is_occupied > 0.5 else 0.0

        # Static pressure
        sa_sp = round(1.5 + random.gauss(0, 0.05), 3) if is_occupied > 0.5 else 0.0
        sa_spspt = 1.5

        records.append({
            "Datetime": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            "OA_TEMP": oa_temp,
            "RA_TEMP": ra_temp,
            "MA_TEMP": ma_temp,
            "SA_TEMP": sa_temp,
            "SA_TEMPSPT": sa_temp_spt,
            "CHWC_VLV_DM": chwc_vlv_cmd,
            "CHWC_VLV": chwc_vlv_actual,
            "OA_DMPR_DM": oa_dmpr_cmd,
            "OA_DMPR": oa_dmpr_cmd,
            "SF_SPD_DM": fan_cmd,
            "SF_SPD": fan_speed,
            "SF_WAT": fan_watts,
            "SA_SP": sa_sp,
            "SA_SPSPT": sa_spspt,
            "SYS_CTL": is_occupied,
            "ZONE_TEMP_1": round(71.5 + random.gauss(0, 0.3), 2),
            "ZONE_TEMP_2": round(72.0 + random.gauss(0, 0.3), 2),
            "ZONE_TEMP_3": round(73.2 + random.gauss(0, 0.3), 2)
        })

        current_time += timedelta(minutes=1)

    df = pd.DataFrame(records)
    csv_bytes = io.BytesIO()
    df.to_csv(csv_bytes, index=False)
    csv_bytes.seek(0)
    return csv_bytes

def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        print("Generating realistic SYNTHETIC_DEMO AHU dataset...")
        csv_bytes = generate_synthetic_demo_csv()
        filename = "synthetic_demo_ahu_7days.csv"
        
        result = ImportService.process_csv_file(
            db=db,
            file_obj=csv_bytes,
            filename=filename,
            source_kind="SYNTHETIC_DEMO",
            source_fault_label="COOLING_VALVE_STUCK_018",
            source_fault_label_type="VALVE_STUCK",
            provenance_note="Синтетический демонстрационный сценарий (7 дней, 1-минутный шаг, смоделировано зависание клапана охлаждения на 18% с 5-го дня, 45-минутный пропуск связи на 3-й день)."
        )
        print("Demo import completed successfully:")
        print(result)
    finally:
        db.close()

if __name__ == "__main__":
    main()
