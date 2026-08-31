from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.database import User, UserRole, DocumentRecord

def test_portal_review_queue_and_override(client: TestClient, session: Session):
    admin = User(
        username="admin_ca",
        full_name="CA Admin",
        hashed_password=User.hash_password("admin123"),
        role=UserRole.CA_ADMIN,
    )
    client_user = User(
        username="client_a",
        full_name="Client A",
        hashed_password=User.hash_password("pass123"),
        role=UserRole.CLIENT,
    )
    session.add_all([admin, client_user])
    session.commit()

    # Create flagged document with required raw_json_data field
    doc = DocumentRecord(
        filename="anomaly.pdf",
        document_type="INVOICE",
        extraction_method="AI_VISION",
        overall_status="NEEDS_REVIEW",
        client_id=client_user.id,
        raw_json_data="{}",
        audit_flags_json='["MISSING_TOTAL_AMOUNT"]',
    )
    session.add(doc)
    session.commit()

    # Login Admin
    login_resp = client.post(
        "/api/auth/login", data={"username": "admin_ca", "password": "admin123"}
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch Review Queue
    queue_resp = client.get("/api/portal/review-queue", headers=headers)
    assert queue_resp.status_code == 200
    assert len(queue_resp.json()) == 1
    assert queue_resp.json()[0]["audit_flags"] == ["MISSING_TOTAL_AMOUNT"]

    # Override Status
    override_resp = client.patch(
        f"/api/portal/documents/{doc.id}/override",
        json={"new_status": "VERIFIED"},
        headers=headers,
    )
    assert override_resp.status_code == 200
    assert override_resp.json()["overall_status"] == "VERIFIED"