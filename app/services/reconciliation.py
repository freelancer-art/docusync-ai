from typing import Any

from sqlmodel import Session, select

from app.core.database import DocumentRecord


class ReconciliationEngine:
    """Matches payments against open invoice records."""

    @staticmethod
    def process_payment(
        session: Session, invoice_number: str, payment_amount: float
    ) -> dict[str, Any]:
        if payment_amount <= 0:
            return {
                "success": False,
                "reason": "Payment amount must be greater than zero",
                "error_code": "INVALID_PAYMENT_AMOUNT",
            }

        statement = select(DocumentRecord).where(
            DocumentRecord.invoice_number == invoice_number
        )
        matches = session.exec(statement).all()

        if not matches:
            return {"success": False, "reason": "Invoice not found"}
        if len(matches) > 1:
            return {
                "success": False,
                "reason": "Multiple invoices found for invoice number",
                "error_code": "DUPLICATE_INVOICE_NUMBER",
            }

        doc = matches[0]

        new_total_paid = doc.amount_paid + payment_amount
        total_due = doc.total_amount or 0.0

        if new_total_paid >= total_due:
            doc.payment_status = "PAID"
        elif new_total_paid > 0:
            doc.payment_status = "PARTIAL"

        doc.amount_paid = new_total_paid
        session.add(doc)
        session.commit()
        session.refresh(doc)

        return {
            "success": True,
            "invoice_number": doc.invoice_number,
            "payment_status": doc.payment_status,
            "amount_paid": doc.amount_paid,
            "balance_remaining": max(0.0, total_due - new_total_paid),
        }
