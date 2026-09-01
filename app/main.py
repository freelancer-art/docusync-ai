from contextlib import asynccontextmanager
import redis
from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlmodel import Session, select

from app.api.auth import router as auth_router
from app.api.client_portal import router as portal_router
from app.api.documents import router as documents_router
from app.api.payments import router as payments_router
from app.api.v1.extraction import router as extraction_router
from app.config import settings
from app.core.database import engine, init_db
from app.core.input_validation import PayloadSizeLimitMiddleware
from app.core.logging import CorrelationIDMiddleware
from app.core.middleware import setup_security_middleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables and seed initial users on boot
    try:
        init_db()
    except Exception as e:
        print(f"Warning: init_db failed on startup: {e}")
    yield

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG, lifespan=lifespan)

# Allow CORS for Streamlit Cloud and local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Middleware (Payload size limit registered early)
app.add_middleware(PayloadSizeLimitMiddleware)
app.add_middleware(CorrelationIDMiddleware)

allowed_origins = getattr(settings, "ALLOWED_ORIGINS", ["https://app.docusync.ai"])
setup_security_middleware(app, allowed_origins=allowed_origins)

# Routers
app.include_router(extraction_router, prefix="/api/v1", tags=["Extraction Engine"])
app.include_router(documents_router)
app.include_router(auth_router)
app.include_router(portal_router)
app.include_router(payments_router)


@app.get("/")
def read_root():
    return {"status": "online", "app": settings.APP_NAME}


@app.get("/healthz", status_code=status.HTTP_200_OK)
def liveness_probe():
    """Basic liveness probe confirming API service is running."""
    return {"status": "alive"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}
    
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
        redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
        r = redis.Redis.from_url(redis_url, socket_timeout=2)
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

    return {"status": "ready" if is_ready else "not_ready", "checks": checks}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)