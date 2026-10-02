"""NPC MAC market with backend-owned rotations and atomic purchases."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import logging
import hashlib
import math
import time

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

MARKET_ART = {
    "Shama Tag": "/assets/market/shama-tag.jpg",
    "Solar Core": "/assets/market/solar-core.jpg",
    "Torpedo Cup": "/assets/market/torpedo-cup.jpg",
    "City Villa": "/assets/market/city-villa.jpg",
    "Torpedo Trophy": "/assets/market/torpedo-trophy.jpg",
    "Shadow Mask": "/assets/market/shadow-mask.jpg",
    "Football": "/assets/market/football.jpg",
    "SH Mansion": "/assets/market/sh-mansion.jpg",
}
MARKET_ROTATION_NAMES = tuple(MARKET_ART.keys())
GAME_MARKET_PERIODS = {"1D": 24, "7D": 24 * 7, "1M": 24 * 30}
GAME_MARKET_SEED = {
    "SHX": 850,
    "FARM": 420,
    "BUILD": 670,
    "TECH": 1150,
}


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
                "offers": [{**dict(row), "market_image": MARKET_ART.get(row["name"], row["image"])} for row in rows],
                "game_market": game_market_state(database_path, user_id)}


def _game_price(code: str, base: int, volatility: float, period: int) -> int:
    """A deterministic fictional price curve; every shown value is persisted."""

    digest = hashlib.sha256(f"shama-market:{code}:{period}".encode()).digest()
    noise = (int.from_bytes(digest[:4], "big") / 2**32 - 0.5) * volatility
    wave = math.sin(period / 7.0 + digest[4] / 30) * volatility * 1.4
    trend = math.sin(period / 89.0 + digest[5] / 50) * volatility * 1.1
    return max(10, int(round(base * (1 + noise + wave + trend))))


def _refresh_game_market(connection: Any) -> None:
    now = datetime.now(timezone.utc)
    current_period = int(time.time() // 3600)
    rows = connection.execute("SELECT * FROM game_market_assets ORDER BY code").fetchall()
    for row in rows:
        base = GAME_MARKET_SEED.get(row["code"], int(row["price"]))
        volatility = float(row["volatility"])
        # Keep a genuine stored one-month chart.  Once created, history is not
        # regenerated, so every market point remains a database record.
        for period in range(current_period - 24 * 30, current_period + 1):
            timestamp = datetime.fromtimestamp(period * 3600, timezone.utc).isoformat()
            price = _game_price(row["code"], base, volatility, period)
            connection.execute(
                "INSERT OR IGNORE INTO game_market_history(asset_code, recorded_at, price) VALUES (?, ?, ?)",
                (row["code"], timestamp, price),
            )
        if int(row["updated_period"]) < current_period:
            price = _game_price(row["code"], base, volatility, current_period)
            connection.execute(
                "UPDATE game_market_assets SET previous_price = price, price = ?, updated_period = ? WHERE code = ?",
                (price, current_period, row["code"]),
            )


def game_market_state(database_path: str, user_id: int, period: str = "1D") -> dict[str, Any]:
    period = period.upper()
    if period not in GAME_MARKET_PERIODS:
        raise MarketError("Доступны периоды 1D, 7D и 1M")
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        _refresh_game_market(connection)
        connection.commit()
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=GAME_MARKET_PERIODS[period])).isoformat()
        rows = connection.execute("SELECT * FROM game_market_assets ORDER BY code").fetchall()
        assets = []
        for row in rows:
            holding = connection.execute(
                "SELECT quantity, average_price FROM player_market_holdings WHERE user_id = ? AND asset_code = ?", (user_id, row["code"])
            ).fetchone()
            history = connection.execute(
                "SELECT recorded_at, price FROM game_market_history WHERE asset_code = ? AND recorded_at >= ? ORDER BY recorded_at",
                (row["code"], cutoff),
            ).fetchall()
            quantity = int(holding["quantity"]) if holding else 0
            average = float(holding["average_price"]) if holding else 0
            price = int(row["price"])
            assets.append({
                "code": row["code"], "name": row["name"], "category": row["category"], "price": price,
                "previous_price": int(row["previous_price"]),
                "change_percent": round((price / max(1, int(row["previous_price"])) - 1) * 100, 2),
                "holding": quantity, "average_price": average,
                "pnl": round((price - average) * quantity, 2) if quantity else 0,
                "history": [{"time": point["recorded_at"], "value": int(point["price"])} for point in history],
            })
        return {"source": "GAME SIMULATION", "period": period, "updated_at": datetime.now(timezone.utc).isoformat(), "assets": assets}


def trade_game_asset(database_path: str, user_id: int, code: str, side: str, quantity: int, request_id: str | None = None) -> dict[str, Any]:
    code = str(code).upper().strip(); side = str(side).upper().strip()
    if side not in {"BUY", "SELL"}:
        raise MarketError("Операция должна быть BUY или SELL")
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1 or quantity > 10_000:
        raise MarketError("Количество должно быть положительным целым числом")
    if request_id is not None:
        request_id = request_id.strip()
        if not request_id or len(request_id) > 128:
            raise MarketError("Некорректный Request ID")
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        if request_id:
            previous = connection.execute(
                "SELECT * FROM player_market_transactions WHERE user_id = ? AND request_id = ?", (user_id, request_id)
            ).fetchone()
            if previous:
                balance = connection.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()["balance"]
                return {"success": True, "idempotent": True, "balance": int(balance), "asset_code": previous["asset_code"], "side": previous["side"], "quantity": int(previous["quantity"]), "total": int(previous["total"])}
        _refresh_game_market(connection)
        asset = connection.execute("SELECT * FROM game_market_assets WHERE code = ?", (code,)).fetchone()
        if asset is None:
            raise MarketError("Игровой актив не найден")
        user = connection.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            raise MarketError("Пользователь не найден")
        price = int(asset["price"]); total = price * quantity; before = int(user["balance"])
        holding = connection.execute("SELECT * FROM player_market_holdings WHERE user_id = ? AND asset_code = ?", (user_id, code)).fetchone()
        if side == "BUY":
            after = remove_balance(connection, user_id, total)
            if holding:
                old_quantity = int(holding["quantity"])
                average = (float(holding["average_price"]) * old_quantity + total) / (old_quantity + quantity)
                connection.execute("UPDATE player_market_holdings SET quantity = ?, average_price = ? WHERE user_id = ? AND asset_code = ?", (old_quantity + quantity, average, user_id, code))
            else:
                connection.execute("INSERT INTO player_market_holdings(user_id, asset_code, quantity, average_price) VALUES (?, ?, ?, ?)", (user_id, code, quantity, price))
        else:
            if holding is None or int(holding["quantity"]) < quantity:
                raise MarketError("Недостаточно актива для продажи")
            after = add_balance(connection, user_id, total)
            remaining = int(holding["quantity"]) - quantity
            if remaining:
                connection.execute("UPDATE player_market_holdings SET quantity = ? WHERE user_id = ? AND asset_code = ?", (remaining, user_id, code))
            else:
                connection.execute("DELETE FROM player_market_holdings WHERE user_id = ? AND asset_code = ?", (user_id, code))
        cursor = connection.execute(
            "INSERT INTO player_market_transactions(user_id, asset_code, side, quantity, price, total, request_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, code, side, quantity, price, total, request_id),
        )
        record_transaction(connection, user_id, "OTHER", total, before, after, description=f"SH Market {side} {code}", metadata={"asset": code, "side": side, "quantity": quantity}, request_id=request_id)
        connection.commit()
        return {"success": True, "idempotent": False, "transaction_id": int(cursor.lastrowid), "asset_code": code, "side": side, "quantity": quantity, "price": price, "total": total, "balance": after}


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
                "description": offer["description"], "rarity": offer["rarity"], "value": offer["value"], "image": offer["image"], "market_image": MARKET_ART.get(offer["name"], offer["image"])}}
