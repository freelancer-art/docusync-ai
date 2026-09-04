import json

from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app import mcp_server
from app.core.database import DocumentRecord


def test_mcp_tools_return_document_metrics(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(mcp_server, "engine", engine)

    with Session(engine) as session:
        session.add_all(
            [
                DocumentRecord(
                    filename="verified.pdf",
                    vendor_name="Verified Vendor",
                    invoice_number="INV-MCP-1",
                    total_amount=100.0,
                    overall_status="VERIFIED",
                    payment_status="UNPAID",
                    raw_json_data='{"total_amount": 100.0}',
                    audit_flags_json="[]",
                ),
                DocumentRecord(
                    filename="flagged.pdf",
                    vendor_name="Flagged Vendor",
                    total_amount=250.0,
                    overall_status="NEEDS_REVIEW",
                    payment_status="PAID",
                    raw_json_data="{bad json",
                    audit_flags_json="{bad json",
                ),
            ]
        )
        session.commit()

    summary = json.loads(mcp_server.get_financial_summary())
    assert summary["total_documents"] == 2
    assert summary["total_value_inr"] == 350.0
    assert summary["flagged_for_review_count"] == 1
    assert summary["outstanding_unpaid_amount"] == 100.0

    flagged = json.loads(mcp_server.list_flagged_documents())
    assert flagged[0]["vendor_name"] == "Flagged Vendor"
    assert flagged[0]["audit_flags"] == []

    doc = json.loads(mcp_server.get_document_by_id(1))
    assert doc["filename"] == "verified.pdf"
    assert doc["extracted_fields"] == {"total_amount": 100.0}

    assert "not found" in mcp_server.get_document_by_id(999)
