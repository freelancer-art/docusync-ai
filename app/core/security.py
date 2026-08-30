from typing import Tuple

# Standard magic byte signatures
ALLOWED_MAGIC_SIGNATURES = {
    "pdf": b"%PDF",
    "png": b"\x89PNG\r\n\x1a\n",
    "jpeg": b"\xff\xd8\xff",
}

class InvalidFileTypeError(ValueError):
    pass

ALLOWED_MAGIC_SIGNATURES = {
    "pdf": b"%PDF",
    "png": b"\x89PNG\r\n\x1a\n",
    "jpeg": b"\xff\xd8\xff",
}

def validate_file_signature(content: bytes) -> str:
    """Validate raw bytes against allowed magic byte signatures."""
    if not content:
        raise InvalidFileTypeError("Uploaded file is empty.")

    if content.startswith(ALLOWED_MAGIC_SIGNATURES["pdf"]):
        return "pdf"
    elif content.startswith(ALLOWED_MAGIC_SIGNATURES["png"]):
        return "png"
    elif content.startswith(ALLOWED_MAGIC_SIGNATURES["jpeg"]):
        return "jpeg"
    
    raise InvalidFileTypeError("Unsupported file signature. Only PDF, PNG, and JPEG files are allowed.")