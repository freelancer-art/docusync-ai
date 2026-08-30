import pdfplumber
import instructor
from groq import Groq
from app.config import settings
from app.schemas.tax_invoice import TaxInvoiceSchema

class ExtractorService:
    def __init__(self):
        self.client = instructor.from_groq(
            Groq(api_key=settings.GROQ_API_KEY),
            mode=instructor.Mode.JSON
        )

    def extract_text_from_pdf(self, file_path: str) -> str:
        extracted_text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"
        return extracted_text

    def parse_invoice(self, file_path: str) -> TaxInvoiceSchema:
        raw_text = self.extract_text_from_pdf(file_path)
        
        if not raw_text.strip():
            raise ValueError("No extractable text found in PDF. Scanned images require OCR preprocessing.")

        structured_data = self.client.chat.completions.create(
            model=settings.PRIMARY_EXTRACTION_MODEL,
            response_model=TaxInvoiceSchema,
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise document extraction assistant. Convert the provided tax invoice text into structured JSON matching the requested schema. Return JSON only."
                },
                {
                    "role": "user",
                    "content": f"Extract structured tax invoice data from this document:\n\n{raw_text}"
                }
            ],
            temperature=0.1,
            max_tokens=4096
        )
        return structured_data

extractor_service = ExtractorService()