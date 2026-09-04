import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.database import DocumentRecord, User, UserRole, get_session
from app.main import app

engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)


@pytest.fixture(name="session")
def session_fixture():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_login_and_jwt_export_flow(client: TestClient, session: Session):
    user = User(
        username="ca_user",
        full_name="CA Test",
        hashed_password=User.hash_password("admin123"),
        role=UserRole.CA_ADMIN,
    )
    session.add(user)
    session.commit()

    # 1. Test Login Endpoint (Form data transmission)
    login_resp = client.post(
        "/api/auth/login", data={"username": "ca_user", "password": "admin123"}
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Add Test Document
    doc = DocumentRecord(
        filename="export_invoice.pdf",
        document_type="INVOICE",
        extraction_method="AI_VISION",
        overall_status="VERIFIED",
        client_id=user.id,
        invoice_number="INV-EXP-001",
        vendor_name="Export Vendor",
        total_amount=250.0,
        raw_json_data="{}",
        audit_flags_json="{}",
    )
    session.add(doc)
    session.commit()

    # 3. Test Zoho CSV Export Endpoint
    zoho_resp = client.get("/api/documents/export/zoho", headers=headers)
    assert zoho_resp.status_code == 200
    assert "text/csv" in zoho_resp.headers["content-type"]
    assert "INV-EXP-001" in zoho_resp.text

    # 4. Test Tally XML Export Endpoint
    tally_resp = client.get("/api/documents/export/tally", headers=headers)
    assert tally_resp.status_code == 200
    assert "application/xml" in tally_resp.headers["content-type"]
    assert "INV-EXP-001" in tally_resp.text


def test_tally_xml_export_flow(client: TestClient, session: Session):
    user = User(
        username="ca_tally_user",
        full_name="CA Tally Test",
        hashed_password=User.hash_password("admin123"),
        role=UserRole.CA_ADMIN,
    )
    session.add(user)
    session.commit()

    login_resp = client.post(
        "/api/auth/login", data={"username": "ca_tally_user", "password": "admin123"}
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    doc = DocumentRecord(
        filename="tally_invoice.pdf",
        document_type="INVOICE",
        extraction_method="AI_VISION",
        overall_status="VERIFIED",
        client_id=user.id,
        invoice_number="INV-TALLY-001",
        vendor_name="Acme Supplies",
        total_amount=500.0,
        raw_json_data="{}",
        audit_flags_json="{}",
    )
    session.add(doc)
    session.commit()

    tally_resp = client.get("/api/documents/export/tally", headers=headers)
    assert tally_resp.status_code == 200
    assert tally_resp.headers["content-type"].startswith("application/xml")

    xml_content = tally_resp.text
    assert "<ENVELOPE>" in xml_content
    assert '<VOUCHER VCHTYPE="Purchase" ACTION="Create">' in xml_content
    assert "<PARTYLEDGERNAME>Acme Supplies</PARTYLEDGERNAME>" in xml_content
    assert "INV-TALLY-001" in xml_content


def test_export_endpoints_use_service_format_and_escaping(
    client: TestClient, session: Session
):
    user = User(
        username="ca_export_security",
        full_name="CA Export Security",
        hashed_password=User.hash_password("admin123"),
        role=UserRole.CA_ADMIN,
    )
    session.add(user)
    session.commit()

    login_resp = client.post(
        "/api/auth/login",
        data={"username": "ca_export_security", "password": "admin123"},
    )
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    doc = DocumentRecord(
        filename="escaped_invoice.pdf",
        document_type="INVOICE",
        extraction_method="AI_VISION",
        overall_status="VERIFIED",
        client_id=user.id,
        invoice_number="+SUM(1,2)",
        vendor_name="=CMD|' /C calc'!A0",
        total_amount=100.0,
        raw_json_data='{"line_items": [{"description": "@danger", "quantity": 1, "unit_price": 100.0, "amount": 100.0}]}',
        audit_flags_json="[]",
    )
    session.add(doc)
    session.commit()

    zoho_resp = client.get("/api/documents/export/zoho", headers=headers)
    assert zoho_resp.status_code == 200
    assert "Vendor Name,Vendor GSTIN,Bill Number" in zoho_resp.text
    assert "'=CMD|' /C calc'!A0" in zoho_resp.text
    assert "'+SUM(1,2)" in zoho_resp.text
    assert "'@danger" in zoho_resp.text

    tally_resp = client.get("/api/documents/export/tally", headers=headers)
    assert tally_resp.status_code == 200
    assert "<REPORTNAME>Vouchers</REPORTNAME>" in tally_resp.text
