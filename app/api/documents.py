import io
import os
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends, BackgroundTasks
from fastapi.responses import Response
from sqlmodel import Session, select
from sqlalchemy.engine import Engine

from app.core.database import DocumentRecord, User, UserRole, get_session, engine as default_engine
from app.core.security import validate_file_signature, InvalidFileTypeError, get_current_user
from app.services import zoho_exporter, tally_exporter
from app.services.audit_engine import process_document_audit

router = APIRouter(prefix="/api/documents", tags=["documents"])

UPLOAD_DIR = "storage/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def run_document_processing_pipeline(doc_id: int, db_engine: Optional[Engine] = None):
    """Async background worker: runs AI vision extraction & audit checks."""
    target_engine = db_engine or default_engine
    with Session(target_engine) as session:
        doc = session.get(DocumentRecord, doc_id)
        if not doc:
            return
        
        # 1. Trigger vision extraction (populates vendor_name, total_amount, raw_json_data)
        # 2. Trigger audit rule engine
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

    safe_filename = DocumentRecord.sanitize_filename(file.filename)

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
    with open(file_path, "wb") as buffer:
        buffer.write(content)

    session.add(doc_record)
    session.commit()
    session.refresh(doc_record)

    # Pass the bound session engine so background tasks share the active database context (e.g. in tests)
    background_tasks.add_task(run_document_processing_pipeline, doc_record.id, session.get_bind())

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
    session: Session = Depends(get_session)
):
    doc = session.get(DocumentRecord, doc_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        
    if current_user.role != UserRole.CA_ADMIN and doc.client_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
    return {
        "id": doc.id,
        "filename": doc.filename,
        "status": doc.overall_status,
        "client_id": doc.client_id
    }

@router.get("/export/zoho")
async def export_zoho_csv(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
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
        headers={"Content-Disposition": "attachment; filename=zoho_bills.csv"}
    )

@router.get("/export/tally")
async def export_tally_xml(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
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
        headers={"Content-Disposition": "attachment; filename=tally_vouchers.xml"}
    )