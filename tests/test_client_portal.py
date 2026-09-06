import pytest
from httpx import AsyncClient
from sqlmodel import Session

from app.core.database import DocumentRecord


@pytest.mark.asyncio
async def test_portal_review_queue_and_override(
    async_client: AsyncClient, db_session: Session, seed_users: dict
):
    # admin = seed_users["admin"]
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


@pytest.mark.asyncio
async def test_admin_can_rerun_classification_and_clients_cannot(
    async_client: AsyncClient, db_session: Session, seed_users: dict, monkeypatch
):
    client_a = seed_users["client_a"]
    doc = DocumentRecord(
        filename="unknown.pdf",
        document_type="UNKNOWN",
        classification_confidence=0.2,
        classification_reasoning="No strong indicators.",
        overall_status="NEEDS_REVIEW",
        client_id=client_a.id,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    def fake_rerun(document, session):
        document.document_type = "BANK_STATEMENT"
        document.classification_confidence = 0.9
        document.classification_reasoning = "Matched statement keywords."
        session.add(document)
        session.commit()
        session.refresh(document)
        return document

    monkeypatch.setattr(
        "app.api.client_portal.rerun_document_classification", fake_rerun
    )

    admin_login = await async_client.post(
        "/api/auth/login",
        data={"username": "admin_test", "password": "admin123"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    rerun_resp = await async_client.post(
        f"/api/portal/documents/{doc.id}/rerun-classification",
        headers=admin_headers,
    )
    assert rerun_resp.status_code == 200
    assert rerun_resp.json()["document_type"] == "BANK_STATEMENT"
    assert rerun_resp.json()["classification_confidence"] == 0.9

    client_login = await async_client.post(
        "/api/auth/login",
        data={"username": "client_a", "password": "pass123"},
    )
    client_headers = {"Authorization": f"Bearer {client_login.json()['access_token']}"}
    forbidden_resp = await async_client.post(
        f"/api/portal/documents/{doc.id}/rerun-classification",
        headers=client_headers,
    )
    assert forbidden_resp.status_code == 403
