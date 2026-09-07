"""Normalize persisted bank transactions and match them to invoice records."""

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlmodel import Session, select

from app.core.database import BankTransactionRecord, DocumentRecord


def persist_normalized_transactions(
    session: Session,
    document: DocumentRecord,
    transactions: list[dict[str, Any]],
) -> list[BankTransactionRecord]:
    """Upsert normalized transactions for one bank-statement document."""
    records = []
    for transaction in transactions:
        source_row = int(transaction["source_row"])
        record = session.exec(
            select(BankTransactionRecord).where(
                BankTransactionRecord.document_id == document.id,
                BankTransactionRecord.source_row == source_row,
            )
        ).first()
        if record is None:
            record = BankTransactionRecord(
                tenant_id=document.client_id or 0,
                document_id=document.id,
                source_row=source_row,
            )
        for field in (
            "transaction_date",
            "description",
            "reference_number",
            "debit",
            "credit",
            "amount",
            "balance",
        ):
            setattr(record, field, transaction.get(field))
        session.add(record)
        records.append(record)
    session.commit()
    for record in records:
        session.refresh(record)
    return records


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def reconcile_transactions(
    session: Session,
    tenant_id: int,
    transaction_id: int | None = None,
    statement_document_id: int | None = None,
) -> dict[str, Any]:
    """Match bank transactions to tenant invoices without cross-tenant reads."""
    query = select(BankTransactionRecord).where(
        BankTransactionRecord.tenant_id == tenant_id
    )
    if transaction_id is not None:
        query = query.where(BankTransactionRecord.id == transaction_id)
    if statement_document_id is not None:
        query = query.where(BankTransactionRecord.document_id == statement_document_id)
    transactions = session.exec(query).all()
    invoices = session.exec(
        select(DocumentRecord).where(DocumentRecord.client_id == tenant_id)
    ).all()

    results = []
    for transaction in transactions:
        candidates = []
        reference = (transaction.reference_number or "").strip().lower()
        transaction_date = _parse_date(transaction.transaction_date)
        transaction_amount = abs(transaction.amount)
        for invoice in invoices:
            invoice_number = (invoice.invoice_number or "").strip().lower()
            outstanding = max(
                0.0, (invoice.total_amount or 0.0) - (invoice.amount_paid or 0.0)
            )
            if outstanding <= 0:
                continue
            score = 0.0
            reasons = []
            if reference and invoice_number and invoice_number in reference:
                score = 1.0
                reasons.append("reference matched invoice number")
            if abs(transaction_amount - outstanding) <= 0.01:
                score = max(score, 0.75)
                reasons.append("amount matched outstanding balance")
            invoice_date = invoice.created_at.date() if invoice.created_at else None
            if (
                transaction_date
                and invoice_date
                and abs(transaction_date - invoice_date) <= timedelta(days=7)
            ):
                score += 0.15 if score else 0.0
                reasons.append("transaction date within seven days")
            description = transaction.description.lower()
            if invoice.vendor_name and invoice.vendor_name.lower() in description:
                score += 0.1
                reasons.append("vendor name found in description")
            if score:
                candidates.append((min(score, 1.0), invoice, reasons))

        candidates.sort(key=lambda item: item[0], reverse=True)
        if not candidates:
            transaction.reconciliation_status = "UNMATCHED"
            transaction.matched_document_id = None
            transaction.match_score = None
            transaction.match_reason = (
                "No invoice matched by reference, amount, or date."
            )
        else:
            best_score, invoice, reasons = candidates[0]
            tied = len(candidates) > 1 and candidates[1][0] == best_score
            transaction.reconciliation_status = "SUGGESTED" if tied else "MATCHED"
            transaction.matched_document_id = None if tied else invoice.id
            transaction.match_score = best_score
            transaction.match_reason = (
                "Ambiguous candidates: " if tied else "Matched: "
            ) + "; ".join(reasons)
        session.add(transaction)
        results.append(transaction)

    session.commit()
    return {
        "processed": len(results),
        "matched": sum(item.reconciliation_status == "MATCHED" for item in results),
        "suggested": sum(item.reconciliation_status == "SUGGESTED" for item in results),
        "unmatched": sum(item.reconciliation_status == "UNMATCHED" for item in results),
        "transactions": [
            {
                "id": item.id,
                "status": item.reconciliation_status,
                "matched_document_id": item.matched_document_id,
                "score": item.match_score,
                "reason": item.match_reason,
            }
            for item in results
        ],
    }


def approve_transaction_match(
    session: Session,
    transaction_id: int,
    approver_id: int,
    invoice_id: int | None = None,
) -> dict[str, Any]:
    """Approve one suggested match and apply its payment to the invoice once."""
    transaction = session.get(BankTransactionRecord, transaction_id)
    if transaction is None:
        return {"success": False, "error_code": "TRANSACTION_NOT_FOUND"}
    if (
        transaction.approved_at is not None
        or transaction.reconciliation_status == "APPLIED"
    ):
        return {
            "success": True,
            "status": "APPLIED",
            "transaction_id": transaction.id,
            "invoice_id": transaction.matched_document_id,
            "applied_amount": transaction.applied_amount or 0.0,
            "idempotent": True,
        }
    if transaction.reconciliation_status not in {"MATCHED", "SUGGESTED"}:
        return {
            "success": False,
            "error_code": "TRANSACTION_NOT_APPROVABLE",
            "reason": "Only matched or suggested transactions can be approved.",
        }
    if transaction.amount <= 0:
        return {
            "success": False,
            "error_code": "NON_PAYMENT_TRANSACTION",
            "reason": "Only credit transactions can be applied as invoice payments.",
        }

    target_invoice_id = invoice_id or transaction.matched_document_id
    if target_invoice_id is None:
        return {
            "success": False,
            "error_code": "INVOICE_REQUIRED",
            "reason": "An invoice is required to approve an ambiguous match.",
        }
    invoice = session.get(DocumentRecord, target_invoice_id)
    if invoice is None or invoice.client_id != transaction.tenant_id:
        return {
            "success": False,
            "error_code": "INVOICE_NOT_FOUND",
            "reason": "Invoice is not available within the transaction tenant.",
        }

    outstanding = max(0.0, (invoice.total_amount or 0.0) - (invoice.amount_paid or 0.0))
    if transaction.amount > outstanding + 0.01:
        return {
            "success": False,
            "error_code": "PAYMENT_EXCEEDS_BALANCE",
            "reason": "Transaction amount exceeds the invoice balance.",
        }

    invoice.amount_paid = (invoice.amount_paid or 0.0) + transaction.amount
    invoice.payment_status = (
        "PAID" if invoice.amount_paid >= (invoice.total_amount or 0.0) else "PARTIAL"
    )
    transaction.matched_document_id = invoice.id
    transaction.reconciliation_status = "APPLIED"
    transaction.approved_by = approver_id
    transaction.approved_at = datetime.now(timezone.utc)
    transaction.applied_amount = transaction.amount
    transaction.match_reason = (
        f"Approved by user {approver_id}; payment applied to invoice {invoice.id}."
    )
    session.add(invoice)
    session.add(transaction)
    session.commit()
    session.refresh(invoice)
    session.refresh(transaction)
    return {
        "success": True,
        "status": transaction.reconciliation_status,
        "transaction_id": transaction.id,
        "invoice_id": invoice.id,
        "applied_amount": transaction.applied_amount,
        "payment_status": invoice.payment_status,
        "amount_paid": invoice.amount_paid,
        "balance_remaining": max(
            0.0, (invoice.total_amount or 0.0) - (invoice.amount_paid or 0.0)
        ),
        "idempotent": False,
    }
