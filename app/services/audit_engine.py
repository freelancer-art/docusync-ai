import json
from typing import Any
from sqlmodel import Session

from app.core.database import DocumentRecord
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

        # Sync top-level attributes to dictionary payload
        if not raw_data.get("total_amount") and doc.total_amount:
            raw_data["total_amount"] = doc.total_amount
        if not raw_data.get("vendor_name") and doc.vendor_name:
            raw_data["vendor_name"] = doc.vendor_name
        if not raw_data.get("invoice_number") and doc.invoice_number:
            raw_data["invoice_number"] = doc.invoice_number

        # 1. Deterministic Verification Suite
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

        # 2. Minimal Document Property Guardrails
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

        # 3. LLM Anomaly Inspection
        try:
            llm_result = verification_service.audit_with_llm_anomaly_check(raw_data)
            if llm_result and getattr(llm_result, "detected_anomalies", None):
                for anomaly in llm_result.detected_anomalies:
                    flags.append(
                        {
                            "code": "AI_ANOMALY_DETECTED",
                            "field": getattr(anomaly, "field", "general"),
                            "severity": getattr(anomaly, "severity", "HIGH"),
                            "message": f"[AI Audit] {getattr(anomaly, 'description', '')}",
                        }
                    )
        except Exception:
            pass  # Non-blocking fallthrough if LLM provider is unavailable

        # 4. Final Review Status Determination
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