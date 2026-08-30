import os
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.extractor_service import extractor_service

router = APIRouter()

TEMP_UPLOAD_DIR = "storage/sample_uploads"
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)

@router.post("/process-auto")
async def process_document_auto(file: UploadFile = File(...)):
    """
    Universal ingestion endpoint: Auto-detects document type (Tax Invoice / Bank Statement),
    applies OCR fallback if needed, and returns extracted JSON schema.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are currently supported.")

    file_path = os.path.join(TEMP_UPLOAD_DIR, file.filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        result = extractor_service.process_document(file_path)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)