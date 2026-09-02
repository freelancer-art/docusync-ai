import json
from datetime import datetime, timezone
import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.database import DocumentRecord
from app.services.audit_engine import AuditEngine, process_document_audit
from app.services.gstin_validator import gstin_validator
from app.services.tally_exporter import tally_exporter
from app.services.verification_service import verification_service
from app.services.zoho_exporter import zoho_exporter


# Setup In-Memory SQLite Engine for DB-bound tests
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


# Mock Class matching DocumentRecord interface for fast execution
class DummyDocumentRecord:
    def __init__(
        self,
        record_id=1,
        vendor_name="Test Corp",
        invoice_number="INV-101",
        total_amount=1500.0,
        raw_data=None,
    ):
        self.id = record_id
        self.vendor_name = vendor_name
        self.invoice_number = invoice_number
        self.total_amount = total_amount
        self.created_at = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)
        self.raw_json_data = json.dumps(
            raw_data
            or {
                "vendor_gstin": "27AAACT2727Q1ZW",
                "line_items": [
                    {
                        "description": "Consulting Services",
                        "quantity": 1,
                        "unit_price": 1500.0,
                        "amount": 1500.0,
                        "tax_rate": 18,
                    }
                ],
            }
        )


# --- GSTIN VALIDATION TESTS ---


def test_gstin_valid_maharashtra():
    res = gstin_validator.verify_gstin("27AAACT2727Q1ZW")
    assert res["valid"] is True
    assert res["state_code"] == "27"
    assert res["state_name"] == "Maharashtra"
    assert res["extracted_pan"] == "AAACT2727Q"
    assert res["checksum_valid"] is True


def test_gstin_invalid_checksum():
    res = gstin_validator.verify_gstin("27AAACT2727Q1Z7")
    assert res["valid"] is False
    assert res["error"] == "Checksum digit verification failed"


def test_gstin_invalid_length():
    res = gstin_validator.verify_gstin("27AAACT2727Q1")
    assert res["valid"] is False
    assert "Invalid format structure" in res["error"]


def test_gstin_whitespace_sanitization():
    res = gstin_validator.verify_gstin("  27AAACT2727Q1ZW  \n")
    assert res["valid"] is True
    assert res["gstin"] == "27AAACT2727Q1ZW"


# --- EXPORTER TESTS ---


def test_zoho_exporter_csv_generation():
    rec = DummyDocumentRecord()
    csv_bytes = zoho_exporter.generate_bills_csv([rec])
    csv_text = csv_bytes.decode("utf-8")

    assert "Vendor Name,Vendor GSTIN,Bill Number" in csv_text
    assert "Test Corp,27AAACT2727Q1ZW,INV-101" in csv_text
    assert "Consulting Services" in csv_text


def test_tally_exporter_xml_structure():
    rec = DummyDocumentRecord()
    xml_str = tally_exporter.generate_purchase_voucher_xml(rec)

    assert "<VOUCHER" in xml_str
    assert "<VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>" in xml_str
    assert "Test Corp" in xml_str
    assert "1500.0" in xml_str


# --- PHASE 4: AI ANOMALY ENGINE TESTS ---


def test_arithmetic_verification_mismatch():
    invoice_data = {
        "vendor_gstin": "27AAACT2727Q1ZW",
        "taxable_amount": 1000.0,
        "tax_amount": 180.0,
        "total_amount": 1500.0,  # 1000 + 180 != 1500
    }
    res = verification_service.audit_tax_invoice(invoice_data)
    assert res.is_valid is False
    assert res.overall_status == "REJECTED"
    flag_codes = [f.code for f in res.flags]
    assert "ARITHMETIC_TOTAL_MISMATCH" in flag_codes


def test_intra_state_tax_mismatch():
    # Both GSTINs start with state code '27' (Maharashtra)
    invoice_data = {
        "vendor_gstin": "27AAACT2727Q1ZW",
        "buyer_gstin": "27BBBCT1111Q1ZP",
        "taxable_amount": 1000.0,
        "tax_amount": 180.0,
        "total_amount": 1180.0,
        "igst": 180.0,
        "cgst": 0.0,
        "sgst": 0.0,
    }
    res = verification_service.audit_tax_invoice(invoice_data)
    assert res.is_valid is False
    flag_codes = [f.code for f in res.flags]
    assert "INTRA_STATE_TAX_MISMATCH" in flag_codes


def test_inter_state_tax_mismatch():
    # Vendor '27' (MH) -> Buyer '07' (Delhi)
    invoice_data = {
        "vendor_gstin": "27AAACT2727Q1ZW",
        "buyer_gstin": "07AAAAA0000A1Z5",
        "taxable_amount": 1000.0,
        "tax_amount": 180.0,
        "total_amount": 1180.0,
        "igst": 0.0,
        "cgst": 90.0,
        "sgst": 90.0,
    }
    res = verification_service.audit_tax_invoice(invoice_data)
    assert res.is_valid is False
    flag_codes = [f.code for f in res.flags]
    assert "INTER_STATE_TAX_MISMATCH" in flag_codes


def test_duplicate_billing_detection(session: Session):
    existing_doc = DocumentRecord(
        client_id=1,
        filename="invoice_1.pdf",
        document_type="TAX_INVOICE",
        vendor_name="Acme Corp",
        invoice_number="INV-2026-001",
        total_amount=5000.0,
        overall_status="VERIFIED",
    )
    session.add(existing_doc)
    session.commit()

    new_doc = DocumentRecord(
        client_id=1,
        filename="invoice_duplicate.pdf",
        document_type="TAX_INVOICE",
        vendor_name="Acme Corp",
        invoice_number="INV-2026-001",
        total_amount=5000.0,
        overall_status="NEEDS_REVIEW",
        raw_json_data=json.dumps({
            "vendor_name": "Acme Corp",
            "invoice_number": "INV-2026-001",
            "vendor_gstin": "27AAACT2727Q1ZW",
            "total_amount": 5000.0,
        }),
    )
    session.add(new_doc)
    session.commit()

    audited_doc = process_document_audit(new_doc, session)
    assert audited_doc.overall_status == "REJECTED"
    flags = json.loads(audited_doc.audit_flags_json)
    codes = [f["code"] for f in flags]
    assert "DUPLICATE_INVOICE" in codes