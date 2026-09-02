import pytest
from httpx import AsyncClient
from sqlmodel import Session, select

from app.core.database import DocumentRecord, User, UserRole


@pytest.mark.asyncio
async def test_health_check(async_client: AsyncClient):
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_tenant_isolation_rules(db_session: Session, seed_users: dict[str, User]):
    client_a = seed_users["client_a"]
    client_b = seed_users["client_b"]

    doc_a = DocumentRecord(
        filename="invoice_a.pdf",
        document_type="INVOICE",
        extraction_method="AI_VISION",
        overall_status="VERIFIED",
        client_id=client_a.id,
    )
    doc_b = DocumentRecord(
        filename="invoice_b.pdf",
        document_type="INVOICE",
        extraction_method="AI_VISION",
        overall_status="NEEDS_REVIEW",
        client_id=client_b.id,
    )

    db_session.add(doc_a)
    db_session.add(doc_b)
    db_session.commit()

    records_a = db_session.exec(
        select(DocumentRecord).where(DocumentRecord.client_id == client_a.id)
    ).all()

    assert len(records_a) == 1
    assert records_a[0].filename == "invoice_a.pdf"

    records_b = db_session.exec(
        select(DocumentRecord).where(DocumentRecord.client_id == client_b.id)
    ).all()

    assert len(records_b) == 1
    assert records_b[0].filename == "invoice_b.pdf"


def test_filename_sanitization():
    dirty_name = "../../../etc/passwd"
    clean_name = DocumentRecord.sanitize_filename(dirty_name)
    assert clean_name == "passwd"


@pytest.mark.asyncio
async def test_admin_create_user_and_list(
    async_client: AsyncClient, db_session: Session, seed_users: dict
):
    # Login Admin
    login_resp = await async_client.post(
        "/api/auth/login",
        data={"username": "admin_test", "password": "admin123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Provision new Client user
    new_user_payload = {
        "username": "new_client_test",
        "full_name": "New Test Client",
        "password": "Password123!",
        "role": "CLIENT",
    }
    create_resp = await async_client.post(
        "/api/users/", json=new_user_payload, headers=headers
    )
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    assert created_data["username"] == "new_client_test"
    assert created_data["role"] == "CLIENT"

    # Verify user saved in DB
    db_user = db_session.exec(
        select(User).where(User.username == "new_client_test")
    ).first()
    assert db_user is not None
    assert db_user.full_name == "New Test Client"

    # List all users as CA Admin
    list_resp = await async_client.get("/api/users/", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 3


@pytest.mark.asyncio
async def test_client_privilege_escalation_blocked(
    async_client: AsyncClient, seed_users: dict
):
    # Login as Standard Client
    login_resp = await async_client.post(
        "/api/auth/login",
        data={"username": "client_a", "password": "pass123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to create a user (Forbidden for CLIENT role)
    unauthorized_create = await async_client.post(
        "/api/users/",
        json={
            "username": "hacker_user",
            "full_name": "Hacker",
            "password": "password123",
            "role": "CA_ADMIN",
        },
        headers=headers,
    )
    assert unauthorized_create.status_code == 403
    assert "Insufficient privileges" in unauthorized_create.json()["detail"]

    # Attempt to list all users (Forbidden for CLIENT role)
    unauthorized_list = await async_client.get("/api/users/", headers=headers)
    assert unauthorized_list.status_code == 403


@pytest.mark.asyncio
async def test_get_current_user_profile(
    async_client: AsyncClient, seed_users: dict
):
    login_resp = await async_client.post(
        "/api/auth/login",
        data={"username": "client_a", "password": "pass123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me_resp = await async_client.get("/api/users/me", headers=headers)
    assert me_resp.status_code == 200
    data = me_resp.json()
    assert data["username"] == "client_a"
    assert data["role"] == "CLIENT"


@pytest.mark.asyncio
async def test_admin_update_and_delete_user(
    async_client: AsyncClient, db_session: Session, seed_users: dict
):
    admin_login = await async_client.post(
        "/api/auth/login",
        data={"username": "admin_test", "password": "admin123"},
    )
    assert admin_login.status_code == 200
    headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    client_b = seed_users["client_b"]

    # Update Client B's details
    patch_resp = await async_client.patch(
        f"/api/users/{client_b.id}",
        json={"full_name": "Updated Client B Name"},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["full_name"] == "Updated Client B Name"

    # Delete Client B account
    del_resp = await async_client.delete(
        f"/api/users/{client_b.id}", headers=headers
    )
    assert del_resp.status_code == 204

    # Verify user is removed from DB
    deleted_user = db_session.get(User, client_b.id)
    assert deleted_user is None