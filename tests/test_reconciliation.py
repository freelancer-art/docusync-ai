import pytest
from httpx import AsyncClient
from sqlmodel import Session
from app.core.database import DocumentRecord


@pytest.mark.asyncio
async def test_payment_reconciliation_flow(
    async_client: AsyncClient, db_session: Session, seed_users: dict
):
    admin = seed_users["admin"]

    doc = DocumentRecord(
        filename="unpaid_inv.pdf",
        document_type="INVOICE",
        extraction_method="AI_VISION",
        overall_status="VERIFIED",
        client_id=admin.id,
        invoice_number="INV-REC-100",
        total_amount=500.0,
        amount_paid=0.0,
        payment_status="UNPAID",
        raw_json_data="{}",
        audit_flags_json="[]",
    )
    db_session.add(doc)
    db_session.commit()

    # Login Admin
    login_resp = await async_client.post(
        "/api/auth/login",
        data={"username": "admin_test", "password": "admin123"},
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Reconcile Partial Payment
    part_resp = await async_client.post(
        "/api/payments/reconcile",
        json={"invoice_number": "INV-REC-100", "payment_amount": 200.0},
        headers=headers,
    )
    assert part_resp.status_code == 200
    assert part_resp.json()["payment_status"] == "PARTIALLY_PAID"

    # Reconcile Full Payment
    full_resp = await async_client.post(
        "/api/payments/reconcile",
        json={"invoice_number": "INV-REC-100", "payment_amount": 300.0},
        headers=headers,
    )
    assert full_resp.status_code == 200
    assert full_resp.json()["payment_status"] == "PAID"