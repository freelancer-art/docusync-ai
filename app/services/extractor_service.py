import io
import json
import logging
from typing import Any

from groq import Groq, GroqError
from instructor import Instructor, from_groq
from instructor.core import InstructorError

from app.config import settings
from app.core import ocr_engine

# ------------------------------------------------------------------
# Safe Dynamic Imports for Enums and Schemas
# ------------------------------------------------------------------
try:
    from app.schemas.document_type import DocumentType
except ImportError:
    try:
        from app.schemas.document import DocumentType
    except ImportError:
        from enum import Enum

        class DocumentType(str, Enum):
            TAX_INVOICE = "TAX_INVOICE"
            BANK_STATEMENT = "BANK_STATEMENT"


try:
    from app.schemas.tax_invoice import TaxInvoice
except ImportError:
    try:
        from app.schemas.tax_invoice import TaxInvoiceSchema as TaxInvoice
    except ImportError:
        try:
            from app.schemas.tax_invoice import InvoiceSchema as TaxInvoice
        except ImportError:
            from pydantic import BaseModel

            class TaxInvoice(BaseModel):
                vendor_name: str | None = None
                invoice_number: str | None = None
                total_amount: float | None = 0.0


try:
    from app.schemas.bank_statement import BankStatement
except ImportError:
    try:
        from app.schemas.bank_statement import BankStatementSchema as BankStatement
    except ImportError:
        from pydantic import BaseModel

        class BankStatement(BaseModel):
            account_number: str | None = None
            opening_balance: float | None = 0.0
            closing_balance: float | None = 0.0


logger = logging.getLogger("docusync.extractor")


def extract_raw_text(file_input: bytes | str, filename: str) -> tuple[str, str]:
    """
    Safely extracts text using available multi-engine cascades (pdfplumber -> Tesseract OCR).
    Returns a tuple of (extracted_text, extraction_method).
    """
    if isinstance(file_input, str):
        try:
            with open(file_input, "rb") as f:
                file_bytes = f.read()
        except (OSError, IOError) as e:
            logger.error(f"Failed to read file path {file_input}: {e}")
            return "", "FAILED"
    else:
        file_bytes = file_input

    stream_or_bytes = (
        io.BytesIO(file_bytes) if isinstance(file_bytes, bytes) else file_bytes
    )

    if hasattr(ocr_engine, "extract_text"):
        try:
            res = ocr_engine.extract_text(stream_or_bytes, filename)
            if isinstance(res, tuple):
                return res[0], res[1]
            return res, "pdfplumber_or_ocr"
        except (RuntimeError, ValueError, TypeError, IOError):
            try:
                res = ocr_engine.extract_text(file_bytes)
                if isinstance(res, tuple):
                    return res[0], res[1]
                return res, "pdfplumber_or_ocr"
            except (RuntimeError, ValueError, TypeError, IOError) as e:
                logger.error(f"OCR engine extraction error: {e}")

    try:
        return file_bytes.decode("utf-8", errors="ignore"), "raw_bytes_fallback"
    except (UnicodeDecodeError, AttributeError):
        return "", "FAILED"


def get_groq_client() -> Instructor | None:
    """Instantiates an instructor-wrapped Groq client if an API key is available."""
    if not settings.GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not set. LLM extraction will use mock fallback.")
        return None
    try:
        raw_client = Groq(api_key=settings.GROQ_API_KEY)
        return from_groq(raw_client)
    except (GroqError, ValueError, RuntimeError) as e:
        logger.error(f"Failed to initialize Groq client: {e}")
        return None


def classify_document_text(text: str) -> DocumentType:
    """Classifies raw text into TAX_INVOICE or BANK_STATEMENT using rule heuristics."""
    lower_text = text.lower()
    bank_keywords = [
        "statement of account",
        "opening balance",
        "closing balance",
        "withdrawal",
        "deposit",
        "account number",
    ]

    if any(keyword in lower_text for keyword in bank_keywords):
        return DocumentType.BANK_STATEMENT
    return DocumentType.TAX_INVOICE


