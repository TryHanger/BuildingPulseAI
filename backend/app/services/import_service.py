import hashlib
import io
import re
import uuid
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.canonical_sensors import resolve_canonical_key, CANONICAL_SENSOR_METADATA
from backend.app.db.models import Dataset, Scenario, Sensor, ImportRecord

MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB limit for web upload

def parse_timestamps(values: pd.Series) -> pd.Series:
    try:
        timestamps = pd.to_datetime(values.astype("string"), format="mixed", errors="coerce")
    except (ValueError, TypeError):
        timestamps = None
    if timestamps is None or not pd.api.types.is_datetime64_any_dtype(timestamps):
        raise HTTPException(422, detail={"code": "INVALID_TIMESTAMP"})
    for mask, code in (
        (timestamps.isna(), "INVALID_TIMESTAMP"),
        (timestamps.duplicated(keep=False), "DUPLICATE_TIMESTAMP"),
        (timestamps.diff().lt(pd.Timedelta(0)), "OUT_OF_ORDER_TIMESTAMP"),
    ):
        if mask.any():
            raise HTTPException(422, detail={"code": code, "row": int(mask.idxmax()) + 2})
    return timestamps


def duplicate_result(db, dataset):
    scenario = db.query(Scenario).filter(Scenario.dataset_id == dataset.id).first()
    return {
        "status": "DUPLICATE_SKIPPED",
        "message": "Файл с таким SHA-256 уже импортирован",
        "dataset_id": dataset.id,
        "scenario_id": scenario.id if scenario else None,
        "sha256": dataset.sha256,
    }


