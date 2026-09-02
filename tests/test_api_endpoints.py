import pytest
from fastapi.testclient import TestClient

from app.core.database import User, UserRole


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