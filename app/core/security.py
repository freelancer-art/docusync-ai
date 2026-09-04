import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

from app.config import Settings, settings
from app.core.database import User, get_session

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

    raise InvalidFileTypeError(
        "Unsupported file signature. Only PDF, PNG, and JPEG files are allowed."
    )


DEV_SECRET_KEY = "docusync-dev-secret-key-change-in-prod-32bytes"


def resolve_secret_key(settings_obj: Settings = settings) -> str:
    secret_key = os.getenv("JWT_SECRET_KEY") or settings_obj.SECRET_KEY
    if secret_key:
        return secret_key
    if settings_obj.DEBUG:
        return DEV_SECRET_KEY
    raise RuntimeError("SECRET_KEY or JWT_SECRET_KEY must be set when DEBUG is false.")


SECRET_KEY = resolve_secret_key()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 hours

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.PyJWTError:
        raise ValueError("Could not validate credentials")


def get_current_user(
    token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)
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
