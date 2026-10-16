"""World location reads and unlock state."""

from __future__ import annotations

try:
    from database import get_connection
except ImportError:  # pragma: no cover
    from ..database import get_connection


def locations(database_path: str, user_id: int) -> list[dict]:
    with get_connection(database_path) as connection:
        user = connection.execute("SELECT level FROM users WHERE id = ?", (user_id,)).fetchone()
        level = int(user["level"]) if user else 1
        rows = connection.execute("SELECT * FROM world_locations ORDER BY id").fetchall()
        return [{**dict(row), "unlocked": level >= int(row["unlock_level"]), "is_unlocked": level >= int(row["unlock_level"])} for row in rows]


def world_state(database_path: str, user_id: int) -> dict:
    return {"locations": locations(database_path, user_id)}
