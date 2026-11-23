# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

FROM python:3.14-slim AS runtime

WORKDIR /app
ENV PATH="/app/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ENV SANDBOX_MCP_TRANSPORT=http
ENV SANDBOX_DB_URL=sqlite:////data/app.db
ENV SANDBOX_LOG_FILE=/var/log/sandbox/service.log

RUN mkdir -p /data /var/log/sandbox

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

EXPOSE 8000

CMD ["sandboxmcp"]
