import json
from typing import Any
from sqlmodel import Session, select

from app.core.database import DocumentRecord
from app.schemas.verification import AuditFlag
from app.services.verification_service import verification_service


class AuditEngine:
    """Evaluates raw document records against deterministic & AI audit rules."""

    @staticmethod
    def evaluate_document(doc: DocumentRecord, session: Session | None = None) -> dict[str, Any]:
        flags: list[dict[str, Any]] = []
        raw_data: dict[str, Any] = {}

        if doc.raw_json_data:
            try:
                raw_data = json.loads(doc.raw_json_data)
            except (json.JSONDecodeError, TypeError):
                flags.append(
                    {
                        "code": "CORRUPTED_RAW_JSON",
                        "field": "raw_json_data",
                        "severity": "CRITICAL",
                        "message": "Raw document JSON data is corrupted or unparseable.",
                    }
                )

        # Ensure minimal top-level attributes are present
        if not raw_data.get("total_amount") and doc.total_amount:
            raw_data["total_amount"] = doc.total_amount
        if not raw_data.get("vendor_name") and doc.vendor_name:
            raw_data["vendor_name"] = doc.vendor_name
        if not raw_data.get("invoice_number") and doc.invoice_number:
            raw_data["invoice_number"] = doc.invoice_number

        # 1. Run VerificationService Deterministic Audit Suite
        if hasattr(verification_service, "audit_tax_invoice"):
            try:
                audit_result = verification_service.audit_tax_invoice(
                    invoice_data=raw_data,
                    session=session,
                    current_doc_id=doc.id,
                )

                for flag in audit_result.flags:
                    flags.append(flag.model_dump())
            except Exception as e:
                flags.append(
                    {
                        "code": "VERIFICATION_SERVICE_ERROR",
                        "field": "verification_service",
                        "severity": "WARNING",
                        "message": f"Verification service encountered an error: {str(e)}",
                    }
                )

        # 2. Check Minimal Document Properties
        if not doc.total_amount or doc.total_amount <= 0:
            flags.append(
                {
                    "code": "MISSING_TOTAL_AMOUNT",
                    "field": "total_amount",
                    "severity": "CRITICAL",
                    "message": "Invoice total amount is zero or missing.",
                }
            )

        if not doc.vendor_name or doc.vendor_name.strip().lower() in [
            "unassigned vendor", "unknown", "unknown_vendor", "extracted vendor"
        ]:
            flags.append(
                {
                    "code": "UNVERIFIED_VENDOR",
                    "field": "vendor_name",
                    "severity": "WARNING",
                    "message": "Vendor name is generic or unverified.",
                }
            )

        if not doc.invoice_number or doc.invoice_number.strip().lower() in ["unknown_inv", "inv-pending", ""]:
            flags.append(
                {
                    "code": "MISSING_INVOICE_NUMBER",
                    "field": "invoice_number",
                    "severity": "WARNING",
                    "message": "Invoice number is missing.",
                }
            )

        # Determine Final Overall Review Status
        has_critical = any(f.get("severity") == "CRITICAL" for f in flags)
        has_warning = any(f.get("severity") in ["WARNING", "HIGH"] for f in flags)

        if has_critical:
            overall_status = "REJECTED"
        elif has_warning:
            overall_status = "NEEDS_REVIEW"
        else:
            overall_status = "VERIFIED"

        return {"status": overall_status, "flags": flags}


def process_document_audit(doc: DocumentRecord, session: Session) -> DocumentRecord:
    """Worker function to run full audit checks and update the database record."""
    results = AuditEngine.evaluate_document(doc, session=session)
    doc.overall_status = results["status"]
    doc.audit_flags_json = json.dumps(results["flags"])

    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc