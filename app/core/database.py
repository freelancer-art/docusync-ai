import os
from datetime import datetime
from enum import Enum
from typing import List, Optional
from passlib.context import CryptContext
from sqlmodel import Field, Relationship, Session, SQLModel, create_engine, select

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def safe_truncate_password(password: str) -> str:
    """Truncates string to maximum 72 bytes safely for Bcrypt."""
    if not password:
        return ""
    if password.startswith("$2b$") or password.startswith("$2a$"):
        return password
    pwd_bytes = password.encode("utf-8")[:72]
    return pwd_bytes.decode("utf-8", errors="ignore")


class UserRole(str, Enum):
    CA_ADMIN = "CA_ADMIN"
    CLIENT = "CLIENT"


class DocumentRecord(SQLModel, table=True):
    __tablename__ = "documentrecord"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    document_type: str = "INVOICE"
    extraction_method: str = "AI_VISION"
    overall_status: str = "NEEDS_REVIEW"
    vendor_name: Optional[str] = None
    invoice_number: Optional[str] = None
    total_amount: Optional[float] = 0.0
    amount_paid: Optional[float] = 0.0
    payment_status: str = "UNPAID"
    audit_flags_json: Optional[str] = "[]"
    raw_json_data: Optional[str] = None
    auditor_notes: Optional[str] = None
    client_id: Optional[int] = Field(default=None, foreign_key="user.id")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    owner: Optional["User"] = Relationship(
        back_populates="documents",
    )

    def __init__(self, **data):
        if "filename" in data and data["filename"]:
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

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    full_name: str
    hashed_password: str
    role: UserRole = Field(default=UserRole.CLIENT)

    documents: List[DocumentRecord] = Relationship(
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
            return pwd_context.verify(truncated_pwd, self.hashed_password)
        except Exception:
            return False

    @staticmethod
    def hash_password(password: str) -> str:
        if not password:
            return ""
        if password.startswith("$2b$") or password.startswith("$2a$"):
            return password
        truncated_pwd = safe_truncate_password(password)
        return pwd_context.hash(truncated_pwd)


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./docusync.db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

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
            default_username = os.getenv("INITIAL_CA_USERNAME", "ca_admin")
            default_password = os.getenv("INITIAL_CA_PASSWORD", "Admin@123456")

            initial_admin = User(
                username=default_username,
                full_name="Default CA Administrator",
                hashed_password=User.hash_password(default_password),
                role=UserRole.CA_ADMIN,
            )
            session.add(initial_admin)
            session.commit()