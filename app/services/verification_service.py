import re

from app.schemas.verification import AuditFlag, DocumentAuditResult
from app.services.gstin_validator import gstin_validator

# Standard Indian GSTIN Regex Pattern
GSTIN_REGEX = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"


class VerificationService:
    @staticmethod
    def audit_tax_invoice(invoice_data: dict) -> DocumentAuditResult:
        flags = []

        # 1. Vendor GSTIN Validation
        vendor_gstin = invoice_data.get("vendor_gstin")
        if not vendor_gstin:
            flags.append(
                AuditFlag(
                    code="MISSING_VENDOR_GSTIN",
                    field="vendor_gstin",
                    severity="WARNING",
                    message="Vendor GSTIN is missing from the invoice.",
                )
            )
        elif not re.match(GSTIN_REGEX, vendor_gstin.strip()):
            flags.append(
                AuditFlag(
                    code="INVALID_VENDOR_GSTIN",
                    field="vendor_gstin",
                    severity="CRITICAL",
                    message=f"Vendor GSTIN '{vendor_gstin}' does not match standard GST format.",
                )
            )

        # 2. Buyer GSTIN Validation (if provided)
        buyer_gstin = invoice_data.get("buyer_gstin")
        if buyer_gstin and not re.match(GSTIN_REGEX, buyer_gstin.strip()):
            flags.append(
                AuditFlag(
                    code="INVALID_BUYER_GSTIN",
                    field="buyer_gstin",
                    severity="WARNING",
                    message=f"Buyer GSTIN '{buyer_gstin}' is malformed.",
                )
            )

        # 3. Line Items vs Subtotal Mathematical Audit
        line_items = invoice_data.get("line_items", [])
        if line_items:
            calculated_line_total = sum(
                item.get("total_amount", 0.0) for item in line_items
            )
            total_amount = invoice_data.get("total_amount", 0.0)
            tax_amount = invoice_data.get("tax_amount", 0.0) or 0.0

            # Check if sum of line items aligns with stated total (accounting for tax)
            expected_total = calculated_line_total + tax_amount
            if abs(expected_total - total_amount) > 1.0:  # 1 INR tolerance threshold
                flags.append(
                    AuditFlag(
                        code="LINE_ITEM_SUM_MISMATCH",
                        field="total_amount",
                        severity="CRITICAL",
                        message=f"Sum of line items ({calculated_line_total}) + tax ({tax_amount}) does not equal total amount ({total_amount}).",
                    )
                )

        # Determine Overall Status
        has_critical = any(f.severity == "CRITICAL" for f in flags)
        has_warning = any(f.severity == "WARNING" for f in flags)

        if has_critical:
            status = "REJECTED"
        elif has_warning:
            status = "NEEDS_REVIEW"
        else:
            status = "VERIFIED"

        return DocumentAuditResult(
            is_valid=not has_critical, overall_status=status, flags=flags
        )

    def audit_document(raw_json: dict) -> list[dict]:
        flags = []

        vendor_gstin = raw_json.get("vendor_gstin")
        if vendor_gstin:
            gstin_res = gstin_validator.verify_gstin(vendor_gstin)

            if not gstin_res["valid"]:
                flags.append(
                    {
                        "code": "INVALID_GSTIN_CHECKSUM",
                        "severity": "HIGH",
                        "message": f"Vendor GSTIN '{vendor_gstin}' failed checksum validation: {gstin_res['error']}",
                    }
                )
            elif gstin_res["registration_status"] != "ACTIVE":
                flags.append(
                    {
                        "code": "GSTIN_INACTIVE",
                        "severity": "HIGH",
                        "message": f"Vendor GSTIN '{vendor_gstin}' registration is flagged as {gstin_res['registration_status']}.",
                    }
                )

        return flags


verification_service = VerificationService()
