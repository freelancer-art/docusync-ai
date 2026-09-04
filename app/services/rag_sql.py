import re
from typing import Any

FORBIDDEN_SQL_PATTERN = re.compile(
    r"\b(attach|alter|create|delete|detach|drop|insert|pragma|replace|update|vacuum)\b",
    re.IGNORECASE,
)
TAIL_CLAUSE_PATTERN = re.compile(r"\b(group\s+by|having|order\s+by|limit)\b", re.IGNORECASE)


def build_safe_ledger_query(
    generated_sql: str,
    *,
    is_admin: bool,
    client_id: int | None,
) -> tuple[str, dict[str, Any]]:
    """Validate LLM SQL and add parameterized tenant scope for client users."""
    sql = _validate_generated_select(generated_sql)
    if is_admin:
        return sql, {}

    if client_id is None:
        raise ValueError("Client-scoped queries require a client ID.")

    return _inject_client_scope(sql), {"tenant_client_id": client_id}


def _validate_generated_select(generated_sql: str) -> str:
    sql = _strip_code_fences(generated_sql).strip()
    upper_sql = sql.upper()

    if not upper_sql.startswith("SELECT"):
        raise ValueError("Generated statement must start with SELECT.")
    if ";" in sql:
        raise ValueError("Generated statement must be a single SELECT without semicolons.")
    if "--" in sql or "/*" in sql or "*/" in sql:
        raise ValueError("Generated statement must not contain SQL comments.")
    if FORBIDDEN_SQL_PATTERN.search(sql):
        raise ValueError("Generated statement contains a forbidden SQL operation.")
    if not re.search(r"\bfrom\s+documentrecord\b", sql, flags=re.IGNORECASE):
        raise ValueError("Generated statement must query the documentrecord table.")
    if re.search(r"\bjoin\b|\bfrom\s+documentrecord\s*,", sql, flags=re.IGNORECASE):
        raise ValueError("Generated statement must not join or combine tables.")

    return sql


def _strip_code_fences(sql: str) -> str:
    return re.sub(r"^```sql\s*|^```\s*|\s*```$", "", sql, flags=re.MULTILINE)


def _inject_client_scope(sql: str) -> str:
    tail_match = TAIL_CLAUSE_PATTERN.search(sql)
    if tail_match:
        body = sql[: tail_match.start()].rstrip()
        tail = " " + sql[tail_match.start():].lstrip()
    else:
        body = sql
        tail = ""

    where_match = re.search(r"\bwhere\b", body, flags=re.IGNORECASE)
    if where_match:
        before_where = body[: where_match.end()]
        after_where = body[where_match.end():].strip()
        scoped_body = (
            f"{before_where} client_id = :tenant_client_id AND ({after_where})"
        )
    else:
        scoped_body = f"{body} WHERE client_id = :tenant_client_id"

    return scoped_body + tail
