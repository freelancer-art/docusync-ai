from fastapi.testclient import TestClient
from sqlmodel import Session
from app.core.database import User, UserRole, DocumentRecord

def test_payment_reconciliation_flow(client: TestClient, session: Session):
    admin = User(
        username="ca_admin_rec",
        full_name="CA Admin",
        hashed_password=User.hash_password("admin123"),
        role=UserRole.CA_ADMIN
    )
    session.add(admin)
    session.commit()

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
        audit_flags_json="[]"
    )
    session.add(doc)
    session.commit()

    login_resp = client.post("/api/auth/login", data={"username": "ca_admin_rec", "password": "admin123"})
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    part_resp = client.post(
        "/api/payments/reconcile",
        json={"invoice_number": "INV-REC-100", "payment_amount": 200.0},
        headers=headers
    )
    assert part_resp.status_code == 200
    assert part_resp.json()["payment_status"] == "PARTIALLY_PAID"
    assert part_resp.json()["balance_remaining"] == 300.0

    full_resp = client.post(
        "/api/payments/reconcile",
        json={"invoice_number": "INV-REC-100", "payment_amount": 300.0},
        headers=headers
    )
    assert full_resp.status_code == 200
    assert full_resp.json()["payment_status"] == "PAID"
    assert full_resp.json()["balance_remaining"] == 0.0