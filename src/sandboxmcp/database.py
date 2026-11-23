"""Read-only database access with strict validation."""

from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from .config import get_settings
from .security import validate_readonly


def get_engine(db_url: str | None = None):
    url = db_url or get_settings().DB_URL
    if url.startswith("sqlite"):
        parsed = make_url(url)
        path = parsed.database or ""

        def _creator():
            import sqlite3

            return sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)

        return create_engine(url, creator=_creator)
    return create_engine(
        url,
        connect_args={"options": "-c default_transaction_read_only=on"},
    )


def run_readonly_query(sql: str, db_url: str | None = None) -> dict[str, Any]:
    """Validate and execute a read-only SQL query. Returns rows/columns."""
    ok, reason = validate_readonly(sql)
    result = {
        "success": ok,
        "error": None if ok else f"Query rejected by read-only guardrail: {reason}",
        "columns": [],
        "rows": [],
        "row_count": 0,
        "truncated": False,
    }
    if not ok:
        return result

    engine = get_engine(db_url)
    try:
        with engine.connect() as connection:
            result_set = connection.execute(text(sql))
            columns = list(result_set.keys())
            rows = [dict(zip(columns, row)) for row in result_set.fetchall()]
        result["columns"] = columns
        result["rows"] = rows
        result["row_count"] = len(rows)
        result["truncated"] = len(rows) >= get_settings().MAX_ROWS
        return result
    except Exception as exc:  # noqa: BLE001 - surface DB errors to the LLM
        result["success"] = False
        result["error"] = f"Query execution failed: {exc}"
        return result


def get_schema_info(db_url: str | None = None) -> dict[str, Any]:
    """Return structured schema metadata (read-only introspection)."""
    engine = get_engine(db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    schema_tables = []
    for table in tables:
        columns = inspector.get_columns(table)
        schema_tables.append(
            {
                "name": table,
                "columns": [
                    {
                        "name": column["name"],
                        "type": str(column.get("type")),
                        "nullable": bool(column.get("nullable")),
                        "primary_key": bool(column.get("primary_key")),
                    }
                    for column in columns
                ],
            }
        )
    return {
        "database": db_url or get_settings().DB_URL,
        "table_count": len(schema_tables),
        "tables": schema_tables,
    }

