"""Service log tailing and stack trace parsing."""

import os
import re
from typing import Any

from .config import get_settings

TRACEBACK_MARKER_RE = re.compile(r"Traceback \(most recent call last\):")
FRAME_RE = re.compile(r'File "([^"]+)", line (\d+), in (.+)')
EXCEPTION_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Failure|Interrupt)?)\b\s*:\s*(.*)$")


def _parse_error_entries(lines: list[str]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal current
        if current is not None:
            errors.append(current)
            current = None

    for line in lines:
        if TRACEBACK_MARKER_RE.search(line):
            flush()
            current = {"exception": None, "message": "", "stack": []}
            continue

        if current is None:
            match = EXCEPTION_RE.match(line.strip())
            if match:
                errors.append(
                    {
                        "exception": match.group(1),
                        "message": match.group(2).strip(),
                        "stack": [],
                    }
                )
            continue

        frame_match = FRAME_RE.search(line)
        if frame_match:
            current["stack"].append(
                {
                    "file": frame_match.group(1),
                    "line": int(frame_match.group(2)),
                    "function": frame_match.group(3).strip(),
                }
            )
            continue

        exc_match = EXCEPTION_RE.match(line.strip())
        if exc_match:
            current["exception"] = exc_match.group(1)
            current["message"] = exc_match.group(2).strip()
            continue

        if not line.strip():
            flush()

    flush()
    return errors


def tail_service_logs(path: str | None = None, lines: int = 100) -> dict[str, Any]:
    """Read the last `lines` lines of a log file and extract stack traces."""
    settings = get_settings()
    log_path = path or settings.LOG_FILE
    entries: list[dict[str, Any]] = []
    total_lines = 0
    returned_lines = 0

    if os.path.exists(log_path):
        with open(log_path, "r", errors="replace") as handle:
            all_lines = handle.read().splitlines()
        total_lines = len(all_lines)
        tail = all_lines[-lines:]
        returned_lines = len(tail)
        entries = _parse_error_entries(tail)

    return {
        "path": log_path,
        "total_lines": total_lines,
        "returned_lines": returned_lines,
        "errors": entries,
    }


def redact_secrets(env: dict[str, str]) -> dict[str, Any]:
    """Redact secret-looking environment variable values."""
    redacted: dict[str, Any] = {}
    secret_key_pattern = re.compile(
        r"(KEY|TOKEN|SECRET|PASSWORD|PASS|PWD|CREDENTIAL|DATABASE|DSN)",
        re.IGNORECASE,
    )
    for key, value in env.items():
        redacted[key] = "***REDACTED***" if secret_key_pattern.search(key) else value
    return redacted
