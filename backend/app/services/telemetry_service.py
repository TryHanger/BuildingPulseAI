from typing import List, Optional
import pandas as pd
from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.models import Scenario, Sensor, Dataset
from backend.app.schemas.telemetry import TelemetryResponse, TelemetrySeries, RangeMeta, SamplingMeta
from backend.app.utils.downsampling import downsample_min_max

class TelemetryService:
    @staticmethod
    def get_telemetry(
        db: Session,
        scenario_id: str,
        channels: List[str],
        start: Optional[str] = None,
        end: Optional[str] = None,
        max_points: int = settings.MAX_POINTS_DEFAULT
    ) -> TelemetryResponse:
        scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
        if not scenario:
            raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")

        dataset = db.query(Dataset).filter(Dataset.id == scenario.dataset_id).first()
        source_kind = dataset.source_kind if dataset else "UNKNOWN"

        parquet_path = settings.scenario_data_path(scenario.data_path)

        if not parquet_path.exists():
            raise HTTPException(status_code=404, detail=f"Data storage file not found for scenario {scenario_id}")

        # Get sensors metadata for the requested channels
        sensor_objs = db.query(Sensor).filter(
            Sensor.scenario_id == scenario_id,
            Sensor.canonical_key.in_(channels)
        ).all()
        sensor_meta = {s.canonical_key: s for s in sensor_objs}

        # Available columns in parquet
        try:
            available_cols = pd.read_parquet(parquet_path, engine="pyarrow").columns.tolist()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading Parquet: {str(e)}")

        time_col = "Datetime" if "Datetime" in available_cols else available_cols[0]
        columns_to_read = [time_col]
        
        # Determine actual column names in parquet
        col_mapping = {}
        for ch in channels:
            if ch in sensor_meta:
                orig_col = sensor_meta[ch].original_column
                if orig_col in available_cols:
                    columns_to_read.append(orig_col)
                    col_mapping[ch] = orig_col
                elif ch in available_cols:
                    columns_to_read.append(ch)
                    col_mapping[ch] = ch
            elif ch in available_cols:
                columns_to_read.append(ch)
                col_mapping[ch] = ch

        try:
            # Read only required columns
            df = pd.read_parquet(parquet_path, columns=columns_to_read, engine="pyarrow")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to read columns: {str(e)}")

        # Convert time column to string ISO format
        df[time_col] = df[time_col].astype(str)

        # Apply time filtering if provided
        if start:
            df = df[df[time_col] >= start]
        if end:
            df = df[df[time_col] <= end]

        total_source_points = len(df)
        if total_source_points == 0:
            return TelemetryResponse(
                scenario_id=scenario_id,
                range=RangeMeta(start=start, end=end, timezone_status=scenario.timezone_status),
                series=[],
                sampling=SamplingMeta(aggregated=False, method="none", returned_points=0, total_source_points=0),
                source_kind=source_kind
            )

        actual_start = df[time_col].iloc[0]
        actual_end = df[time_col].iloc[-1]
        timestamps = df[time_col].tolist()

        series_list: List[TelemetrySeries] = []
        is_any_aggregated = False
        sampling_method = "none"
        max_returned_points = 0

        for ch in channels:
            actual_col = col_mapping.get(ch)
            if not actual_col or actual_col not in df.columns:
                continue

            vals = df[actual_col].tolist()
            downsampled_pts, agg, method = downsample_min_max(timestamps, vals, max_points=max_points)
            if agg:
                is_any_aggregated = True
                sampling_method = method
            max_returned_points = max(max_returned_points, len(downsampled_pts))

            s_info = sensor_meta.get(ch)
            display_name = s_info.display_name_ru if s_info else ch
            unit = s_info.unit_normalized or s_info.unit_raw or "" if s_info else ""
            comp = s_info.component if s_info else "UNKNOWN"
            sig_kind = s_info.signal_kind if s_info else "MEASUREMENT"

            series_list.append(TelemetrySeries(
                channel=ch,
                display_name_ru=display_name,
                unit=unit,
                component=comp,
                signal_kind=sig_kind,
                points=downsampled_pts
            ))

        return TelemetryResponse(
            scenario_id=scenario_id,
            range=RangeMeta(start=actual_start, end=actual_end, timezone_status=scenario.timezone_status),
            series=series_list,
            sampling=SamplingMeta(
                aggregated=is_any_aggregated,
                method=sampling_method,
                returned_points=max_returned_points,
                total_source_points=total_source_points
            ),
            source_kind=source_kind
        )
