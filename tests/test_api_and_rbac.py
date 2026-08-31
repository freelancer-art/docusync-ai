import pytest
from httpx import AsyncClient
from sqlmodel import Session, select

from app.core.database import DocumentRecord, User


@pytest.mark.asyncio
async def test_health_check(async_client: AsyncClient):
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_tenant_isolation_rules(db_session: Session, seed_users: dict[str, User]):
    client_a = seed_users["client_a"]
    client_b = seed_users["client_b"]

    doc_a = DocumentRecord(
        filename="invoice_a.pdf",
        document_type="INVOICE",
        extraction_method="AI_VISION",
        overall_status="VERIFIED",
        client_id=client_a.id,
    )
    doc_b = DocumentRecord(
        filename="invoice_b.pdf",
        document_type="INVOICE",
        extraction_method="AI_VISION",
        overall_status="NEEDS_REVIEW",
        client_id=client_b.id,
    )

    db_session.add(doc_a)
    db_session.add(doc_b)
    db_session.commit()

    # Query scoped strictly to Client A
    records_a = db_session.exec(
        select(DocumentRecord).where(DocumentRecord.client_id == client_a.id)
    ).all()

    assert len(records_a) == 1
    assert records_a[0].filename == "invoice_a.pdf"

    # Query scoped strictly to Client B
    records_b = db_session.exec(
        select(DocumentRecord).where(DocumentRecord.client_id == client_b.id)
    ).all()

    assert len(records_b) == 1
    assert records_b[0].filename == "invoice_b.pdf"


def test_filename_sanitization():
    dirty_name = "../../../etc/passwd"
    clean_name = DocumentRecord.sanitize_filename(dirty_name)
    assert clean_name == "passwd"