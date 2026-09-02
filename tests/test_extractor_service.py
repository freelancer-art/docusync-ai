import json
import pytest
from unittest.mock import MagicMock, patch

from app.services.extractor_service import (
    TaxInvoiceSchema,
    LineItem,
    BankStatementSchema,
    extract_structured_data,
    classify_document_text,
    _calculate_confidence_score,
)
from app.services.audit_engine import AuditEngine
from app.core.database import DocumentRecord


class TestExtractorSchemas:
    def test_tax_invoice_schema_instantiation(self):
        """Tests that TaxInvoiceSchema correctly instantiates and calculates defaults."""
        item = LineItem(
            description="Consulting Services",
            hsn_sac="998311",
            quantity=1.0,
            unit_price=5000.0,
            taxable_amount=5000.0,
            gst_rate=18.0,
            total_amount=5900.0,
        )
        invoice = TaxInvoiceSchema(
            vendor_name="Acme Corp",
            vendor_gstin="27AAAAA0000A1Z5",
            customer_name="Beta Ltd",
            customer_gstin="27BBBBB0000B1Z2",
            invoice_number="INV-2026-001",
            invoice_date="2026-09-01",
            taxable_amount=5000.0,
            cgst_amount=450.0,
            sgst_amount=450.0,
            igst_amount=0.0,
            tax_amount=900.0,
            total_amount=5900.0,
            line_items=[item],
        )

        assert invoice.vendor_name == "Acme Corp"
        assert invoice.vendor_gstin == "27AAAAA0000A1Z5"
        assert len(invoice.line_items) == 1
        assert invoice.line_items[0].hsn_sac == "998311"


class TestDocumentClassification:
    def test_classify_tax_invoice(self):
        text = "Tax Invoice\nVendor: ABC Pvt Ltd\nGSTIN: 27AAAAA0000A1Z5\nTotal: 1000"
        assert classify_document_text(text) == "TAX_INVOICE"

    def test_classify_bank_statement(self):
        text = "Statement of Account\nOpening Balance: 5000.00\nClosing Balance: 12000.00\nWithdrawal: 200"
        assert classify_document_text(text) == "BANK_STATEMENT"


class TestExtractorFallback:
    @patch("app.services.extractor_service.get_ai_client")
    def test_fallback_when_no_ai_client(self, mock_get_ai_client):
        """Tests that extraction degrades gracefully to structured fallback when AI client is unavailable."""
        mock_get_ai_client.return_value = (None, None)

        result = extract_structured_data(
            file_input=b"Sample raw invoice bytes",
            filename="sample_invoice.pdf",
            doc_type="TAX_INVOICE",
        )

        assert result["vendor_name"] == "Extracted Vendor"
        assert result["invoice_number"] == "INV-PENDING"
        assert result["doc_type"] == "TAX_INVOICE"
        assert "confidence_score" in result
        assert result["confidence_score"] <= 1.0


class TestAuditEngineIntegration:
    def test_extracted_data_audit_evaluation(self):
        """Tests that output structure produced by extractor maps seamlessly into AuditEngine."""
        extracted_data = {
            "vendor_name": "Test Vendor",
            "vendor_gstin": "27AAAAA0000A1Z5",  # Maharashtra (27)
            "buyer_gstin": "07BBBBB0000B1Z2",   # Delhi (07) - Inter-state
            "taxable_amount": 1000.0,
            "cgst": 90.0,  # Invalid tax head for inter-state (should be IGST)
            "sgst": 90.0,
            "igst": 0.0,
            "tax_amount": 180.0,
            "total_amount": 1180.0,
            "line_items": [
                {
                    "quantity": 2,
                    "unit_price": 500.0,
                    "total_amount": 1000.0,
                }
            ],
        }

        doc = DocumentRecord(
            filename="test_invoice.pdf",
            vendor_name="Test Vendor",
            invoice_number="INV-100",
            total_amount=1180.0,
            raw_json_data=json.dumps(extracted_data),
        )

        audit_result = AuditEngine.evaluate_document(doc)

        assert audit_result["status"] == "NEEDS_REVIEW"
        assert "INTER_STATE_TAX_TYPE_MISMATCH" in audit_result["flags"]