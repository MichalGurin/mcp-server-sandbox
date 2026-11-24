# SandboxMCP — Root Cause Analysis Workflow

Detailed reference for the `sandbox-mcp` agent skill. The skill (`skills/sandbox-mcp/SKILL.md`)
contains the overview, safety invariants, and environment profiles; this document describes the
step-by-step debugging procedure.

## Goal

Systematically find the root cause of a failing service using only guarded, non-destructive,
sandboxed operations.

## Step 0 — Confirm the failure mode

- Read the MCP resource `sys://health` to confirm the Docker daemon and resource limits are
  healthy (`status: ok`).
- Read `logs://recent-errors` for an immediate snapshot of recent parsed errors.

## Step 1 — Context gathering

1. Read resource `db://schema` → understand tables/columns before querying data.
2. Read resource `logs://recent-errors` → collect exception types/messages and stack frames.
3. If more log context is needed, call tool `tail_service_logs` with `path` and `lines`.

## Step 2 — Investigation

- Call tool `query_readonly_db` with targeted, read-only SQL, e.g.:

  ```json
  { "sql": "SELECT * FROM orders ORDER BY created_at DESC LIMIT 20" }
  ```

- Use `WITH ... SELECT` CTEs for multi-hop queries.
- Inspect related data via foreign keys / joins.
- Do **not** write any data.

## Step 3 — Reproduction

- Call tool `run_isolated_test` with a minimal, self-contained Python repro:

  ```json
  {
    "code": "import requests; ...",
    "timeout_seconds": 30
  }
  ```

- Container is ephemeral: read-only rootfs, no network, 256 MB memory, 0.5 CPU, 30 s timeout.
- Interpret `exit_code`, `stdout`, `stderr`, `timed_out`.

## Step 4 — Fix and verification

- Only after root cause confirmed, propose a minimal backwards-compatible fix.
- Describe regression tests (run via `run_isolated_test` after the fix).
- Optionally plan a migration via the `/generate_migration_plan` prompt (verifies schema first).

## Environment notes

- **Development:** `SANDBOX_DB_URL=sqlite:////tmp/sandbox/app.db`, `SANDBOX_LOG_FILE=/var/log/sandbox/service.log`.
- **Staging:** point `SANDBOX_DB_URL` to the staging DB and `SANDBOX_LOG_FILE` to staging logs;
  consider larger `SANDBOX_TEST_TIMEOUT_SECONDS` for slow repros.

## Output format

Report findings as:

1. Symptom summary
2. Evidence (log excerpts, query results, repro output)
3. Root cause
4. Fix + validation plan
