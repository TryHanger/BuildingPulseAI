from typing import List, Dict, Any
import pandas as pd
from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.models import Scenario
from backend.app.schemas.data_quality import DataQualityReport, QualityMetric, MissingInterval

class QualityService:
    @staticmethod
    def evaluate_quality(db: Session, scenario_id: str) -> DataQualityReport:
        scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
        if not scenario:
            raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")

        parquet_path = settings.scenario_data_path(scenario.data_path)

        if not parquet_path.exists():
            raise HTTPException(status_code=404, detail="Data file not found")

        df = pd.read_parquet(parquet_path)
        total_records = len(df)
        if total_records == 0:
            return DataQualityReport(
                scenario_id=scenario_id,
                total_records=0,
                time_monotonic=True,
                duplicate_timestamps_count=0,
                missing_intervals=[],
                missing_ratio=0.0,
                stuck_channels=[],
                metrics=[]
            )

        time_col = "Datetime" if "Datetime" in df.columns else df.columns[0]
        
        # 1. Monotonicity and duplicates
        time_series = pd.to_datetime(df[time_col], errors="coerce")
        is_monotonic = bool(time_series.is_monotonic_increasing)
        dup_count = int(time_series.duplicated().sum())

        # 2. Missing intervals
        expected_interval_sec = scenario.sample_interval_seconds or 60
        diffs = time_series.diff()
        gap_mask = diffs > pd.Timedelta(seconds=expected_interval_sec * 1.5)
        gap_indices = df.index[gap_mask].tolist()

        missing_intervals: List[MissingInterval] = []
        total_missing_seconds = 0.0

        for idx in gap_indices[:50]:  # Limit to first 50 gaps
            t_prev = time_series.iloc[idx - 1]
            t_curr = time_series.iloc[idx]
            gap_dur = (t_curr - t_prev).total_seconds()
            total_missing_seconds += gap_dur
            missing_intervals.append(MissingInterval(
                start=str(t_prev),
                end=str(t_curr),
                duration_minutes=round(gap_dur / 60.0, 1)
            ))

        time_span_seconds = max(1.0, (time_series.iloc[-1] - time_series.iloc[0]).total_seconds())
        missing_ratio = round(total_missing_seconds / time_span_seconds, 4)

        # 3. Stuck channel detection (constant value for > 120 consecutive points)
        # Strictly target continuous physical measurement sensors (e.g. temperatures, pressures, flows).
        # Operational setpoints (_SPT), control commands (_DM), and binary modes (SYS_CTL, _CS) are legitimately constant in steady state.
        stuck_channels = []
        continuous_sensor_cols = [
            c for c in df.select_dtypes(include=["number"]).columns
            if c != time_col
            and not c.endswith("_DM")
            and "SPT" not in c
            and c not in ["SYS_CTL", "SF_CS", "RF_CS"]
        ]
        for col in continuous_sensor_cols:
            vals = df[col].dropna()
            if len(vals) > 120:
                diff_zeros = (vals.diff() == 0).astype(int)
                max_consec = (diff_zeros * (diff_zeros.groupby((diff_zeros != 1).cumsum()).cumcount() + 1)).max()
                if max_consec >= 120:
                    stuck_idx = diff_zeros.idxmax() if (diff_zeros == 1).any() else 0
                    stuck_channels.append({
                        "channel": col,
                        "consecutive_constant_points": int(max_consec),
                        "constant_value": float(vals.loc[stuck_idx]) if stuck_idx in vals.index else float(vals.iloc[0])
                    })

        metrics = [
            QualityMetric(
                name="Временная монотонность",
                description="Проверка строго возрастающего порядка временных меток",
                status="OK" if is_monotonic else "ERROR",
                value="Монотонно" if is_monotonic else "Нарушен порядок времени"
            ),
            QualityMetric(
                name="Дубликаты меток времени",
                description="Количество строк с повторяющимися временными метками",
                status="OK" if dup_count == 0 else "WARNING",
                value=f"{dup_count} дубликатов"
            ),
            QualityMetric(
                name="Пропуски измерений",
                description="Доля отсутствующих интервалов во временном ряду",
                status="OK" if missing_ratio < 0.01 else "WARNING",
                value=f"{round(missing_ratio * 100, 2)}% пропусков ({len(missing_intervals)} интервалов)"
            ),
            QualityMetric(
                name="Замирание сигналов (Stuck)",
                description="Сигналы с неизменным значением более 120 точек",
                status="OK" if len(stuck_channels) == 0 else "WARNING",
                value=f"{len(stuck_channels)} каналов с замиранием"
            )
        ]

        return DataQualityReport(
            scenario_id=scenario_id,
            total_records=total_records,
            time_monotonic=is_monotonic,
            duplicate_timestamps_count=dup_count,
            missing_intervals=missing_intervals,
            missing_ratio=missing_ratio,
            stuck_channels=stuck_channels,
            metrics=metrics
        )
