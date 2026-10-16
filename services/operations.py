"""Shared durable request receipts and inventory consumption for all game flows."""
from __future__ import annotations

import json
import uuid
from typing import Any

from services.economy import EconomyError


def request_key(value: str | None) -> str:
    if value is None:
        return str(uuid.uuid4())
    if not isinstance(value, str) or not value.strip() or len(value) > 110:
        raise EconomyError("Некорректный идентификатор операции")
    return value.strip()


def fingerprint(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def cached(connection: Any, user_id: int, key: str, action: str, payload: Any) -> dict | None:
    row = connection.execute("SELECT * FROM game_actions WHERE user_id=? AND request_id=?", (user_id, key)).fetchone()
    if row:
        if row["action"] != action or row["fingerprint"] != fingerprint(payload):
            raise EconomyError("Идентификатор операции уже использован для другого запроса")
        return {**json.loads(row["response_json"]), "idempotent": True}
    return None


def receipt(connection: Any, user_id: int, key: str, action: str, payload: Any, result: dict) -> dict:
    connection.execute("INSERT INTO game_actions VALUES (?,?,?,?,?)", (user_id, key, action, fingerprint(payload), json.dumps(result, ensure_ascii=False)))
    return result


def add_item(connection: Any, user_id: int, item_id: int, quantity: int = 1) -> None:
    connection.execute("""INSERT INTO inventory(user_id,item_id,quantity) VALUES (?,?,?)
        ON CONFLICT(user_id,item_id) DO UPDATE SET quantity=quantity+excluded.quantity, updated_at=CURRENT_TIMESTAMP""", (user_id, item_id, quantity))


def consume_item(connection: Any, user_id: int, item_id: int, quantity: int, status: str,
                 result_ids: list[str] | None = None) -> None:
    row = connection.execute("SELECT quantity FROM inventory WHERE user_id=? AND item_id=?", (user_id, item_id)).fetchone()
    if row is None or row["quantity"] < quantity:
        raise EconomyError("Предмет уже продан, использован или выставлен на рынок")
    if result_ids is None:
        tracked = connection.execute("SELECT id FROM opening_results WHERE user_id=? AND item_id=? AND status IN ('AVAILABLE','KEPT') ORDER BY rowid", (user_id, item_id)).fetchall()
        legacy = max(0, int(row["quantity"]) - len(tracked))
        result_ids = [r["id"] for r in tracked[:max(0, quantity - legacy)]]
    for result_id in result_ids:
        updated = connection.execute("UPDATE opening_results SET status=? WHERE id=? AND user_id=? AND item_id=? AND status IN ('AVAILABLE','KEPT')", (status, result_id, user_id, item_id))
        if updated.rowcount != 1:
            raise EconomyError("Этот результат уже обработан")
    if row["quantity"] == quantity:
        connection.execute("DELETE FROM inventory WHERE user_id=? AND item_id=?", (user_id, item_id))
    else:
        connection.execute("UPDATE inventory SET quantity=quantity-?,updated_at=CURRENT_TIMESTAMP WHERE user_id=? AND item_id=?", (quantity, user_id, item_id))
