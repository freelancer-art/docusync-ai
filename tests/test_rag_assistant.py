import json
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.database import DocumentRecord, User, UserRole
from app.services.rag_sql import build_safe_ledger_query


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


def test_rag_sql_rejects_unsafe_statements():
    unsafe_statements = [
        "DELETE FROM documentrecord",
        "SELECT * FROM documentrecord; DROP TABLE user",
        "SELECT * FROM documentrecord -- bypass",
        "PRAGMA table_info(documentrecord)",
        "SELECT * FROM documentrecord JOIN user ON user.id = documentrecord.client_id",
    ]

    for sql in unsafe_statements:
        with pytest.raises(ValueError):
            build_safe_ledger_query(sql, is_admin=True, client_id=None)


def test_rag_sql_scopes_client_queries_with_bound_parameter():
    sql, params = build_safe_ledger_query(
        "SELECT id, client_id, total_amount FROM documentrecord WHERE overall_status = 'VERIFIED'",
        is_admin=False,
        client_id=42,
    )

    assert "client_id = :tenant_client_id" in sql
    assert "overall_status = 'VERIFIED'" in sql
    assert params == {"tenant_client_id": 42}


def test_rag_sql_preserves_admin_query_without_params():
    sql, params = build_safe_ledger_query(
        "SELECT COUNT(*) AS total_documents FROM documentrecord",
        is_admin=True,
        client_id=None,
    )

    assert sql == "SELECT COUNT(*) AS total_documents FROM documentrecord"
    assert params == {}
