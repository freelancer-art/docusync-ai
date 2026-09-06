"""SQLModel entities, engine setup, authentication records, and tenant metadata."""

import os
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import bcrypt
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, Session, SQLModel, create_engine, select

from app.config import settings


def safe_truncate_password(password: str) -> str:
    """Truncates string to maximum 72 bytes safely for Bcrypt."""
    if not password:
        return ""
    if password.startswith(("$2b$", "$2a$")):
        return password
    pwd_bytes = password.encode("utf-8")[:72]
    return pwd_bytes.decode("utf-8", errors="ignore")


class UserRole(str, Enum):
    CA_ADMIN = "CA_ADMIN"
    CLIENT = "CLIENT"


class MCPToolInvocation(SQLModel, table=True):
    __tablename__ = "mcptoolinvocation"
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    actor: str = "anonymous"
    tool_name: str
    arguments_json: str = "{}"
    outcome: str
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MCPConfirmationToken(SQLModel, table=True):
    __tablename__ = "mcpconfirmationtoken"
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    token_hash: str = Field(index=True, unique=True)
    action: str
    requested_by: str = "anonymous"
    expires_at: datetime
    consumed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConnectorBinding(SQLModel, table=True):
    __tablename__ = "connectorbinding"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", "external_account_id"),
        {"extend_existing": True},
    )

    id: int | None = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="user.id", index=True)
    provider: str = Field(index=True)
    external_account_id: str
    credential_ref: str | None = None
    enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ImportedFile(SQLModel, table=True):
    __tablename__ = "importedfile"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", "source_file_id"),
        UniqueConstraint("tenant_id", "provider", "content_hash"),
        {"extend_existing": True},
    )

    id: int | None = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="user.id", index=True)
    provider: str = Field(index=True)
    source_file_id: str
    content_hash: str = Field(index=True)
    original_filename: str
    storage_key: str
    document_id: int | None = Field(default=None, foreign_key="documentrecord.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DocumentRecord(SQLModel, table=True):
    __tablename__ = "documentrecord"
    __table_args__ = {"extend_existing": True}
    __allow_unmapped__ = True

    id: int | None = Field(default=None, primary_key=True)
    filename: str
    document_type: str = "INVOICE"
    extraction_method: str = "AI_VISION"
    overall_status: str = "NEEDS_REVIEW"
    vendor_name: str | None = None
    invoice_number: str | None = None
    total_amount: float | None = 0.0
    amount_paid: float | None = 0.0
    payment_status: str = "UNPAID"
    audit_flags_json: str | None = "[]"
    raw_json_data: str | None = None
    auditor_notes: str | None = None
    client_id: int | None = Field(default=None, foreign_key="user.id")
    created_at: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    owner: Optional["User"] = Relationship(
        back_populates="documents",
        sa_relationship_kwargs={
            "lazy": "joined",
        },
    )

    def __init__(self, **data):
        if data.get("filename"):
            data["filename"] = self.sanitize_filename(data["filename"])
        super().__init__(**data)

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        if not filename:
            return "unnamed_document"
        clean_name = os.path.basename(filename.replace("\\", "/"))
        clean_name = clean_name.replace("..", "").strip()
        return clean_name or "unnamed_document"


class User(SQLModel, table=True):
    __tablename__ = "user"
    __table_args__ = {"extend_existing": True}
    __allow_unmapped__ = True

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    full_name: str
    hashed_password: str
    role: UserRole = Field(default=UserRole.CLIENT)

    documents: list[DocumentRecord] = Relationship(
        back_populates="owner",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "post_update": True,
        },
    )

    def verify_password(self, password: str) -> bool:
        if not self.hashed_password:
            return False
        truncated_pwd = safe_truncate_password(password)
        try:
            return bcrypt.checkpw(
                truncated_pwd.encode("utf-8"), self.hashed_password.encode("utf-8")
            )
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def hash_password(password: str) -> str:
        if not password:
            return ""
        if password.startswith(("$2b$", "$2a$")):
            return password
        truncated_pwd = safe_truncate_password(password)
        return bcrypt.hashpw(truncated_pwd.encode("utf-8"), bcrypt.gensalt()).decode(
            "utf-8"
        )


DATABASE_URL = settings.SQLALCHEMY_DATABASE_URI

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False,
)


def get_session():
    with Session(engine) as session:
        yield session


def init_db():
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        existing_user = session.exec(select(User)).first()
        if not existing_user:
            default_username = settings.INITIAL_CA_USERNAME
            default_password = settings.INITIAL_CA_PASSWORD
            if not default_username or not default_password:
                if not settings.DEBUG:
                    return
                default_username = settings.DEBUG_DEFAULT_CA_USERNAME
                default_password = settings.DEBUG_DEFAULT_CA_PASSWORD

            initial_admin = User(
                username=default_username,
                full_name=settings.INITIAL_CA_FULL_NAME,
                hashed_password=User.hash_password(default_password),
                role=UserRole.CA_ADMIN,
            )
            session.add(initial_admin)
            session.commit()
