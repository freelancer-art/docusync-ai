import csv
import io
import json
import xml.etree.ElementTree as ET
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.auth import get_current_user
from app.core.database import DocumentRecord, User, UserRole, get_session

router = APIRouter(prefix="/api/documents", tags=["Documents"])


class DocumentUpdateSchema(BaseModel):
    vendor_name: Optional[str] = None
    invoice_number: Optional[str] = None
    total_amount: Optional[float] = None
    overall_status: Optional[str] = None
    auditor_notes: Optional[str] = None


@router.get("/", response_model=List[DocumentRecord])
def get_documents(
    status_filter: Optional[str] = Query(None, alias="status"),
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

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Invoice Number",
        "Vendor Name",
        "Document Type",
        "Total Amount",
        "Status",
        "Created At",
    ])

    for doc in records:
        writer.writerow([
            doc.invoice_number or "",
            doc.vendor_name or "",
            doc.document_type,
            doc.total_amount or 0.0,
            doc.overall_status,
            doc.created_at.isoformat() if doc.created_at else "",
        ])

    return Response(
        content=output.getvalue(),
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

    envelope = ET.Element("ENVELOPE")
    header = ET.SubElement(envelope, "HEADER")
    tally_req = ET.SubElement(header, "TALLYREQUEST")
    tally_req.text = "Import Data"

    body = ET.SubElement(envelope, "BODY")
    import_data = ET.SubElement(body, "IMPORTDATA")
    request_data = ET.SubElement(import_data, "REQUESTDATA")

    for doc in records:
        voucher = ET.SubElement(
            request_data, "VOUCHER", VCHTYPE="Purchase", ACTION="Create"
        )
        party = ET.SubElement(voucher, "PARTYLEDGERNAME")
        party.text = doc.vendor_name or "Unknown Vendor"

        inv_num = ET.SubElement(voucher, "VOUCHERNUMBER")
        inv_num.text = doc.invoice_number or ""

        amount = ET.SubElement(voucher, "AMOUNT")
        amount.text = str(doc.total_amount or 0.0)

    xml_data = ET.tostring(envelope, encoding="utf-8", xml_declaration=True).decode("utf-8")

    return Response(
        content=xml_data,
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
    return None