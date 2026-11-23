"""Isolated Docker execution with strict resource limits."""

import time
from typing import Any

import docker

from .config import get_settings

_client: docker.DockerClient | None = None


def _get_client() -> docker.DockerClient:
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client


def get_docker_client() -> docker.DockerClient:
    return _get_client()


def is_docker_available() -> bool:
    try:
        _get_client().ping()
        return True
    except Exception:  # noqa: BLE001 - docker daemon may be unreachable
        return False


def run_isolated_test(
    code: str,
    timeout_seconds: int | None = None,
    memory_mb: int | None = None,
) -> dict[str, Any]:
    """Run LLM-generated code inside an ephemeral, locked-down Docker container."""
    settings = get_settings()
    client = _get_client()
    container = client.containers.run(
        image=settings.DOCKER_IMAGE,
        command=["python", "-c", code],
        detach=True,
        read_only=True,
        network_mode="none",
        mem_limit=(memory_mb or settings.DOCKER_MEMORY_MB) * 1024 * 1024,
        nano_cpus=int(settings.DOCKER_CPU_CORES * 1_000_000_000),
        environment={"SANDBOX_ISOLATED_TEST": "1"},
    )

    effective_timeout = timeout_seconds or settings.TEST_TIMEOUT_SECONDS
    start = time.monotonic()
    timed_out = False
    exit_code = -1
    try:
        wait_result = container.wait(timeout=effective_timeout)
        # docker-py >= 7 returns the exit code directly; older versions return (code, status)
        exit_code = int(wait_result) if isinstance(wait_result, int) else int(wait_result.get("StatusCode", -1))
    except Exception:  # noqa: BLE001 - TimeoutExpired or daemon hiccup
        timed_out = True
        try:
            container.kill()
        except Exception:  # noqa: BLE001
            pass
    duration_seconds = round(time.monotonic() - start, 3)

    stdout = ""
    stderr = ""
    if not timed_out:
        stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
        stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")

    try:
        client.containers.remove(container.id, force=True)
    except Exception:  # noqa: BLE001
        pass

    return {
        "exit_code": exit_code,
        "timed_out": timed_out,
        "stdout": stdout,
        "stderr": stderr,
        "duration_seconds": duration_seconds,
        "timed_out_at_seconds": effective_timeout,
    }
