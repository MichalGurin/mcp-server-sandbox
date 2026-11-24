# SandboxMCP: Sandboxed DevOps & Execution Server

**SandboxMCP** is a production-grade Model Context Protocol (MCP) server that equips AI agents with safe, deterministic access to local databases, service logs, and isolated Docker execution environments for automated root-cause analysis.

Unlike a passive RAG pipeline that only retrieves text, this project proves that LLMs can be wired into real execution environments with strict guardrails, human-in-the-loop approvals, and stateful context.

## Key Engineering Highlights

- **Guardrailed Tool Execution:** Enforces AST/regex query validation to guarantee read-only SQL operations and isolates test runs inside ephemeral Docker containers with strict timeout and memory limits.
- **Stateful Context via MCP Resources:** Dynamically exposes live database schemas, environment variables (redacted), and recent error logs via custom resource URIs, eliminating manual copy-pasting during debugging.
- **Transport & Security Best Practices:** Implements strict JSON-schema input validation, structured stderr telemetry, and zero-trust credential handling for seamless integration with Claude Desktop and Cursor.

## Features

### Tools

| Tool | Description |
| --- | --- |
| `run_isolated_test` | Executes Python code inside an ephemeral, read-only, network-isolated Docker container (`python:3.14-slim`) with hard memory/CPU limits and a strict timeout. Returns exit code, stdout/stderr, and duration. |
| `query_readonly_db` | Validates and executes strictly read-only SQL (`SELECT`/`WITH`/`EXPLAIN` only). Destructive statements (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `PRAGMA`, multi-statement payloads, etc.) are rejected before execution. Returns columns, rows, and truncation info. |
| `tail_service_logs` | Tails the configured service log file and automatically parses embedded stack traces into structured error entries (exception type, message, frames). |

### Resources

| URI | Description |
| --- | --- |
| `sys://health` | Live health and resource-exhaustion telemetry (Docker daemon availability, memory, disk usage) for the host and Docker daemon. |
| `db://schema` | Read-only structured schema introspection (tables + columns, types, nullability, primary keys) of the configured database. |
| `logs://recent-errors` | Automatically tails and parses the most recent error stack traces from the service log. |

### Prompts

| Prompt | Description |
| --- | --- |
| `/root_cause_analysis` | Standardized debugging workflow that forces the model to verify the database schema via `db://schema`, tail errors via `logs://recent-errors`, investigate with read-only SQL, and reproduce via isolated Docker execution before proposing a fix. |
| `/generate_migration_plan` | Standardized migration workflow that forces schema verification before proposing DDL, with forward-compatible design and explicit rollback steps. |

## Architecture

```
src/sandboxmcp/
├── server.py         # FastMCP instance: tools, resources, prompts
├── config.py         # pydantic-settings (SANDBOX_* env vars)
├── security.py       # read-only SQL validation (comments/literals stripped, SELECT-only)
├── database.py       # read-only engine + query execution + schema introspection
├── logs.py           # log tailing + stack trace parsing
└── docker_executor.py  # ephemeral Docker container runner (limits, isolation)
```

## Tech Stack

- Python 3.14+
- [FastMCP](https://github.com/jlowin/fastmcp) (Model Context Protocol SDK)
- Docker (sandboxed code execution)
- SQLAlchemy (read-only connections)
- Pydantic / pydantic-settings (strict input validation)

## Getting Started

```bash
# install uv-managed Python and project dependencies
uv sync

# run the server (stdio transport for Claude Desktop / Cursor)
uv run sandboxmcp

# or run via MCP Inspector
uv run mcp-inspector run src/sandboxmcp/server.py
```

### Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `SANDBOX_DB_URL` | `sqlite:////tmp/sandbox/app.db` | SQLAlchemy database URL (e.g. `sqlite:////abs/path.db` or `postgresql+asyncpg://...`). |
| `SANDBOX_LOG_FILE` | `/var/log/sandbox/service.log` | Path to the service log file. |
| `SANDBOX_DOCKER_IMAGE` | `python:3.14-slim` | Base image for isolated test runs. |
| `SANDBOX_DOCKER_MEMORY_MB` | `256` | Hard memory limit per sandboxed container. |
| `SANDBOX_DOCKER_CPU_CORES` | `0.5` | CPU quota per sandboxed container. |
| `SANDBOX_TEST_TIMEOUT_SECONDS` | `30` | Wall-clock timeout per sandboxed run. |

## Security Model

1. **Read-only SQL guardrail:** comments and string literals are stripped before tokenizing, so `INSERT ... VALUES ('DELETE FROM users')` cannot smuggle destructive keywords through naive prefix checks. Only `SELECT`, `WITH`, `EXPLAIN`, and `VALUES` statements are permitted; multi-statement payloads are rejected.
2. **Ephemeral sandbox:** containers run with `read_only` rootfs, `network_mode="none"`, a hard memory limit, CPU quota, and a wall-clock timeout. The container is force-removed after each run.
3. **Structured validation:** strict JSON-schema input validation via Pydantic on every tool input.

## Integration

Add to `claude_desktop_config.json` or Cursor MCP settings:

```json
{
  "mcpServers": {
    "sandboxmcp": {
      "command": "uv",
      "args": ["run", "sandboxmcp"],
      "env": {}
    }
  }
}
```

## Agent Skill

The MCP server is packaged as an installable agent skill that teaches AI agents **when** and **how**
to use its safe debugging tools, turning it into something installable into Claude Code, Cursor,
Copilot and 20+ other agents.

- **Skill location:** [`skills/sandbox-mcp/SKILL.md`](skills/sandbox-mcp/SKILL.md) (with detailed
  workflow in [`skills/sandbox-mcp/references/root-cause-workflow.md`](skills/sandbox-mcp/references/root-cause-workflow.md))
- **Paired with:** the `sandboxmcp` MCP server (tools: `run_isolated_test`, `query_readonly_db`,
  `tail_service_logs`; resources: `sys://health`, `db://schema`, `logs://recent-errors`;
  prompts: `/root_cause_analysis`, `/generate_migration_plan`)

### Install the skill

- **Claude Code:** copy the skill into your project or personal skills directory:
  - Project: `.claude/skills/sandbox-mcp/SKILL.md`
  - Personal: `~/.claude/skills/sandbox-mcp/SKILL.md`
  Then invoke with `/sandbox-mcp`, or let Claude auto-select it.
- **Agent Skills–compatible clients** (Cursor, Copilot, Windsurf, etc.): import the
  `skills/sandbox-mcp/` directory as a skill package.

### Why pair them

The MCP server enforces the hard guarantees (read-only SQL guardrails, ephemeral sandbox with
limits, strict timeouts), while the skill enforces the safe workflow (context → investigate →
reproduce → fix) and tells the agent when to reach for those tools.

## Features

- Sandboxed Model Context Protocol (MCP) server enabling AI coding agents to inspect live database schemas, parse application logs, and execute unit tests inside ephemeral Docker containers.
- Deterministic security guardrails and read-only SQL validation, preventing destructive mutations and isolating untrusted LLM-generated code execution.
- Dynamic MCP Resource endpoints and reusable debugging prompts, streamlining automated root-cause analysis workflows across MCP-compatible IDE clients.

---
