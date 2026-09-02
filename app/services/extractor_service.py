import base64
import io
import json
import logging
from typing import Any, List, Optional
from pydantic import BaseModel, Field

import pypdfium2 as pdfium

from app.config import settings
from app.core import ocr_engine
from app.core.groq_client import get_ai_client

logger = logging.getLogger("docusync.extractor")

# ------------------------------------------------------------------
# Explicit Schema Definitions for Structured AI Extraction
# ------------------------------------------------------------------
class LineItem(BaseModel):
    description: Optional[str] = Field(default=None, description="Description of product or service")
    hsn_sac: Optional[str] = Field(default=None, description="HSN or SAC code")
    quantity: Optional[float] = Field(default=0.0, description="Quantity")
    unit_price: Optional[float] = Field(default=0.0, description="Price per unit")
    taxable_amount: Optional[float] = Field(default=0.0, description="Taxable amount before GST")
    gst_rate: Optional[float] = Field(default=0.0, description="GST Rate Percentage (e.g. 18.0)")
    total_amount: Optional[float] = Field(default=0.0, description="Line item total including taxes")


class TaxInvoiceSchema(BaseModel):
    vendor_name: Optional[str] = Field(default=None, description="Legal Name of the Vendor/Supplier")
    vendor_gstin: Optional[str] = Field(default=None, description="15-digit GSTIN of the Vendor")
    customer_name: Optional[str] = Field(default=None, description="Legal Name of the Recipient/Client")
    customer_gstin: Optional[str] = Field(default=None, description="15-digit GSTIN of the Recipient")
    invoice_number: Optional[str] = Field(default=None, description="Invoice or Bill Reference Number")
    invoice_date: Optional[str] = Field(default=None, description="Date of Invoice issuance (YYYY-MM-DD)")
    taxable_amount: Optional[float] = Field(default=0.0, description="Total Taxable Value")
    cgst_amount: Optional[float] = Field(default=0.0, description="Central GST Amount")
    sgst_amount: Optional[float] = Field(default=0.0, description="State GST Amount")
    igst_amount: Optional[float] = Field(default=0.0, description="Integrated GST Amount")
    tax_amount: Optional[float] = Field(default=0.0, description="Total Combined Tax Amount (CGST+SGST or IGST)")
    total_amount: Optional[float] = Field(default=0.0, description="Grand Total Invoice Amount")
    line_items: List[LineItem] = Field(default_factory=list, description="Itemized invoice rows")


class BankStatementSchema(BaseModel):
    bank_name: Optional[str] = Field(default=None, description="Name of the Bank")
    account_number: Optional[str] = Field(default=None, description="Bank Account Number")
    statement_period: Optional[str] = Field(default=None, description="Date Range of Statement")
    opening_balance: Optional[float] = Field(default=0.0, description="Opening Balance")
    closing_balance: Optional[float] = Field(default=0.0, description="Closing Balance")


def convert_pdf_to_images_base64(file_bytes: bytes, max_pages: int = 2) -> List[str]:
    """Renders PDF pages to base64 JPEG strings for Multi-Modal Vision processing."""
    base64_images = []
    try:
        pdf = pdfium.PdfDocument(file_bytes)
        num_pages = min(len(pdf), max_pages)
        for i in range(num_pages):
            page = pdf[i]
            bitmap = page.render(scale=2.0)
            pil_image = bitmap.to_pil()
            buffer = io.BytesIO()
            pil_image.save(buffer, format="JPEG", quality=85)
            img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
            base64_images.append(img_str)
    except Exception as e:
        logger.warning(f"Failed PDF page rendering to Vision base64: {e}")
    return base64_images


def extract_raw_text(file_input: bytes | str, filename: str) -> tuple[str, str, bytes]:
    """Safely reads input bytes and extracts text using available OCR cascades."""
    if isinstance(file_input, str):
        try:
            with open(file_input, "rb") as f:
                file_bytes = f.read()
        except OSError as e:
            logger.error(f"Failed to read file path {file_input}: {e}")
            return "", "FAILED", b""
    else:
        file_bytes = file_input

    stream_or_bytes = io.BytesIO(file_bytes) if isinstance(file_bytes, bytes) else file_bytes

    if hasattr(ocr_engine, "extract_text"):
        try:
            res = ocr_engine.extract_text(stream_or_bytes, filename)
            if isinstance(res, tuple):
                return res[0], res[1], file_bytes
            return res, "pdfplumber_or_ocr", file_bytes
        except Exception as e:
            logger.error(f"OCR engine extraction error: {e}")

    try:
        return file_bytes.decode("utf-8", errors="ignore"), "raw_bytes_fallback", file_bytes
    except Exception:
        return "", "FAILED", file_bytes


def classify_document_text(text: str) -> str:
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
        return "BANK_STATEMENT"
    return "TAX_INVOICE"


