from fastapi.testclient import TestClient

from app.main import app


def test_readiness_reports_redis_failure(monkeypatch):
    class FailingRedis:
        def ping(self):
            raise OSError("redis unavailable")

    monkeypatch.setattr("app.main.redis.Redis.from_url", lambda *args, **kwargs: FailingRedis())
    client = TestClient(app)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["checks"]["database"] == "healthy"
    assert "redis unavailable" in response.json()["checks"]["redis"]


def test_readiness_reports_all_healthy(monkeypatch):
    class HealthyRedis:
        def ping(self):
            return True

    monkeypatch.setattr("app.main.redis.Redis.from_url", lambda *args, **kwargs: HealthyRedis())
    client = TestClient(app)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["checks"] == {"database": "healthy", "redis": "healthy"}
