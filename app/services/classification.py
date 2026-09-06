"""Document classification rerun workflow shared by API and dashboard surfaces."""

import json

from sqlmodel import Session

from app.core.database import DocumentRecord
from app.services.extractor_service import extract_structured_data
from app.services.storage_service import storage_service

LOW_CONFIDENCE_THRESHOLD = 0.6


def rerun_document_classification(
    document: DocumentRecord, session: Session
) -> DocumentRecord:
    """Re-extract one stored document and persist classification evidence."""
    content = storage_service.get_file_bytes(document.filename)
    extracted = extract_structured_data(content, document.filename)

    document.document_type = extracted.get("doc_type", "UNKNOWN")
    document.classification_confidence = extracted.get("classification_confidence")
    document.classification_reasoning = extracted.get("classification_reasoning")
    document.raw_json_data = json.dumps(extracted)
    document.vendor_name = extracted.get("vendor_name")
    document.invoice_number = extracted.get("invoice_number")
    document.total_amount = extracted.get("total_amount", 0.0)
    document.overall_status = "NEEDS_REVIEW"
    session.add(document)
    session.commit()
    session.refresh(document)
    return document