def _calculate_confidence_score(extracted_dict: dict[str, Any], extraction_method: str) -> float:
    """Calculates overall extraction confidence score (0.0 to 1.0)."""
    score = 1.0
    if "ocr" in extraction_method.lower():
        score -= 0.15
    elif extraction_method == "raw_bytes_fallback":
        score -= 0.30

    missing_keys = 0
    total_keys = len(extracted_dict) or 1
    for v in extracted_dict.values():
        if v in [None, "", 0.0, "Extracted Vendor", "INV-PENDING"]:
            missing_keys += 1

    field_completeness = 1.0 - (missing_keys / total_keys)
    final_score = round(max(0.0, min(1.0, (score * 0.4) + (field_completeness * 0.6))), 2)
    return final_score


def extract_structured_data(
    file_input: bytes | str,
    filename: str,
    doc_type: str | None = None,
) -> dict:
    """
    AI Vision Pipeline:
    1. Extract text and convert PDF pages into vision images.
    2. Auto-classify document type.
    3. Invoke Vision LLM (Groq / Gemini) via instructor.
    4. Compute complete confidence score and return structured schema.
    """
    raw_text, extraction_method, file_bytes = extract_raw_text(file_input, filename)

    if not doc_type:
        doc_type = classify_document_text(raw_text)

    base64_images = convert_pdf_to_images_base64(file_bytes) if file_bytes else []
    
    client, model_name = get_ai_client()

    if not client:
        fallback = _generate_fallback_extraction(doc_type, filename, raw_text)
        fallback["confidence_score"] = _calculate_confidence_score(fallback, extraction_method)
        fallback["extraction_method"] = extraction_method
        fallback["doc_type"] = doc_type
        return fallback

    target_schema = TaxInvoiceSchema if doc_type == "TAX_INVOICE" else BankStatementSchema

    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert Indian Chartered Accountant and financial document auditor. "
                "Extract structured metadata including Vendor GSTIN, Buyer GSTIN, Invoice Number, Line Items, HSN/SAC, "
                "CGST, SGST, IGST, Tax Amount, and Grand Total Amount. If any field is missing or absent, set it to null."
            ),
        }
    ]

    user_content = []
    if raw_text and raw_text.strip():
        user_content.append({"type": "text", "text": f"Extracted Document Text:\n{raw_text[:4000]}"})
    else:
        user_content.append({"type": "text", "text": f"Analyze attached document image for filename: {filename}"})

    for b64_img in base64_images:
        user_content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"},
            }
        )

    messages.append({"role": "user", "content": user_content})

    try:
        response = client.chat.completions.create(
            model=model_name,
            response_model=target_schema,
            messages=messages,
            temperature=0.0,
        )
        data = json.loads(response.model_dump_json())

        # Ensure tax_amount is computed if missing from individual tax heads
        if doc_type == "TAX_INVOICE":
            cgst = data.get("cgst_amount") or 0.0
            sgst = data.get("sgst_amount") or 0.0
            igst = data.get("igst_amount") or 0.0
            if not data.get("tax_amount"):
                data["tax_amount"] = round(cgst + sgst + igst, 2)
            
            # Alias customer_gstin to buyer_gstin for AuditEngine alignment
            data["buyer_gstin"] = data.get("customer_gstin")
            data["cgst"] = cgst
            data["sgst"] = sgst
            data["igst"] = igst

        data["confidence_score"] = _calculate_confidence_score(data, f"AI_VISION ({model_name})")
        data["extraction_method"] = f"AI_VISION ({model_name})"
        data["doc_type"] = doc_type
        return data
    except Exception as e:
        logger.error(f"LLM Vision extraction error: {e}. Falling back to default parser.")
        fallback = _generate_fallback_extraction(doc_type, filename, raw_text)
        fallback["confidence_score"] = _calculate_confidence_score(fallback, extraction_method)
        fallback["extraction_method"] = extraction_method
        fallback["doc_type"] = doc_type
        return fallback


def _generate_fallback_extraction(doc_type: str, filename: str, text: str) -> dict:
    if doc_type == "TAX_INVOICE":
        return {
            "vendor_name": "Extracted Vendor",
            "vendor_gstin": None,
            "buyer_gstin": None,
            "customer_name": None,
            "customer_gstin": None,
            "invoice_number": "INV-PENDING",
            "invoice_date": None,
            "taxable_amount": 0.0,
            "cgst_amount": 0.0,
            "sgst_amount": 0.0,
            "igst_amount": 0.0,
            "cgst": 0.0,
            "sgst": 0.0,
            "igst": 0.0,
            "tax_amount": 0.0,
            "total_amount": 0.0,
            "line_items": [],
            "raw_text_snippet": text[:200],
        }
    return {
        "bank_name": "Unknown Bank",
        "account_number": "ACC-PENDING",
        "opening_balance": 0.0,
        "closing_balance": 0.0,
        "raw_text_snippet": text[:200],
    }


class ExtractorService:
    def process_document(
        self,
        file_input: bytes | str,
        filename: str,
        doc_type: str | None = None,
    ) -> dict:
        return extract_structured_data(file_input, filename, doc_type)


extractor_service = ExtractorService()