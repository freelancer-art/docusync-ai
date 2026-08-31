import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.api.documents import get_session, get_current_user
from app.core.database import User, UserRole, DocumentRecord

# Set up clean in-memory SQLite database for test isolation
engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)

@pytest.fixture(name="session")
def session_fixture():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)

@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_upload_document_creates_db_record(client: TestClient, session: Session):
    # Setup test user
    user = User(username="test_client", full_name="Test Client", hashed_password="pw", role=UserRole.CLIENT)
    session.add(user)
    session.commit()
    session.refresh(user)

    app.dependency_overrides[get_current_user] = lambda: user

    pdf_bytes = b"%PDF-1.4 test invoice content"
    files = {"file": ("../../malicious_invoice.pdf", pdf_bytes, "application/pdf")}

    response = client.post("/api/documents/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    
    # Path traversal should be stripped
    assert data["filename"] == "malicious_invoice.pdf"
    
    # Verify DB record creation
    db_doc = session.get(DocumentRecord, data["id"])
    assert db_doc is not None
    assert db_doc.client_id == user.id


def test_multitenant_access_control(client: TestClient, session: Session):
    user1 = User(id=1, username="user1", full_name="User 1", hashed_password="pw", role=UserRole.CLIENT)
    user2 = User(id=2, username="user2", full_name="User 2", hashed_password="pw", role=UserRole.CLIENT)
    session.add_all([user1, user2])
    session.commit()

    doc = DocumentRecord(
        filename="user1_doc.pdf",
        document_type="INVOICE",
        extraction_method="AI_VISION",
        overall_status="PENDING",
        client_id=user1.id,
        raw_json_data="{}",
        audit_flags_json="{}",
    )
    session.add(doc)
    session.commit()

    # User 2 attempting to view User 1's document should receive 403 Forbidden
    app.dependency_overrides[get_current_user] = lambda: user2
    response = client.get(f"/api/documents/{doc.id}")
    assert response.status_code == 403