import json
import os

from sqlalchemy import create_engine
from sqlmodel import Session

from app.config import settings
from app.core.celery_app import celery_app
from app.core.database import DocumentRecord
from app.core.database import engine as default_engine
from app.services.audit_engine import process_document_audit
from app.services.extractor_service import extract_structured_data

UPLOAD_DIR = settings.UPLOAD_DIR


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def process_document_task(self, doc_id: int, db_url: str | None = None):
    """
    Celery background worker task for async document processing.
    Handles extraction, database updates, and audit evaluation with retry fallback.
    """
    engine = create_engine(db_url) if db_url else default_engine

    try:
        with Session(engine) as session:
            doc = session.get(DocumentRecord, doc_id)
            if not doc:
                return {"status": "SKIPPED", "reason": f"Document {doc_id} not found"}

            file_path = os.path.join(UPLOAD_DIR, doc.filename)
            if not os.path.exists(file_path):
                doc.overall_status = "FAILED"
                session.add(doc)
                session.commit()
                return {"status": "FAILED", "reason": "File not found on disk"}

            with open(file_path, "rb") as f:
                content = f.read()

            # 1. Structured AI/OCR extraction
            extracted_data = extract_structured_data(content, doc.filename)

            # 2. Update record metadata
            doc.raw_json_data = json.dumps(extracted_data)
            doc.vendor_name = extracted_data.get("vendor_name")
            doc.invoice_number = extracted_data.get("invoice_number")
            doc.total_amount = extracted_data.get("total_amount", 0.0)

            # 3. Audit Engine evaluation
            process_document_audit(doc, session)

            return {
                "status": doc.overall_status,
                "doc_id": doc.id,
                "vendor": doc.vendor_name,
            }
    except (RuntimeError, ValueError, OSError) as exc:
        raise self.retry(exc=exc)
