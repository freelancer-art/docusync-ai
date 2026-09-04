import json

from sqlmodel import Session, select

from app.core.database import DocumentRecord, engine

try:
    import mcp.shared.exceptions as mcp_exceptions

    if not hasattr(mcp_exceptions, "McpError") and hasattr(mcp_exceptions, "MCPError"):
        mcp_exceptions.McpError = mcp_exceptions.MCPError

    from fastmcp import FastMCP
except ImportError:

    class FastMCP:
        def __init__(self, name: str):
            self.name = name

        def tool(self):
            def decorator(func):
                return func

            return decorator

        def run(self):
            raise RuntimeError("FastMCP is not available in the current environment.")

# Initialize FastMCP Server
mcp = FastMCP("DocuSync-MCP-Server")


def _safe_json_loads(value: str | None, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return fallback


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
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "extracted_fields": _safe_json_loads(doc.raw_json_data, {}),
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
                    "audit_flags": _safe_json_loads(doc.audit_flags_json, []),
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
