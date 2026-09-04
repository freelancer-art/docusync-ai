from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.middleware import setup_security_middleware
from app.main import app

mock_app = FastAPI()
setup_security_middleware(mock_app, allowed_origins=["https://app.docusync.ai"])


@mock_app.get("/ping")
def ping():
    return {"message": "pong"}


def test_security_headers_present():
    client = TestClient(mock_app)
    response = client.get("/ping")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-XSS-Protection"] == "1; mode=block"
    assert (
        response.headers["Strict-Transport-Security"]
        == "max-age=31536000; includeSubDomains"
    )
    assert response.headers["Content-Security-Policy"] == "default-src 'self'"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_cors_allowed_origin():
    client = TestClient(mock_app)
    headers = {
        "Origin": "https://app.docusync.ai",
        "Access-Control-Request-Method": "GET",
    }
    response = client.options("/ping", headers=headers)

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://app.docusync.ai"


def test_cors_disallowed_origin():
    client = TestClient(mock_app)
    headers = {
        "Origin": "https://malicious-site.com",
        "Access-Control-Request-Method": "GET",
    }
    response = client.options("/ping", headers=headers)

    # Disallowed origins should not return Access-Control-Allow-Origin header
    assert "access-control-allow-origin" not in response.headers


def test_real_app_does_not_allow_wildcard_cors_for_disallowed_origin():
    client = TestClient(app)
    headers = {
        "Origin": "https://malicious-site.com",
        "Access-Control-Request-Method": "GET",
    }
    response = client.options("/health", headers=headers)

    assert response.status_code == 400
    assert response.headers.get("access-control-allow-origin") != "*"