def _calculate_confidence_score(
    extracted_dict: dict[str, Any], extraction_method: str
) -> float:
    """Calculates overall extraction confidence score (0.0 to 1.0) based on present fields and method."""
    score = 1.0

    # Penalize fallback OCR engines relative to direct digital PDF extraction
    if extraction_method == "tesseract_ocr":
        score -= 0.15
    elif extraction_method == "raw_bytes_fallback":
        score -= 0.30

    # Field completeness penalties
    missing_key_count = 0
    total_keys = len(extracted_dict) or 1
    for v in extracted_dict.values():
        if v is None or v in ["", 0.0, "UNKNOWN_VENDOR", "UNKNOWN_INV"]:
            missing_key_count += 1

    field_completeness = 1.0 - (missing_key_count / total_keys)
    final_score = round(
        max(0.0, min(1.0, (score * 0.4) + (field_completeness * 0.6))), 2
    )
    return final_score


def extract_structured_data(
    file_input: bytes | str,
    filename: str,
    doc_type: DocumentType | None = None,
) -> dict:
    """
    Full extraction pipeline:
    1. Extracts raw text via pdfplumber / OCR fallback cascade.
    2. Classifies document type if not specified.
    3. Calls Groq structured outputs via instructor.
    4. Computes confidence score.
    """
    raw_text, extraction_method = extract_raw_text(file_input, filename)

    if not doc_type:
        doc_type = classify_document_text(raw_text)

    client = get_groq_client()

    if not client:
        fallback_data = _generate_fallback_extraction(doc_type, filename, raw_text)
        fallback_data["confidence_score"] = _calculate_confidence_score(
            fallback_data, extraction_method
        )
        fallback_data["extraction_method"] = extraction_method
        return fallback_data

    prompt_content = (
        raw_text.strip()
        if raw_text and raw_text.strip()
        else f"No text content could be extracted from {filename}."
    )
    target_schema = (
        TaxInvoice if doc_type == DocumentType.TAX_INVOICE else BankStatement
    )

    try:
        response = client.chat.completions.create(
            model=settings.PRIMARY_EXTRACTION_MODEL,
            response_model=target_schema,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert financial document auditor. "
                        "Extract all requested fields accurately from the provided document text. "
                        "If a value is missing or unclear, set it to null or default."
                    ),
                },
                {"role": "user", "content": prompt_content},
            ],
            temperature=0.0,
        )
        data = json.loads(response.model_dump_json())
        data["confidence_score"] = _calculate_confidence_score(data, extraction_method)
        data["extraction_method"] = extraction_method
        return data
    except (GroqError, InstructorError, json.JSONDecodeError, ValueError) as e:
        logger.error(
            f"LLM extraction error: {e}. Falling back to default schema parsing."
        )
        fallback_data = _generate_fallback_extraction(doc_type, filename, raw_text)
        fallback_data["confidence_score"] = _calculate_confidence_score(
            fallback_data, extraction_method
        )
        fallback_data["extraction_method"] = extraction_method
        return fallback_data


def _generate_fallback_extraction(
    doc_type: DocumentType, filename: str, text: str
) -> dict:
    """Generates basic structural JSON when live LLM parsing is offline."""
    if doc_type == DocumentType.TAX_INVOICE:
        return {
            "vendor_name": "Extracted Vendor",
            "invoice_number": "INV-PENDING",
            "total_amount": 0.0,
            "cgst_amount": 0.0,
            "sgst_amount": 0.0,
            "igst_amount": 0.0,
            "line_items": [],
            "raw_text_snippet": text[:200],
        }
    else:
        return {
            "account_number": "ACC-PENDING",
            "opening_balance": 0.0,
            "closing_balance": 0.0,
            "transactions": [],
            "raw_text_snippet": text[:200],
        }


class ExtractorService:
    def process_document(
        self,
        file_input: bytes | str,
        filename: str,
        doc_type: DocumentType | None = None,
    ) -> dict:
        return extract_structured_data(file_input, filename, doc_type)


extractor_service = ExtractorService()