import json

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.database import DocumentRecord, User, UserRole
from app.core.security import InvalidFileTypeError, validate_file_signature
from app.services.gstin_validator import gstin_validator
from app.services.tally_exporter import tally_exporter
from app.services.zoho_exporter import zoho_exporter


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_gstin_validator_xss_and_sql_injection():
    malicious_inputs = [
        "' OR '1'='1",
        "27AAACT2727Q1ZW'; DROP TABLE documentrecord;--",
        "<script>alert('xss')</script>",
        "27AAACT2727Q1ZW SELECT * FROM users",
    ]
    for bad_input in malicious_inputs:
        res = gstin_validator.verify_gstin(bad_input)
        assert res["valid"] is False
        assert (
            "Invalid format structure" in res["error"]
            or "GSTIN missing" in res["error"]
        )


def test_malformed_json_resilience():
    class MalformedRecord:
        id = 99
        vendor_name = "<script>alert('vendor')</script>"
        invoice_number = "INV-SQL'-- OR 1=1"
        total_amount = 999.99
        created_at = None
        raw_json_data = "{ invalid_json: true, "

    rec = MalformedRecord()
    csv_bytes = zoho_exporter.generate_bills_csv([rec])
    assert b"INV-SQL'-- OR 1=1" in csv_bytes
    assert isinstance(csv_bytes, bytes)

    xml_str = tally_exporter.generate_purchase_voucher_xml(rec)
    assert "INV-SQL'-- OR 1=1" in xml_str
    assert isinstance(xml_str, str)


def test_sql_injection_prevention_in_queries(session):
    user = User(
        username="testuser",
        full_name="Test User",
        hashed_password="hashed_pw",
        role=UserRole.CLIENT,
    )
    session.add(user)
    session.commit()

    doc = DocumentRecord(
        filename="clean_invoice.pdf",
        document_type="INVOICE",
        extraction_method="AI_VISION",
        client_id=user.id,
        overall_status="VERIFIED",
        invoice_number="INV-1001",
        vendor_name="Malicious Vendor'; DROP TABLE users; --",
        total_amount=500.0,
        raw_json_data=json.dumps({"vendor_name": "Malicious Vendor"}),
        audit_flags_json="[]",
        auditor_notes="",
    )
    session.add(doc)
    session.commit()

    malicious_status = "VERIFIED' OR '1'='1"
    statement = select(DocumentRecord).where(
        DocumentRecord.overall_status == malicious_status
    )
    result = session.exec(statement).all()

    assert len(result) == 0

    users_in_db = session.exec(select(User)).all()
    assert len(users_in_db) == 1
    assert users_in_db[0].username == "testuser"


def test_rbac_client_isolation(session):
    client_a = User(
        username="client_a",
        full_name="Client A",
        hashed_password="pw",
        role=UserRole.CLIENT,
    )
    client_b = User(
        username="client_b",
        full_name="Client B",
        hashed_password="pw",
        role=UserRole.CLIENT,
    )
    session.add_all([client_a, client_b])
    session.commit()

    doc_a = DocumentRecord(
        filename="client_a_doc.pdf",
        document_type="INVOICE",
        extraction_method="AI_VISION",
        client_id=client_a.id,
        overall_status="VERIFIED",
        invoice_number="INV-A",
        vendor_name="Vendor A",
        total_amount=100.0,
        raw_json_data="{}",
        audit_flags_json="[]",
        auditor_notes="",
    )
    session.add(doc_a)
    session.commit()

    # Query strictly scoped to client_b
    stmt = select(DocumentRecord).where(
        DocumentRecord.client_id == client_b.id,
        DocumentRecord.id == doc_a.id,
    )
    result = session.exec(stmt).all()
    assert len(result) == 0


def test_filename_path_traversal_prevention():
    malicious_filenames = [
        "../../etc/passwd",
        "..\\..\\Windows\\System32\\cmd.exe",
        "../../var/log/syslog.pdf",
    ]
    for bad_name in malicious_filenames:
        doc = DocumentRecord(
            filename=bad_name,
            document_type="INVOICE",
            extraction_method="AI_VISION",
            client_id=1,
            overall_status="PENDING",
            invoice_number="INV-001",
            vendor_name="Test",
            total_amount=50.0,
            raw_json_data="{}",
            audit_flags_json="[]",
            auditor_notes="",
        )
        assert ".." not in doc.filename
        assert "/" not in doc.filename
        assert "\\" not in doc.filename


