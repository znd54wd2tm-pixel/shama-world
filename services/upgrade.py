"""Server-authoritative item upgrade mechanics."""

from __future__ import annotations

import random
import threading
from collections import defaultdict
from typing import Any

try:
    from database import get_connection
    from services.economy import upgrade_transaction, record_transaction
except ImportError:  # pragma: no cover
    from ..database import get_connection
    from .economy import upgrade_transaction, record_transaction


BASE_CHANCE = 90.0
EXPONENT = 1.25
MIN_CHANCE = 1.0
MAX_CHANCE = 95.0
XP_PER_UPGRADE = 5


class UpgradeError(RuntimeError):
    status_code = 400


class UpgradeItemNotFoundError(UpgradeError):
    status_code = 404


class UpgradeOwnershipError(UpgradeError):
    status_code = 409


class InvalidUpgradeTargetError(UpgradeError):
    status_code = 400


class UpgradeInProgressError(UpgradeError):
    status_code = 409


_locks: defaultdict[int, threading.Lock] = defaultdict(threading.Lock)
_rng = random.SystemRandom()


def calculate_chance(source_value: int, target_value: int) -> float:
    """Return a bounded chance derived only from database item values."""

    if source_value <= 0 or target_value <= source_value:
        raise InvalidUpgradeTargetError("Цель должна быть дороже исходного предмета")
    ratio = target_value / source_value
    chance = BASE_CHANCE / (ratio ** EXPONENT)
    return round(max(MIN_CHANCE, min(MAX_CHANCE, chance)), 1)


def _item(row: Any, *, quantity: int | None = None) -> dict[str, Any]:
    result = {
        "id": row["id"], "name": row["name"], "description": row["description"],
        "rarity": row["rarity"], "value": row["value"], "image": row["image"],
    }
    if quantity is not None:
        result["quantity"] = quantity
    return result


def _load_items(connection: Any, source_item_id: int, target_item_id: int) -> tuple[Any, Any]:
    source = connection.execute("SELECT * FROM items WHERE id = ?", (source_item_id,)).fetchone()
    if source is None:
        raise UpgradeItemNotFoundError("Исходный предмет больше недоступен")
    target = connection.execute("SELECT * FROM items WHERE id = ?", (target_item_id,)).fetchone()
    if target is None:
        raise UpgradeItemNotFoundError("Целевой предмет больше недоступен")
    if target["value"] <= source["value"]:
        raise InvalidUpgradeTargetError("Цель должна быть дороже исходного предмета")
    return source, target


def _owned_quantity(connection: Any, user_id: int, item_id: int) -> int:
    row = connection.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_id = ?", (user_id, item_id)).fetchone()
    return int(row["quantity"]) if row else 0


def _recommendations(connection: Any, source: Any, limit: int = 8) -> list[dict[str, Any]]:
    rows = connection.execute("SELECT * FROM items WHERE value > ? ORDER BY value ASC, id ASC", (source["value"],)).fetchall()
    return [{**_item(row), "chance": calculate_chance(source["value"], row["value"])} for row in rows[:limit]]


def preview_upgrade(database_path: str, user_id: int, source_item_id: int, target_item_id: int) -> dict[str, Any]:
    with get_connection(database_path) as connection:
        source, target = _load_items(connection, source_item_id, target_item_id)
        quantity = _owned_quantity(connection, user_id, source_item_id)
        if quantity < 1:
            raise UpgradeOwnershipError("Исходный предмет больше недоступен")
        chance = calculate_chance(source["value"], target["value"])
        return {
            "source": _item(source, quantity=quantity),
            "target": _item(target),
            "chance": chance,
            "recommended_targets": _recommendations(connection, source),
        }


def target_options(database_path: str, user_id: int, source_item_id: int) -> list[dict[str, Any]]:
    with get_connection(database_path) as connection:
        source = connection.execute("SELECT * FROM items WHERE id = ?", (source_item_id,)).fetchone()
        if source is None:
            raise UpgradeItemNotFoundError("Исходный предмет больше недоступен")
        if _owned_quantity(connection, user_id, source_item_id) < 1:
            raise UpgradeOwnershipError("Исходный предмет больше недоступен")
        return _recommendations(connection, source, limit=10_000)


