import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.logging import (
    CorrelationIDMiddleware,
    StructuredLogFormatter,
    get_correlation_id,
)

mock_app = FastAPI()
mock_app.add_middleware(CorrelationIDMiddleware)


@mock_app.get("/test-log")
def log_endpoint():
    return {"correlation_id": get_correlation_id()}


def test_correlation_id_generated_if_missing():
    client = TestClient(mock_app)
    response = client.get("/test-log")

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert response.json()["correlation_id"] == response.headers["X-Request-ID"]


def test_correlation_id_propagated_if_provided():
    client = TestClient(mock_app)
    custom_id = "custom-req-id-12345"
    response = client.get("/test-log", headers={"X-Request-ID": custom_id})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == custom_id
    assert response.json()["correlation_id"] == custom_id


def test_structured_log_formatter():
    formatter = StructuredLogFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test log message",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)

    assert "'message': 'Test log message'" in formatted
    assert "'level': 'INFO'" in formatted
    assert "'correlation_id':" in formatted
