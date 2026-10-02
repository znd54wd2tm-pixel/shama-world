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
    supabase_url: str = ""
    supabase_service_role_key: str = ""

    @property
    def supabase_configured(self) -> bool:
        """Whether the backend can use the private Supabase state backup."""

        return bool(self.supabase_url and self.supabase_service_role_key)


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"Missing environment variable: {name}")
    return value


def is_render_environment() -> bool:
    """Return whether the process runs under Render's production runtime."""

    return any(os.getenv(name) for name in ("RENDER", "RENDER_SERVICE_ID", "RENDER_EXTERNAL_URL"))


def require_persistent_database(settings: "Settings") -> None:
    """Fail closed if a Render deployment would create an ephemeral SQLite file.

    A relative or `/opt/render/project` database path works locally but is
    discarded on a Render restart. Refusing that configuration is safer than
    silently starting a fresh world with an empty user table.
    """

    if not is_render_environment():
        return
    persistent_root = Path("/var/data")
    database_path = settings.database_path.resolve(strict=False)
    try:
        database_path.relative_to(persistent_root)
    except ValueError as error:
        raise ConfigError(
            "Render production requires DATABASE_PATH inside /var/data. "
            "Attach the persistent disk and set DATABASE_PATH=/var/data/shama_world.db."
        ) from error
    if not persistent_root.is_dir() or not os.access(persistent_root, os.W_OK):
        raise ConfigError(
            "Render persistent disk /var/data is unavailable or not writable. "
            "Refusing to start with an ephemeral SQLite database."
        )


def get_settings(*, require_bot: bool = True, require_webapp: bool = True) -> Settings:
    """Build settings without validating secrets at import time.

    The API only needs the database path for health checks, while the bot and
    authenticated API routes require both Telegram values.
    """

    bot_token = _required("BOT_TOKEN") if require_bot else os.getenv("BOT_TOKEN", "").strip()
    webapp_url = _required("WEBAPP_URL") if require_webapp else os.getenv("WEBAPP_URL", "").strip()
    database_value = os.getenv("DATABASE_PATH", "shama_world.db").strip()
    if not database_value:
        raise ConfigError("Missing environment variable: DATABASE_PATH")

    if webapp_url:
        parsed = urlparse(webapp_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ConfigError("WEBAPP_URL must be a valid http(s) URL")

    supabase_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if bool(supabase_url) != bool(supabase_service_role_key):
        raise ConfigError(
            "Set both SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY, or leave both unset."
        )
    if supabase_url:
        parsed_supabase = urlparse(supabase_url)
        if parsed_supabase.scheme != "https" or not parsed_supabase.netloc:
            raise ConfigError("SUPABASE_URL must be a valid https URL")

    database_path = Path(database_value)
    if not database_path.is_absolute():
        database_path = PROJECT_ROOT / database_path

    return Settings(
        bot_token=bot_token,
        webapp_url=webapp_url,
        database_path=database_path,
        supabase_url=supabase_url,
        supabase_service_role_key=supabase_service_role_key,
    )
