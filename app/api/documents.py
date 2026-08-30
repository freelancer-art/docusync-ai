# Change "Status" to "status"
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends
from app.core.security import validate_file_signature, InvalidFileTypeError

router = APIRouter(prefix="/api/documents", tags=["documents"])

@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    content = await file.read()
    try:
        validate_file_signature(content)
    except InvalidFileTypeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=str(e)
        )
    
    return {"id": 1, "filename": file.filename, "status": "UPLOADED"}

@router.get("/{doc_id}")
async def get_document(doc_id: int):
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, 
        detail="Not authenticated"
    )