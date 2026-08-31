import json
from typing import Any, List
from xml.sax.saxutils import escape

class TallyExporterService:
    @staticmethod
    def generate_purchase_voucher_xml(record: Any) -> str:
        raw_data = {}
        raw_str = getattr(record, "raw_json_data", None)
        if raw_str:
            try:
                raw_data = json.loads(raw_str)
            except (json.JSONDecodeError, TypeError):
                raw_data = {}

        vendor_name = escape(getattr(record, "vendor_name", None) or "Unassigned Vendor")
        rec_id = getattr(record, "id", "0")
        invoice_num = escape(getattr(record, "invoice_number", None) or f"INV-{rec_id}")
        total_amount = getattr(record, "total_amount", 0.0) or 0.0

        created_at = getattr(record, "created_at", None)
        voucher_date = created_at.strftime("%Y%m%d") if created_at else "20260101"

        return f"""          <VOUCHER VCHTYPE="Purchase" ACTION="Create">
            <DATE>{voucher_date}</DATE>
            <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
            <REFERENCE>{invoice_num}</REFERENCE>
            <PARTYLEDGERNAME>{vendor_name}</PARTYLEDGERNAME>
            <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
            <ALLLEDGERENTRIES.LIST>
              <LEDGERNAME>{vendor_name}</LEDGERNAME>
              <ISDEEMEDPOSITIVE>NO</ISDEEMEDPOSITIVE>
              <AMOUNT>{total_amount}</AMOUNT>
            </ALLLEDGERENTRIES.LIST>
            <ALLLEDGERENTRIES.LIST>
              <LEDGERNAME>Purchase Account</LEDGERNAME>
              <ISDEEMEDPOSITIVE>YES</ISDEEMEDPOSITIVE>
              <AMOUNT>-{total_amount}</AMOUNT>
            </ALLLEDGERENTRIES.LIST>
          </VOUCHER>"""

    @classmethod
    def generate_vouchers_xml(cls, records: List[Any]) -> str:
        vouchers = [cls.generate_purchase_voucher_xml(rec) for rec in records]
        vouchers_str = "\n".join(vouchers)

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<ENVELOPE>
  <HEADER>
    <TALLYREQUEST>Import Data</TALLYREQUEST>
  </HEADER>
  <BODY>
    <IMPORTDATA>
      <REQUESTDESC>
        <REPORTNAME>Vouchers</REPORTNAME>
      </REQUESTDESC>
      <REQUESTDATA>
        <TALLYMESSAGE xmlns:UDF="TallyUDF">
{vouchers_str}
        </TALLYMESSAGE>
      </REQUESTDATA>
    </IMPORTDATA>
  </BODY>
</ENVELOPE>"""

tally_exporter = TallyExporterService()