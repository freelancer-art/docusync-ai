from fastapi import FastAPI
from app.config import settings
from app.api.v1.extraction import router as extraction_router

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

app.include_router(extraction_router, prefix="/api/v1", tags=["Extraction Engine"])

@app.get("/")
def read_root():
    return {"status": "online", "app": settings.APP_NAME}