import os
from datetime import datetime, timezone
from enum import Enum

import bcrypt
from pydantic import ConfigDict, field_validator
from sqlalchemy import Index
from sqlmodel import Field, Relationship, Session, SQLModel, create_engine, select

from app.config import settings

DATABASE_DIR = "storage"
os.makedirs(DATABASE_DIR, exist_ok=True)

# Determine driver arguments dynamically based on database type
is_sqlite = settings.SQLALCHEMY_DATABASE_URI.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    connect_args=connect_args,
    echo=False,
)


class UserRole(str, Enum):
    CA_ADMIN = "CA_ADMIN"
    CLIENT = "CLIENT"


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    full_name: str
    hashed_password: str
    role: UserRole = Field(default=UserRole.CLIENT)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    documents: list["DocumentRecord"] = Relationship(back_populates="owner")

    @staticmethod
    def hash_password(password: str) -> str:
        pwd_bytes = password.encode("utf-8")
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

    def verify_password(self, password: str) -> bool:
        pwd_bytes = password.encode("utf-8")
        hashed_bytes = self.hashed_password.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)


class DocumentRecord(SQLModel, table=True):
    __table_args__ = (
        Index("ix_doc_client_status", "client_id", "overall_status"),
        Index("ix_doc_created_at", "created_at"),
    )

    model_config = ConfigDict(validate_assignment=True, revalidate_instances="always")

    id: int | None = Field(default=None, primary_key=True)
    filename: str
    document_type: str
    extraction_method: str
    overall_status: str  # VERIFIED, NEEDS_REVIEW, REJECTED
    vendor_name: str | None = None
    invoice_number: str | None = None
    total_amount: float | None = None
    raw_json_data: str = Field(default="{}")
    audit_flags_json: str = Field(default="[]")
    auditor_notes: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Payment Reconciliation Fields
    payment_status: str = Field(default="UNPAID")
    amount_paid: float = Field(default=0.0)
    due_date: str | None = None

    # Multi-tenancy link
    client_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    owner: User | None = Relationship(back_populates="documents")

    @field_validator("filename", mode="before")
    @classmethod
    def sanitize_filename(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            return v
        clean = v.replace("\\", "/")
        return os.path.basename(clean)


def get_session():
    with Session(engine) as session:
        yield session


def init_db():
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        existing_users = session.exec(select(User)).all()
        if not existing_users:
            ca_user = User(
                username="ca_admin",
                full_name="Mehta & Co. CAs",
                hashed_password=User.hash_password("admin123"),
                role=UserRole.CA_ADMIN,
            )
            client_user1 = User(
                username="acme_corp",
                full_name="Acme Trading Ltd.",
                hashed_password=User.hash_password("client123"),
                role=UserRole.CLIENT,
            )
            client_user2 = User(
                username="apex_tech",
                full_name="Apex Solutions",
                hashed_password=User.hash_password("client123"),
                role=UserRole.CLIENT,
            )
            session.add(ca_user)
            session.add(client_user1)
            session.add(client_user2)
            session.commit()