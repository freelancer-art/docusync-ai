from fastapi import FastAPI
from app.config import settings
from app.api.v1.extraction import router as extraction_router
from app.api.documents import router as documents_router

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

# Existing Routers
app.include_router(extraction_router, prefix="/api/v1", tags=["Extraction Engine"])

# New Security & Document Handling Router
app.include_router(documents_router)

@app.get("/")
def read_root():
    return {"status": "online", "app": settings.APP_NAME}