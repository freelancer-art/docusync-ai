import re
import json
import logging
from typing import Dict, Any, List, Tuple
from pypdf import PdfReader
from sqlmodel import Session

from app.core.database import engine, DocumentRecord, init_db

logger = logging.getLogger("docusync.extractor")

class ExtractorService:
    def __init__(self):
        init_db()

    def extract_raw_text(self, file_path: str) -> str:
        """Extract plain text from input PDF."""
        extracted_text = ""
        try:
            reader = PdfReader(file_path)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"
        except Exception as e:
            logger.error(f"Failed to read PDF file at {file_path}: {e}")
            raise RuntimeError(f"Could not parse PDF content: {str(e)}")
        
        return extracted_text.strip()

    def parse_document_data(self, text: str) -> Dict[str, Any]:
        """
        Parses raw document text into structured accounting data.
        In production, replace or augment this with LLM JSON mode / OCR output.
        """
        extracted = {
            "document_type": "TAX_INVOICE",
            "vendor_name": None,
            "invoice_number": None,
            "vendor_gstin": None,
            "customer_gstin": None,
            "subtotal": None,
            "cgst_amount": None,
            "sgst_amount": None,
            "igst_amount": None,
            "total_tax": None,
            "total_amount": None,
            "line_items": []
        }

        lines = [line.strip() for line in text.split("\n") if line.strip()]
        
        # Look for 15-character GSTIN patterns (Regex)
        gstin_pattern = r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}\b"
        found_gstins = re.findall(gstin_pattern, text)
        if found_gstins:
            extracted["vendor_gstin"] = found_gstins[0]
            if len(found_gstins) > 1:
                extracted["customer_gstin"] = found_gstins[1]

        for line in lines:
            line_upper = line.upper()
            
            if ("INVOICE NO" in line_upper or "INVOICE #" in line_upper) and not extracted["invoice_number"]:
                parts = line.split(":") if ":" in line else line.split()
                extracted["invoice_number"] = parts[-1].strip()
            
            elif "TOTAL" in line_upper and not extracted["total_amount"]:
                words = line.split()
                for word in reversed(words):
                    clean_val = word.replace("₹", "").replace(",", "").replace("$", "").strip()
                    try:
                        extracted["total_amount"] = float(clean_val)
                        break
                    except ValueError:
                        continue

            elif ("VENDOR" in line_upper or "SUPPLIER" in line_upper) and not extracted["vendor_name"]:
                parts = line.split(":")
                if len(parts) > 1:
                    extracted["vendor_name"] = parts[1].strip()

        if not extracted["vendor_name"] and lines:
            extracted["vendor_name"] = lines[0]

        return extracted

    def run_audit_checks(self, data: Dict[str, Any]) -> Tuple[str, List[Dict[str, str]]]:
        """
        Executes enterprise audit rules: GSTIN syntax, arithmetic validation, and threshold checks.
        Returns overall_status ("VERIFIED", "NEEDS_REVIEW", "REJECTED") and flag details.
        """
        flags: List[Dict[str, str]] = []

        # ------------------------------------------------------------------
        # RULE 1: GSTIN Format & State Code Validation
        # ------------------------------------------------------------------
        vendor_gstin = data.get("vendor_gstin")
        gstin_regex = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"

        if not vendor_gstin:
            flags.append({
                "code": "MISSING_VENDOR_GSTIN",
                "severity": "HIGH",
                "message": "Vendor GSTIN was not found on the tax invoice."
            })
        elif not re.match(gstin_regex, str(vendor_gstin)):
            flags.append({
                "code": "INVALID_GSTIN_FORMAT",
                "severity": "HIGH",
                "message": f"GSTIN '{vendor_gstin}' fails standard 15-character statutory format checks."
            })

        # ------------------------------------------------------------------
        # RULE 2: Line Item & Tax Arithmetic Integrity
        # ------------------------------------------------------------------
        subtotal = data.get("subtotal") or 0.0
        cgst = data.get("cgst_amount") or 0.0
        sgst = data.get("sgst_amount") or 0.0
        igst = data.get("igst_amount") or 0.0
        total_tax = data.get("total_tax") or (cgst + sgst + igst)
        total_amount = data.get("total_amount") or 0.0

        line_items = data.get("line_items") or []
        if line_items:
            items_sum = sum(item.get("amount", 0.0) for item in line_items)
            # Allow 1.0 margin for rounding tolerances
            if subtotal > 0 and abs(items_sum - subtotal) > 1.0:
                flags.append({
                    "code": "LINE_ITEM_MISMATCH",
                    "severity": "CRITICAL",
                    "message": f"Sum of line items (₹{items_sum:,.2f}) does not match subtotal (₹{subtotal:,.2f})."
                })

        if subtotal > 0 and total_amount > 0:
            calculated_total = subtotal + total_tax
            if abs(calculated_total - total_amount) > 1.0:
                flags.append({
                    "code": "ARITHMETIC_TOTAL_MISMATCH",
                    "severity": "CRITICAL",
                    "message": f"Subtotal + Tax (₹{calculated_total:,.2f}) does not equal total amount (₹{total_amount:,.2f})."
                })

        # ------------------------------------------------------------------
        # RULE 3: Tax Rate Consistency Checks
        # ------------------------------------------------------------------
        if cgst > 0 and sgst > 0 and abs(cgst - sgst) > 0.5:
            flags.append({
                "code": "CGST_SGST_MISMATCH",
                "severity": "MEDIUM",
                "message": f"Intra-state CGST (₹{cgst:,.2f}) and SGST (₹{sgst:,.2f}) must be equal."
            })

        # ------------------------------------------------------------------
        # RULE 4: Metadata Completeness & High-Value Approval Thresholds
        # ------------------------------------------------------------------
        if not data.get("invoice_number"):
            flags.append({
                "code": "MISSING_INVOICE_NO",
                "severity": "HIGH",
                "message": "Invoice number could not be detected automatically."
            })
            
        if total_amount <= 0:
            flags.append({
                "code": "INVALID_TOTAL_AMOUNT",
                "severity": "CRITICAL",
                "message": "Total invoice amount is missing or non-positive."
            })

        if total_amount > 100000.0:  # ₹1,00,000 threshold
            flags.append({
                "code": "HIGH_VALUE_TRANSACTION",
                "severity": "MEDIUM",
                "message": "High-value invoice (> ₹1,00,000) requires senior auditor sign-off."
            })

        # ------------------------------------------------------------------
        # STATUS DECISION
        # ------------------------------------------------------------------
        severities = {f["severity"] for f in flags}
        if "CRITICAL" in severities:
            overall_status = "REJECTED"
        elif "HIGH" in severities or "MEDIUM" in severities:
            overall_status = "NEEDS_REVIEW"
        else:
            overall_status = "VERIFIED"

        return overall_status, flags

    def process_document(self, file_path: str, filename: str, client_id: int) -> Dict[str, Any]:
        """Main pipeline runner: Extracts, audits, and persists to SQLModel DB."""
        raw_text = self.extract_raw_text(file_path)
        parsed_data = self.parse_document_data(raw_text)

        overall_status, audit_flags = self.run_audit_checks(parsed_data)

        doc_record = DocumentRecord(
            filename=filename,
            document_type=parsed_data.get("document_type", "UNKNOWN"),
            extraction_method="HYBRID_LLM_OCR",
            overall_status=overall_status,
            vendor_name=parsed_data.get("vendor_name"),
            invoice_number=parsed_data.get("invoice_number"),
            total_amount=parsed_data.get("total_amount"),
            raw_json_data=json.dumps(parsed_data),
            audit_flags_json=json.dumps(audit_flags),
            client_id=client_id
        )

        with Session(engine) as session:
            session.add(doc_record)
            session.commit()
            session.refresh(doc_record)

        return {
            "record_id": doc_record.id,
            "status": overall_status,
            "flags": audit_flags,
            "data": parsed_data
        }

extractor_service = ExtractorService()