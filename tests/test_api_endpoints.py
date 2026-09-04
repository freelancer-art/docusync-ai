from fastapi.testclient import TestClient

from app.core.database import DocumentRecord, User


def test_user_creation_duplicate_username(client: TestClient, admin_token_headers: dict, db_session):
    """Cover lines 56: Duplicate username creation returns 400 Bad Request."""
    response = client.post(
        "/api/users/",
        json={
            "username": "admin",
            "full_name": "Duplicate Admin",
            "password": "Password123!",
            "role": "CLIENT",
        },
        headers=admin_token_headers,
    )
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower() or "exists" in response.json()["detail"].lower()


def test_get_user_not_found(client: TestClient, admin_token_headers: dict):
    """Cover lines 91-97: Fetching non-existent user returns 404 Not Found."""
    response = client.get("/api/users/999999", headers=admin_token_headers)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_update_user_not_found(client: TestClient, admin_token_headers: dict):
    """Cover lines 110, 118, 120: Updating non-existent user returns 404 Not Found."""
    response = client.patch(
        "/api/users/999999",
        json={"full_name": "Ghost User", "password": "NewPassword123!"},
        headers=admin_token_headers,
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_delete_user_not_found(client: TestClient, admin_token_headers: dict):
    """Cover line 137: Deleting non-existent user returns 404 Not Found."""
    response = client.delete("/api/users/999999", headers=admin_token_headers)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_delete_self_as_admin_forbidden(client: TestClient, admin_user: User, admin_token_headers: dict):
    """Cover line 143: Admin attempting self-deletion returns 400 Bad Request."""
    response = client.delete(f"/api/users/{admin_user.id}", headers=admin_token_headers)
    assert response.status_code == 400
    assert "cannot delete" in response.json()["detail"].lower()


def test_document_get_update_delete_forbidden_for_client(
    client: TestClient, db_session, seed_users
):
    client_a = seed_users["client_a"]
    client_b = seed_users["client_b"]
    doc_b = DocumentRecord(
        filename="client_b_invoice.pdf",
        document_type="INVOICE",
        extraction_method="AI_VISION",
        overall_status="VERIFIED",
        client_id=client_b.id,
        invoice_number="INV-B",
        vendor_name="Vendor B",
        total_amount=100.0,
    )
    db_session.add(doc_b)
    db_session.commit()
    db_session.refresh(doc_b)

    login_resp = client.post(
        "/api/auth/login",
        data={"username": client_a.username, "password": "pass123"},
    )
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    get_resp = client.get(f"/api/documents/{doc_b.id}", headers=headers)
    patch_resp = client.patch(
        f"/api/documents/{doc_b.id}",
        json={"overall_status": "VERIFIED"},
        headers=headers,
    )
    delete_resp = client.delete(f"/api/documents/{doc_b.id}", headers=headers)

    assert get_resp.status_code == 403
    assert patch_resp.status_code == 403
    assert delete_resp.status_code == 403


def test_document_update_and_delete_not_found_for_admin(
    client: TestClient, admin_token_headers: dict
):
    patch_resp = client.patch(
        "/api/documents/999999",
        json={"overall_status": "VERIFIED"},
        headers=admin_token_headers,
    )
    delete_resp = client.delete("/api/documents/999999", headers=admin_token_headers)

    assert patch_resp.status_code == 404
    assert delete_resp.status_code == 404
