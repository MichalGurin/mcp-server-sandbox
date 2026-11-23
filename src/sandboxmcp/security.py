"""Deterministic, fail-safe SQL guardrails.

The LLM must never be able to issue a mutating statement. This module strips
comments and string literals, splits statements on semicolons and only allows
read-only statement types to pass.
"""

import re
from typing import Tuple
# Statements that are considered read-only. WITH ... SELECT (CTEs) is safe.
ALLOWED_STATEMENT_PREFIXES = frozenset(
    {
        "SELECT",
        "WITH",
        "EXPLAIN",
        "VALUES",
    }
)

FORBIDDEN_KEYWORDS = frozenset(
    {
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "REPLACE",
        "GRANT",
        "REVOKE",
        "ATTACH",
        "DETACH",
        "PRAGMA",
        "VACUUM",
        "REINDEX",
        "SAVEPOINT",
        "RELEASE",
        "COMMIT",
        "ROLLBACK",
        "SET",
        "USE",
        "CALL",
        "EXPORT",
        "IMPORT",
    }
)


def strip_comments_and_literals(sql: str) -> str:
    """Remove SQL comments and quoted string/identifier literals.

    Replacing literals with a space prevents payloads such as
    ``INSERT ... VALUES ('DELETE FROM users')`` from sneaking destructive
    keywords past a naive prefix check.
    """
    out: list[str] = []
    i = 0
    n = len(sql)
    while i < n:
        char = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""
        if char == "-" and nxt == "-":
            end = sql.find("\n", i)
            i = n if end == -1 else end
            continue
        if char == "/" and nxt == "*":
            end = sql.find("*/", i + 2)
            i = n if end == -1 else end + 2
            continue
        if char in ("'", '"'):
            quote = char
            j = i + 1
            while j < n:
                if sql[j] == quote:
                    if j + 1 < n and sql[j + 1] == quote:
                        j += 2
                        continue
                    break
                j += 1
            out.append(" ")
            i = j + 1
            continue
        out.append(char)
        i += 1
    return "".join(out)


def validate_readonly(sql: str) -> Tuple[bool, str]:
    """Return ``(is_safe, reason)`` for a candidate SQL statement."""
    if not sql or not sql.strip():
        return False, "Empty query"

    cleaned = strip_comments_and_literals(sql).upper()
    statements = [s.strip() for s in cleaned.split(";") if s.strip()]
    if not statements:
        return False, "Empty query"

    for statement in statements:
        tokens = re.findall(r"[A-Z_][A-Z0-9_]*", statement)
        if not tokens:
            return False, "Unable to parse statement"
        first = tokens[0]
        if first not in ALLOWED_STATEMENT_PREFIXES:
            return False, f"Statement type '{first}' is not allowed (read-only SELECT-only policy)"
        for token in tokens:
            if token in FORBIDDEN_KEYWORDS:
                return False, f"Forbidden keyword '{token}' detected in query"

    return True, "OK"


def is_safe_select(sql: str) -> bool:
    ok, _reason = validate_readonly(sql)
    return ok
