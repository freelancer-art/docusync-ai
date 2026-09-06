from typing import Literal

from pydantic import BaseModel, Field

DocumentCategory = Literal["TAX_INVOICE", "BANK_STATEMENT", "UNKNOWN"]


class DocumentClassification(BaseModel):
    document_type: DocumentCategory = Field(
        description="The classified category of the uploaded document"
    )
    confidence_reasoning: str = Field(
        description="Brief explanation of why this category was selected based on keywords or layout"
    )
    confidence_score: float = Field(ge=0.0, le=1.0)
