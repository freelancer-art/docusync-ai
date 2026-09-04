import json
from datetime import date, datetime
from typing import Any

from sqlmodel import Session, select

from app.core.database import DocumentRecord, engine
from app.services.gstin_validator import gstin_validator
from app.services.tally_exporter import tally_exporter
from app.services.zoho_exporter import zoho_exporter

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


def _json_response(payload: Any) -> str:
    return json.dumps(payload, indent=2, default=str)


def _bounded_limit(limit: int | None, default: int = 25, maximum: int = 100) -> int:
    if limit is None:
        return default
    return max(1, min(limit, maximum))


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Dates must use YYYY-MM-DD format.") from exc


def _record_created_date(doc: DocumentRecord) -> date | None:
    if not doc.created_at:
        return None
    if isinstance(doc.created_at, datetime):
        return doc.created_at.date()
    return None


def _matches_period(
    doc: DocumentRecord,
    start_date: date | None,
    end_date: date | None,
) -> bool:
    created_date = _record_created_date(doc)
    if start_date and (created_date is None or created_date < start_date):
        return False
    return not (end_date and (created_date is None or created_date > end_date))


def _base_record_payload(doc: DocumentRecord, include_raw: bool = False) -> dict[str, Any]:
    payload = {
        "id": doc.id,
        "client_id": doc.client_id,
        "filename": doc.filename,
        "document_type": doc.document_type,
        "vendor_name": doc.vendor_name,
        "invoice_number": doc.invoice_number,
        "total_amount": doc.total_amount,
        "amount_paid": doc.amount_paid,
        "payment_status": doc.payment_status,
        "overall_status": doc.overall_status,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }
    if include_raw:
        payload["extracted_fields"] = _safe_json_loads(doc.raw_json_data, {})
        payload["audit_flags"] = _safe_json_loads(doc.audit_flags_json, [])
    return payload


def _filtered_records(
    session: Session,
    *,
    client_id: int | None = None,
    overall_status: str | None = None,
    payment_status: str | None = None,
    vendor_name: str | None = None,
    invoice_number: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int | None = None,
) -> list[DocumentRecord]:
    start = _parse_date(start_date)
    end = _parse_date(end_date)

    statement = select(DocumentRecord)
    if client_id is not None:
        statement = statement.where(DocumentRecord.client_id == client_id)
    if overall_status:
        statement = statement.where(DocumentRecord.overall_status == overall_status)
    if payment_status:
        statement = statement.where(DocumentRecord.payment_status == payment_status)
    if vendor_name:
        statement = statement.where(DocumentRecord.vendor_name.contains(vendor_name))
    if invoice_number:
        statement = statement.where(DocumentRecord.invoice_number == invoice_number)

    records = session.exec(statement).all()
    records = [doc for doc in records if _matches_period(doc, start, end)]
    records.sort(
        key=lambda doc: doc.created_at.timestamp()
        if isinstance(doc.created_at, datetime)
        else 0,
        reverse=True,
    )
    return records[: _bounded_limit(limit)]


@mcp.tool()
def get_document_by_id(doc_id: int) -> str:
    """Fetch structured invoice details and metadata by Document ID."""
    with Session(engine) as session:
        doc = session.get(DocumentRecord, doc_id)
        if not doc:
            return f"Error: Document with ID {doc_id} not found."

        return _json_response(_base_record_payload(doc, include_raw=True))


@mcp.tool()
def validate_gstin(gstin: str) -> str:
    """Validate GSTIN format, checksum, state code, and extracted PAN."""
    return _json_response(gstin_validator.verify_gstin(gstin))


@mcp.tool()
def search_documents(
    client_id: int | None = None,
    overall_status: str | None = None,
    payment_status: str | None = None,
    vendor_name: str | None = None,
    invoice_number: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int | None = 25,
) -> str:
    """Search document records with safe bounded filters for AI agent workflows."""
    with Session(engine) as session:
        try:
            records = _filtered_records(
                session,
                client_id=client_id,
                overall_status=overall_status,
                payment_status=payment_status,
                vendor_name=vendor_name,
                invoice_number=invoice_number,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
            )
        except ValueError as exc:
            return _json_response({"error": str(exc)})

        return _json_response([_base_record_payload(doc) for doc in records])


