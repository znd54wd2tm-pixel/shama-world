"""Atomic integer SH and inventory economy operations."""

from __future__ import annotations

import threading
import logging
import json
from collections import defaultdict
from typing import Any

try:
    from database import get_connection
except ImportError:  # pragma: no cover
    from ..database import get_connection


class EconomyError(RuntimeError):
    status_code = 400


class InvalidAmountError(EconomyError):
    pass


class EconomyItemNotFoundError(EconomyError):
    status_code = 404


class NotEnoughItemsError(EconomyError):
    status_code = 409


class SaleInProgressError(EconomyError):
    status_code = 409


_sale_locks: defaultdict[int, threading.Lock] = defaultdict(threading.Lock)
logger = logging.getLogger(__name__)


def _positive_integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise InvalidAmountError(f"{label} должен быть положительным целым числом")
    return value


def get_balance(connection: Any, user_id: int) -> int:
    row = connection.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise EconomyError("Пользователь не найден")
    return int(row["balance"])


def add_balance(connection: Any, user_id: int, amount: int) -> int:
    amount = _positive_integer(amount, "Сумма")
    before = get_balance(connection, user_id)
    after = before + amount
    connection.execute("UPDATE users SET balance = ? WHERE id = ?", (after, user_id))
    return after


def remove_balance(connection: Any, user_id: int, amount: int) -> int:
    amount = _positive_integer(amount, "Сумма")
    before = get_balance(connection, user_id)
    if before < amount:
        raise EconomyError(f"Недостаточно SH. Баланс: {before} SH")
    after = before - amount
    if after < 0:
        raise EconomyError("Баланс не может быть отрицательным")
    connection.execute("UPDATE users SET balance = ? WHERE id = ?", (after, user_id))
    return after


def case_payment(connection: Any, user_id: int, amount: int) -> int:
    """Shared balance deduction helper for future case economy changes."""

    return remove_balance(connection, user_id, amount)


