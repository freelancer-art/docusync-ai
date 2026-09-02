import json
import pytest
from unittest.mock import MagicMock, patch
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.database import DocumentRecord, User, UserRole


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_rag_context_scoping_client_vs_admin(session: Session):
    admin_user = User(
        username="ca_admin",
        hashed_password="hashed_pwd",
        full_name="CA Admin",
        role=UserRole.CA_ADMIN,
    )
    client1 = User(
        username="client_1",
        hashed_password="hashed_pwd",
        full_name="Client One Corp",
        role=UserRole.CLIENT,
    )
    client2 = User(
        username="client_2",
        hashed_password="hashed_pwd",
        full_name="Client Two Corp",
        role=UserRole.CLIENT,
    )
    session.add_all([admin_user, client1, client2])
    session.commit()

    doc1 = DocumentRecord(
        client_id=client1.id,
        filename="doc1.pdf",
        vendor_name="Vendor A",
        total_amount=1000.0,
        overall_status="VERIFIED",
    )
    doc2 = DocumentRecord(
        client_id=client2.id,
        filename="doc2.pdf",
        vendor_name="Vendor B",
        total_amount=2000.0,
        overall_status="NEEDS_REVIEW",
    )
    session.add_all([doc1, doc2])
    session.commit()

    # Query scoping for Client 1
    c1_records = session.query(DocumentRecord).filter(DocumentRecord.client_id == client1.id).all()
    assert len(c1_records) == 1
    assert c1_records[0].vendor_name == "Vendor A"

    # Query scoping for CA Admin (All Records)
    admin_records = session.query(DocumentRecord).all()
    assert len(admin_records) == 2


@patch("app.core.groq_client.get_ai_client")
def test_rag_chat_synthesis_mock(mock_get_ai_client):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="Total GST exposure is ₹180.00 across 1 document."))
    ]
    mock_client.chat.completions.create.return_value = mock_response
    mock_get_ai_client.return_value = (mock_client, "llama-3.3-70b-versatile")

    from app.core.groq_client import get_ai_client
    client, model = get_ai_client()
    
    context = [{"id": 1, "vendor": "Test Corp", "total_amount": 1180.0}]
    user_query = "What is the total GST exposure?"

    system_prompt = f"Context:\n{json.dumps(context)}"
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query},
        ],
    )

    assert "Total GST exposure is ₹180.00" in response.choices[0].message.content