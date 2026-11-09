from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class SensorRead(BaseModel):
    id: int
    scenario_id: str
    canonical_key: str
    original_column: str
    display_name_ru: str
    unit_raw: Optional[str] = None
    unit_normalized: Optional[str] = None
    component: str
    signal_kind: str
    is_basic: bool
    is_available: bool

    model_config = ConfigDict(from_attributes=True)

class SensorListResponse(BaseModel):
    items: List[SensorRead]
    total: int