class ImportService:
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Strip dangerous characters and path traversal attempts."""
        base = Path(filename).name
        cleaned = re.sub(r'[^a-zA-Z0-9_\.-]', '_', base)
        return cleaned or "uploaded_data.csv"

    @staticmethod
    def process_csv_file(
        db: Session,
        file_obj: io.BytesIO,
        filename: str,
        source_kind: str = "USER_UPLOADED",
        source_fault_label: Optional[str] = None,
        source_fault_label_type: Optional[str] = None,
        provenance_note: Optional[str] = None,
        max_size: Optional[int] = MAX_UPLOAD_SIZE
    ) -> Dict[str, Any]:
        content = file_obj.read()
        file_size = len(content)
        if max_size is not None and file_size > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"Размер файла ({file_size} байт) превышает веб-лимит {max_size // (1024*1024)} МБ. Для крупных архивов используйте scripts/import_lbnl.py."
            )

        sha256 = hashlib.sha256(content).hexdigest()
        sanitized_name = ImportService.sanitize_filename(filename)

        # Validate CSV structure first
        try:
            df = pd.read_csv(io.BytesIO(content))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Ошибка парсинга CSV: {str(e)}")

        if df.empty:
            raise HTTPException(status_code=400, detail="CSV-файл пуст")

        # Check for timestamp column
        time_candidates = ["Datetime", "datetime", "timestamp", "Time", "time", "Date"]
        time_col = None
        for cand in time_candidates:
            if cand in df.columns:
                time_col = cand
                break
        
        if not time_col:
            # Check first column only if it's text/string format with recognizable date structure
            first_col = df.columns[0]
            if df[first_col].dtype == object:
                try:
                    parsed = pd.to_datetime(df[first_col].iloc[:10])
                    # Ensure parsed dates are in a realistic year range (> 1990)
                    if parsed.dt.year.min() >= 1990:
                        time_col = first_col
                except Exception:
                    pass

        if not time_col:
            raise HTTPException(
                status_code=422,
                detail="В CSV не найдена колонка даты/времени (ожидалось 'Datetime' или колонка с метками времени ISO)."
            )

        timestamps = parse_timestamps(df[time_col])
        if time_col != "Datetime":
            df = df.rename(columns={time_col: "Datetime"})
        df["Datetime"] = timestamps.astype(str)

        existing_dataset = db.query(Dataset).filter(Dataset.sha256 == sha256).first()
        if existing_dataset:
            return duplicate_result(db, existing_dataset)

        total_rows = len(df)
        start_at, end_at = df["Datetime"].iloc[[0, -1]]
        steps = timestamps.diff().dropna().dt.total_seconds()
        expected_step = int(steps.mode().iloc[0]) if not steps.empty else None

        # A stable primary key serializes concurrent imports of new content.
        dataset_id = f"ds_{sha256[:61]}"
        scenario_id = f"sc_{uuid.uuid4().hex[:12]}"
        processed_dir = settings.data_dir / "processed"
        raw_dir = settings.data_dir / "raw"
        parquet_path = processed_dir / f"{scenario_id}_{sanitized_name}.parquet"
        raw_path = raw_dir / f"{dataset_id}_{sanitized_name}"

        # Create Database records
        dataset_obj = Dataset(
            id=dataset_id,
            name=sanitized_name,
            source_kind=source_kind,
            source_url=None,
            license_note="Open Access / User upload",
            sha256=sha256,
            size_bytes=file_size,
            processing_version="1.0.0",
            status="READY",
            provenance_note=provenance_note or f"Импортирован из файла {sanitized_name}"
        )
        db.add(dataset_obj)

        scenario_obj = Scenario(
            id=scenario_id,
            dataset_id=dataset_id,
            name=f"Сценарий: {sanitized_name}",
            start_at=start_at,
            end_at=end_at,
            sample_interval_seconds=expected_step or 60,
            timezone_status="unknown",
            source_fault_label=source_fault_label,
            source_fault_label_type=source_fault_label_type or ("FAULT_FREE" if not source_fault_label else "CUSTOM_FAULT"),
            description=f"Импортирован {sanitized_name}, строк: {total_rows}",
            data_path=f"data/processed/{parquet_path.name}",
            total_rows=total_rows
        )
        db.add(scenario_obj)

        # Map sensors
        mapped_sensors = []
        for col in df.columns:
            if col == "Datetime":
                continue
            canonical = resolve_canonical_key(col)
            if canonical and canonical in CANONICAL_SENSOR_METADATA:
                meta = CANONICAL_SENSOR_METADATA[canonical]
                display_ru = meta["display_name_ru"]
                component = meta["component"]
                signal_kind = meta["signal_kind"]
                unit = meta["unit"]
                is_basic = meta["is_basic"]
            else:
                canonical = col
                display_ru = col
                component = "UNKNOWN"
                signal_kind = "MEASUREMENT"
                unit = ""
                is_basic = False

            sensor_obj = Sensor(
                scenario_id=scenario_id,
                canonical_key=canonical,
                original_column=col,
                display_name_ru=display_ru,
                unit_raw=unit,
                unit_normalized=unit,
                component=component,
                signal_kind=signal_kind,
                is_basic=is_basic,
                is_available=True
            )
            db.add(sensor_obj)
            mapped_sensors.append(canonical)

        import_rec = ImportRecord(
            id=str(uuid.uuid4()),
            filename=sanitized_name,
            sha256=sha256,
            status="SUCCESS",
            rows_count=total_rows
        )
        db.add(import_rec)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            existing_dataset = db.query(Dataset).filter(Dataset.sha256 == sha256).first()
            if existing_dataset:
                return duplicate_result(db, existing_dataset)
            raise

        parquet_tmp = parquet_path.with_suffix(".tmp")
        raw_tmp = raw_path.with_name(f".{scenario_id}.tmp")
        published = []
        try:
            processed_dir.mkdir(parents=True, exist_ok=True)
            raw_dir.mkdir(parents=True, exist_ok=True)
            df.to_parquet(parquet_tmp, engine="pyarrow", index=False)
            raw_tmp.write_bytes(content)
            # Hard links publish complete files and fail if a destination already exists.
            parquet_path.hardlink_to(parquet_tmp)
            published.append(parquet_path)
            try:
                raw_path.hardlink_to(raw_tmp)
            except FileExistsError:
                # A process interrupted before commit can leave the original raw bytes.
                if raw_path.is_symlink() or hashlib.sha256(raw_path.read_bytes()).hexdigest() != sha256:
                    raise
            else:
                published.append(raw_path)
            db.commit()
        except Exception:
            db.rollback()
            for path in published:
                path.unlink(missing_ok=True)
            raise
        finally:
            parquet_tmp.unlink(missing_ok=True)
            raw_tmp.unlink(missing_ok=True)

        return {
            "status": "SUCCESS",
            "dataset_id": dataset_id,
            "scenario_id": scenario_id,
            "filename": sanitized_name,
            "rows_count": total_rows,
            "start_at": start_at,
            "end_at": end_at,
            "mapped_channels_count": len(mapped_sensors),
            "mapped_channels": mapped_sensors
        }
