from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.input_validation import PayloadSizeLimitMiddleware

mock_app = FastAPI()
mock_app.add_middleware(PayloadSizeLimitMiddleware)


@mock_app.post("/test-size")
def payload_endpoint():
    return {"status": "ok"}


def test_payload_within_limit_succeeds():
    client = TestClient(mock_app)
    response = client.post("/test-size", json={"key": "value"})
    assert response.status_code == 200


def test_payload_exceeding_limit_rejected():
    client = TestClient(mock_app)
    # Simulate oversized Content-Length header
    headers = {"Content-Length": str(15 * 1024 * 1024)}
    response = client.post("/test-size", headers=headers, json={"key": "value"})

    assert response.status_code == 413
    assert "exceeds maximum allowed limit" in response.json()["detail"]
