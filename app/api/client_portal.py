import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.database import DocumentRecord, User, UserRole, get_session
from app.core.security import get_current_user
from app.services.audit_engine import process_document_audit

router = APIRouter(prefix="/api/portal", tags=["client_portal"])


class StatusOverrideRequest(BaseModel):
    new_status: str  # "VERIFIED" or "REJECTED"
    override_reason: str | None = None


class DocumentFieldOverrideRequest(BaseModel):
    vendor_name: str | None = None
    invoice_number: str | None = None
    total_amount: float | None = None
    raw_json_data: dict[str, Any] | None = None
    re_audit: bool = Field(
        default=True, description="Re-run audit rule engine after applying overrides"
    )


class DocumentDetailResponse(BaseModel):
    id: int
    filename: str
    document_type: str
    overall_status: str
    vendor_name: str | None = None
    invoice_number: str | None = None
    total_amount: float | None = None
    audit_flags: list[str]
    client_id: int
    raw_json_data: str | None = None


@router.get("/review-queue", response_model=list[DocumentDetailResponse])
async def get_review_queue(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """CA Admin endpoint: Returns all documents requiring CA review."""
    if current_user.role != UserRole.CA_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="CA Admin access required"
        )

    statement = select(DocumentRecord).where(
        DocumentRecord.overall_status == "NEEDS_REVIEW"
    )
    records = session.exec(statement).all()

    response = []
    for rec in records:
        flags = json.loads(rec.audit_flags_json) if rec.audit_flags_json else []
        response.append(
            DocumentDetailResponse(
                id=rec.id,
                filename=rec.filename,
                document_type=rec.document_type,
                overall_status=rec.overall_status,
                vendor_name=rec.vendor_name,
                invoice_number=rec.invoice_number,
                total_amount=rec.total_amount,
                audit_flags=flags,
                client_id=rec.client_id,
                raw_json_data=rec.raw_json_data,
            )
        )
    return response


@router.patch("/documents/{doc_id}/override", response_model=DocumentDetailResponse)
async def override_document_status(
    doc_id: int,
    payload: StatusOverrideRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """CA Admin endpoint: Manual approval or rejection of flagged document status."""
    if current_user.role != UserRole.CA_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="CA Admin access required"
        )

    doc = session.get(DocumentRecord, doc_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    if payload.new_status not in ["VERIFIED", "REJECTED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status option"
        )

    doc.overall_status = payload.new_status
    session.add(doc)
    session.commit()
    session.refresh(doc)

    flags = json.loads(doc.audit_flags_json) if doc.audit_flags_json else []
    return DocumentDetailResponse(
        id=doc.id,
        filename=doc.filename,
        document_type=doc.document_type,
        overall_status=doc.overall_status,
        vendor_name=doc.vendor_name,
        invoice_number=doc.invoice_number,
        total_amount=doc.total_amount,
        audit_flags=flags,
        client_id=doc.client_id,
        raw_json_data=doc.raw_json_data,
    )


@router.put("/documents/{doc_id}/fields", response_model=DocumentDetailResponse)
async def override_document_fields(
    doc_id: int,
    payload: DocumentFieldOverrideRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """CA Admin endpoint: Edit extracted invoice fields directly and re-run audit validation."""
    if current_user.role != UserRole.CA_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="CA Admin access required"
        )

    doc = session.get(DocumentRecord, doc_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    if payload.vendor_name is not None:
        doc.vendor_name = payload.vendor_name
    if payload.invoice_number is not None:
        doc.invoice_number = payload.invoice_number
    if payload.total_amount is not None:
        doc.total_amount = payload.total_amount
    if payload.raw_json_data is not None:
        doc.raw_json_data = json.dumps(payload.raw_json_data)

    session.add(doc)
    session.commit()
    session.refresh(doc)

    # Automatically re-run audit rules against corrected metadata if requested
    if payload.re_audit:
        doc = process_document_audit(doc, session)

    flags = json.loads(doc.audit_flags_json) if doc.audit_flags_json else []
    return DocumentDetailResponse(
        id=doc.id,
        filename=doc.filename,
        document_type=doc.document_type,
        overall_status=doc.overall_status,
        vendor_name=doc.vendor_name,
        invoice_number=doc.invoice_number,
        total_amount=doc.total_amount,
        audit_flags=flags,
        client_id=doc.client_id,
        raw_json_data=doc.raw_json_data,
    )


@router.get("/my-documents", response_model=list[DocumentDetailResponse])
async def get_client_documents(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Client endpoint: Fetch logged-in user's active documents and flags."""
    statement = select(DocumentRecord).where(
        DocumentRecord.client_id == current_user.id
    )
    records = session.exec(statement).all()

    response = []
    for rec in records:
        flags = json.loads(rec.audit_flags_json) if rec.audit_flags_json else []
        response.append(
            DocumentDetailResponse(
                id=rec.id,
                filename=rec.filename,
                document_type=rec.document_type,
                overall_status=rec.overall_status,
                vendor_name=rec.vendor_name,
                invoice_number=rec.invoice_number,
                total_amount=rec.total_amount,
                audit_flags=flags,
                client_id=rec.client_id,
                raw_json_data=rec.raw_json_data,
            )
        )
    return response