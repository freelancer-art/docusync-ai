"""FastAPI application entrypoint, lifecycle hooks, middleware, and health probes."""

import logging
from contextlib import asynccontextmanager

import redis
from fastapi import FastAPI, Response, status
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlmodel import Session, select

from app.api.auth import router as auth_router
from app.api.client_portal import router as portal_router
from app.api.documents import router as documents_router
from app.api.endpoints.users import router as users_router
from app.api.payments import router as payments_router
from app.api.v1.extraction import router as extraction_router
from app.config import settings
from app.core.database import engine, init_db
from app.core.input_validation import PayloadSizeLimitMiddleware
from app.core.logging import CorrelationIDMiddleware, configure_logging
from app.core.middleware import setup_security_middleware
from app.core.observability import MetricsMiddleware, metrics, send_alert

configure_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize application resources before serving requests."""
    # Initialize database tables and seed initial users on boot
    try:
        init_db()
    except Exception:
        logger.exception("Database initialization failed on startup")
    yield


app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG, lifespan=lifespan)

# Register Middleware (Payload size limit registered early)
app.add_middleware(PayloadSizeLimitMiddleware)
app.add_middleware(CorrelationIDMiddleware)
if settings.METRICS_ENABLED:
    app.add_middleware(MetricsMiddleware)

allowed_origins = getattr(settings, "ALLOWED_ORIGINS", ["https://app.docusync.ai"])
setup_security_middleware(app, allowed_origins=allowed_origins)

# Routers
app.include_router(extraction_router, prefix="/api/v1", tags=["Extraction Engine"])
app.include_router(documents_router)
app.include_router(auth_router)
app.include_router(portal_router)
app.include_router(payments_router)
app.include_router(users_router)


@app.get("/")
def read_root():
    """Return a minimal service identity response."""
    return {"status": "online", "app": settings.APP_NAME}


@app.get("/healthz", status_code=status.HTTP_200_OK)
def liveness_probe():
    """Basic liveness probe confirming API service is running."""
    return {"status": "alive"}


@app.get("/health")
async def health_check():
    """Return a lightweight health response without dependency checks."""
    return {"status": "ok"}


@app.get("/metrics", include_in_schema=False)
def metrics_endpoint():
    """Expose request counters in Prometheus text format when metrics are enabled."""
    if not settings.METRICS_ENABLED:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    return Response(
        content=metrics.prometheus(), media_type="text/plain; version=0.0.4"
    )


@app.get("/ready")
def readiness_probe(response: Response):
    """Readiness probe verifying DB pool & Redis worker broker connectivity."""
    checks = {"database": "unknown", "redis": "unknown"}
    is_ready = True

    # 1. Database Connectivity Check
    try:
        with Session(engine) as session:
            session.exec(select(1)).first()
            checks["database"] = "healthy"
    except (OperationalError, SQLAlchemyError) as e:
        checks["database"] = f"unhealthy: {e!s}"
        is_ready = False

    # 2. Redis Broker Connectivity Check
    try:
        r = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=2)
        if r.ping():
            checks["redis"] = "healthy"
        else:
            checks["redis"] = "unhealthy"
            is_ready = False
    except (redis.RedisError, ConnectionError, OSError) as e:
        checks["redis"] = f"unhealthy: {e!s}"
        is_ready = False

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        send_alert(f"DocuSync readiness failure: {checks}")

    return {"status": "ready" if is_ready else "not_ready", "checks": checks}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app", host=settings.API_HOST, port=settings.API_PORT, reload=True
    )
