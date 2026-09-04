import os
import uuid

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlmodel import Session

from app.config import settings
from app.core.database import DocumentRecord, User, UserRole, get_session
from app.core.rate_limiter import rate_limiter
from app.core.security import (
    InvalidFileTypeError,
    get_current_user,
    validate_file_signature,
)
from app.services.extractor_service import extractor_service
from app.worker import process_document_task

router = APIRouter()

UPLOAD_DIR = settings.UPLOAD_DIR
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf": "pdf", ".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg"}


def _validated_upload_content(filename: str | None, content: bytes) -> str:
    if not filename:
        raise HTTPException(status_code=400, detail="Uploaded file must have a filename.")

    _, ext = os.path.splitext(filename.lower())
    expected_signature = ALLOWED_EXTENSIONS.get(ext)
    if not expected_signature:
        raise HTTPException(
            status_code=400, detail="Only PDF and image files are supported."
        )

    try:
        actual_signature = validate_file_signature(content)
    except InvalidFileTypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if actual_signature != expected_signature:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file extension does not match file contents.",
        )

    return DocumentRecord.sanitize_filename(filename)


def _resolve_target_client_id(
    requested_client_id: int | None,
    current_user: User,
    db: Session,
) -> int:
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Authenticated user is invalid.")

    if current_user.role == UserRole.CA_ADMIN:
        target_client_id = requested_client_id or current_user.id
    else:
        if requested_client_id is not None and requested_client_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Clients can only upload documents to their own account.",
            )
        target_client_id = current_user.id

    if not db.get(User, target_client_id):
        raise HTTPException(status_code=404, detail="Target client account not found.")

    return target_client_id


@router.post("/process-auto")
async def process_document_auto(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Synchronous processing endpoint: Auto-detects document type, runs extraction,
    and returns immediate JSON results without database persistence.
    """
    content = await file.read()
    safe_filename = _validated_upload_content(file.filename, content)
    temp_path = os.path.join(UPLOAD_DIR, f"temp_{uuid.uuid4().hex}_{safe_filename}")
    try:
        async with aiofiles.open(temp_path, "wb") as buffer:
            await buffer.write(content)

        result = extractor_service.process_document(temp_path, safe_filename)
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
    client_id: int | None = Query(None),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Asynchronous ingestion endpoint: Persists file to storage, creates a DocumentRecord,
    and dispatches background task via Celery worker.
    """
    content = await file.read()
    safe_filename = _validated_upload_content(file.filename, content)
    target_client_id = _resolve_target_client_id(client_id, current_user, db)
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    # Save file to upload directory
    async with aiofiles.open(file_path, "wb") as buffer:
        await buffer.write(content)

    # Initialize Database Record
    doc_record = DocumentRecord(
        filename=safe_filename,
        document_type="TAX_INVOICE",
        extraction_method="PENDING",
        overall_status="PROCESSING",
        client_id=target_client_id,
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
