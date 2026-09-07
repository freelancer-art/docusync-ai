from datetime import datetime, timezone

from sqlmodel import Session, select

from app.core.database import BankTransactionRecord, DocumentRecord
from app.services.bank_reconciliation import (
    approve_transaction_match,
    persist_normalized_transactions,
    reconcile_transactions,
)


def _invoice(
    client_id: int,
    invoice_number: str,
    total_amount: float,
    vendor_name: str = "Acme Supplies",
) -> DocumentRecord:
    return DocumentRecord(
        filename=f"{invoice_number}.pdf",
        document_type="TAX_INVOICE",
        client_id=client_id,
        invoice_number=invoice_number,
        vendor_name=vendor_name,
        total_amount=total_amount,
        amount_paid=0.0,
        raw_json_data="{}",
        audit_flags_json="[]",
        created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )


def _statement(client_id: int) -> DocumentRecord:
    return DocumentRecord(
        filename="statement.csv",
        document_type="BANK_STATEMENT",
        client_id=client_id,
        raw_json_data="{}",
        audit_flags_json="[]",
    )


def test_persist_normalized_transactions_is_idempotent(db_session: Session, seed_users):
    statement = _statement(seed_users["client_a"].id)
    db_session.add(statement)
    db_session.commit()
    db_session.refresh(statement)

    payload = [
        {
            "source_row": 2,
            "transaction_date": "2026-09-02",
            "description": "Payment INV-100",
            "reference_number": "INV-100",
            "debit": None,
            "credit": 500.0,
            "amount": 500.0,
            "balance": 1500.0,
        }
    ]
    first = persist_normalized_transactions(db_session, statement, payload)
    second = persist_normalized_transactions(db_session, statement, payload)

    assert len(first) == 1
    assert len(second) == 1
    assert len(db_session.exec(select(BankTransactionRecord)).all()) == 1


def test_reconcile_exact_reference_match(db_session: Session, seed_users):
    tenant_id = seed_users["client_a"].id
    invoice = _invoice(tenant_id, "INV-100", 500.0)
    statement = _statement(tenant_id)
    db_session.add_all([invoice, statement])
    db_session.commit()
    db_session.refresh(invoice)
    db_session.refresh(statement)
    [transaction] = persist_normalized_transactions(
        db_session,
        statement,
        [
            {
                "source_row": 2,
                "transaction_date": "2026-09-02",
                "description": "Payment Acme Supplies",
                "reference_number": "INV-100",
                "debit": None,
                "credit": 500.0,
                "amount": 500.0,
                "balance": 1500.0,
            }
        ],
    )

    result = reconcile_transactions(
        db_session, tenant_id, transaction_id=transaction.id
    )

    assert result["matched"] == 1
    db_session.refresh(transaction)
    assert transaction.reconciliation_status == "MATCHED"
    assert transaction.matched_document_id == invoice.id


def test_reconcile_ambiguous_amount_is_suggested(db_session: Session, seed_users):
    tenant_id = seed_users["client_a"].id
    first = _invoice(tenant_id, "INV-101", 500.0, "Vendor One")
    second = _invoice(tenant_id, "INV-102", 500.0, "Vendor Two")
    statement = _statement(tenant_id)
    db_session.add_all([first, second, statement])
    db_session.commit()
    db_session.refresh(statement)
    [transaction] = persist_normalized_transactions(
        db_session,
        statement,
        [
            {
                "source_row": 2,
                "transaction_date": "2026-09-02",
                "description": "Unknown payment",
                "reference_number": None,
                "debit": None,
                "credit": 500.0,
                "amount": 500.0,
                "balance": 1500.0,
            }
        ],
    )

    result = reconcile_transactions(
        db_session, tenant_id, transaction_id=transaction.id
    )

    assert result["suggested"] == 1
    db_session.refresh(transaction)
    assert transaction.reconciliation_status == "SUGGESTED"
    assert transaction.matched_document_id is None


def test_reconcile_does_not_cross_tenant_boundary(db_session: Session, seed_users):
    owner_id = seed_users["client_a"].id
    other_tenant_id = seed_users["client_b"].id
    invoice = _invoice(other_tenant_id, "INV-OTHER", 500.0)
    statement = _statement(owner_id)
    db_session.add_all([invoice, statement])
    db_session.commit()
    db_session.refresh(statement)
    [transaction] = persist_normalized_transactions(
        db_session,
        statement,
        [
            {
                "source_row": 2,
                "transaction_date": "2026-09-02",
                "description": "Payment INV-OTHER",
                "reference_number": "INV-OTHER",
                "debit": None,
                "credit": 500.0,
                "amount": 500.0,
                "balance": 1500.0,
            }
        ],
    )

    result = reconcile_transactions(db_session, owner_id, transaction_id=transaction.id)

    assert result["unmatched"] == 1
    db_session.refresh(transaction)
    assert transaction.matched_document_id is None