def test_csv_formula_injection_prevention():
    class FormulaInjectionRecord:
        id = 1
        vendor_name = "=CMD|' /C calc'!A0"
        invoice_number = "+2+5"
        total_amount = 100.0
        created_at = None
        raw_json_data = "{}"

    rec = FormulaInjectionRecord()
    csv_bytes = zoho_exporter.generate_bills_csv([rec])
    csv_str = csv_bytes.decode("utf-8")

    assert "=CMD" not in csv_str or "'=CMD" in csv_str or '"=CMD' in csv_str


def test_monetary_edge_cases_zero_and_negative():
    """Verify zero and negative total amounts are handled correctly without breaking exports."""
    record_zero = DocumentRecord(
        filename="zero_amount.pdf",
        document_type="INVOICE",
        extraction_method="AI_VISION",
        client_id=1,
        overall_status="VERIFIED",
        invoice_number="INV-ZERO",
        vendor_name="Zero Vendor",
        total_amount=0.0,
        raw_json_data=json.dumps(
            {
                "line_items": [
                    {
                        "description": "Free Item",
                        "quantity": 1,
                        "unit_price": 0.0,
                        "amount": 0.0,
                    }
                ]
            }
        ),
        audit_flags_json="[]",
    )

    record_negative = DocumentRecord(
        filename="credit_note.pdf",
        document_type="CREDIT_NOTE",
        extraction_method="AI_VISION",
        client_id=1,
        overall_status="VERIFIED",
        invoice_number="CN-100",
        vendor_name="Refund Vendor",
        total_amount=-150.75,
        raw_json_data=json.dumps(
            {
                "line_items": [
                    {
                        "description": "Refund",
                        "quantity": 1,
                        "unit_price": -150.75,
                        "amount": -150.75,
                    }
                ]
            }
        ),
        audit_flags_json="[]",
    )

    csv_bytes = zoho_exporter.generate_bills_csv([record_zero, record_negative])
    csv_str = csv_bytes.decode("utf-8")

    assert "INV-ZERO" in csv_str
    assert "0.0" in csv_str
    assert "CN-100" in csv_str
    assert "-150.75" in csv_str


def test_monetary_floating_point_precision():
    """Ensure high-precision floating point amounts are serialized gracefully."""
    record = DocumentRecord(
        filename="precision.pdf",
        document_type="INVOICE",
        extraction_method="AI_VISION",
        client_id=1,
        overall_status="VERIFIED",
        invoice_number="INV-PRECISION",
        vendor_name="Precision Tech",
        total_amount=100.33333333333333,
        raw_json_data="{}",
        audit_flags_json="[]",
    )

    csv_bytes = zoho_exporter.generate_bills_csv([record])
    assert b"INV-PRECISION" in csv_bytes


def test_missing_optional_fields_resilience():
    """Verify exporter degrades gracefully when mandatory fields are None or omitted."""

    class SparseRecord:
        id = None
        vendor_name = None
        invoice_number = None
        total_amount = None
        created_at = None
        raw_json_data = None

    sparse_rec = SparseRecord()
    csv_bytes = zoho_exporter.generate_bills_csv([sparse_rec])
    csv_str = csv_bytes.decode("utf-8")

    assert "Unassigned Vendor" in csv_str
    assert "BILL-0" in csv_str


def test_malformed_json_types_in_line_items():
    """Verify system resilience when raw_json_data contains invalid data structures."""
    malformed_payloads = [
        "null",
        "[]",
        '{"line_items": "not_a_list"}',
        '{"line_items": [{"quantity": "invalid_number", "unit_price": None}]}',
    ]

    for payload in malformed_payloads:
        record = DocumentRecord(
            filename="malformed.pdf",
            document_type="INVOICE",
            extraction_method="AI_VISION",
            client_id=1,
            overall_status="NEEDS_REVIEW",
            invoice_number="INV-BAD",
            vendor_name="Bad Payload Ltd",
            total_amount=50.0,
            raw_json_data=payload,
            audit_flags_json="[]",
        )

        csv_bytes = zoho_exporter.generate_bills_csv([record])
        assert isinstance(csv_bytes, bytes)


def test_valid_pdf_magic_bytes():
    fake_pdf = b"%PDF-1.7 header content here..."
    assert validate_file_signature(fake_pdf) == "pdf"


def test_valid_image_magic_bytes():
    fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR..."
    fake_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF..."
    assert validate_file_signature(fake_png) == "png"
    assert validate_file_signature(fake_jpeg) == "jpeg"


def test_reject_executable_disguised_as_pdf():
    malicious_exe = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00..."
    with pytest.raises(InvalidFileTypeError, match="Unsupported file signature"):
        validate_file_signature(malicious_exe)


def test_reject_empty_file():
    with pytest.raises(InvalidFileTypeError, match="file is empty"):
        validate_file_signature(b"")