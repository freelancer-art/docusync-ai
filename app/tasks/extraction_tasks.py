import logging

from sqlmodel import Session, select

from app.core.celery_app import celery_app
from app.core.database import DocumentRecord, engine
from app.services.extractor_service import extractor_service

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    autoretry_for=(OSError, IOError, ValueError, RuntimeError),
)
def process_document_task(self, file_path: str, filename: str, client_id: int | None = None) -> dict:
    """
    Asynchronously processes a PDF document through OCR/LLM extraction,
    executes compliance audit rules, and persists the record to DB.
    """
    logger.info(f"Processing document async: {filename} (Task ID: {self.request.id})")

    try:
        # Run core extraction engine
        result = extractor_service.process_document(
            file_input=file_path,
            filename=filename,
        )

        # Update or create database record asynchronously
        with Session(engine) as session:
            record = session.exec(
                select(DocumentRecord).where(
                    DocumentRecord.filename == filename,
                    DocumentRecord.client_id == client_id,
                )
            ).first()

            if not record:
                record = DocumentRecord(
                    filename=filename,
                    document_type=result.get("document_type", "INVOICE"),
                    extraction_method=result.get("extraction_method", "AI_VISION"),
                    overall_status=result.get("audit_status", "NEEDS_REVIEW"),
                    vendor_name=result.get("vendor_name"),
                    invoice_number=result.get("invoice_number"),
                    total_amount=result.get("total_amount"),
                    raw_json_data=result.get("raw_json_data", "{}"),
                    audit_flags_json=result.get("audit_flags_json", "[]"),
                    client_id=client_id,
                )
            else:
                record.overall_status = result.get("audit_status", "NEEDS_REVIEW")
                record.vendor_name = result.get("vendor_name")
                record.invoice_number = result.get("invoice_number")
                record.total_amount = result.get("total_amount")
                record.raw_json_data = result.get("raw_json_data", "{}")
                record.audit_flags_json = result.get("audit_flags_json", "[]")

            session.add(record)
            session.commit()
            session.refresh(record)

            return {
                "status": "success",
                "record_id": record.id,
                "overall_status": record.overall_status,
            }

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Task failed for {filename}: {exc!s}")
        raise self.retry(exc=exc)