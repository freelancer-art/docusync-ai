from pydantic import BaseModel, Field
from typing import Literal

DocumentCategory = Literal["tax_invoice", "bank_statement", "pan_card", "unknown"]

class DocumentClassification(BaseModel):
    document_type: DocumentCategory = Field(
        description="The classified category of the uploaded document"
    )
    confidence_reasoning: str = Field(
        description="Brief explanation of why this category was selected based on keywords or layout"
    )