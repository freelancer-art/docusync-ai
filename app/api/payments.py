from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session

from app.core.database import User, UserRole, get_session
from app.core.security import get_current_user
from app.services.reconciliation import ReconciliationEngine

router = APIRouter(prefix="/api/payments", tags=["payments"])


class PaymentRecordRequest(BaseModel):
    invoice_number: str
    payment_amount: float


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

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=result["reason"]
        )

    return result
