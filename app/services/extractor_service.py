import instructor
from groq import Groq
from app.config import settings
from app.core.ocr_engine import ocr_engine
from app.schemas.document_type import DocumentClassification
from app.schemas.tax_invoice import TaxInvoiceSchema
from app.schemas.bank_statement import BankStatementSchema
from app.services.verification_service import verification_service

class ExtractorService:
    def __init__(self):
        self.client = instructor.from_groq(
            Groq(api_key=settings.GROQ_API_KEY),
            mode=instructor.Mode.JSON
        )

    def classify_document(self, raw_text: str) -> DocumentClassification:
        return self.client.chat.completions.create(
            model=settings.PRIMARY_EXTRACTION_MODEL,
            response_model=DocumentClassification,
            messages=[
                {"role": "system", "content": "Classify document content accurately."},
                {"role": "user", "content": f"Classify this text:\n\n{raw_text[:2000]}"}
            ],
            temperature=0.0
        )

    def process_document(self, file_path: str):
        raw_text, extraction_method = ocr_engine.extract_text(file_path)

        if not raw_text.strip():
            raise ValueError("Unable to extract text from document using digital or OCR methods.")

        # 1. Classify
        classification = self.classify_document(raw_text)
        doc_type = classification.document_type

        parsed_dict = {}
        audit_results = None

        # 2. Extract Data & Audit
        if doc_type == "tax_invoice":
            parsed_data = self.client.chat.completions.create(
                model=settings.PRIMARY_EXTRACTION_MODEL,
                response_model=TaxInvoiceSchema,
                messages=[
                    {"role": "system", "content": "Extract tax invoice metadata precisely into JSON."},
                    {"role": "user", "content": raw_text}
                ],
                temperature=0.1,
                max_tokens=4096
            )
            parsed_dict = parsed_data.model_dump()
            
            # Run Rule Audit Engine
            audit_results = verification_service.audit_tax_invoice(parsed_dict).model_dump()

        elif doc_type == "bank_statement":
            parsed_data = self.client.chat.completions.create(
                model=settings.PRIMARY_EXTRACTION_MODEL,
                response_model=BankStatementSchema,
                messages=[
                    {"role": "system", "content": "Extract bank statement metadata precisely into JSON."},
                    {"role": "user", "content": raw_text}
                ],
                temperature=0.1,
                max_tokens=4096
            )
            parsed_dict = parsed_data.model_dump()
        else:
            raise ValueError(f"Document type '{doc_type}' is not supported.")

        return {
            "document_type": doc_type,
            "extraction_method": extraction_method,
            "reasoning": classification.confidence_reasoning,
            "data": parsed_dict,
            "audit_summary": audit_results
        }

extractor_service = ExtractorService()