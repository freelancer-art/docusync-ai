from typing import Dict, Any
from sqlmodel import Session, select
from app.core.database import DocumentRecord

class ReconciliationEngine:
    """Matches payments against open invoice records."""

    @staticmethod
    def process_payment(
        session: Session, 
        invoice_number: str, 
        payment_amount: float
    ) -> Dict[str, Any]:
        statement = select(DocumentRecord).where(DocumentRecord.invoice_number == invoice_number)
        doc = session.exec(statement).first()

        if not doc:
            return {"success": False, "reason": "Invoice not found"}

        new_total_paid = doc.amount_paid + payment_amount
        total_due = doc.total_amount or 0.0

        if new_total_paid >= total_due:
            doc.payment_status = "PAID"
        elif new_total_paid > 0:
            doc.payment_status = "PARTIALLY_PAID"

        doc.amount_paid = new_total_paid
        session.add(doc)
        session.commit()
        session.refresh(doc)

        return {
            "success": True,
            "invoice_number": doc.invoice_number,
            "payment_status": doc.payment_status,
            "amount_paid": doc.amount_paid,
            "balance_remaining": max(0.0, total_due - new_total_paid)
        }