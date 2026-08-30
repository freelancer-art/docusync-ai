from pydantic import BaseModel, Field
from typing import List, Optional

class BankTransaction(BaseModel):
    date: str = Field(description="Transaction date (YYYY-MM-DD or DD/MM/YYYY)")
    description: str = Field(description="Transaction description or narrative")
    reference_number: Optional[str] = Field(None, description="UPI/UTR/Cheque/Ref number if available")
    debit: Optional[float] = Field(None, description="Amount debited/withdrawn")
    credit: Optional[float] = Field(None, description="Amount credited/deposited")
    balance: Optional[float] = Field(None, description="Closing balance after transaction")

class BankStatementSchema(BaseModel):
    account_holder_name: str = Field(description="Name of the account holder")
    bank_name: str = Field(description="Name of the bank")
    account_number: Optional[str] = Field(None, description="Masked or full account number")
    ifsc_code: Optional[str] = Field(None, description="Bank IFSC code")
    statement_period_start: Optional[str] = Field(None, description="Start date of statement period")
    statement_period_end: Optional[str] = Field(None, description="End date of statement period")
    opening_balance: Optional[float] = Field(None, description="Opening balance")
    closing_balance: Optional[float] = Field(None, description="Closing balance")
    transactions: List[BankTransaction] = Field(default_factory=list, description="List of parsed transactions")