from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str = Field(description="Description of the item or service")
    quantity: float = Field(default=1.0, description="Quantity of item")
    unit_price: float = Field(default=0.0, description="Price per unit before tax")
    amount: float = Field(default=0.0, description="Total amount for this line item")


class ExtractedInvoiceData(BaseModel):
    document_type: str = Field(
        default="TAX_INVOICE",
        description="Type of document, e.g., TAX_INVOICE, PURCHASE_ORDER, RECEIPT",
    )
    vendor_name: str | None = Field(None, description="Name of the seller or vendor")
    vendor_gstin: str | None = Field(
        None, description="15-digit GSTIN of the vendor if applicable"
    )
    invoice_number: str | None = Field(None, description="Unique invoice identifier")
    invoice_date: str | None = Field(
        None, description="Invoice date in YYYY-MM-DD format"
    )
    subtotal: float = Field(default=0.0, description="Subtotal amount before taxes")
    cgst_amount: float = Field(default=0.0, description="CGST amount in INR")
    sgst_amount: float = Field(default=0.0, description="SGST amount in INR")
    igst_amount: float = Field(default=0.0, description="IGST amount in INR")
    total_amount: float = Field(default=0.0, description="Final total payable amount")
    line_items: list[LineItem] = Field(
        default_factory=list, description="Itemized list of products/services"
    )
