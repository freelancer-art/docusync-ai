from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str = Field(
        default="Unknown Item", description="Description of item or service"
    )
    quantity: float | None = Field(None, description="Quantity billed")
    unit_price: float | None = Field(None, description="Price per unit")
    total_amount: float = Field(default=0.0, description="Total line item amount")


class TaxInvoiceSchema(BaseModel):
    vendor_name: str | None = Field(
        default="UNKNOWN_VENDOR",
        description="Name of supplier/business issuing invoice",
    )
    vendor_gstin: str | None = Field(
        None, description="GST Identification Number of vendor"
    )
    buyer_name: str | None = Field(None, description="Name of customer/buyer")
    buyer_gstin: str | None = Field(None, description="GSTIN of buyer")
    invoice_number: str | None = Field(
        default="UNKNOWN_INV", description="Invoice identification number"
    )
    invoice_date: str | None = Field(
        default="1970-01-01", description="Date invoice was issued (YYYY-MM-DD)"
    )
    total_amount: float = Field(default=0.0, description="Final total payable amount")
    tax_amount: float | None = Field(
        None, description="Total tax applied (CGST/SGST/IGST)"
    )
    line_items: list[LineItem] = Field(
        default_factory=list, description="List of items/services billed"
    )
