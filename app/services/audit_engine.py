import json
from typing import Any

from sqlmodel import Session

from app.core.database import DocumentRecord

# Mapping of standard Indian GST State Codes (First 2 digits of GSTIN)
GST_STATE_CODES = {
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "25": "Daman and Diu",
    "26": "Dadra and Nagar Haveli",
    "27": "Maharashtra",
    "28": "Andhra Pradesh (Old)",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
}


class AuditEngine:
    """Evaluates raw invoice extraction data against CA audit rules."""

    @staticmethod
    def evaluate_document(doc: DocumentRecord) -> dict[str, Any]:
        flags: list[str] = []
        raw_data: dict[str, Any] = {}

        if doc.raw_json_data:
            try:
                raw_data = json.loads(doc.raw_json_data)
            except (json.JSONDecodeError, TypeError):
                flags.append("CORRUPTED_RAW_JSON")

        # 1. Standard Metadata Checks
        if not doc.total_amount or doc.total_amount <= 0:
            flags.append("MISSING_TOTAL_AMOUNT")

        if not doc.vendor_name or doc.vendor_name.strip().lower() in [
            "unassigned vendor",
            "unknown",
            "unknown_vendor",
        ]:
            flags.append("UNVERIFIED_VENDOR")

        if not doc.invoice_number or doc.invoice_number.strip().lower() in [
            "unknown_inv",
            "",
        ]:
            flags.append("MISSING_INVOICE_NUMBER")

        # Extract structured GST and financial fields
        vendor_gstin = raw_data.get("vendor_gstin")
        buyer_gstin = raw_data.get("buyer_gstin")
        tax_amount = raw_data.get("tax_amount")
        line_items = raw_data.get("line_items", [])

        # 2. Line Item Arithmetic Validation
        if line_items and isinstance(line_items, list):
            calculated_items_total = 0.0
            for idx, item in enumerate(line_items):
                if not isinstance(item, dict):
                    continue
                qty = item.get("quantity")
                unit_price = item.get("unit_price")
                item_total = item.get("total_amount", 0.0)

                # Check if Qty * Unit Price matches Line Total
                if qty is not None and unit_price is not None:
                    expected_item_total = round(float(qty) * float(unit_price), 2)
                    if abs(expected_item_total - float(item_total)) > 0.05:
                        flags.append(f"LINE_ITEM_MATH_DISCREPANCY_INDEX_{idx}")

                calculated_items_total += float(item_total)

            # Check if Sum of Line Items matches Subtotal/Total Amount
            if doc.total_amount and doc.total_amount > 0 and calculated_items_total > 0:
                # Account for tax when comparing line totals to total_amount
                expected_total = calculated_items_total + (
                    float(tax_amount) if tax_amount else 0.0
                )
                if abs(expected_total - float(doc.total_amount)) > 0.50:
                    flags.append("SUM_LINE_ITEMS_MISMATCH")

        # 3. GSTIN State Alignment Check (Intra-state vs Inter-state)
        if vendor_gstin and buyer_gstin:
            vendor_state_code = vendor_gstin[:2]
            buyer_state_code = buyer_gstin[:2]

            if vendor_state_code.isdigit() and buyer_state_code.isdigit():
                is_intra_state = vendor_state_code == buyer_state_code

                # Verify if state codes exist in standard GST list
                if vendor_state_code not in GST_STATE_CODES:
                    flags.append("INVALID_VENDOR_GSTIN_STATE_CODE")
                if buyer_state_code not in GST_STATE_CODES:
                    flags.append("INVALID_BUYER_GSTIN_STATE_CODE")

                # Check tax structure alignment if tax details are provided
                cgst = raw_data.get("cgst")
                sgst = raw_data.get("sgst")
                igst = raw_data.get("igst")

                if is_intra_state and igst and float(igst) > 0 and not (cgst or sgst):
                    flags.append("INTRA_STATE_TAX_TYPE_MISMATCH")  # Should be CGST+SGST
                elif (
                    not is_intra_state
                    and ((cgst and float(cgst) > 0) or (sgst and float(sgst) > 0))
                    and not igst
                ):
                    flags.append("INTER_STATE_TAX_TYPE_MISMATCH")  # Should be IGST

        # 4. Tax Amount Math Validation
        if (
            tax_amount is not None
            and doc.total_amount
            and doc.total_amount > 0
            and float(tax_amount) >= float(doc.total_amount)
        ):
            flags.append("TAX_AMOUNT_EXCEEDS_TOTAL")

        # Determine overall review status
        overall_status = "NEEDS_REVIEW" if flags else "VERIFIED"

        return {"status": overall_status, "flags": flags}


def process_document_audit(doc: DocumentRecord, session: Session) -> DocumentRecord:
    """Worker function to run audit checks and update the database record."""
    results = AuditEngine.evaluate_document(doc)
    doc.overall_status = results["status"]
    doc.audit_flags_json = json.dumps(results["flags"])

    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc