import os
from sqlmodel import SQLModel, Field, create_engine, Session
from typing import Optional
from datetime import datetime

DATABASE_DIR = "storage"
os.makedirs(DATABASE_DIR, exist_ok=True)
DATABASE_URL = f"sqlite:///{DATABASE_DIR}/docusync.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

class DocumentRecord(SQLModel, table=True):
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
    created_at: datetime = Field(default_factory=datetime.utcnow)

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session