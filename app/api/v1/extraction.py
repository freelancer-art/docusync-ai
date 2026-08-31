import os
import aiofiles

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.rate_limiter import rate_limiter
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
    if not file.filename or not file.filename.endswith(".pdf"):
        raise HTTPException(
            status_code=400, detail="Only PDF files are currently supported."
        )

    file_path = os.path.join(TEMP_UPLOAD_DIR, file.filename)
    try:
        async with aiofiles.open(file_path, "wb") as buffer:
            content = await file.read()
            await buffer.write(content)

        result = extractor_service.process_document(file_path)
        return result
    except (OSError, IOError, ValueError) as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


@router.post(
    "/extract",
    dependencies=[Depends(rate_limiter(requests_limit=5, window_seconds=60))],
)
async def extract_document(file: UploadFile = File(...)):
    # Existing extraction handler logic
    return {"status": "success", "filename": file.filename}