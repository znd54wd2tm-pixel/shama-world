"""Durable Supabase backup and recovery for the SQLite game state.

SQLite remains the transactional source used by every game service.  A compact
database snapshot is stored in the private ``shama_world_state`` Supabase row
after game API calls.  On Render, a new empty persistent-disk database is
restored before the app serves requests.  This protects player progress while
keeping the normal request path and Telegram cold start fast.

The service-role credential is read only from server environment variables.
It is never returned to callers, written to snapshots, or exposed to the web
application.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    from config import Settings, is_render_environment
    from database import get_connection
except ImportError:  # pragma: no cover
    from ..config import Settings, is_render_environment
    from ..database import get_connection


logger = logging.getLogger(__name__)
SNAPSHOT_FORMAT = "shama-world-sqlite-v1"
HTTP_TIMEOUT_SECONDS = 4
MAX_SNAPSHOT_BYTES = 4_500_000
STATE_TABLE = "shama_world_state"
_sync_lock = threading.RLock()


class SupabaseSyncError(RuntimeError):
    """Raised when configured durable storage cannot safely be used."""


@dataclass(frozen=True)
class SyncResult:
    status: str
    users: int
    updated_at: str | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _configured(settings: Settings) -> bool:
    return settings.supabase_configured


def _headers(settings: Settings, *, json_body: bool = False) -> dict[str, str]:
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Accept": "application/json",
    }
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


def _request_json(settings: Settings, method: str, path: str, *, body: Any | None = None) -> Any:
    """Execute one short server-to-server REST request without logging secrets."""

    if not _configured(settings):
        raise SupabaseSyncError("Supabase backup is not configured")
    payload = None if body is None else json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    headers = _headers(settings, json_body=payload is not None)
    if method == "POST":
        headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
    request = Request(
        f"{settings.supabase_url}{path}",
        data=payload,
        method=method,
        headers=headers,
    )
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:  # nosec B310: configured HTTPS endpoint
            raw = response.read()
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))
    except HTTPError as error:
        # Response details can include request context, so keep logs generic.
        raise SupabaseSyncError(f"Supabase returned HTTP {error.code}") from error
    except (URLError, TimeoutError, OSError) as error:
        raise SupabaseSyncError("Supabase is temporarily unavailable") from error
    except json.JSONDecodeError as error:
        raise SupabaseSyncError("Supabase returned an invalid response") from error


def _table_names(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute(
        """SELECT name FROM sqlite_master
           WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
           ORDER BY name"""
    ).fetchall()
    return [str(row[0]) for row in rows]


def _export_state(database_path: Path | str) -> tuple[dict[str, Any], int]:
    """Read a consistent, JSON-safe full state snapshot from SQLite."""

    with get_connection(database_path) as connection:
        connection.execute("BEGIN")
        tables: dict[str, list[dict[str, Any]]] = {}
        for table in _table_names(connection):
            rows = connection.execute(f"SELECT * FROM {_quote(table)}").fetchall()
            tables[table] = [dict(row) for row in rows]
        users = len(tables.get("users", []))
        connection.commit()
    state = {"format": SNAPSHOT_FORMAT, "tables": tables}
    encoded = json.dumps(state, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_SNAPSHOT_BYTES:
        raise SupabaseSyncError("The game snapshot is too large for the configured cloud backup")
    return state, users


def user_count(database_path: Path | str) -> int:
    with get_connection(database_path) as connection:
        row = connection.execute("SELECT COUNT(*) AS count FROM users").fetchone()
        return int(row["count"])


def sync_snapshot(database_path: Path | str, settings: Settings) -> SyncResult:
    """UPSERT the complete game snapshot into the single protected row."""

    if not _configured(settings):
        return SyncResult(status="disabled", users=user_count(database_path))
    with _sync_lock:
        state, users = _export_state(database_path)
        updated_at = _now_iso()
        _request_json(
            settings,
            "POST",
            f"/rest/v1/{STATE_TABLE}?on_conflict=id",
            body={
                "id": 1,
                "schema_version": SNAPSHOT_FORMAT,
                "state": state,
                "updated_at": updated_at,
            },
        )
        return SyncResult(status="synced", users=users, updated_at=updated_at)


def _fetch_snapshot(settings: Settings) -> tuple[dict[str, Any] | None, str | None]:
    query = urlencode({"id": "eq.1", "select": "schema_version,state,updated_at"})
    rows = _request_json(settings, "GET", f"/rest/v1/{STATE_TABLE}?{query}")
    if not rows:
        return None, None
    row = rows[0]
    if row.get("schema_version") != SNAPSHOT_FORMAT:
        raise SupabaseSyncError("Supabase snapshot format is not supported by this version")
    state = row.get("state")
    if not isinstance(state, dict) or state.get("format") != SNAPSHOT_FORMAT:
        raise SupabaseSyncError("Supabase snapshot is invalid")
    return state, row.get("updated_at")


def _foreign_parent_order(connection: sqlite3.Connection, tables: Iterable[str]) -> list[str]:
    """Return local tables parent-first so restoration honors foreign keys."""

    names = list(tables)
    allowed = set(names)
    parents: dict[str, set[str]] = {}
    for table in names:
        refs = connection.execute(f"PRAGMA foreign_key_list({_quote(table)})").fetchall()
        parents[table] = {str(row[2]) for row in refs if str(row[2]) in allowed}

    ordered: list[str] = []
    visited: set[str] = set()
    visiting: set[str] = set()

    def visit(table: str) -> None:
        if table in visited:
            return
        if table in visiting:
            # The schema has no cycles today.  Keeping the current table last
            # still permits SQLite's post-restore foreign-key verification.
            return
        visiting.add(table)
        for parent in sorted(parents[table]):
            visit(parent)
        visiting.remove(table)
        visited.add(table)
        ordered.append(table)

    for table_name in names:
        visit(table_name)
    return ordered


def _restore_state(database_path: Path | str, state: dict[str, Any]) -> int:
    tables = state.get("tables")
    if not isinstance(tables, dict):
        raise SupabaseSyncError("Supabase snapshot has no tables")

    with get_connection(database_path) as connection:
        local_tables = _table_names(connection)
        restorable = [name for name in local_tables if isinstance(tables.get(name), list)]
        if "users" not in restorable:
            raise SupabaseSyncError("Supabase snapshot has no user data table")
        parent_first = _foreign_parent_order(connection, restorable)
        try:
            # A foreign-key switch must be made outside a transaction.
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("BEGIN IMMEDIATE")
            for table in reversed(parent_first):
                connection.execute(f"DELETE FROM {_quote(table)}")
            for table in parent_first:
                columns = [str(row[1]) for row in connection.execute(f"PRAGMA table_info({_quote(table)})").fetchall()]
                for raw_row in tables[table]:
                    if not isinstance(raw_row, dict):
                        raise SupabaseSyncError(f"Invalid row in snapshot table {table}")
                    row = {column: raw_row[column] for column in columns if column in raw_row}
                    if not row:
                        continue
                    names = list(row)
                    placeholders = ", ".join("?" for _ in names)
                    connection.execute(
                        f"INSERT INTO {_quote(table)} ({', '.join(_quote(name) for name in names)}) VALUES ({placeholders})",
                        tuple(row[name] for name in names),
                    )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.execute("PRAGMA foreign_keys = ON")
        problems = connection.execute("PRAGMA foreign_key_check").fetchall()
        if problems:
            raise SupabaseSyncError("Restored snapshot failed the foreign-key validation")
    return user_count(database_path)


def restore_if_empty(database_path: Path | str, settings: Settings, *, required: bool = False) -> SyncResult:
    """Restore durable player state only into a database with no users.

    ``required`` is used by a Render production boot.  It prevents a newly
    attached or accidentally empty disk from silently creating a fresh world
    when a configured backup is unreachable.
    """

    current_users = user_count(database_path)
    if current_users:
        return SyncResult(status="local-state-present", users=current_users)
    if not _configured(settings):
        if required:
            raise SupabaseSyncError(
                "The persistent database is empty and Supabase recovery is not configured"
            )
        return SyncResult(status="disabled", users=0)
    with _sync_lock:
        snapshot, updated_at = _fetch_snapshot(settings)
        if snapshot is None:
            if required:
                raise SupabaseSyncError(
                    "The persistent database is empty and no Supabase backup exists"
                )
            return SyncResult(status="no-cloud-state", users=0)
        restored_users = _restore_state(database_path, snapshot)
        return SyncResult(status="restored", users=restored_users, updated_at=updated_at)


def configure_application_state(application: Any, database_path: Path, settings: Settings) -> None:
    application.state.supabase_sync_enabled = _configured(settings)
    application.state.supabase_sync_settings = settings
    application.state.supabase_sync_path = database_path
    application.state.supabase_sync_task = None
    application.state.supabase_sync_pending = False
    application.state.supabase_last_sync_error = None


def queue_snapshot_sync(application: Any) -> None:
    """Coalesce a burst of successful API calls into background cloud writes."""

    if not getattr(application.state, "supabase_sync_enabled", False):
        return
    active = getattr(application.state, "supabase_sync_task", None)
    if active is not None and not active.done():
        application.state.supabase_sync_pending = True
        return

    async def worker() -> None:
        while True:
            application.state.supabase_sync_pending = False
            try:
                result = await asyncio.to_thread(
                    sync_snapshot,
                    application.state.supabase_sync_path,
                    application.state.supabase_sync_settings,
                )
                application.state.supabase_last_sync_error = None
                logger.info("Supabase state synced: users=%s updated_at=%s", result.users, result.updated_at)
            except Exception as error:  # disk remains source of truth; retry on later activity/restart
                application.state.supabase_last_sync_error = str(error)
                logger.warning("Supabase state sync deferred: %s", error)
            if not application.state.supabase_sync_pending:
                break

    application.state.supabase_sync_task = asyncio.create_task(worker(), name="shama-supabase-sync")


async def flush_snapshot_sync(application: Any) -> None:
    """Make one bounded final sync during graceful shutdown."""

    if not getattr(application.state, "supabase_sync_enabled", False):
        return
    active = getattr(application.state, "supabase_sync_task", None)
    if active is not None:
        try:
            await asyncio.wait_for(asyncio.shield(active), timeout=HTTP_TIMEOUT_SECONDS + 2)
            return
        except (asyncio.TimeoutError, Exception):
            pass
    try:
        await asyncio.wait_for(
            asyncio.to_thread(
                sync_snapshot,
                application.state.supabase_sync_path,
                application.state.supabase_sync_settings,
            ),
            timeout=HTTP_TIMEOUT_SECONDS + 2,
        )
    except Exception as error:
        logger.warning("Final Supabase state sync deferred: %s", error)


def should_require_recovery(settings: Settings, database_existed: bool) -> bool:
    """Only production empty disks must prove recovery before accepting players."""

    return is_render_environment() and not database_existed
