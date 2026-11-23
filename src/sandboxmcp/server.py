"""FastMCP server exposing safe, sandboxed DevOps tools and debugging resources."""

import json
import os
import shutil
from typing import Any

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from .config import get_settings
from .database import get_schema_info, run_readonly_query
from .docker_executor import get_docker_client, is_docker_available, run_isolated_test
from .logs import redact_secrets, tail_service_logs

mcp = FastMCP(
    name="SandboxMCP",
    instructions=(
        "Production-grade sandboxed DevOps MCP server. Provides read-only "
        "database access, service log tailing with stack trace parsing, and "
        "isolated Docker execution for AI coding agents. All mutating SQL and "
        "arbitrary code execution are strictly guarded."
    ),
)


class IsolatedRunResult(BaseModel):
    exit_code: int = 0
    timed_out: bool = False
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    timed_out_at_seconds: int = 30


class QueryResult(BaseModel):
    success: bool = True
    error: str | None = None
    columns: list[str] = []
    rows: list[dict[str, Any]] = []
    row_count: int = 0
    truncated: bool = False


class LogTailResult(BaseModel):
    path: str = ""
    total_lines: int = 0
    returned_lines: int = 0
    errors: list[dict[str, Any]] = []


@mcp.tool(
    name="run_isolated_test",
    description=(
        "Run LLM-generated or user-provided Python code inside an ephemeral, "
        "read-only, network-isolated Docker container with hard memory/CPU limits "
        "and a strict timeout. Use this to safely reproduce bugs or validate fixes "
        "without touching the host."
    ),
)
def run_isolated_test_tool(
    code: str = Field(
        description=(
            "Python source code to execute in the sandbox. Must be a self-contained "
            "script (no host filesystem access beyond what the image provides)."
        ),
        default="print('hello from sandbox')",
    ),
    timeout_seconds: int = Field(
        default=30,
        description="Hard wall-clock timeout in seconds for the sandboxed run.",
    ),
) -> IsolatedRunResult:
    result = run_isolated_test(code, timeout_seconds=timeout_seconds)
    return IsolatedRunResult(**result)


@mcp.tool(
    name="query_readonly_db",
    description=(
        "Execute a strictly validated, read-only SQL query against the local "
        "database. Destructive statements (INSERT/UPDATE/DELETE/DROP/ALTER/CREATE) "
        "are rejected before execution. Returns columns, rows and truncation info."
    ),
)
def query_readonly_db_tool(
    sql: str = Field(
        description="A single read-only SELECT/WITH/EXPLAIN statement. Mutating SQL is rejected.",
    ),
) -> QueryResult:
    result = run_readonly_query(sql)
    return QueryResult(
        success=result["success"],
        error=result["error"],
        columns=result["columns"],
        rows=result["rows"],
        row_count=result["row_count"],
        truncated=result["truncated"],
    )


@mcp.tool(
    name="tail_service_logs",
    description=(
        "Tail the most recent lines of the service log file and automatically "
        "parse any embedded stack traces into structured error entries."
    ),
)
def tail_service_logs_tool(
    path: str = Field(
        default="",
        description="Optional absolute path to the log file. Defaults to the configured SANDBOX_LOG_FILE.",
    ),
    lines: int = Field(
        default=100,
        description="Maximum number of trailing log lines to inspect.",
    ),
) -> LogTailResult:
    resolved = path or get_settings().LOG_FILE
    result = tail_service_logs(resolved, lines=lines)
    return LogTailResult(
        path=result["path"],
        total_lines=result["total_lines"],
        returned_lines=result["returned_lines"],
        errors=result["errors"],
    )


