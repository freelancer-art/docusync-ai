from fastapi import Depends, FastAPI, status
from fastapi.testclient import TestClient

from app.core.rate_limiter import rate_limiter

# Isolated app instance for testing limit enforcement
rate_limit_app = FastAPI()


@rate_limit_app.get(
    "/test-limit",
    dependencies=[Depends(rate_limiter(requests_limit=3, window_seconds=60))],
)
def limited_endpoint():
    return {"message": "success"}


def test_rate_limiter_enforcement():
    client = TestClient(rate_limit_app)

    # First 3 requests must succeed
    for _ in range(3):
        res = client.get("/test-limit")
        assert res.status_code == status.HTTP_200_OK

    # 4th request must be rate limited
    blocked_res = client.get("/test-limit")
    assert blocked_res.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert blocked_res.json()["detail"] == "Rate limit exceeded. Please retry later."
    assert "Retry-After" in blocked_res.headers