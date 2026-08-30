import sys
import json
from app.services.extractor_service import extractor_service

def test():
    pdf_path = "storage/sample_uploads/test_invoice.pdf"
    print(f"Testing extraction service with: {pdf_path}\n")

    try:
        # Call process_document instead of parse_invoice
        result = extractor_service.process_document(
            file_path=pdf_path, 
            filename="test_invoice.pdf"
        )
        print("--- Extraction & Verification Result ---")
        print(json.dumps(result, indent=2))
        print("\n✅ Document successfully processed, verified, and saved to SQLite!")

    except Exception as e:
        print("\n--- Extraction Error Details ---")
        print(e)
        sys.exit(1)

if __name__ == "__main__":
    test()