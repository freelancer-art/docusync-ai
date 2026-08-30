import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, SQLModel
from sqlmodel.pool import StaticPool
from app.main import app

client = TestClient(app)

@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

def test_upload_document_endpoint_success(session):
    pdf_bytes = b"%PDF-1.4 test invoice content"
    files = {"file": ("invoice.pdf", pdf_bytes, "application/pdf")}
    
    response = client.post("/api/documents/upload", files=files)
    assert response.status_code in [200, 201]
    data = response.json()
    assert "id" in data
    assert data["filename"] == "invoice.pdf"

def test_upload_document_invalid_mime_type():
    fake_payload = b"MZ executable payload"
    files = {"file": ("malware.pdf", fake_payload, "application/pdf")}
    
    response = client.post("/api/documents/upload", files=files)
    assert response.status_code == 400
    assert "Unsupported file signature" in response.json()["detail"]

def test_unauthorized_document_access():
    response = client.get("/api/documents/1")
    assert response.status_code in [401, 403]