"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")


class ConfigError(RuntimeError):
    """Raised when a required environment variable is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    bot_token: str
    webapp_url: str
    database_path: Path


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"Missing environment variable: {name}")
    return value


def is_render_environment() -> bool:
    """Return True when running inside Render's runtime."""
    return any(
        os.getenv(name)
        for name in ("RENDER", "RENDER_SERVICE_ID", "RENDER_EXTERNAL_URL")
    )


def get_settings(*, require_bot: bool = True, require_webapp: bool = True) -> Settings:
    """Build settings without validating secrets at import time.

    The API only needs the database path for health checks, while the bot and
    authenticated API routes require both Telegram values.
    """

    bot_token = _required("BOT_TOKEN") if require_bot else os.getenv("BOT_TOKEN", "").strip()
    webapp_url = _required("WEBAPP_URL") if require_webapp else os.getenv("WEBAPP_URL", "").strip()
    # SQLite is intentionally stored on Render's ephemeral filesystem.
    # A Persistent Disk is not required for the free deployment.  If an old
    # Render environment variable still points at /var/data, transparently
    # fall back to the project directory when that mount is unavailable.
    database_value = os.getenv("DATABASE_PATH", "shama_world.db").strip() or "shama_world.db"

    if webapp_url:
        parsed = urlparse(webapp_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ConfigError("WEBAPP_URL must be a valid http(s) URL")

    database_path = Path(database_value)
    if not database_path.is_absolute():
        database_path = PROJECT_ROOT / database_path

    # Backwards compatibility with the previous paid-disk configuration.
    # On Render Free /var/data is not mounted, so never fail startup because
    # an old DATABASE_PATH value is still present in the service settings.
    if is_render_environment():
        try:
            database_path.relative_to(Path("/var/data"))
        except ValueError:
            pass
        else:
            persistent_root = Path("/var/data")
            if not persistent_root.is_dir() or not os.access(persistent_root, os.W_OK):
                database_path = PROJECT_ROOT / "shama_world.db"

    return Settings(
        bot_token=bot_token,
        webapp_url=webapp_url,
        database_path=database_path,
    )
