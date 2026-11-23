# CLAUDE.md — Claude Code / AI Assistant Project Guide for SandboxMCP

## Project Overview

SandboxMCP is a sandboxed DevOps & execution Model Context Protocol (MCP) server built with
Python 3.14+, FastMCP, Docker, SQLAlchemy, and Pydantic.

It lets an AI coding agent (Claude Desktop, Cursor, Claude Code, custom agent) safely inspect
local databases, tail service logs, and run isolated Docker test suites — without unrestricted
shell access.

## Commands

```bash
uv sync                  # install dependencies (uv-managed Python 3.14)
uv run pytest            # run unit tests
uv run sandboxmcp        # run server (stdio transport, default)
uv run mcp-inspector run src/sandboxmcp/server.py   # MCP Inspector UI

docker compose up --build                     # run server via Docker (HTTP on :8000)
docker compose exec sandboxmcp ...           # exec into container
```

## Architecture

- `src/sandboxmcp/server.py` — FastMCP instance wiring tools, resources, prompts
- `src/sandboxmcp/config.py` — pydantic-settings (`SANDBOX_*` env vars, `.env` support)
- `src/sandboxmcp/security.py` — read-only SQL validation
- `src/sandboxmcp/database.py` — read-only engine + query + schema introspection
- `src/sandboxmcp/logs.py` — log tailing, stack trace parsing, secret redaction
- `src/sandboxmcp/docker_executor.py` — ephemeral container runner (limits, isolation)

## MCP Surface

- Tools: `run_isolated_test`, `query_readonly_db`, `tail_service_logs`
- Resources: `sys://health`, `db://schema`, `logs://recent-errors`
- Prompts: `/root_cause_analysis`, `/generate_migration_plan`
- Transports: stdio (`SANDBOX_MCP_TRANSPORT=stdio`) or streamable HTTP
  (`SANDBOX_MCP_TRANSPORT=http`, port via `PORT`, default 8000)

## Security Invariants (do not weaken)

- `query_readonly_db` must only ever allow `SELECT` / `WITH` / `EXPLAIN` / `VALUES`.
- Destructive keywords (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`,
  `PRAGMA`, multi-statement payloads, …) must be rejected.
- Isolated runs must keep: read-only rootfs, no network, memory + CPU limits, hard timeout.
- Secrets must never reach the LLM: redaction applied in `logs.redact_secrets`.

## Code Conventions

- Tool outputs: Pydantic models (`BaseModel`) with strict fields.
- Resources/prompts return JSON strings.
- Keep inputs validated via Pydantic / FastMCP JSON schema.
- Add tests under `tests/` for any new security or parsing logic.

## Deployment

- Local: `uv run sandboxmcp` (stdio) or `docker compose up`.
- Cloud: `render.yaml` (Render blueprint, Docker runtime, HTTP transport).
