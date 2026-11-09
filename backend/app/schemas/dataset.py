from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class DatasetBase(BaseModel):
    id: str
    name: str
    source_kind: str
    source_url: Optional[str] = None
    license_note: Optional[str] = None
    sha256: Optional[str] = None
    size_bytes: Optional[int] = None
    processing_version: str = "1.0.0"
    status: str = "READY"
    provenance_note: Optional[str] = None

class DatasetRead(DatasetBase):
    imported_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class DatasetListResponse(BaseModel):
    items: List[DatasetRead]
    total: int
