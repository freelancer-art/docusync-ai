from typing import Literal

from pydantic import BaseModel, Field

FlagSeverity = Literal["INFO", "WARNING", "CRITICAL"]


class AuditFlag(BaseModel):
    code: str = Field(
        description="Error or rule code, e.g., INVALID_GSTIN, TAX_MISMATCH"
    )
    field: str = Field(description="Target JSON field being evaluated")
    severity: FlagSeverity = Field(description="Impact level of the detected issue")
    message: str = Field(description="Human-readable explanation of the issue")


class DocumentAuditResult(BaseModel):
    is_valid: bool = Field(description="True if zero CRITICAL flags were raised")
    overall_status: Literal["VERIFIED", "NEEDS_REVIEW", "REJECTED"] = Field(...)
    flags: list[AuditFlag] = Field(
        default_factory=list, description="List of raised rule flags"
    )
