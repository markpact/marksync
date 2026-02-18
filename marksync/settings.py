"""
marksync.settings — Centralized configuration loaded from environment / .env file.

Priority (highest → lowest):
    1. Explicit function arguments
    2. Environment variables (os.environ)
    3. .env file in project root
    4. Built-in defaults

Usage:
    from marksync.settings import settings
    print(settings.MARKSYNC_PORT)        # 8765
    print(settings.server_uri)           # ws://localhost:8765
    print(settings.ollama_url)           # http://localhost:11434
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _find_dotenv() -> Path | None:
    """Walk up from CWD and package dir to find .env."""
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


def _load_dotenv(path: Path) -> dict[str, str]:
    """Minimal .env parser — no external dependency required."""
    env: dict[str, str] = {}
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Strip surrounding quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        env[key] = value
    return env


def _env(key: str, default: str, dotenv: dict[str, str]) -> str:
    """Read from os.environ first, then dotenv, then default."""
    return os.environ.get(key, dotenv.get(key, default))


def _env_int(key: str, default: int, dotenv: dict[str, str]) -> int:
    raw = _env(key, str(default), dotenv)
    try:
        return int(raw)
    except (ValueError, TypeError):
        return default


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""

    # Sync server
    MARKSYNC_HOST: str = "0.0.0.0"
    MARKSYNC_PORT: int = 8765
    MARKSYNC_SERVER: str = "ws://localhost:8765"
    MARKSYNC_SERVER_DOCKER: str = "ws://sync-server:8765"

    # DSL API
    MARKSYNC_API_HOST: str = "0.0.0.0"
    MARKSYNC_API_PORT: int = 8080

    # Ollama
    OLLAMA_HOST: str = "localhost"
    OLLAMA_PORT: int = 11434
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_URL_DOCKER: str = "http://host.docker.internal:11434"
    OLLAMA_MODEL: str = "qwen2.5-coder:7b"

    # Markpact
    MARKPACT_PORT: int = 8088

    # Project
    PROJECT_README: str = "README.md"
    LOG_LEVEL: str = "INFO"

    # ── Derived helpers ────────────────────────────────────────────────

    @property
    def server_uri(self) -> str:
        return self.MARKSYNC_SERVER

    @property
    def ollama_url(self) -> str:
        return self.OLLAMA_URL

    @property
    def api_host(self) -> str:
        return self.MARKSYNC_API_HOST

    @property
    def api_port(self) -> int:
        return self.MARKSYNC_API_PORT


def load_settings() -> Settings:
    """Load settings from environment + .env file."""
    dotenv_path = _find_dotenv()
    dotenv = _load_dotenv(dotenv_path) if dotenv_path else {}

    return Settings(
        MARKSYNC_HOST=_env("MARKSYNC_HOST", "0.0.0.0", dotenv),
        MARKSYNC_PORT=_env_int("MARKSYNC_PORT", 8765, dotenv),
        MARKSYNC_SERVER=_env("MARKSYNC_SERVER", "ws://localhost:8765", dotenv),
        MARKSYNC_SERVER_DOCKER=_env("MARKSYNC_SERVER_DOCKER", "ws://sync-server:8765", dotenv),
        MARKSYNC_API_HOST=_env("MARKSYNC_API_HOST", "0.0.0.0", dotenv),
        MARKSYNC_API_PORT=_env_int("MARKSYNC_API_PORT", 8080, dotenv),
        OLLAMA_HOST=_env("OLLAMA_HOST", "localhost", dotenv),
        OLLAMA_PORT=_env_int("OLLAMA_PORT", 11434, dotenv),
        OLLAMA_URL=_env("OLLAMA_URL", "http://localhost:11434", dotenv),
        OLLAMA_URL_DOCKER=_env("OLLAMA_URL_DOCKER", "http://host.docker.internal:11434", dotenv),
        OLLAMA_MODEL=_env("OLLAMA_MODEL", "qwen2.5-coder:7b", dotenv),
        MARKPACT_PORT=_env_int("MARKPACT_PORT", 8088, dotenv),
        PROJECT_README=_env("PROJECT_README", "README.md", dotenv),
        LOG_LEVEL=_env("LOG_LEVEL", "INFO", dotenv),
    )


# Singleton — imported as `from marksync.settings import settings`
settings = load_settings()
