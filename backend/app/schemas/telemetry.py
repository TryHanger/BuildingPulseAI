from typing import List, Optional, Any
from pydantic import BaseModel

class RangeMeta(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None
    timezone_status: str = "unknown"

class TelemetryPoint(BaseModel):
    timestamp: str
    value: Optional[float] = None

class TelemetrySeries(BaseModel):
    channel: str
    display_name_ru: str
    unit: str
    component: str
    signal_kind: str
    points: List[List[Any]]  # [[iso_time, float_val_or_null], ...]

class SamplingMeta(BaseModel):
    aggregated: bool
    method: str
    returned_points: int
    total_source_points: int

class TelemetryResponse(BaseModel):
    scenario_id: str
    range: RangeMeta
    series: List[TelemetrySeries]
    sampling: SamplingMeta
    source_kind: str