@mcp.tool()
def explain_audit_flags(doc_id: int) -> str:
    """Return an agent-friendly explanation of audit flags for one document."""
    with Session(engine) as session:
        doc = session.get(DocumentRecord, doc_id)
        if not doc:
            return _json_response({"error": f"Document with ID {doc_id} not found."})

        flags = _safe_json_loads(doc.audit_flags_json, [])
        if not flags:
            return _json_response(
                {
                    "document_id": doc.id,
                    "overall_status": doc.overall_status,
                    "summary": "No audit flags are currently recorded for this document.",
                    "flags": [],
                }
            )

        critical_count = sum(1 for flag in flags if flag.get("severity") == "CRITICAL")
        warning_count = sum(
            1 for flag in flags if flag.get("severity") in {"WARNING", "HIGH"}
        )

        return _json_response(
            {
                "document_id": doc.id,
                "overall_status": doc.overall_status,
                "summary": (
                    f"{len(flags)} audit flag(s): {critical_count} critical, "
                    f"{warning_count} warning/high."
                ),
                "flags": flags,
                "recommended_action": (
                    "Review critical flags before export or reconciliation."
                    if critical_count
                    else "Review warnings and auditor notes before final approval."
                ),
            }
        )


@mcp.tool()
def find_duplicate_invoices(client_id: int | None = None) -> str:
    """Find duplicate vendor and invoice-number combinations."""
    with Session(engine) as session:
        statement = select(DocumentRecord)
        if client_id is not None:
            statement = statement.where(DocumentRecord.client_id == client_id)
        records = session.exec(statement).all()

    groups: dict[tuple[str, str], list[DocumentRecord]] = {}
    for doc in records:
        vendor = (doc.vendor_name or "").strip().lower()
        invoice = (doc.invoice_number or "").strip().lower()
        if not vendor or not invoice:
            continue
        groups.setdefault((vendor, invoice), []).append(doc)

    duplicates = []
    for (vendor, invoice), docs in groups.items():
        if len(docs) <= 1:
            continue
        duplicates.append(
            {
                "vendor_name": vendor,
                "invoice_number": invoice,
                "record_ids": [doc.id for doc in docs],
                "total_value_inr": round(sum(doc.total_amount or 0.0 for doc in docs), 2),
            }
        )

    return _json_response(duplicates)


@mcp.tool()
def summarize_client_tax_position(
    client_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """Summarize invoice totals, GST credit fields, and status counts."""
    with Session(engine) as session:
        try:
            records = _filtered_records(
                session,
                client_id=client_id,
                start_date=start_date,
                end_date=end_date,
                limit=100,
            )
        except ValueError as exc:
            return _json_response({"error": str(exc)})

    status_counts: dict[str, int] = {}
    payment_counts: dict[str, int] = {}
    gst_credit = 0.0
    total_value = 0.0

    for doc in records:
        status_counts[doc.overall_status] = status_counts.get(doc.overall_status, 0) + 1
        payment_counts[doc.payment_status] = payment_counts.get(doc.payment_status, 0) + 1
        total_value += doc.total_amount or 0.0

        raw_data = _safe_json_loads(doc.raw_json_data, {})
        if isinstance(raw_data, dict):
            gst_credit += sum(
                float(raw_data.get(key) or 0.0)
                for key in ("cgst_amount", "sgst_amount", "igst_amount")
            )

    return _json_response(
        {
            "client_id": client_id,
            "period": {"start_date": start_date, "end_date": end_date},
            "document_count": len(records),
            "total_invoice_value_inr": round(total_value, 2),
            "estimated_gst_credit_inr": round(gst_credit, 2),
            "overall_status_counts": status_counts,
            "payment_status_counts": payment_counts,
        }
    )


@mcp.tool()
def prepare_accounting_export(
    export_type: str,
    client_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int | None = 100,
) -> str:
    """Prepare Tally XML or Zoho CSV export payload metadata and preview."""
    normalized_type = export_type.strip().lower()
    if normalized_type not in {"tally", "zoho"}:
        return _json_response({"error": "export_type must be either 'tally' or 'zoho'."})

    with Session(engine) as session:
        try:
            records = _filtered_records(
                session,
                client_id=client_id,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
            )
        except ValueError as exc:
            return _json_response({"error": str(exc)})

    if normalized_type == "tally":
        payload = tally_exporter.generate_vouchers_xml(records)
        content_type = "application/xml"
        filename = "tally_vouchers.xml"
    else:
        payload = zoho_exporter.generate_bills_csv(records).decode("utf-8")
        content_type = "text/csv"
        filename = "zoho_bills.csv"

    return _json_response(
        {
            "export_type": normalized_type,
            "filename": filename,
            "content_type": content_type,
            "record_count": len(records),
            "preview": payload[:2000],
            "truncated": len(payload) > 2000,
        }
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

        return _json_response(results)


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

        return _json_response(
            {
                "total_documents": total_invoices,
                "total_value_inr": round(total_value, 2),
                "flagged_for_review_count": needs_review_count,
                "outstanding_unpaid_amount": round(unpaid_value, 2),
            }
        )


if __name__ == "__main__":
    mcp.run()
