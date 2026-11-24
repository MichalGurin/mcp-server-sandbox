---
name: sandbox-mcp
description: >
  Safe DevOps debugging for AI agents — gives coding assistants guarded access to local
  databases, service logs, and isolated Docker execution so they can perform root-cause
  analysis without unrestricted shell access. Use when a service is failing, errors or stack
  traces need parsing, database state must be inspected before a fix is proposed, or an agent
  must safely reproduce a bug. Drives the SandboxMCP MCP server tools (query_readonly_db,
  tail_service_logs, run_isolated_test) and resources (db://schema, logs://recent-errors,
  sys://health) through a deterministic debugging workflow.
---

# SandboxMCP

## Purpose

This skill turns the SandboxMCP MCP server into a safe, stateful debugging capability for the
host AI agent. It defines **when** the agent should reach for those tools and **how** to use them
in a strict, safe order. The MCP server enforces the hard guarantees (read-only SQL, sandboxed
Docker execution, strict timeouts); this skill enforces the workflow (gather context →
investigate → reproduce → fix).

## When to use this skill

- A service or API is erroring and logs contain errors or stack traces.
- A suspected database or state issue must be investigated before proposing a fix.
- A bug/fix cycle requires safe reproduction before validation.
- A migration needs to be planned or verified against the live schema first.

## When NOT to use this skill

- Pure code generation or refactoring with no runtime investigation required.
- Any task that requires writes or mutations — the toolset is strictly read-only plus
  sandboxed execution.

## Prerequisites

- MCP server named `sandboxmcp` configured in the host agent (project: `.mcp.json`, or
  `~/.claude.json` / `~/.cursor/mcp.json` / equivalent for the target platform).
- Docker daemon running (required by the `run_isolated_test` tool).
- Database reachable via `SANDBOX_DB_URL` and log file present at `SANDBOX_LOG_FILE`.

## Tools and resources

| Kind | Identifier | Purpose |
| --- | --- | --- |
| Tool | `query_readonly_db` | Strictly validated `SELECT`/`WITH`/`EXPLAIN` execution; destructive SQL is rejected before execution. |
| Tool | `tail_service_logs` | Tails the log file and parses stack traces into structured error entries. |
| Tool | `run_isolated_test` | Runs code in an ephemeral, read-only, network-isolated Docker container with hard memory/CPU limits and a wall-clock timeout. |
| Resource | `sys://health` | Live health, limits, and redacted environment snapshot. |
| Resource | `db://schema` | Read-only schema introspection (tables, columns, types, PK info). |
| Resource | `logs://recent-errors` | Automatically tailed + parsed recent error stack traces. |
| Prompt | `/root_cause_analysis` | Ready-made root-cause workflow prompt. |
| Prompt | `/generate_migration_plan` | Migration planning workflow (verifies schema before DDL). |

## Standard debugging workflow

Follow this order whenever a root-cause investigation is triggered:

1. **Context gathering** — read the `db://schema` and `logs://recent-errors` resources; fall back
   to `tail_service_logs` for additional lines.
2. **Investigation** — issue targeted read-only queries via `query_readonly_db`.
3. **Reproduction** — run a minimal repro via `run_isolated_test`.
4. **Fix** — only after the root cause is confirmed, propose a minimal, backwards-compatible fix
   with regression tests.

## Safety invariants

- Never issue mutating SQL (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`,
  `PRAGMA`, multi-statement payloads, …).
- Never pass code to anything other than `run_isolated_test`.
- Never surface or echo redacted secrets.
- Respect sandbox limits (memory, CPU, timeout) configured via `SANDBOX_*` variables.

## Environments: development vs staging

The workflow is identical for development and staging; only configuration differs:

- **Development:** `SANDBOX_DB_URL=sqlite:////tmp/sandbox/app.db`, `SANDBOX_LOG_FILE=/var/log/sandbox/service.log`, `SANDBOX_DOCKER_IMAGE=python:3.14-slim`, `SANDBOX_TEST_TIMEOUT_SECONDS=30`.
- **Staging:** point `SANDBOX_DB_URL` at the staging database (e.g. `postgresql+asyncpg://...`),
  point `SANDBOX_LOG_FILE` at the staging log path, and optionally raise `SANDBOX_TEST_TIMEOUT_SECONDS`.

Prefer discovering actual runtime values through the `sys://health`, `db://schema`, and
`logs://recent-errors` resources / tool parameters rather than hardcoding assumptions.

## References

- `skills/sandbox-mcp/references/root-cause-workflow.md` — detailed step-by-step debugging
  workflow, example tool calls, and expected outputs.