@mcp.resource(
    "sys://health",
    name="System Health",
    description="Live health and resource-exhaustion telemetry for the host and Docker daemon.",
)
def system_health() -> str:
    """Return host + Docker daemon health snapshot as JSON."""
    settings = get_settings()
    checks: dict[str, Any] = {}
    docker_ok = is_docker_available()
    checks["docker"] = {"available": docker_ok}
    try:
        info = get_docker_client().info()
        checks["docker"]["memory_mb_total"] = round(int(info.get("MemTotal", 0)) / 1024 / 1024, 1)
        checks["docker"]["memory_mb_used"] = round(int(info.get("MemUsage", "0")) / 1024 / 1024, 1)
    except Exception:  # noqa: BLE001
        checks["docker"]["memory_mb_total"] = None
        checks["docker"]["memory_mb_used"] = None

    usage = shutil.disk_usage("/")
    checks["disk"] = {
        "total_gb": round(usage.total / 1024**3, 2),
        "used_gb": round(usage.used / 1024**3, 2),
        "free_gb": round(usage.free / 1024**3, 2),
    }
    payload = {
        "status": "ok" if docker_ok else "degraded",
        "service": "sandboxmcp",
        "docker": settings.DOCKER_IMAGE,
        "limits": {
            "memory_mb": settings.DOCKER_MEMORY_MB,
            "cpu_cores": settings.DOCKER_CPU_CORES,
            "timeout_seconds": settings.TEST_TIMEOUT_SECONDS,
        },
        "checks": checks,
        "redacted_env": redact_secrets(dict(os.environ)),
    }
    return json.dumps(payload)


@mcp.resource(
    "db://schema",
    name="Database Schema",
    description="Read-only structured schema introspection of the configured database.",
)
def database_schema() -> str:
    """Return JSON database schema (tables + columns) for the configured DB."""
    schema = get_schema_info()
    return json.dumps(schema, default=str)


@mcp.resource(
    "logs://recent-errors",
    name="Recent Errors",
    description="Automatically tail and parse the most recent error stack traces from the service log.",
)
def recent_errors() -> str:
    """Return JSON of recently parsed error stack traces."""
    tail = tail_service_logs()
    return json.dumps(tail, default=str)


@mcp.prompt("root_cause_analysis")
def root_cause_analysis(service: str = "payment-service") -> str:
    """Standardized root-cause debugging workflow.

    Forces the agent to gather environment context (schema + logs) before
    proposing any fix.
    """
    return f"""Perform a structured root-cause analysis for the failing service: {service}.

Follow this workflow strictly, using only the available MCP tools/resources:

1. CONTEXT GATHERING (read-only):
   - Read the MCP resource db://schema to understand the current database schema.
   - Read the MCP resource logs://recent-errors for the most recent parsed stack traces.
   - If more log detail is needed, call the tail_service_logs tool.

2. INVESTIGATION:
   - Call query_readonly_db with targeted SELECT/WITH queries (e.g. recent rows,
     foreign-key relationships, enum values) to narrow down the failing code path.

3. REPRODUCTION:
   - Call run_isolated_test to execute a minimal reproduction of the suspected fault
     inside the ephemeral Docker sandbox.

4. HYPOTHESIS & FIX:
   - Only after the root cause is confirmed, propose a minimal, backwards-compatible fix
     and describe the regression tests to add.
"""


@mcp.prompt("generate_migration_plan")
def generate_migration_plan(table: str = "users") -> str:
    """Generate a safe, reversible database migration plan.

    Forces the agent to verify the live schema before proposing DDL changes.
    """
    return f"""Generate a migration plan for the table: {table}.

Follow this workflow strictly:

1. VERIFY SCHEMA:
   - Read the MCP resource db://schema to inspect the live table definition.
   - Use query_readonly_db for read-only checks if column/data confirmation is needed.

2. DESIGN:
   - Propose forward-compatible, idempotent DDL (CREATE/ALTER guarded behind explicit approval).
   - Provide the exact SQL, affected rows estimate, and backward-compatibility notes.

3. ROLLBACK:
   - Define a precise, tested rollback path for the migration.

4. VALIDATION:
   - List the verification steps (read-only queries, isolated test run) before shipping.
"""


def main() -> None:
    transport = os.environ.get("SANDBOX_MCP_TRANSPORT", "stdio")
    if transport in ("http", "streamable-http", "streamable_http"):
        mcp.run(transport="http", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
