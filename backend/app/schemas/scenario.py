from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class ScenarioBase(BaseModel):
    id: str
    dataset_id: str
    name: str
    start_at: Optional[str] = None
    end_at: Optional[str] = None
    sample_interval_seconds: int = 60
    timezone_status: str = "unknown"
    source_fault_label: Optional[str] = None
    source_fault_label_type: Optional[str] = None
    description: Optional[str] = None
    total_rows: int = 0

class ScenarioRead(ScenarioBase):
    model_config = ConfigDict(from_attributes=True)

class ScenarioListResponse(BaseModel):
    items: List[ScenarioRead]
    total: int
