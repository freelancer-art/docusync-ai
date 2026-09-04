from unittest.mock import MagicMock

from app.services import parser


def test_parser_returns_schema_defaults_without_api_key(monkeypatch):
    monkeypatch.setattr(parser.settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(parser.settings, "GOOGLE_API_KEY", "")

    result = parser.parse_document_data(b"content", "application/pdf")

    assert result["document_type"] == "TAX_INVOICE"
    assert result["total_amount"] == 0.0


def test_parser_uses_configured_vision_model(monkeypatch):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"document_type":"TAX_INVOICE","vendor_name":"Acme","vendor_gstin":null,"invoice_number":"INV-1","invoice_date":null,"subtotal":0.0,"cgst_amount":0.0,"sgst_amount":0.0,"igst_amount":0.0,"total_amount":10.0,"line_items":[]}'
    mock_client.models.generate_content.return_value = mock_response

    monkeypatch.setattr(parser, "get_parser_client", lambda: mock_client)
    monkeypatch.setattr(parser.settings, "VISION_EXTRACTION_MODEL", "configured-model")

    result = parser.parse_document_data(b"content", "application/pdf")

    assert result["vendor_name"] == "Acme"
    assert result["total_amount"] == 10.0
    assert mock_client.models.generate_content.call_args.kwargs["model"] == "configured-model"
