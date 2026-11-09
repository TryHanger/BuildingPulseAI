import io
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models import Dataset
from backend.app.schemas.dataset import DatasetRead, DatasetListResponse
from backend.app.services.import_service import ImportService

router = APIRouter()

@router.get("/datasets", response_model=DatasetListResponse)
def list_datasets(db: Session = Depends(get_db)):
    datasets = db.query(Dataset).order_by(Dataset.imported_at.desc()).all()
    return DatasetListResponse(
        items=[DatasetRead.model_validate(d) for d in datasets],
        total=len(datasets)
    )

@router.post("/datasets/import")
async def import_dataset_csv(
    file: UploadFile = File(...),
    source_kind: str = Form("USER_UPLOADED"),
    source_fault_label: Optional[str] = Form(None),
    source_fault_label_type: Optional[str] = Form(None),
    provenance_note: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Поддерживаются только файлы формата .csv")
    
    content = await file.read()
    file_bytes = io.BytesIO(content)
    result = ImportService.process_csv_file(
        db=db,
        file_obj=file_bytes,
        filename=file.filename,
        source_kind=source_kind,
        source_fault_label=source_fault_label,
        source_fault_label_type=source_fault_label_type,
        provenance_note=provenance_note
    )
    return result