def upgrade_transaction(connection: Any, user_id: int, source_item_id: int, target_item_id: int,
                        source_value: int, target_value: int, chance: float, result: str,
                        request_id: str | None = None) -> int:
    cursor = connection.execute(
        """INSERT INTO upgrade_transactions
           (user_id, source_item_id, target_item_id, source_value, target_value, chance, result, request_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, source_item_id, target_item_id, source_value, target_value, chance, result, request_id),
    )
    return int(cursor.lastrowid)


def record_transaction(connection: Any, user_id: int, transaction_type: str, amount: int,
                       balance_before: int, balance_after: int, *, item_id: int | None = None,
                       quantity: int = 1, description: str = "", metadata: dict[str, Any] | None = None,
                       request_id: str | None = None) -> int:
    """Write a normalized economic ledger row inside the caller's transaction."""

    if balance_before < 0 or balance_after < 0 or amount < 0:
        raise EconomyError("Экономическая транзакция содержит отрицательное значение")
    quantity = _positive_integer(quantity, "Количество")
    cursor = connection.execute(
        """INSERT INTO transactions
           (user_id, type, item_id, quantity, amount, balance_before, balance_after, description, metadata, request_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, transaction_type, item_id, quantity, amount, balance_before, balance_after,
         description, json.dumps(metadata or {}, ensure_ascii=False), request_id),
    )
    return int(cursor.lastrowid)


def sell_item(database_path: str, user_id: int, item_id: int, quantity: int,
              request_id: str | None = None) -> dict[str, Any]:
    """Sell owned units atomically and return the database-calculated result."""

    try:
        item_id = _positive_integer(item_id, "item_id")
        quantity = _positive_integer(quantity, "Количество")
    except EconomyError:
        logger.warning("sale_invalid_request user_id=%s", user_id)
        raise
    lock = _sale_locks[user_id]
    if not lock.acquire(blocking=False):
        raise SaleInProgressError("Продажа уже выполняется")
    try:
        with get_connection(database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            if request_id:
                previous = connection.execute(
                    """SELECT t.*, u.total_items_sold, u.total_sh_earned_from_sales,
                              i.name, i.rarity, i.value, i.image,
                       inv.quantity AS remaining_quantity
                       FROM transactions t JOIN items i ON i.id = t.item_id
                       JOIN users u ON u.id = t.user_id
                       LEFT JOIN inventory inv ON inv.user_id = t.user_id AND inv.item_id = t.item_id
                       WHERE t.user_id = ? AND t.type = 'SELL' AND t.request_id = ?""",
                    (user_id, request_id),
                ).fetchone()
                if previous:
                    return {
                        "success": True, "transaction_id": previous["id"], "item_id": previous["item_id"],
                        "item_name": previous["name"], "quantity": previous["quantity"], "amount": previous["amount"],
                        "balance_before": previous["balance_before"], "balance_after": previous["balance_after"],
                    "balance": previous["balance_after"], "remaining_quantity": previous["remaining_quantity"] or 0,
                    "total_items_sold": previous["total_items_sold"], "total_sh_earned_from_sales": previous["total_sh_earned_from_sales"],
                        "idempotent": True,
                    }

            row = connection.execute(
                """SELECT inv.quantity, i.id, i.name, i.value, i.rarity, i.image
                   FROM inventory inv JOIN items i ON i.id = inv.item_id
                   WHERE inv.user_id = ? AND inv.item_id = ?""",
                (user_id, item_id),
            ).fetchone()
            if row is None:
                logger.warning("sale_item_unavailable user_id=%s item_id=%s", user_id, item_id)
                raise EconomyItemNotFoundError("ITEM NO LONGER AVAILABLE")
            if row["quantity"] < quantity:
                logger.warning("sale_not_enough_items user_id=%s item_id=%s requested=%s", user_id, item_id, quantity)
                raise NotEnoughItemsError("NOT ENOUGH ITEMS")

            balance_before = get_balance(connection, user_id)
            amount = int(row["value"]) * quantity
            balance_after = add_balance(connection, user_id, amount)
            if row["quantity"] == quantity:
                connection.execute("DELETE FROM inventory WHERE user_id = ? AND item_id = ?", (user_id, item_id))
                remaining_quantity = 0
            else:
                connection.execute(
                    "UPDATE inventory SET quantity = quantity - ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND item_id = ?",
                    (quantity, user_id, item_id),
                )
                remaining_quantity = row["quantity"] - quantity
            connection.execute(
                """UPDATE users SET total_items_sold = total_items_sold + ?,
                   total_sh_earned_from_sales = total_sh_earned_from_sales + ? WHERE id = ?""",
                (quantity, amount, user_id),
            )
            stats = connection.execute(
                "SELECT total_items_sold, total_sh_earned_from_sales FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            transaction_id = record_transaction(
                connection, user_id, "SELL", amount, balance_before, balance_after,
                item_id=item_id, quantity=quantity, description="Item sale", request_id=request_id,
            )
            connection.commit()
            result = {
                "success": True, "transaction_id": transaction_id, "item_id": row["id"], "item_name": row["name"],
                "quantity": quantity, "amount": amount, "balance_before": balance_before, "balance_after": balance_after,
                "balance": balance_after, "remaining_quantity": remaining_quantity, "idempotent": False,
                "total_items_sold": stats["total_items_sold"], "total_sh_earned_from_sales": stats["total_sh_earned_from_sales"],
            }
            logger.info("sale_success user_id=%s item_id=%s quantity=%s amount=%s", user_id, item_id, quantity, amount)
            return result
    finally:
        lock.release()


def transaction_history(database_path: str, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    with get_connection(database_path) as connection:
        rows = connection.execute(
            """SELECT t.id, t.type, t.item_id, t.quantity, t.amount,
                      t.balance_before, t.balance_after, t.description, t.metadata, t.created_at,
                      i.name AS item_name, i.image AS item_image, i.rarity AS item_rarity
               FROM transactions t LEFT JOIN items i ON i.id = t.item_id
               WHERE t.user_id = ? ORDER BY t.id DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]
