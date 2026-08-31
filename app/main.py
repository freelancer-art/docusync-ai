from fastapi import FastAPI
from app.config import settings
from app.api.v1.extraction import router as extraction_router
from app.api.documents import router as documents_router
from app.api.auth import router as auth_router
from app.api.client_portal import router as portal_router
from app.api.payments import router as payments_router

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

# Existing Routers
app.include_router(extraction_router, prefix="/api/v1", tags=["Extraction Engine"])

# New Security & Document Handling Router
app.include_router(documents_router)
# Authentication Router for User Management
app.include_router(auth_router)
# Portal Router for Client Access
app.include_router(portal_router)
# Payments Router for Payment Processing
app.include_router(payments_router)

@app.get("/")
def read_root():
    return {"status": "online", "app": settings.APP_NAME}