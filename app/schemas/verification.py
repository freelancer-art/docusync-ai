from typing import Literal

from pydantic import BaseModel, Field

FlagSeverity = Literal["INFO", "LOW", "MEDIUM", "HIGH", "WARNING", "CRITICAL"]


class AuditFlag(BaseModel):
    code: str = Field(
        description="Error or rule code, e.g., INVALID_GSTIN, TAX_MISMATCH, DUPLICATE_INVOICE"
    )
    field: str = Field(description="Target JSON field being evaluated")
    severity: FlagSeverity = Field(description="Impact level of the detected issue")
    message: str = Field(description="Human-readable explanation of the issue")


class DocumentAuditResult(BaseModel):
    is_valid: bool = Field(description="True if zero CRITICAL or HIGH flags were raised")
    overall_status: Literal["VERIFIED", "NEEDS_REVIEW", "REJECTED"] = Field(...)
    flags: list[AuditFlag] = Field(
        default_factory=list, description="List of raised rule flags"
    )


class AIAnomalyResult(BaseModel):
    has_anomalies: bool = Field(
        description="True if LLM detected suspicious pattern or inconsistency"
    )
    anomaly_summary: str = Field(
        description="Brief summary of potential accounting or compliance anomalies"
    )
    suggested_status: Literal["VERIFIED", "NEEDS_REVIEW", "REJECTED"] = Field(...)
    detected_flags: list[AuditFlag] = Field(
        default_factory=list, description="AI-detected flag objects"
    )