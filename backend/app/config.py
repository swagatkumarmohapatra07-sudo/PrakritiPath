"""Application configuration.

All settings are read from environment variables (optionally loaded from a
project-root ``.env`` file) so that no secrets live in source code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

FRONTEND_DIR = PROJECT_ROOT / "frontend"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    env: str = os.getenv("BIOTRACE_ENV", "development")
    host: str = os.getenv("BIOTRACE_HOST", "127.0.0.1")
    port: int = field(default_factory=lambda: _env_int("BIOTRACE_PORT", 8000))

    database_url: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{(PROJECT_ROOT / 'data' / 'biotrace.db').as_posix()}"
    )
    secret_key: str = os.getenv("BIOTRACE_SECRET_KEY", "dev-only-insecure-secret")

    cors_origins: list[str] = field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000"
            ).split(",")
            if origin.strip()
        ]
    )

    admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "change-me-please")
    admin_token_ttl_minutes: int = field(
        default_factory=lambda: _env_int("ADMIN_TOKEN_TTL_MINUTES", 480)
    )

    max_upload_mb: int = field(default_factory=lambda: _env_int("MAX_UPLOAD_MB", 8))
    upload_dir: Path = field(
        default_factory=lambda: (PROJECT_ROOT / os.getenv("UPLOAD_DIR", "data/uploads")).resolve()
    )
    model_dir: Path = field(
        default_factory=lambda: (PROJECT_ROOT / os.getenv("MODEL_DIR", "models")).resolve()
    )

    # Selective-prediction threshold selected on the validation split of the
    # demo models. Recorded in each model_card.json and overridable here.
    min_confidence: float = float(os.getenv("BIOTRACE_MIN_CONFIDENCE", "0.55"))

    # Nominatim blocks generic browser strings and some contact formats. Set a
    # unique app name plus a real contact address in .env before bulk imports.
    nominatim_user_agent: str = os.getenv(
        "NOMINATIM_USER_AGENT", "BioTrace-Academic-Project/1.0"
    )
    wikipedia_enrichment: bool = field(
        default_factory=lambda: _env_bool("WIKIPEDIA_ENRICHMENT", False)
    )

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


settings = Settings()

# Directories created eagerly so the app can boot on a fresh clone.
# On read-only filesystems (for example Vercel Functions) creation is skipped;
# point UPLOAD_DIR/MODEL_DIR/DATABASE_URL at a writable location such as /tmp.
for directory in (
    settings.upload_dir,
    settings.model_dir,
    PROJECT_ROOT / "data",
):
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:  # pragma: no cover - only on read-only serverless filesystems
        pass
