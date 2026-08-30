from pydantic import BaseModel, Field
from typing import List, Optional

class LineItem(BaseModel):
    description: str = Field(description="Description of item or service")
    quantity: Optional[float] = Field(None, description="Quantity billed")
    unit_price: Optional[float] = Field(None, description="Price per unit")
    total_amount: float = Field(description="Total line item amount")

class TaxInvoiceSchema(BaseModel):
    vendor_name: str = Field(description="Name of supplier/business issuing invoice")
    vendor_gstin: Optional[str] = Field(None, description="GST Identification Number of vendor")
    buyer_name: Optional[str] = Field(None, description="Name of customer/buyer")
    buyer_gstin: Optional[str] = Field(None, description="GSTIN of buyer")
    invoice_number: str = Field(description="Invoice identification number")
    invoice_date: str = Field(description="Date invoice was issued (YYYY-MM-DD)")
    total_amount: float = Field(description="Final total payable amount")
    tax_amount: Optional[float] = Field(None, description="Total tax applied (CGST/SGST/IGST)")
    line_items: List[LineItem] = Field(default_factory=list, description="List of items/services billed")