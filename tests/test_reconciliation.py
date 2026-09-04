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
    assert part_resp.json()["payment_status"] == "PARTIAL"

    # Reconcile Full Payment
    full_resp = await async_client.post(
        "/api/payments/reconcile",
        json={"invoice_number": "INV-REC-100", "payment_amount": 300.0},
        headers=headers,
    )
    assert full_resp.status_code == 200
    assert full_resp.json()["payment_status"] == "PAID"


@pytest.mark.asyncio
async def test_payment_reconciliation_overpayment_returns_zero_balance(
    async_client: AsyncClient, db_session: Session, seed_users: dict
):
    admin = seed_users["admin"]
    doc = DocumentRecord(
        filename="overpaid_inv.pdf",
        document_type="INVOICE",
        extraction_method="AI_VISION",
        overall_status="VERIFIED",
        client_id=admin.id,
        invoice_number="INV-OVER-100",
        total_amount=100.0,
        amount_paid=0.0,
        payment_status="UNPAID",
        raw_json_data="{}",
        audit_flags_json="[]",
    )
    db_session.add(doc)
    db_session.commit()

    login_resp = await async_client.post(
        "/api/auth/login",
        data={"username": "admin_test", "password": "admin123"},
    )
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    response = await async_client.post(
        "/api/payments/reconcile",
        json={"invoice_number": "INV-OVER-100", "payment_amount": 150.0},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["payment_status"] == "PAID"
    assert response.json()["amount_paid"] == 150.0
    assert response.json()["balance_remaining"] == 0.0


@pytest.mark.asyncio
async def test_payment_reconciliation_rejects_client_user(
    async_client: AsyncClient, seed_users: dict
):
    login_resp = await async_client.post(
        "/api/auth/login",
        data={"username": "client_a", "password": "pass123"},
    )
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    response = await async_client.post(
        "/api/payments/reconcile",
        json={"invoice_number": "INV-REC-100", "payment_amount": 10.0},
        headers=headers,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_payment_reconciliation_rejects_invalid_amount(
    async_client: AsyncClient, seed_users: dict
):
    login_resp = await async_client.post(
        "/api/auth/login",
        data={"username": "admin_test", "password": "admin123"},
    )
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    response = await async_client.post(
        "/api/payments/reconcile",
        json={"invoice_number": "INV-REC-100", "payment_amount": -10.0},
        headers=headers,
    )

    assert response.status_code == 400
    assert "greater than zero" in response.json()["detail"]


@pytest.mark.asyncio
async def test_payment_reconciliation_rejects_duplicate_invoice_numbers(
    async_client: AsyncClient, db_session: Session, seed_users: dict
):
    admin = seed_users["admin"]
    docs = [
        DocumentRecord(
            filename=f"duplicate_{idx}.pdf",
            document_type="INVOICE",
            extraction_method="AI_VISION",
            overall_status="VERIFIED",
            client_id=admin.id,
            invoice_number="INV-DUP-100",
            total_amount=500.0,
            amount_paid=0.0,
            payment_status="UNPAID",
            raw_json_data="{}",
            audit_flags_json="[]",
        )
        for idx in range(2)
    ]
    db_session.add_all(docs)
    db_session.commit()

    login_resp = await async_client.post(
        "/api/auth/login",
        data={"username": "admin_test", "password": "admin123"},
    )
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    response = await async_client.post(
        "/api/payments/reconcile",
        json={"invoice_number": "INV-DUP-100", "payment_amount": 10.0},
        headers=headers,
    )

    assert response.status_code == 409
    assert "Multiple invoices" in response.json()["detail"]
