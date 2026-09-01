import json
from fastmcp import FastMCP
from sqlmodel import Session, select

from app.core.database import DocumentRecord, engine

# Initialize FastMCP Server
mcp = FastMCP("DocuSync-MCP-Server")


@mcp.tool()
def get_document_by_id(doc_id: int) -> str:
    """Fetch structured invoice details and metadata by Document ID."""
    with Session(engine) as session:
        doc = session.get(DocumentRecord, doc_id)
        if not doc:
            return f"Error: Document with ID {doc_id} not found."

        return json.dumps(
            {
                "id": doc.id,
                "filename": doc.filename,
                "vendor_name": doc.vendor_name,
                "invoice_number": doc.invoice_number,
                "total_amount": doc.total_amount,
                "overall_status": doc.overall_status,
                "payment_status": doc.payment_status,
                "created_at": doc.created_at.isoformat(),
                "extracted_fields": json.loads(doc.raw_json_data),
            },
            indent=2,
        )


@mcp.tool()
def list_flagged_documents() -> str:
    """Retrieve all invoices that failed audit rules and require human review."""
    with Session(engine) as session:
        statement = select(DocumentRecord).where(
            DocumentRecord.overall_status == "NEEDS_REVIEW"
        )
        records = session.exec(statement).all()

        results = []
        for doc in records:
            results.append(
                {
                    "id": doc.id,
                    "filename": doc.filename,
                    "vendor_name": doc.vendor_name,
                    "total_amount": doc.total_amount,
                    "audit_flags": json.loads(doc.audit_flags_json),
                }
            )

        return json.dumps(results, indent=2)


@mcp.tool()
def get_financial_summary() -> str:
    """Calculate aggregate total invoice amounts split by payment and review status."""
    with Session(engine) as session:
        records = session.exec(select(DocumentRecord)).all()

        total_invoices = len(records)
        total_value = sum(doc.total_amount or 0.0 for doc in records)
        needs_review_count = sum(
            1 for doc in records if doc.overall_status == "NEEDS_REVIEW"
        )
        unpaid_value = sum(
            doc.total_amount or 0.0
            for doc in records
            if doc.payment_status == "UNPAID"
        )

        return json.dumps(
            {
                "total_documents": total_invoices,
                "total_value_inr": round(total_value, 2),
                "flagged_for_review_count": needs_review_count,
                "outstanding_unpaid_amount": round(unpaid_value, 2),
            },
            indent=2,
        )


if __name__ == "__main__":
    mcp.run()