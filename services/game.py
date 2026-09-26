"""Atomic case opening and drop selection."""

from __future__ import annotations

import random
import threading
from collections import defaultdict
from typing import Any

try:
    from database import get_connection
    from services.economy import case_payment, record_transaction
except ImportError:  # pragma: no cover
    from ..database import get_connection
    from .economy import case_payment, record_transaction


class GameError(RuntimeError):
    status_code = 400


class CaseNotFoundError(GameError):
    status_code = 404


class InsufficientBalanceError(GameError):
    status_code = 400


class EmptyDropPoolError(GameError):
    status_code = 409


class OpeningInProgressError(GameError):
    status_code = 409


_locks: defaultdict[int, threading.Lock] = defaultdict(threading.Lock)
_rng = random.SystemRandom()


def _choose_drop(rows: list[Any]) -> Any:
    if not rows:
        raise EmptyDropPoolError("У кейса нет доступных предметов")
    total = sum(float(row["chance"]) for row in rows)
    if abs(total - 1.0) > 0.00001:
        raise EmptyDropPoolError("Drop pool кейса настроен некорректно")
    roll = _rng.random()
    cursor = 0.0
    for row in rows:
        cursor += float(row["chance"])
        if roll < cursor:
            return row
    return rows[-1]


def open_case(database_path: str, user_id: int, case_id: int, request_id: str | None = None) -> dict[str, Any]:
    lock = _locks[user_id]
    if not lock.acquire(blocking=False):
        raise OpeningInProgressError("Открытие уже выполняется")
    try:
        with get_connection(database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            if request_id:
                previous = connection.execute(
                    """
                    SELECT o.case_id, o.item_id, i.name, i.description, i.rarity, i.value, i.image,
                           inv.quantity, u.balance, u.xp, u.level
                    FROM case_openings o JOIN items i ON i.id = o.item_id
                    JOIN users u ON u.id = o.user_id
                    LEFT JOIN inventory inv ON inv.user_id = o.user_id AND inv.item_id = o.item_id
                    WHERE o.user_id = ? AND o.request_id = ?
                    """,
                    (user_id, request_id),
                ).fetchone()
                if previous:
                    if previous["case_id"] != case_id:
                        raise GameError("Идентификатор открытия уже использован")
                    return {
                        "success": True,
                        "item": {"id": previous["item_id"], "name": previous["name"], "description": previous["description"],
                                 "rarity": previous["rarity"], "value": previous["value"], "image": previous["image"],
                                 "quantity": previous["quantity"]},
                        "balance": previous["balance"], "xp": previous["xp"], "level": previous["level"], "idempotent": True,
                    }
            case = connection.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
            if case is None:
                raise CaseNotFoundError("Кейс не найден")
            user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if user is None:
                raise GameError("Пользователь не найден")
            if user["balance"] < case["price"]:
                raise InsufficientBalanceError(f"Недостаточно SH. Баланс: {user['balance']} SH")

            drops = connection.execute(
                """
                SELECT d.chance, i.id, i.name, i.description, i.rarity, i.value, i.image
                FROM case_drops d JOIN items i ON i.id = d.item_id
                WHERE d.case_id = ? ORDER BY d.id
                """,
                (case_id,),
            ).fetchall()
            item = _choose_drop(drops)
            new_xp = user["xp"] + 10
            new_level = new_xp // 100 + 1
            existing = connection.execute(
                "SELECT id, quantity FROM inventory WHERE user_id = ? AND item_id = ?",
                (user_id, item["id"]),
            ).fetchone()
            if existing:
                connection.execute(
                    "UPDATE inventory SET quantity = quantity + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (existing["id"],),
                )
                quantity = existing["quantity"] + 1
                collected_increment = 0
            else:
                connection.execute("INSERT INTO inventory (user_id, item_id, quantity) VALUES (?, ?, 1)", (user_id, item["id"]))
                quantity = 1
                collected_increment = 1

            balance_before = int(user["balance"])
            balance = case_payment(connection, user_id, case["price"])
            connection.execute(
                """
                UPDATE users SET xp = ?, level = ?,
                    cases_opened = cases_opened + 1, items_collected = items_collected + ?
                WHERE id = ?
                """,
                (new_xp, new_level, collected_increment, user_id),
            )
            connection.execute(
                "INSERT INTO case_openings (user_id, case_id, item_id, price_paid, request_id) VALUES (?, ?, ?, ?, ?)",
                (user_id, case_id, item["id"], case["price"], request_id),
            )
            record_transaction(
                connection, user_id, "CASE_OPEN", int(case["price"]), balance_before, balance,
                item_id=item["id"], description=f"Open {case['name']}", metadata={"case_id": case_id}, request_id=request_id,
            )
            connection.commit()
            return {
                "success": True,
                "item": {
                    "id": item["id"], "name": item["name"], "description": item["description"],
                    "rarity": item["rarity"], "value": item["value"], "image": item["image"], "quantity": quantity,
                },
                "balance": balance,
                "xp": new_xp,
                "level": new_level,
            }
    finally:
        lock.release()
