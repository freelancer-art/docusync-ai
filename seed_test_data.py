import json
from sqlmodel import Session, select
from app.core.database import engine, DocumentRecord, User, init_db

def reseed():
    init_db()
    with Session(engine) as session:
        # Clear existing records
        session.exec(DocumentRecord.__table__.delete())
        session.commit()

        acme = session.exec(select(User).where(User.username == "acme_corp")).first()
        apex = session.exec(select(User).where(User.username == "apex_tech")).first()

        docs = [
            # 1. Clean Verified Document
            DocumentRecord(
                filename="Clean_Invoice_Acme.pdf",
                document_type="TAX_INVOICE",
                extraction_method="HYBRID_LLM_OCR",
                overall_status="VERIFIED",
                vendor_name="TATA Communications Ltd",
                invoice_number="INV-2026-901",
                total_amount=23600.00,
                raw_json_data=json.dumps({
                    "vendor_name": "TATA Communications Ltd",
                    "vendor_gstin": "27AAACT2727Q1ZW",
                    "invoice_number": "INV-2026-901",
                    "subtotal": 20000.00,
                    "cgst_amount": 1800.00,
                    "sgst_amount": 1800.00,
                    "total_amount": 23600.00
                }),
                audit_flags_json=json.dumps([]),
                client_id=acme.id
            ),
            # 2. Arithmetic Error (REJECTED)
            DocumentRecord(
                filename="Arithmetic_Error_Invoice.pdf",
                document_type="TAX_INVOICE",
                extraction_method="HYBRID_LLM_OCR",
                overall_status="REJECTED",
                vendor_name="Bad Math Vendor",
                invoice_number="INV-BAD-01",
                total_amount=50000.00,
                raw_json_data=json.dumps({
                    "vendor_name": "Bad Math Vendor",
                    "vendor_gstin": "27ABCDE1234F1Z5",
                    "invoice_number": "INV-BAD-01",
                    "subtotal": 20000.00,
                    "total_tax": 3600.00,
                    "total_amount": 50000.00  # 20000 + 3600 != 50000
                }),
                audit_flags_json=json.dumps([
                    {
                        "code": "ARITHMETIC_TOTAL_MISMATCH",
                        "severity": "CRITICAL",
                        "message": "Subtotal + Tax (₹23,600.00) does not equal total amount (₹50,000.00)."
                    }
                ]),
                client_id=apex.id
            ),
            # 3. Invalid GSTIN & High Value Warning (NEEDS_REVIEW)
            DocumentRecord(
                filename="Invalid_GSTIN_HighValue.pdf",
                document_type="TAX_INVOICE",
                extraction_method="HYBRID_LLM_OCR",
                overall_status="NEEDS_REVIEW",
                vendor_name="Global Enterprise Tech",
                invoice_number="INV-GET-882",
                total_amount=150000.00,
                raw_json_data=json.dumps({
                    "vendor_name": "Global Enterprise Tech",
                    "vendor_gstin": "INVALID_GSTIN_123",
                    "invoice_number": "INV-GET-882",
                    "total_amount": 150000.00
                }),
                audit_flags_json=json.dumps([
                    {
                        "code": "INVALID_GSTIN_FORMAT",
                        "severity": "HIGH",
                        "message": "GSTIN 'INVALID_GSTIN_123' fails standard 15-character statutory format checks."
                    },
                    {
                        "code": "HIGH_VALUE_TRANSACTION",
                        "severity": "MEDIUM",
                        "message": "High-value invoice (> ₹1,00,000) requires senior auditor sign-off."
                    }
                ]),
                client_id=acme.id
            )
        ]
        session.add_all(docs)
        session.commit()
        print("✓ Updated seed data with custom audit rule test cases!")

if __name__ == "__main__":
    reseed()