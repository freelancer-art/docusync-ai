import json
import pandas as pd
from typing import List, Dict, Any

class ZohoExporterService:
    DEFAULT_ACCOUNT_HEAD = "Cost of Goods Sold"
    DEFAULT_ITEM_NAME = "General Purchase"

    @staticmethod
    def sanitize_csv_field(value: Any) -> Any:
        if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
            return f"'{value}"
        return value

    @staticmethod
    def generate_bills_csv(records: List[Any]) -> bytes:
        rows: List[Dict[str, Any]] = []

        for rec in records:
            raw_data = {}
            raw_str = getattr(rec, "raw_json_data", None)
            if raw_str:
                try:
                    parsed = json.loads(raw_str)
                    if isinstance(parsed, dict):
                        raw_data = parsed
                except (json.JSONDecodeError, TypeError):
                    raw_data = {}

            line_items = raw_data.get("line_items", []) if isinstance(raw_data, dict) else []
            
            created_at = getattr(rec, "created_at", None)
            bill_date = created_at.strftime("%Y-%m-%d") if created_at else ""
            due_date = bill_date

            vendor_name = ZohoExporterService.sanitize_csv_field(getattr(rec, "vendor_name", None) or "Unassigned Vendor")
            
            rec_id = getattr(rec, "id", None)
            if rec_id is None:
                rec_id = "0"

            invoice_no = getattr(rec, "invoice_number", None)
            bill_number = ZohoExporterService.sanitize_csv_field(invoice_no if invoice_no else f"BILL-{rec_id}")
            vendor_gstin = ZohoExporterService.sanitize_csv_field(raw_data.get("vendor_gstin", raw_data.get("gstin", "")))
            
            try:
                total_amount = float(getattr(rec, "total_amount", 0.0) or 0.0)
            except (ValueError, TypeError):
                total_amount = 0.0

            if line_items and isinstance(line_items, list):
                for item in line_items:
                    if not isinstance(item, dict):
                        continue

                    desc = ZohoExporterService.sanitize_csv_field(item.get("description", ZohoExporterService.DEFAULT_ITEM_NAME))
                    
                    try:
                        qty = float(item.get("quantity", 1))
                    except (ValueError, TypeError):
                        qty = 1.0

                    try:
                        rate = float(item.get("unit_price", item.get("amount", total_amount)))
                    except (ValueError, TypeError):
                        rate = total_amount

                    try:
                        amount = float(item.get("amount", qty * rate))
                    except (ValueError, TypeError):
                        amount = qty * rate

                    try:
                        tax_rate = float(item.get("tax_rate", 0))
                    except (ValueError, TypeError):
                        tax_rate = 0.0

                    rows.append({
                        "Vendor Name": vendor_name,
                        "Vendor GSTIN": vendor_gstin,
                        "Bill Number": bill_number,
                        "Bill Date": bill_date,
                        "Due Date": due_date,
                        "Account": ZohoExporterService.DEFAULT_ACCOUNT_HEAD,
                        "Item Name": desc,
                        "Item Description": desc,
                        "Quantity": qty,
                        "Rate": rate,
                        "Item Total": amount,
                        "Tax Percentage": tax_rate,
                        "Currency Code": "INR"
                    })
            else:
                desc = ZohoExporterService.sanitize_csv_field(f"Invoice #{bill_number}")
                rows.append({
                    "Vendor Name": vendor_name,
                    "Vendor GSTIN": vendor_gstin,
                    "Bill Number": bill_number,
                    "Bill Date": bill_date,
                    "Due Date": due_date,
                    "Account": ZohoExporterService.DEFAULT_ACCOUNT_HEAD,
                    "Item Name": ZohoExporterService.DEFAULT_ITEM_NAME,
                    "Item Description": desc,
                    "Quantity": 1,
                    "Rate": total_amount,
                    "Item Total": total_amount,
                    "Tax Percentage": 0,
                    "Currency Code": "INR"
                })

        df = pd.DataFrame(rows)
        return df.to_csv(index=False).encode("utf-8")

zoho_exporter = ZohoExporterService()