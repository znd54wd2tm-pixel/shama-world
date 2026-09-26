"""NPC MAC market with backend-owned rotations and atomic purchases."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import logging

try:
    from database import get_connection
    from seed_data import ensure_market_rotation
    from services.economy import add_balance, record_transaction, remove_balance
except ImportError:  # pragma: no cover
    from ..database import get_connection
    from ..seed_data import ensure_market_rotation
    from .economy import add_balance, record_transaction, remove_balance


class MarketError(RuntimeError):
    status_code = 400


class OfferNotFoundError(MarketError):
    status_code = 404


class OfferUnavailableError(MarketError):
    status_code = 409


logger = logging.getLogger(__name__)


def _rotation(connection: Any) -> Any:
    row = connection.execute("SELECT * FROM market_rotations ORDER BY id DESC LIMIT 1").fetchone()
    if row is None:
        return None
    if datetime.fromisoformat(row["ends_at"].replace("Z", "+00:00")) <= datetime.now(timezone.utc):
        return None
    return row


def market_data(database_path: str, user_id: int) -> dict[str, Any]:
    ensure_market_rotation(database_path)
    with get_connection(database_path) as connection:
        rotation = _rotation(connection)
        if rotation is None:
            raise MarketError("Ротация рынка недоступна")
        rows = connection.execute(
            """SELECT o.id AS offer_id, o.price, o.stock, i.id, i.name, i.description, i.rarity, i.value, i.image
               FROM market_offers o JOIN items i ON i.id = o.item_id WHERE o.rotation_id = ? ORDER BY o.id""",
            (rotation["id"],),
        ).fetchall()
        return {"rotation": {"id": rotation["id"], "started_at": rotation["started_at"], "ends_at": rotation["ends_at"]},
                "offers": [dict(row) for row in rows]}


def buy_offer(database_path: str, user_id: int, offer_id: int, quantity: int = 1, request_id: str | None = None) -> dict[str, Any]:
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity != 1:
        raise MarketError("Количество покупки должно быть равно 1")
    ensure_market_rotation(database_path)
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        if request_id:
            previous = connection.execute("SELECT * FROM transactions WHERE user_id = ? AND request_id = ? AND type = 'MARKET_PURCHASE'", (user_id, request_id)).fetchone()
            if previous:
                return {"success": True, "idempotent": True, "transaction_id": previous["id"], "balance": previous["balance_after"], "amount": previous["amount"]}
        rotation = _rotation(connection)
        if rotation is None:
            raise OfferUnavailableError("Ротация рынка завершилась")
        offer = connection.execute(
            "SELECT o.*, i.name, i.description, i.rarity, i.value, i.image FROM market_offers o JOIN items i ON i.id = o.item_id WHERE o.id = ? AND o.rotation_id = ?",
            (offer_id, rotation["id"]),
        ).fetchone()
        if offer is None:
            raise OfferNotFoundError("Предложение не найдено")
        if int(offer["stock"]) < 1:
            raise OfferUnavailableError("Предмет закончился")
        user = connection.execute("SELECT balance, xp FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            raise MarketError("Пользователь не найден")
        before = int(user["balance"])
        after = remove_balance(connection, user_id, int(offer["price"]))
        new_xp = int(user["xp"]) + 1
        connection.execute("UPDATE users SET xp = ?, level = ? WHERE id = ?", (new_xp, new_xp // 100 + 1, user_id))
        existing = connection.execute("SELECT id FROM inventory WHERE user_id = ? AND item_id = ?", (user_id, offer["item_id"])).fetchone()
        if existing:
            connection.execute("UPDATE inventory SET quantity = quantity + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (existing["id"],))
        else:
            connection.execute("INSERT INTO inventory(user_id, item_id, quantity) VALUES (?, ?, 1)", (user_id, offer["item_id"]))
        connection.execute("UPDATE market_offers SET stock = stock - 1 WHERE id = ?", (offer_id,))
        transaction_id = record_transaction(connection, user_id, "MARKET_PURCHASE", int(offer["price"]), before, after,
                                            item_id=offer["item_id"], description="MAC market purchase",
                                            metadata={"offer_id": offer_id}, request_id=request_id)
        connection.commit()
        logger.info("market_purchase_success user_id=%s offer_id=%s amount=%s", user_id, offer_id, offer["price"])
        return {"success": True, "idempotent": False, "transaction_id": transaction_id, "balance": after,
                "amount": int(offer["price"]), "xp": new_xp, "level": new_xp // 100 + 1, "item": {"id": offer["item_id"], "name": offer["name"],
                "description": offer["description"], "rarity": offer["rarity"], "value": offer["value"], "image": offer["image"]}}
