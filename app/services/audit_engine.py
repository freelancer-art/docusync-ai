import json
from typing import Dict, Any, List
from sqlmodel import Session
from app.core.database import DocumentRecord

class AuditEngine:
    """Evaluates raw invoice extraction data against CA audit rules."""

    @staticmethod
    def evaluate_document(doc: DocumentRecord) -> Dict[str, Any]:
        flags: List[str] = []
        raw_data: Dict[str, Any] = {}

        if doc.raw_json_data:
            try:
                raw_data = json.loads(doc.raw_json_data)
            except (json.JSONDecodeError, TypeError):
                flags.append("CORRUPTED_RAW_JSON")

        # Rule 1: Missing or Zero Total Amount
        if not doc.total_amount or doc.total_amount <= 0:
            flags.append("MISSING_TOTAL_AMOUNT")

        # Rule 2: Unassigned or Generic Vendor
        if not doc.vendor_name or doc.vendor_name.strip().lower() in ["unassigned vendor", "unknown"]:
            flags.append("UNVERIFIED_VENDOR")

        # Rule 3: Missing Invoice Number
        if not doc.invoice_number:
            flags.append("MISSING_INVOICE_NUMBER")

        # Determine review status
        overall_status = "NEEDS_REVIEW" if flags else "VERIFIED"

        return {
            "status": overall_status,
            "flags": flags
        }

def process_document_audit(doc: DocumentRecord, session: Session) -> DocumentRecord:
    """Worker function to run audit checks and update the database record."""
    results = AuditEngine.evaluate_document(doc)
    doc.overall_status = results["status"]
    doc.audit_flags_json = json.dumps(results["flags"])
    
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc