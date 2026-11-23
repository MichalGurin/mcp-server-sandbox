"""Log tailing and stack trace parsing tests."""

import pytest

from sandboxmcp.logs import _parse_error_entries, redact_secrets, tail_service_logs


LOG_SAMPLE = """2026-11-23 10:00:01 INFO  worker started
2026-11-23 10:00:12 ERROR boom happened
Traceback (most recent call last):
  File "/app/api.py", line 42, in handle
    result = self.service.pay()
  File "/app/services/payment.py", line 17, in pay
    raise PaymentError("card declined")
PaymentError: card declined
2026-11-23 10:00:13 INFO  worker still running
"""


def test_parses_stack_trace_entries() -> None:
    errors = _parse_error_entries(LOG_SAMPLE.splitlines())
    assert len(errors) == 1
    entry = errors[0]
    assert entry["exception"] == "PaymentError"
    assert entry["message"] == "card declined"
    assert len(entry["stack"]) == 2
    assert entry["stack"][0]["file"] == "/app/api.py"
    assert entry["stack"][0]["line"] == 42
    assert entry["stack"][0]["function"] == "handle"
    assert entry["stack"][1]["file"] == "/app/services/payment.py"
    assert entry["stack"][1]["function"] == "pay"


def test_tail_missing_file_returns_empty(tmp_path) -> None:
    result = tail_service_logs(str(tmp_path / "does-not-exist.log"), lines=10)
    assert result["errors"] == []
    assert result["total_lines"] == 0


def test_tail_parses_recent_errors(tmp_path) -> None:
    log_file = tmp_path / "service.log"
    log_file.write_text(LOG_SAMPLE)
    result = tail_service_logs(str(log_file), lines=100)
    assert result["total_lines"] == 9
    assert len(result["errors"]) == 1
    assert result["errors"][0]["exception"] == "PaymentError"
    assert result["returned_lines"] == 9


def test_tail_respects_line_limit(tmp_path) -> None:
    log_file = tmp_path / "service.log"
    log_file.write_text("\n".join(f"log line {i}" for i in range(50)))
    result = tail_service_logs(str(log_file), lines=3)
    assert result["returned_lines"] == 3


def test_redact_secrets_masks_sensitive_values() -> None:
    redacted = redact_secrets({"API_KEY": "super-secret", "DATABASE_URL": "postgres://x", "APP_ENV": "prod"})
    assert redacted["API_KEY"] == "***REDACTED***"
    assert redacted["DATABASE_URL"] == "***REDACTED***"
    assert redacted["APP_ENV"] == "prod"
