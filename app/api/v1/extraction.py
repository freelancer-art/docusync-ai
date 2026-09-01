import os
import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlmodel import Session

from app.core.database import DocumentRecord, get_session
from app.core.rate_limiter import rate_limiter
from app.services.extractor_service import extractor_service
from app.worker import process_document_task

router = APIRouter()

UPLOAD_DIR = "storage/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/process-auto")
async def process_document_auto(file: UploadFile = File(...)):
    """
    Synchronous processing endpoint: Auto-detects document type, runs extraction,
    and returns immediate JSON results without database persistence.
    """
    if not file.filename or not file.filename.lower().endswith((".pdf", ".png", ".jpg", ".jpeg")):
        raise HTTPException(
            status_code=400, detail="Only PDF and image files are supported."
        )

    temp_path = os.path.join(UPLOAD_DIR, f"temp_{file.filename}")
    try:
        content = await file.read()
        async with aiofiles.open(temp_path, "wb") as buffer:
            await buffer.write(content)

        result = extractor_service.process_document(temp_path, file.filename)
        return result
    except (OSError, ValueError) as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@router.post(
    "/upload",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limiter(requests_limit=10, window_seconds=60))],
)
async def upload_document_async(
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
):
    """
    Asynchronous ingestion endpoint: Persists file to storage, creates a DocumentRecord,
    and dispatches background task via Celery worker.
    """
    if not file.filename or not file.filename.lower().endswith((".pdf", ".png", ".jpg", ".jpeg")):
        raise HTTPException(
            status_code=400, detail="Only PDF and image files are supported."
        )

    file_path = os.path.join(UPLOAD_DIR, file.filename)
    
    # Save file to upload directory
    content = await file.read()
    async with aiofiles.open(file_path, "wb") as buffer:
        await buffer.write(content)

    # Initialize Database Record
    doc_record = DocumentRecord(
        filename=file.filename,
        document_type="TAX_INVOICE",
        extraction_method="PENDING",
        overall_status="PROCESSING",
    )
    db.add(doc_record)
    db.commit()
    db.refresh(doc_record)

    # Trigger Celery Background Processing
    process_document_task.delay(doc_record.id)

    return {
        "message": "Document accepted for async processing",
        "document_id": doc_record.id,
        "filename": doc_record.filename,
        "status": doc_record.overall_status,
    }