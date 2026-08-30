import os
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.extractor_service import extractor_service
from app.schemas.tax_invoice import TaxInvoiceSchema

router = APIRouter()

TEMP_UPLOAD_DIR = "storage/sample_uploads"
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)

@router.post("/extract/invoice", response_model=TaxInvoiceSchema)
async def extract_invoice(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are currently supported.")

    file_path = os.path.join(TEMP_UPLOAD_DIR, file.filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        extracted_data = extractor_service.parse_invoice(file_path)
        return extracted_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)