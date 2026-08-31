import json
import os

import aiofiles
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import Response
from sqlalchemy import Engine
from sqlmodel import Session, select

from app.core.database import (
    DocumentRecord,
    User,
    UserRole,
    get_session,
)
from app.core.database import (
    engine as default_engine,
)
from app.core.security import (
    InvalidFileTypeError,
    get_current_user,
    validate_file_signature,
)
from app.services import tally_exporter, zoho_exporter
from app.services.audit_engine import process_document_audit
from app.services.extractor_service import extract_structured_data

router = APIRouter(prefix="/api/documents", tags=["documents"])

UPLOAD_DIR = "storage/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def run_document_processing_pipeline(doc_id: int, db_engine: Engine | None = None):
    """Async background worker: runs text extraction, structured parsing & audit checks."""
    target_engine = db_engine or default_engine
    with Session(target_engine) as session:
        doc = session.get(DocumentRecord, doc_id)
        if not doc:
            return

        file_path = os.path.join(UPLOAD_DIR, doc.filename)
        if os.path.exists(file_path):
            try:
                with open(file_path, "rb") as f:
                    content = f.read()

                # 1. Run live/fallback structured extraction
                extracted_data = extract_structured_data(content, doc.filename)

                # 2. Update DocumentRecord with extracted details
                doc.raw_json_data = json.dumps(extracted_data)
                doc.vendor_name = extracted_data.get("vendor_name")
                doc.invoice_number = extracted_data.get("invoice_number")
                doc.total_amount = extracted_data.get("total_amount", 0.0)
            except (OSError, ValueError) as e:
                doc.overall_status = "FAILED"
                doc.raw_json_data = json.dumps({"error": str(e)})

        # 3. Trigger audit rule engine
        process_document_audit(doc, session)


@router.post("/upload", response_model=dict)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    content = await file.read()

    try:
        validate_file_signature(content)
    except InvalidFileTypeError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    safe_filename = DocumentRecord.sanitize_filename(file.filename or "uploaded_doc.pdf")

    doc_record = DocumentRecord(
        filename=safe_filename,
        document_type="INVOICE",
        extraction_method="AI_VISION",
        overall_status="PENDING",
        client_id=current_user.id,
        raw_json_data="{}",
        audit_flags_json="[]",
    )

    file_path = os.path.join(UPLOAD_DIR, doc_record.filename)
    async with aiofiles.open(file_path, "wb") as buffer:
        await buffer.write(content)

    session.add(doc_record)
    session.commit()
    session.refresh(doc_record)

    background_tasks.add_task(
        run_document_processing_pipeline, doc_record.id, session.get_bind()
    )

    return {
        "id": doc_record.id,
        "filename": doc_record.filename,
        "status": doc_record.overall_status,
        "client_id": doc_record.client_id,
    }


@router.get("/{doc_id}", response_model=dict)
async def get_document(
    doc_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    doc = session.get(DocumentRecord, doc_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    if current_user.role != UserRole.CA_ADMIN and doc.client_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    return {
        "id": doc.id,
        "filename": doc.filename,
        "status": doc.overall_status,
        "client_id": doc.client_id,
    }


@router.get("/export/zoho")
async def export_zoho_csv(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    query = select(DocumentRecord)
    if current_user.role != UserRole.CA_ADMIN:
        query = query.where(DocumentRecord.client_id == current_user.id)

    records = session.exec(query).all()
    if not records:
        raise HTTPException(status_code=404, detail="No documents available to export")

    csv_bytes = zoho_exporter.generate_bills_csv(records)
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=zoho_bills.csv"},
    )


@router.get("/export/tally")
async def export_tally_xml(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    query = select(DocumentRecord)
    if current_user.role != UserRole.CA_ADMIN:
        query = query.where(DocumentRecord.client_id == current_user.id)

    records = session.exec(query).all()
    if not records:
        raise HTTPException(status_code=404, detail="No documents available to export")

    xml_content = tally_exporter.generate_vouchers_xml(records)
    return Response(
        content=xml_content,
        media_type="application/xml",
        headers={"Content-Disposition": "attachment; filename=tally_vouchers.xml"},
    )