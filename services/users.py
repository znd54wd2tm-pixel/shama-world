"""User persistence service."""

from __future__ import annotations

import sqlite3
from typing import Any

try:
    from database import get_connection
except ImportError:  # pragma: no cover
    from ..database import get_connection


def serialize_user(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def get_or_create_user(database_path: str, telegram_user: dict[str, Any]) -> dict[str, Any]:
    telegram_id = int(telegram_user["id"])
    with get_connection(database_path) as connection:
        row = connection.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        if row is None:
            connection.execute(
                "INSERT INTO users (telegram_id, username, first_name, last_name) VALUES (?, ?, ?, ?)",
                (telegram_id, telegram_user.get("username"), telegram_user.get("first_name", ""), telegram_user.get("last_name")),
            )
            connection.commit()
            row = connection.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        return serialize_user(row)
