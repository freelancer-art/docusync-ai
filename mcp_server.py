import json
from mcp.server import MCPServer
from sqlmodel import Session, select
from app.core.database import engine, DocumentRecord

mcp = MCPServer("DocuSync AI Client Portal")

@mcp.tool()
def get_flagged_documents(status: str = "REJECTED") -> str:
    """
    Fetch all client documents that have audit issues or flags matching a status ('REJECTED' or 'NEEDS_REVIEW').
    """
    with Session(engine) as session:
        statement = select(DocumentRecord).where(DocumentRecord.overall_status == status.upper())
        results = session.exec(statement).all()

        output = []
        for doc in results:
            output.append({
                "id": doc.id,
                "filename": doc.filename,
                "vendor_name": doc.vendor_name,
                "invoice_number": doc.invoice_number,
                "total_amount": doc.total_amount,
                "status": doc.overall_status,
                "flags": json.loads(doc.audit_flags_json)
            })
        return json.dumps(output, indent=2)

@mcp.tool()
def get_client_summary() -> str:
    """
    Summarize overall client submission metrics: total processed documents, total amount parsed, and audit status breakdown.
    """
    with Session(engine) as session:
        all_docs = session.exec(select(DocumentRecord)).all()
        
        total_docs = len(all_docs)
        total_value = sum(doc.total_amount or 0.0 for doc in all_docs)
        status_counts = {"VERIFIED": 0, "NEEDS_REVIEW": 0, "REJECTED": 0}

        for doc in all_docs:
            status = doc.overall_status
            if status in status_counts:
                status_counts[status] += 1

        return json.dumps({
            "total_documents_processed": total_docs,
            "total_financial_value_parsed": total_value,
            "status_breakdown": status_counts
        }, indent=2)

if __name__ == "__main__":
    mcp.run()