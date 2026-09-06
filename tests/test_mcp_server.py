import json
from datetime import UTC, datetime

from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app import mcp_server
from app.core.database import DocumentRecord, MCPToolInvocation


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
                    amount_paid=0.0,
                    overall_status="VERIFIED",
                    payment_status="UNPAID",
                    created_at=datetime(2026, 4, 1, tzinfo=UTC),
                    raw_json_data='{"total_amount": 100.0, "cgst_amount": 9.0, "sgst_amount": 9.0}',
                    audit_flags_json="[]",
                ),
                DocumentRecord(
                    filename="flagged.pdf",
                    vendor_name="Flagged Vendor",
                    invoice_number="INV-MCP-2",
                    total_amount=250.0,
                    amount_paid=250.0,
                    overall_status="NEEDS_REVIEW",
                    payment_status="PAID",
                    created_at=datetime(2026, 5, 1, tzinfo=UTC),
                    raw_json_data="{bad json",
                    audit_flags_json='[{"code": "MISSING_VENDOR_GSTIN", "severity": "WARNING"}]',
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
    assert flagged[0]["audit_flags"] == [
        {"code": "MISSING_VENDOR_GSTIN", "severity": "WARNING"}
    ]

    doc = json.loads(mcp_server.get_document_by_id(1))
    assert doc["filename"] == "verified.pdf"
    assert doc["extracted_fields"] == {
        "total_amount": 100.0,
        "cgst_amount": 9.0,
        "sgst_amount": 9.0,
    }

    assert "not found" in mcp_server.get_document_by_id(999)


def test_mcp_agent_tools_search_summarize_and_export(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(mcp_server, "engine", engine)

    with Session(engine) as session:
        session.add_all(
            [
                DocumentRecord(
                    client_id=1,
                    filename="alpha-1.pdf",
                    vendor_name="Alpha Traders",
                    invoice_number="INV-1",
                    total_amount=1180.0,
                    amount_paid=0.0,
                    overall_status="VERIFIED",
                    payment_status="UNPAID",
                    created_at=datetime(2026, 4, 10, tzinfo=UTC),
                    raw_json_data=json.dumps(
                        {
                            "vendor_gstin": "27AAACT2727Q1ZW",
                            "cgst_amount": 90.0,
                            "sgst_amount": 90.0,
                            "igst_amount": 0.0,
                        }
                    ),
                    audit_flags_json="[]",
                ),
                DocumentRecord(
                    client_id=1,
                    filename="alpha-dup.pdf",
                    vendor_name="Alpha Traders",
                    invoice_number="INV-1",
                    total_amount=1180.0,
                    amount_paid=100.0,
                    overall_status="REJECTED",
                    payment_status="PARTIAL",
                    created_at=datetime(2026, 4, 11, tzinfo=UTC),
                    raw_json_data=json.dumps({"igst_amount": 180.0}),
                    audit_flags_json=json.dumps(
                        [
                            {
                                "code": "DUPLICATE_INVOICE",
                                "severity": "CRITICAL",
                                "message": "Duplicate invoice found.",
                            }
                        ]
                    ),
                ),
                DocumentRecord(
                    client_id=2,
                    filename="beta.pdf",
                    vendor_name="Beta Supplies",
                    invoice_number="INV-2",
                    total_amount=500.0,
                    overall_status="VERIFIED",
                    payment_status="PAID",
                    created_at=datetime(2026, 6, 1, tzinfo=UTC),
                    raw_json_data=json.dumps({"igst_amount": 50.0}),
                ),
            ]
        )
        session.commit()

    search_results = json.loads(
        mcp_server.search_documents(
            client_id=1,
            vendor_name="Alpha",
            start_date="2026-04-01",
            end_date="2026-04-30",
        )
    )
    assert [doc["client_id"] for doc in search_results] == [1, 1]
    assert search_results[0]["filename"] == "alpha-dup.pdf"

    summary = json.loads(
        mcp_server.summarize_client_tax_position(
            client_id=1,
            start_date="2026-04-01",
            end_date="2026-04-30",
        )
    )
    assert summary["document_count"] == 2
    assert summary["total_invoice_value_inr"] == 2360.0
    assert summary["estimated_gst_credit_inr"] == 360.0
    assert summary["overall_status_counts"] == {"REJECTED": 1, "VERIFIED": 1}

    duplicates = json.loads(mcp_server.find_duplicate_invoices(client_id=1))
    assert duplicates == [
        {
            "vendor_name": "alpha traders",
            "invoice_number": "inv-1",
            "record_ids": [1, 2],
            "total_value_inr": 2360.0,
        }
    ]

    explanation = json.loads(mcp_server.explain_audit_flags(2))
    assert explanation["document_id"] == 2
    assert (
        explanation["recommended_action"]
        == "Review critical flags before export or reconciliation."
    )

    tally_export = json.loads(
        mcp_server.prepare_accounting_export("tally", client_id=1)
    )
    assert tally_export["content_type"] == "application/xml"
    assert tally_export["record_count"] == 2
    assert "<VOUCHER" in tally_export["preview"]

    zoho_export = json.loads(mcp_server.prepare_accounting_export("zoho", client_id=1))
    assert zoho_export["content_type"] == "text/csv"
    assert "Vendor Name,Vendor GSTIN" in zoho_export["preview"]


def test_mcp_tools_return_structured_errors_and_gstin_validation(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(mcp_server, "engine", engine)

    invalid_search = json.loads(mcp_server.search_documents(start_date="04-01-2026"))
    assert invalid_search == {"error": "Dates must use YYYY-MM-DD format."}

    invalid_export = json.loads(mcp_server.prepare_accounting_export("quickbooks"))
    assert invalid_export == {"error": "export_type must be either 'tally' or 'zoho'."}

    gstin_result = json.loads(mcp_server.validate_gstin("27AAACT2727Q1ZW"))
    assert gstin_result["valid"] is True
    assert gstin_result["state_name"] == "Maharashtra"


def test_mcp_audit_confirmation_and_tenant_scoped_query(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(mcp_server, "engine", engine)

    with Session(engine) as session:
        session.add_all(
            [
                DocumentRecord(
                    client_id=7,
                    filename="client-seven.pdf",
                    total_amount=700.0,
                    overall_status="NEEDS_REVIEW",
                ),
                DocumentRecord(
                    client_id=8,
                    filename="client-eight.pdf",
                    total_amount=800.0,
                    overall_status="NEEDS_REVIEW",
                ),
            ]
        )
        session.commit()

    search = json.loads(mcp_server.search_documents(client_id=7, actor="client-7"))
    assert [record["client_id"] for record in search] == [7]

    query = json.loads(
        mcp_server.run_ledger_query(
            "SELECT SUM(total_amount) AS total FROM documentrecord",
            is_admin=False,
            client_id=7,
        )
    )
    assert query["results"] == [{"total": 700.0}]
    assert "error" in json.loads(
        mcp_server.run_ledger_query(
            "UPDATE documentrecord SET total_amount = 0",
            is_admin=False,
            client_id=7,
        )
    )

    token_payload = json.loads(
        mcp_server.request_mutation_confirmation(
            "override_document_status", requested_by="ca-admin"
        )
    )
    updated = json.loads(
        mcp_server.override_document_status(
            1,
            "VERIFIED",
            token_payload["confirmation_token"],
            auditor_notes="Reviewed by CA",
        )
    )
    assert updated["updated"] is True
    reused = json.loads(
        mcp_server.override_document_status(
            1,
            "REJECTED",
            token_payload["confirmation_token"],
        )
    )
    assert "error" in reused

    with Session(engine) as session:
        invocations = session.exec(select(MCPToolInvocation)).all()
    assert any(
        invocation.tool_name == "search_documents"
        and invocation.actor == "client-7"
        and invocation.outcome == "success"
        for invocation in invocations
    )
