from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class QualityMetric(BaseModel):
    name: str
    description: str
    status: str  # OK, WARNING, ERROR
    value: Any

class MissingInterval(BaseModel):
    start: str
    end: str
    duration_minutes: float

class DataQualityReport(BaseModel):
    scenario_id: str
    total_records: int
    time_monotonic: bool
    duplicate_timestamps_count: int
    missing_intervals: List[MissingInterval]
    missing_ratio: float
    stuck_channels: List[Dict[str, Any]]
    metrics: List[QualityMetric]
