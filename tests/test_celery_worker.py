import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.database import DocumentRecord
from app.worker import process_document_task

TEST_DB_URL = "sqlite:///file:celery_test?mode=memory&cache=shared&uri=true"


@pytest.fixture(name="test_db_engine")
def test_db_engine_fixture():
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


def test_process_document_task_missing_doc(test_db_engine):
    """Task should skip processing gracefully if the document ID does not exist."""
    result = process_document_task.apply(args=(999, TEST_DB_URL)).get()

    assert result["status"] == "SKIPPED"
    assert "not found" in result["reason"]


def test_process_document_task_missing_file(test_db_engine):
    """Task should mark status as FAILED if the file does not exist on disk."""
    with Session(test_db_engine) as session:
        doc = DocumentRecord(
            filename="non_existent_file.pdf",
            document_type="TAX_INVOICE",
            extraction_method="AUTO_PARSER",
            overall_status="PENDING",
            client_id=1,
            audit_flags_json="[]",
        )
        session.add(doc)
        session.commit()
        session.refresh(doc)
        doc_id = doc.id

    result = process_document_task.apply(args=(doc_id, TEST_DB_URL)).get()

    assert result["status"] == "FAILED"
    assert result["reason"] == "File not found on disk"

    with Session(test_db_engine) as session:
        updated_doc = session.get(DocumentRecord, doc_id)
        assert updated_doc.overall_status == "FAILED"


def test_process_document_task_successful_execution(
    tmp_path, test_db_engine, monkeypatch
):
    """Task should parse valid files, update metadata, and run audit evaluation."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    sample_file = upload_dir / "sample_invoice.pdf"
    sample_file.write_text(
        "Dummy Invoice Content: Tax Invoice #12345 from Vendor Corp. Total: 500"
    )

    monkeypatch.setattr("app.worker.UPLOAD_DIR", str(upload_dir))

    with Session(test_db_engine) as session:
        doc = DocumentRecord(
            filename="sample_invoice.pdf",
            document_type="TAX_INVOICE",
            extraction_method="AUTO_PARSER",
            overall_status="PENDING",
            client_id=1,
            audit_flags_json="[]",
        )
        session.add(doc)
        session.commit()
        session.refresh(doc)
        doc_id = doc.id

    result = process_document_task.apply(args=(doc_id, TEST_DB_URL)).get()

    assert result["status"] in ["VERIFIED", "NEEDS_REVIEW"]
    assert result["doc_id"] == doc_id

    with Session(test_db_engine) as session:
        updated_doc = session.get(DocumentRecord, doc_id)
        assert updated_doc.raw_json_data is not None
        assert updated_doc.overall_status in ["VERIFIED", "NEEDS_REVIEW"]
