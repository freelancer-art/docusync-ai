from app.services.verification_service import verification_service

sample_invoice_data = {
    "vendor_name": "Test Vendor",
    "vendor_gstin": "INVALID_GSTIN_123",  # Malformed
    "total_amount": 10000.0,
    "tax_amount": 1800.0,
    "line_items": [
        {"description": "Consulting", "total_amount": 5000.0}  # Mismatch: 5000 + 1800 != 10000
    ]
}

audit = verification_service.audit_tax_invoice(sample_invoice_data)
print("\n--- Audit Result ---")
print(audit.model_dump_json(indent=2))