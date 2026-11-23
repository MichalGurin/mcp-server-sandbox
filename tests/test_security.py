"""Security guardrail unit tests."""

import pytest

from sandboxmcp.security import is_safe_select, validate_readonly


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM users",
        "select id, email from users where active = 1",
        "WITH cte AS (SELECT * FROM orders) SELECT * FROM cte",
        "EXPLAIN SELECT * FROM users",
        "SELECT * FROM users -- get me the data\n",
        "SELECT * FROM users /* block comment */",
    ],
)
def test_safe_queries_accepted(sql: str) -> None:
    ok, reason = validate_readonly(sql)
    assert ok, reason
    assert is_safe_select(sql) is True


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM users",
        "UPDATE users SET email = 'x' WHERE id = 1",
        "DROP TABLE users",
        "ALTER TABLE users ADD COLUMN age INT",
        "INSERT INTO users (id) VALUES (1)",
        "CREATE TABLE users (id INT)",
        "TRUNCATE TABLE sessions",
        "SELECT * FROM users; DELETE FROM users",
        "SELECT * FROM users; DROP TABLE users",
        "PRAGMA table_info(users)",
        "SELECT * FROM users; UPDATE users SET admin = 1",
        # destructive keyword hidden behind a CTE must not pass
        "WITH sneaky AS (SELECT * FROM users) DELETE FROM sneaky",
    ],
)
def test_dangerous_queries_rejected(sql: str) -> None:
    ok, reason = validate_readonly(sql)
    assert ok is False
    assert reason != "OK"


def test_empty_query_rejected() -> None:
    ok, reason = validate_readonly("   ")
    assert ok is False
    assert "Empty" in reason
