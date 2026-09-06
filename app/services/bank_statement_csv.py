"""CSV bank-statement normalization with aliases, validation, and row-level errors."""

import csv
import io
import re
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class NormalizedBankTransaction(BaseModel):
    """One normalized bank transaction with a signed net amount."""

    source_row: int
    date: str
    description: str
    reference_number: str | None = None
    debit: float | None = None
    credit: float | None = None
    amount: float
    balance: float | None = None


class BankStatementRowError(BaseModel):
    """A row-level normalization error retained for CA review."""

    source_row: int
    field: str
    message: str
    raw_row: dict[str, Any] = Field(default_factory=dict)


class CSVBankStatementResult(BaseModel):
    """Normalized CSV output and non-fatal malformed-row reports."""

    source_filename: str
    delimiter: str
    transactions: list[NormalizedBankTransaction] = Field(default_factory=list)
    errors: list[BankStatementRowError] = Field(default_factory=list)
    total_rows: int


_COLUMN_ALIASES = {
    "date": {"date", "transaction date", "txn date", "value date", "posting date"},
    "description": {
        "description",
        "narration",
        "particulars",
        "details",
        "transaction details",
        "remarks",
    },
    "reference": {
        "reference",
        "reference number",
        "ref no",
        "ref number",
        "utr",
        "utr number",
        "cheque number",
        "check number",
    },
    "debit": {"debit", "debit amount", "withdrawal", "withdrawals", "dr"},
    "credit": {"credit", "credit amount", "deposit", "deposits", "cr"},
    "amount": {"amount", "transaction amount", "value", "net amount"},
    "balance": {"balance", "closing balance", "running balance", "available balance"},
    "type": {"type", "transaction type", "dr cr", "debit credit"},
}


def _normal_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.strip().lower()).strip()


def _find_columns(headers: list[str]) -> dict[str, str]:
    normalized = {_normal_header(header): header for header in headers if header}
    columns = {}
    for target, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                columns[target] = normalized[alias]
                break
    return columns


def _parse_date(value: str) -> str:
    candidate = value.strip()
    for date_format in (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%d/%m/%y",
        "%d-%m-%y",
    ):
        try:
            return (
                datetime.strptime(candidate, date_format)
                .replace(tzinfo=timezone.utc)
                .date()
                .isoformat()
            )
        except ValueError:
            continue
    raise ValueError("date must use YYYY-MM-DD, DD/MM/YYYY, or a supported date format")


def _parse_amount(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    candidate = value.strip().replace("₹", "").replace("Rs.", "").replace("Rs", "")
    candidate = candidate.replace(",", "").replace(" ", "")
    negative = candidate.startswith("(") and candidate.endswith(")")
    candidate = candidate.strip("()")
    try:
        amount = float(candidate)
    except ValueError as exc:
        raise ValueError(f"invalid numeric amount: {value!r}") from exc
    return -abs(amount) if negative else amount


def _value(row: dict[str, Any], columns: dict[str, str], key: str) -> str:
    column = columns.get(key)
    return str(row.get(column, "") or "").strip() if column else ""


def normalize_bank_statement_csv(
    content: bytes, source_filename: str = "statement.csv"
) -> CSVBankStatementResult:
    """Normalize common bank CSV layouts without discarding malformed rows."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV bank statements must be valid UTF-8 text.") from exc
    if not text.strip():
        raise ValueError("CSV bank statement is empty.")

    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    headers = reader.fieldnames or []
    columns = _find_columns(headers)
    missing = [name for name in ("date",) if name not in columns]
    if "amount" not in columns and not ({"debit", "credit"} & columns.keys()):
        missing.append("amount or debit/credit")
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing)}")

    transactions = []
    errors = []
    total_rows = 0
    for row_number, row in enumerate(reader, start=2):
        total_rows += 1
        try:
            date = _parse_date(_value(row, columns, "date"))
            description = _value(row, columns, "description") or "Unlabeled transaction"
            debit = _parse_amount(_value(row, columns, "debit"))
            credit = _parse_amount(_value(row, columns, "credit"))
            amount = _parse_amount(_value(row, columns, "amount"))
            transaction_type = _value(row, columns, "type").lower()

            if debit is not None and debit < 0:
                debit = abs(debit)
            if credit is not None and credit < 0:
                credit = abs(credit)
            if debit is not None or credit is not None:
                amount = (credit or 0.0) - (debit or 0.0)
            elif amount is None:
                raise ValueError("an amount or debit/credit value is required")
            elif transaction_type in {"debit", "dr", "withdrawal", "withdraw"}:
                amount = -abs(amount)
            elif transaction_type in {"credit", "cr", "deposit"}:
                amount = abs(amount)

            transactions.append(
                NormalizedBankTransaction(
                    source_row=row_number,
                    date=date,
                    description=description,
                    reference_number=_value(row, columns, "reference") or None,
                    debit=debit,
                    credit=credit,
                    amount=round(amount, 2),
                    balance=_parse_amount(_value(row, columns, "balance")),
                )
            )
        except ValueError as exc:
            field = "date" if "date" in str(exc) else "amount"
            errors.append(
                BankStatementRowError(
                    source_row=row_number,
                    field=field,
                    message=str(exc),
                    raw_row=dict(row),
                )
            )

    return CSVBankStatementResult(
        source_filename=source_filename,
        delimiter=delimiter,
        transactions=transactions,
        errors=errors,
        total_rows=total_rows,
    )