def _result_payload(transaction: Any, source: Any, target: Any, balance: int, xp: int, level: int) -> dict[str, Any]:
    return {
        "success": transaction["result"] == "SUCCESS",
        "result": transaction["result"],
        "source": _item(source), "target": _item(target),
        "chance": transaction["chance"], "balance": balance, "xp": xp, "level": level,
        "transaction_id": transaction["id"], "idempotent": False,
    }


def execute_upgrade(
    database_path: str,
    user_id: int,
    source_item_id: int,
    target_item_id: int,
    request_id: str | None = None,
) -> dict[str, Any]:
    lock = _locks[user_id]
    if not lock.acquire(blocking=False):
        raise UpgradeInProgressError("Апгрейд уже выполняется")
    try:
        with get_connection(database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            if request_id:
                previous = connection.execute(
                    "SELECT * FROM upgrade_transactions WHERE user_id = ? AND request_id = ?",
                    (user_id, request_id),
                ).fetchone()
                if previous:
                    if previous["source_item_id"] != source_item_id or previous["target_item_id"] != target_item_id:
                        raise UpgradeError("Идентификатор апгрейда уже использован")
                    source, target = _load_items(connection, source_item_id, target_item_id)
                    user = connection.execute("SELECT balance, xp, level FROM users WHERE id = ?", (user_id,)).fetchone()
                    result = _result_payload(previous, source, target, user["balance"], user["xp"], user["level"])
                    result["idempotent"] = True
                    return result

            source, target = _load_items(connection, source_item_id, target_item_id)
            quantity = _owned_quantity(connection, user_id, source_item_id)
            if quantity < 1:
                raise UpgradeOwnershipError("Исходный предмет больше недоступен")
            user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if user is None:
                raise UpgradeError("Пользователь не найден")
            chance = calculate_chance(source["value"], target["value"])
            result_name = "SUCCESS" if _rng.random() * 100 < chance else "FAIL"

            if quantity == 1:
                connection.execute("DELETE FROM inventory WHERE user_id = ? AND item_id = ?", (user_id, source_item_id))
            else:
                connection.execute(
                    "UPDATE inventory SET quantity = quantity - 1, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND item_id = ?",
                    (user_id, source_item_id),
                )

            if result_name == "SUCCESS":
                existing_target = connection.execute("SELECT id FROM inventory WHERE user_id = ? AND item_id = ?", (user_id, target_item_id)).fetchone()
                if existing_target:
                    connection.execute("UPDATE inventory SET quantity = quantity + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (existing_target["id"],))
                else:
                    connection.execute("INSERT INTO inventory (user_id, item_id, quantity) VALUES (?, ?, 1)", (user_id, target_item_id))

            new_xp = user["xp"] + XP_PER_UPGRADE
            new_level = new_xp // 100 + 1
            connection.execute(
                """UPDATE users SET xp = ?, level = ?, upgrades_total = upgrades_total + 1,
                   upgrades_success = upgrades_success + ?, upgrades_failed = upgrades_failed + ? WHERE id = ?""",
                (new_xp, new_level, int(result_name == "SUCCESS"), int(result_name == "FAIL"), user_id),
            )
            transaction_id = upgrade_transaction(
                connection, user_id, source_item_id, target_item_id,
                source["value"], target["value"], chance, result_name, request_id,
            )
            record_transaction(
                connection, user_id, "UPGRADE_SUCCESS" if result_name == "SUCCESS" else "UPGRADE_FAIL", 0,
                int(user["balance"]), int(user["balance"]), item_id=target_item_id,
                description=f"Upgrade {result_name.lower()}", metadata={"source_item_id": source_item_id, "target_item_id": target_item_id},
                request_id=request_id,
            )
            transaction = connection.execute("SELECT * FROM upgrade_transactions WHERE id = ?", (transaction_id,)).fetchone()
            connection.commit()
            return _result_payload(transaction, source, target, user["balance"], new_xp, new_level)
    finally:
        lock.release()


def upgrade_history(database_path: str, user_id: int, limit: int = 5) -> list[dict[str, Any]]:
    with get_connection(database_path) as connection:
        rows = connection.execute(
            """
            SELECT t.id, t.source_value, t.target_value, t.chance, t.result, t.created_at,
                   s.name AS source_name, s.image AS source_image, s.rarity AS source_rarity,
                   g.name AS target_name, g.image AS target_image, g.rarity AS target_rarity
            FROM upgrade_transactions t
            JOIN items s ON s.id = t.source_item_id
            JOIN items g ON g.id = t.target_item_id
            WHERE t.user_id = ? ORDER BY t.id DESC LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]
