from typing import Tuple
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from fastapi.security import OAuth2PasswordBearer
import jwt

from fastapi import Depends, HTTPException, status
from sqlmodel import Session, select
from app.core.database import get_session, User

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

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "docusync-dev-secret-key-change-in-prod-32bytes")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 hours

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.PyJWTError:
        raise ValueError("Could not validate credentials")

def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except ValueError:
        raise credentials_exception

    user = session.exec(select(User).where(User.username == username)).first()
    if user is None:
        raise credentials_exception
    return user