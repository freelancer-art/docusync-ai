import pytest
import json
from datetime import datetime
from app.services.gstin_validator import gstin_validator
from app.services.zoho_exporter import zoho_exporter
from app.services.tally_exporter import tally_exporter

# Mock Class matching DocumentRecord interface for fast execution
class DummyDocumentRecord:
    def __init__(self, record_id=1, vendor_name="Test Corp", invoice_number="INV-101", total_amount=1500.0, raw_data=None):
        self.id = record_id
        self.vendor_name = vendor_name
        self.invoice_number = invoice_number
        self.total_amount = total_amount
        self.created_at = datetime(2026, 8, 30, 12, 0, 0)
        self.raw_json_data = json.dumps(raw_data or {
            "vendor_gstin": "27AAACT2727Q1ZW",
            "line_items": [
                {"description": "Consulting Services", "quantity": 1, "unit_price": 1500.0, "amount": 1500.0, "tax_rate": 18}
            ]
        })

# --- GSTIN VALIDATION TESTS ---

def test_gstin_valid_maharashtra():
    res = gstin_validator.verify_gstin("27AAACT2727Q1ZW")
    assert res["valid"] is True
    assert res["state_code"] == "27"
    assert res["state_name"] == "Maharashtra"
    assert res["extracted_pan"] == "AAACT2727Q"
    assert res["checksum_valid"] is True

def test_gstin_invalid_checksum():
    # '7' instead of 'W' at position 15
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