from dotenv import load_dotenv
from app.services.extractor_service import extractor_service

load_dotenv()

try:
    print("Testing extraction service with test PDF...")
    result = extractor_service.parse_invoice("storage/sample_uploads/test_invoice.pdf")
    print("\n--- Extraction Result Success ---")
    print(result.model_dump_json(indent=2))
except Exception as e:
    print("\n--- Extraction Error Details ---")
    print(e)