import json
import re
from typing import Any
from sqlmodel import Session, select

from app.core.database import DocumentRecord
from app.core.groq_client import get_ai_client
from app.schemas.verification import AIAnomalyResult, AuditFlag, DocumentAuditResult
from app.services.gstin_validator import gstin_validator

GSTIN_REGEX = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"


class VerificationService:
    @staticmethod
    def audit_tax_invoice(
        invoice_data: dict, session: Session | None = None, current_doc_id: int | None = None
    ) -> DocumentAuditResult:
        flags: list[AuditFlag] = []

        # 1. Vendor GSTIN Format & Checksum Validation
        vendor_gstin = (invoice_data.get("vendor_gstin") or "").strip()
        if not vendor_gstin:
            flags.append(
                AuditFlag(
                    code="MISSING_VENDOR_GSTIN",
                    field="vendor_gstin",
                    severity="WARNING",
                    message="Vendor GSTIN is missing from the invoice.",
                )
            )
        elif not re.match(GSTIN_REGEX, vendor_gstin):
            flags.append(
                AuditFlag(
                    code="INVALID_VENDOR_GSTIN",
                    field="vendor_gstin",
                    severity="CRITICAL",
                    message=f"Vendor GSTIN '{vendor_gstin}' does not match standard GST format.",
                )
            )
        else:
            gstin_res = gstin_validator.verify_gstin(vendor_gstin)
            if not gstin_res.get("valid"):
                flags.append(
                    AuditFlag(
                        code="INVALID_GSTIN_CHECKSUM",
                        field="vendor_gstin",
                        severity="CRITICAL",
                        message=f"Vendor GSTIN '{vendor_gstin}' failed checksum: {gstin_res.get('error')}",
                    )
                )

        # 2. Buyer GSTIN Format Validation
        buyer_gstin = (invoice_data.get("buyer_gstin") or invoice_data.get("customer_gstin") or "").strip()
        if buyer_gstin and not re.match(GSTIN_REGEX, buyer_gstin):
            flags.append(
                AuditFlag(
                    code="INVALID_BUYER_GSTIN",
                    field="buyer_gstin",
                    severity="WARNING",
                    message=f"Buyer GSTIN '{buyer_gstin}' is malformed.",
                )
            )

        # 3. Arithmetic Verification: Taxable + Tax == Total
        taxable_amount = float(invoice_data.get("taxable_amount") or 0.0)
        tax_amount = float(invoice_data.get("tax_amount") or 0.0)
        total_amount = float(invoice_data.get("total_amount") or 0.0)

        if taxable_amount > 0 and total_amount > 0:
            expected_total = taxable_amount + tax_amount
            if abs(expected_total - total_amount) > 1.0:
                flags.append(
                    AuditFlag(
                        code="ARITHMETIC_TOTAL_MISMATCH",
                        field="total_amount",
                        severity="CRITICAL",
                        message=f"Taxable amount ({taxable_amount}) + tax ({tax_amount}) = {expected_total:.2f}, does not match stated total ({total_amount}).",
                    )
                )

        # 4. Tax Structure Alignment (Intra-state CGST+SGST vs Inter-state IGST)
        if vendor_gstin and buyer_gstin and len(vendor_gstin) >= 2 and len(buyer_gstin) >= 2:
            vendor_state = vendor_gstin[:2]
            buyer_state = buyer_gstin[:2]

            cgst = float(invoice_data.get("cgst") or invoice_data.get("cgst_amount") or 0.0)
            sgst = float(invoice_data.get("sgst") or invoice_data.get("sgst_amount") or 0.0)
            igst = float(invoice_data.get("igst") or invoice_data.get("igst_amount") or 0.0)

            if vendor_state == buyer_state:
                if igst > 0 and (cgst == 0 and sgst == 0):
                    flags.append(
                        AuditFlag(
                            code="INTRA_STATE_TAX_MISMATCH",
                            field="igst",
                            severity="CRITICAL",
                            message=f"Same-state transaction (State {vendor_state}) charged IGST ({igst}) instead of CGST + SGST.",
                        )
                    )
            else:
                if (cgst > 0 or sgst > 0) and igst == 0:
                    flags.append(
                        AuditFlag(
                            code="INTER_STATE_TAX_MISMATCH",
                            field="cgst_sgst",
                            severity="CRITICAL",
                            message=f"Inter-state transaction ({vendor_state} -> {buyer_state}) charged CGST/SGST instead of IGST.",
                        )
                    )

        # 5. Line Item Sum Validation
        line_items = invoice_data.get("line_items", [])
        if line_items and isinstance(line_items, list):
            calculated_line_sum = sum(
                float(item.get("total_amount", item.get("taxable_amount", 0.0)))
                for item in line_items
                if isinstance(item, dict)
            )
            if taxable_amount > 0 and abs(calculated_line_sum - taxable_amount) > 1.0 and abs(calculated_line_sum - total_amount) > 1.0:
                flags.append(
                    AuditFlag(
                        code="LINE_ITEM_SUM_MISMATCH",
                        field="line_items",
                        severity="CRITICAL",
                        message=f"Sum of line items ({calculated_line_sum:.2f}) does not equal taxable or total amount.",
                    )
                )

        # 6. Duplicate Billing Detection
        vendor_name = (invoice_data.get("vendor_name") or "").strip()
        invoice_number = (invoice_data.get("invoice_number") or "").strip()

        if session and vendor_name and invoice_number and invoice_number not in ["INV-PENDING", "0", ""]:
            query = select(DocumentRecord).where(
                DocumentRecord.vendor_name == vendor_name,
                DocumentRecord.invoice_number == invoice_number,
            )
            if current_doc_id:
                query = query.where(DocumentRecord.id != current_doc_id)

            duplicates = session.exec(query).all()
            if duplicates:
                dup_ids = ", ".join([f"#{d.id}" for d in duplicates])
                flags.append(
                    AuditFlag(
                        code="DUPLICATE_INVOICE",
                        field="invoice_number",
                        severity="CRITICAL",
                        message=f"Duplicate invoice detected for Vendor '{vendor_name}' & Invoice #{invoice_number} (Matches Record {dup_ids}).",
                    )
                )

        has_critical = any(f.severity == "CRITICAL" for f in flags)
        has_warning = any(f.severity in ["WARNING", "HIGH"] for f in flags)

        if has_critical:
            status = "REJECTED"
        elif has_warning:
            status = "NEEDS_REVIEW"
        else:
            status = "VERIFIED"

        return DocumentAuditResult(
            is_valid=not has_critical, overall_status=status, flags=flags
        )

    @staticmethod
    def audit_with_llm_anomaly_check(invoice_data: dict) -> AIAnomalyResult | None:
        client, model = get_ai_client()
        if not client or model == "NONE":
            return None

        prompt = f"""
        Analyze the following extracted invoice data for potential tax evasion, arithmetic inconsistency, or structural anomalies:
        {json.dumps(invoice_data, indent=2)}
        
        Check specifically for:
        1. Unusually high tax rates or incorrect tax calculations.
        2. Suspicious vendor names or placeholder values.
        3. Taxable vs total mismatches.
        """

        try:
            response = client.chat.completions.create(
                model=model,
                response_model=AIAnomalyResult,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            return response
        except Exception:
            return None


verification_service = VerificationService()