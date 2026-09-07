"""Payment reconciliation endpoint for tenant-owned invoice records."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session

from app.core.database import (
    BankTransactionRecord,
    DocumentRecord,
    User,
    UserRole,
    get_session,
)
from app.core.security import get_current_user
from app.services.bank_reconciliation import (
    approve_transaction_match,
    reconcile_transactions,
)
from app.services.reconciliation import ReconciliationEngine

router = APIRouter(prefix="/api/payments", tags=["payments"])


class PaymentRecordRequest(BaseModel):
    invoice_number: str
    payment_amount: float


class BankReconciliationRequest(BaseModel):
    transaction_id: int | None = None
    statement_document_id: int | None = None


class BankReconciliationApprovalRequest(BaseModel):
    invoice_id: int | None = None


@router.post("/reconcile")
async def reconcile_payment(
    payload: PaymentRecordRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if current_user.role != UserRole.CA_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="CA Admin access required"
        )

    result = ReconciliationEngine.process_payment(
        session=session,
        invoice_number=payload.invoice_number,
        payment_amount=payload.payment_amount,
    )

    if not result["success"] and result.get("error_code") == "INVALID_PAYMENT_AMOUNT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=result["reason"]
        )
    if not result["success"] and result.get("error_code") == "DUPLICATE_INVOICE_NUMBER":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=result["reason"]
        )
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=result["reason"]
        )

    return result


@router.post("/reconcile-bank")
async def reconcile_bank_statement(
    payload: BankReconciliationRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Run tenant-scoped deterministic matching for normalized bank transactions."""
    if current_user.role != UserRole.CA_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="CA Admin access required"
        )
    if payload.transaction_id is None and payload.statement_document_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide transaction_id or statement_document_id",
        )

    if payload.transaction_id is not None:
        transaction = session.get(BankTransactionRecord, payload.transaction_id)
        if transaction is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bank transaction not found",
            )
        tenant_id = transaction.tenant_id
    else:
        statement = session.get(DocumentRecord, payload.statement_document_id)
        if statement is None or statement.document_type != "BANK_STATEMENT":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bank statement not found",
            )
        if statement.client_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bank statement is not assigned to a tenant",
            )
        tenant_id = statement.client_id

    return reconcile_transactions(
        session,
        tenant_id=tenant_id,
        transaction_id=payload.transaction_id,
        statement_document_id=payload.statement_document_id,
    )


@router.post("/reconcile-bank/{transaction_id}/approve")
async def approve_bank_reconciliation(
    transaction_id: int,
    payload: BankReconciliationApprovalRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Approve and apply one tenant-safe bank transaction match."""
    if current_user.role != UserRole.CA_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="CA Admin access required"
        )
    transaction = session.get(BankTransactionRecord, transaction_id)
    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bank transaction not found"
        )
    result = approve_transaction_match(
        session,
        transaction_id=transaction_id,
        approver_id=current_user.id,
        invoice_id=payload.invoice_id,
    )
    if result["success"]:
        return result
    error_status = {
        "INVOICE_REQUIRED": status.HTTP_400_BAD_REQUEST,
        "NON_PAYMENT_TRANSACTION": status.HTTP_400_BAD_REQUEST,
        "PAYMENT_EXCEEDS_BALANCE": status.HTTP_409_CONFLICT,
        "TRANSACTION_NOT_APPROVABLE": status.HTTP_409_CONFLICT,
        "INVOICE_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    }.get(result.get("error_code"), status.HTTP_400_BAD_REQUEST)
    raise HTTPException(status_code=error_status, detail=result.get("reason"))
