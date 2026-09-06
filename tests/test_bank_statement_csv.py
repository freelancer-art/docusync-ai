from unittest.mock import patch

import pytest

from app.services.bank_statement_csv import normalize_bank_statement_csv
from app.services.extractor_service import extract_structured_data

VALID_CSV = """Txn Date,Narration,UTR,Debit,Credit,Running Balance
01/09/2026,Vendor payment,UTR-1,"1,200.00",,8800.00
2026-09-02,Customer receipt,UTR-2,,2500,11300.00
"""


def test_normalize_bank_csv_aliases_dates_and_signed_amounts():
    result = normalize_bank_statement_csv(VALID_CSV.encode(), "bank.csv")

    assert result.total_rows == 2
    assert result.errors == []
    assert result.delimiter == ","
    assert result.transactions[0].date == "2026-09-01"
    assert result.transactions[0].reference_number == "UTR-1"
    assert result.transactions[0].debit == 1200.0
    assert result.transactions[0].amount == -1200.0
    assert result.transactions[1].credit == 2500.0
    assert result.transactions[1].amount == 2500.0
    assert result.transactions[1].balance == 11300.0


def test_normalize_amount_column_uses_transaction_type_sign():
    content = b"date,description,type,amount\n03/09/2026,ATM withdrawal,DR,500\n"

    result = normalize_bank_statement_csv(content)

    assert result.transactions[0].amount == -500.0
    assert result.transactions[0].debit is None
    assert result.transactions[0].credit is None


def test_normalize_reports_bad_rows_without_discarding_valid_rows():
    content = (
        b"date,description,amount\n"
        b"2026-09-01,Valid,100\n"
        b"not-a-date,Bad date,200\n"
        b"2026-09-03,Bad amount,not-number\n"
    )

    result = normalize_bank_statement_csv(content)

    assert len(result.transactions) == 1
    assert [error.source_row for error in result.errors] == [3, 4]
    assert result.errors[0].field == "date"
    assert result.errors[1].field == "amount"
    assert result.errors[1].raw_row["description"] == "Bad amount"


def test_normalize_rejects_missing_required_headers():
    with pytest.raises(ValueError, match="missing required columns"):
        normalize_bank_statement_csv(b"description\nOnly text\n")


@patch("app.services.extractor_service.get_ai_client")
def test_csv_extraction_returns_structured_bank_transactions(mock_get_ai_client):
    mock_get_ai_client.return_value = (None, None)

    result = extract_structured_data(VALID_CSV.encode(), "bank.csv")

    assert result["doc_type"] == "BANK_STATEMENT"
    assert result["extraction_method"] == "CSV_NORMALIZED"
    assert result["transactions"][0]["amount"] == -1200.0
    assert result["classification_confidence"] == 0.95
    assert result["errors"] == []
