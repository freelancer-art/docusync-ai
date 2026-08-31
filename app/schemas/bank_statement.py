from pydantic import BaseModel, Field


class BankTransaction(BaseModel):
    date: str = Field(description="Transaction date (YYYY-MM-DD or DD/MM/YYYY)")
    description: str = Field(description="Transaction description or narrative")
    reference_number: str | None = Field(
        None, description="UPI/UTR/Cheque/Ref number if available"
    )
    debit: float | None = Field(None, description="Amount debited/withdrawn")
    credit: float | None = Field(None, description="Amount credited/deposited")
    balance: float | None = Field(None, description="Closing balance after transaction")


class BankStatementSchema(BaseModel):
    account_holder_name: str = Field(description="Name of the account holder")
    bank_name: str = Field(description="Name of the bank")
    account_number: str | None = Field(
        None, description="Masked or full account number"
    )
    ifsc_code: str | None = Field(None, description="Bank IFSC code")
    statement_period_start: str | None = Field(
        None, description="Start date of statement period"
    )
    statement_period_end: str | None = Field(
        None, description="End date of statement period"
    )
    opening_balance: float | None = Field(None, description="Opening balance")
    closing_balance: float | None = Field(None, description="Closing balance")
    transactions: list[BankTransaction] = Field(
        default_factory=list, description="List of parsed transactions"
    )
