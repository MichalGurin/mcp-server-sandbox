"""Runtime configuration for SandboxMCP (env vars prefixed with SANDBOX_)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SANDBOX_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Database ---
    # SQLAlchemy-style URL. SQLite example: sqlite:////absolute/path/to/app.db
    DB_URL: str = "sqlite:////tmp/sandbox/app.db"
    MAX_ROWS: int = 100

    # --- Logs ---
    LOG_FILE: str = "/var/log/sandbox/service.log"

    # --- Isolated Docker execution ---
    DOCKER_IMAGE: str = "python:3.14-slim"
    DOCKER_MEMORY_MB: int = 256
    DOCKER_CPU_CORES: float = 0.5
    TEST_TIMEOUT_SECONDS: int = 30


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
