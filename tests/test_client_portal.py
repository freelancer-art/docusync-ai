import pytest
from httpx import AsyncClient
from sqlmodel import Session
from app.core.database import DocumentRecord


@pytest.mark.asyncio
async def test_portal_review_queue_and_override(
    async_client: AsyncClient, db_session: Session, seed_users: dict
):
    admin = seed_users["admin"]
    client_a = seed_users["client_a"]

    doc = DocumentRecord(
        filename="anomaly.pdf",
        document_type="INVOICE",
        extraction_method="AI_VISION",
        overall_status="NEEDS_REVIEW",
        client_id=client_a.id,
        raw_json_data="{}",
        audit_flags_json='["MISSING_TOTAL_AMOUNT"]',
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

    # Fetch Review Queue
    queue_resp = await async_client.get("/api/portal/review-queue", headers=headers)
    assert queue_resp.status_code == 200
    assert len(queue_resp.json()) == 1

    # Override Status
    override_resp = await async_client.patch(
        f"/api/portal/documents/{doc.id}/override",
        json={"new_status": "VERIFIED"},
        headers=headers,
    )
    assert override_resp.status_code == 200
    assert override_resp.json()["overall_status"] == "VERIFIED"