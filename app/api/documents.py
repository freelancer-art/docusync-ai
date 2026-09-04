from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.auth import get_current_user
from app.core.database import DocumentRecord, User, UserRole, get_session
from app.services.tally_exporter import tally_exporter
from app.services.zoho_exporter import zoho_exporter

router = APIRouter(prefix="/api/documents", tags=["Documents"])


class DocumentUpdateSchema(BaseModel):
    vendor_name: str | None = None
    invoice_number: str | None = None
    total_amount: float | None = None
    overall_status: str | None = None
    auditor_notes: str | None = None


@router.get("/", response_model=list[DocumentRecord])
def get_documents(
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Fetch documents scoped by user role (CA_ADMIN sees all, CLIENT sees owned documents).
    """
    query = select(DocumentRecord)

    if current_user.role != UserRole.CA_ADMIN:
        query = query.where(DocumentRecord.client_id == current_user.id)

    if status_filter and status_filter.upper() != "ALL":
        query = query.where(DocumentRecord.overall_status == status_filter.upper())

    records = db.exec(query).all()
    return records


@router.get("/export/zoho")
def export_zoho_csv(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Export verified document records formatted as Zoho Books CSV.
    """
    if current_user.role != UserRole.CA_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only CA_ADMIN can export document records",
        )

    query = select(DocumentRecord).where(DocumentRecord.overall_status == "VERIFIED")
    records = db.exec(query).all()

    return Response(
        content=zoho_exporter.generate_bills_csv(records),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=zoho_export.csv"},
    )


@router.get("/export/tally")
def export_tally_xml(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Export verified document records formatted as Tally ERP XML.
    """
    if current_user.role != UserRole.CA_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only CA_ADMIN can export document records",
        )

    query = select(DocumentRecord).where(DocumentRecord.overall_status == "VERIFIED")
    records = db.exec(query).all()

    return Response(
        content=tally_exporter.generate_vouchers_xml(records),
        media_type="application/xml",
        headers={"Content-Disposition": "attachment; filename=tally_export.xml"},
    )


@router.get("/{document_id}", response_model=DocumentRecord)
def get_document_by_id(
    document_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve details for a specific document by ID.
    """
    record = db.get(DocumentRecord, document_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    if (
        current_user.role != UserRole.CA_ADMIN
        and record.client_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this document",
        )

    return record


@router.patch("/{document_id}", response_model=DocumentRecord)
def update_document_audit(
    document_id: int,
    payload: DocumentUpdateSchema,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Update document metadata and status (Restricted to CA_ADMIN).
    """
    if current_user.role != UserRole.CA_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only CA_ADMIN can modify document audit status",
        )

    record = db.get(DocumentRecord, document_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(record, field, value)

    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a document record (Restricted to CA_ADMIN).
    """
    if current_user.role != UserRole.CA_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only CA_ADMIN can delete documents",
        )

    record = db.get(DocumentRecord, document_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    db.delete(record)
    db.commit()
