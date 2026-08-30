import json
from typing import Any
from xml.sax.saxutils import escape

class TallyExporterService:
    """
    Service for converting DocumentRecord instances into
    Tally XML Purchase Voucher import format.
    """

    @classmethod
    def generate_purchase_voucher_xml(cls, record: Any) -> str:
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

        xml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<ENVELOPE>',
            '  <HEADER>',
            '    <TALLYREQUEST>Import Data</TALLYREQUEST>',
            '  </HEADER>',
            '  <BODY>',
            '    <IMPORTDATA>',
            '      <REQUESTDESC>',
            '        <REPORTNAME>Vouchers</REPORTNAME>',
            '      </REQUESTDESC>',
            '      <REQUESTDATA>',
            '        <TALLYMESSAGE xmlns:UDF="TallyUDF">',
            f'          <VOUCHER VCHTYPE="Purchase" ACTION="Create">',
            f'            <DATE>{voucher_date}</DATE>',
            f'            <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>',
            f'            <REFERENCE>{invoice_num}</REFERENCE>',
            f'            <PARTYLEDGERNAME>{vendor_name}</PARTYLEDGERNAME>',
            f'            <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>',
            '            <ALLLEDGERENTRIES.LIST>',
            f'              <LEDGERNAME>{vendor_name}</LEDGERNAME>',
            '              <ISDEEMEDPOSITIVE>NO</ISDEEMEDPOSITIVE>',
            f'              <AMOUNT>{total_amount}</AMOUNT>',
            '            </ALLLEDGERENTRIES.LIST>',
            '            <ALLLEDGERENTRIES.LIST>',
            '              <LEDGERNAME>Purchase Account</LEDGERNAME>',
            '              <ISDEEMEDPOSITIVE>YES</ISDEEMEDPOSITIVE>',
            f'              <AMOUNT>-{total_amount}</AMOUNT>',
            '            </ALLLEDGERENTRIES.LIST>',
            '          </VOUCHER>',
            '        </TALLYMESSAGE>',
            '      </REQUESTDATA>',
            '    </IMPORTDATA>',
            '  </BODY>',
            '</ENVELOPE>'
        ]

        return "\n".join(xml_lines)

tally_exporter = TallyExporterService()