def test_approval_applies_payment_once_and_is_idempotent(
    db_session: Session, seed_users
):
    tenant_id = seed_users["client_a"].id
    invoice = _invoice(tenant_id, "INV-APPROVE", 500.0)
    statement = _statement(tenant_id)
    db_session.add_all([invoice, statement])
    db_session.commit()
    db_session.refresh(invoice)
    db_session.refresh(statement)
    [transaction] = persist_normalized_transactions(
        db_session,
        statement,
        [
            {
                "source_row": 2,
                "transaction_date": "2026-09-02",
                "description": "Payment INV-APPROVE",
                "reference_number": "INV-APPROVE",
                "debit": None,
                "credit": 500.0,
                "amount": 500.0,
                "balance": 1500.0,
            }
        ],
    )
    reconcile_transactions(db_session, tenant_id, transaction_id=transaction.id)

    first = approve_transaction_match(
        db_session, transaction.id, seed_users["admin"].id
    )
    second = approve_transaction_match(
        db_session, transaction.id, seed_users["admin"].id
    )

    assert first["status"] == "APPLIED"
    assert first["payment_status"] == "PAID"
    assert first["amount_paid"] == 500.0
    assert second["idempotent"] is True
    db_session.refresh(invoice)
    assert invoice.amount_paid == 500.0


def test_ambiguous_approval_requires_and_accepts_selected_invoice(
    db_session: Session, seed_users
):
    tenant_id = seed_users["client_a"].id
    first = _invoice(tenant_id, "INV-CHOICE-1", 500.0, "Vendor One")
    second = _invoice(tenant_id, "INV-CHOICE-2", 500.0, "Vendor Two")
    statement = _statement(tenant_id)
    db_session.add_all([first, second, statement])
    db_session.commit()
    db_session.refresh(statement)
    db_session.refresh(first)
    [transaction] = persist_normalized_transactions(
        db_session,
        statement,
        [
            {
                "source_row": 2,
                "transaction_date": "2026-09-02",
                "description": "Unknown payment",
                "reference_number": None,
                "debit": None,
                "credit": 500.0,
                "amount": 500.0,
                "balance": 1500.0,
            }
        ],
    )
    reconcile_transactions(db_session, tenant_id, transaction_id=transaction.id)

    missing_invoice = approve_transaction_match(
        db_session, transaction.id, seed_users["admin"].id
    )
    applied = approve_transaction_match(
        db_session, transaction.id, seed_users["admin"].id, invoice_id=first.id
    )

    assert missing_invoice["error_code"] == "INVOICE_REQUIRED"
    assert applied["invoice_id"] == first.id
    assert applied["status"] == "APPLIED"


def test_approval_rejects_overpayment_without_mutation(db_session: Session, seed_users):
    tenant_id = seed_users["client_a"].id
    invoice = _invoice(tenant_id, "INV-SMALL", 100.0)
    statement = _statement(tenant_id)
    db_session.add_all([invoice, statement])
    db_session.commit()
    db_session.refresh(invoice)
    db_session.refresh(statement)
    [transaction] = persist_normalized_transactions(
        db_session,
        statement,
        [
            {
                "source_row": 2,
                "transaction_date": "2026-09-02",
                "description": "Payment INV-SMALL",
                "reference_number": "INV-SMALL",
                "debit": None,
                "credit": 150.0,
                "amount": 150.0,
                "balance": 1500.0,
            }
        ],
    )
    reconcile_transactions(db_session, tenant_id, transaction_id=transaction.id)

    result = approve_transaction_match(
        db_session, transaction.id, seed_users["admin"].id
    )

    assert result["error_code"] == "PAYMENT_EXCEEDS_BALANCE"
    db_session.refresh(invoice)
    db_session.refresh(transaction)
    assert invoice.amount_paid == 0.0
    assert transaction.reconciliation_status == "MATCHED"


def test_approval_rejects_invoice_from_another_tenant(db_session: Session, seed_users):
    tenant_id = seed_users["client_a"].id
    foreign_invoice = _invoice(seed_users["client_b"].id, "INV-FOREIGN", 500.0)
    statement = _statement(tenant_id)
    db_session.add_all([foreign_invoice, statement])
    db_session.commit()
    db_session.refresh(foreign_invoice)
    db_session.refresh(statement)
    [transaction] = persist_normalized_transactions(
        db_session,
        statement,
        [
            {
                "source_row": 2,
                "transaction_date": "2026-09-02",
                "description": "Payment",
                "reference_number": None,
                "debit": None,
                "credit": 500.0,
                "amount": 500.0,
                "balance": 1500.0,
            }
        ],
    )
    transaction.reconciliation_status = "SUGGESTED"
    db_session.add(transaction)
    db_session.commit()

    result = approve_transaction_match(
        db_session,
        transaction.id,
        seed_users["admin"].id,
        invoice_id=foreign_invoice.id,
    )

    assert result["error_code"] == "INVOICE_NOT_FOUND"
