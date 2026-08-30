import os
import bcrypt
from enum import Enum
from datetime import datetime, timezone
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship, create_engine, Session
from pydantic import field_validator, ConfigDict

DATABASE_DIR = "storage"
os.makedirs(DATABASE_DIR, exist_ok=True)
DATABASE_URL = f"sqlite:///{DATABASE_DIR}/docusync.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

class UserRole(str, Enum):
    CA_ADMIN = "CA_ADMIN"
    CLIENT = "CLIENT"

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    full_name: str
    hashed_password: str
    role: UserRole = Field(default=UserRole.CLIENT)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    documents: List["DocumentRecord"] = Relationship(back_populates="owner")

    @staticmethod
    def hash_password(password: str) -> str:
        pwd_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

    def verify_password(self, password: str) -> bool:
        pwd_bytes = password.encode('utf-8')
        hashed_bytes = self.hashed_password.encode('utf-8')
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)

class DocumentRecord(SQLModel, table=True):
    # Enable Pydantic validation upon class instantiation and assignment
    model_config = ConfigDict(validate_assignment=True, revalidate_instances="always")

    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    document_type: str
    extraction_method: str
    overall_status: str  # VERIFIED, NEEDS_REVIEW, REJECTED
    vendor_name: Optional[str] = None
    invoice_number: Optional[str] = None
    total_amount: Optional[float] = None
    raw_json_data: str  # Serialized JSON string
    audit_flags_json: str  # Serialized JSON flags
    auditor_notes: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("filename", mode="before")
    @classmethod
    def sanitize_filename(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            return v
        # Normalize Windows backslashes to forward slashes first
        clean = v.replace("\\", "/")
        # Extract only the base filename to strip path traversal sequences
        return os.path.basename(clean)

    # Multi-tenancy link
    client_id: Optional[int] = Field(default=None, foreign_key="user.id")
    owner: Optional[User] = Relationship(back_populates="documents")

def init_db():
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        from sqlmodel import select
        existing_users = session.exec(select(User)).all()
        if not existing_users:
            ca_user = User(
                username="ca_admin",
                full_name="Mehta & Co. CAs",
                hashed_password=User.hash_password("admin123"),
                role=UserRole.CA_ADMIN
            )
            client_user1 = User(
                username="acme_corp",
                full_name="Acme Trading Ltd.",
                hashed_password=User.hash_password("client123"),
                role=UserRole.CLIENT
            )
            client_user2 = User(
                username="apex_tech",
                full_name="Apex Solutions",
                hashed_password=User.hash_password("client123"),
                role=UserRole.CLIENT
            )
            session.add(ca_user)
            session.add(client_user1)
            session.add(client_user2)
            session.commit()