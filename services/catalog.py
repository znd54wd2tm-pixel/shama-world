"""Case and inventory read services."""

from __future__ import annotations

from typing import Any

try:
    from database import get_connection
except ImportError:  # pragma: no cover
    from ..database import get_connection


def _item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["item_id"] if "item_id" in row else row["id"],
        "name": row["item_name"] if "item_name" in row else row["name"],
        "description": row["description"],
        "rarity": row["rarity"],
        "value": row["value"],
        "image": row["image"],
    }


def list_cases(database_path: str) -> list[dict[str, Any]]:
    with get_connection(database_path) as connection:
        rows = connection.execute("SELECT id, name, description, price, image,kind,style,active FROM cases ORDER BY price").fetchall()
        return [dict(row) for row in rows]


def get_case(database_path: str, case_id: int) -> dict[str, Any] | None:
    with get_connection(database_path) as connection:
        case = connection.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        if case is None:
            return None
        drops = connection.execute(
            """
            SELECT d.chance, i.id AS item_id, i.name AS item_name, i.description,
                   i.rarity, i.value, i.image
            FROM case_drops d JOIN items i ON i.id = d.item_id
            WHERE d.case_id = ? ORDER BY d.chance DESC, i.id
            """,
            (case_id,),
        ).fetchall()
        result = dict(case)
        result["drops"] = [{**_item(dict(row)), "chance": row["chance"]} for row in drops]
        if case["kind"] == "BUSINESS":
            business_drops = connection.execute("SELECT e.*,d.chance FROM enterprise_drops d JOIN enterprise_catalog e ON e.id=d.enterprise_type_id WHERE d.case_id=? ORDER BY d.chance DESC", (case_id,)).fetchall()
            result["drops"] = [{**dict(r),"value":r["original_price"],"description":"Предприятие с почасовым доходом","kind":"BUSINESS"} for r in business_drops]
        return result


def list_inventory(database_path: str, user_id: int) -> list[dict[str, Any]]:
    with get_connection(database_path) as connection:
        rows = connection.execute(
            """
            SELECT i.id, i.name, i.description, i.rarity, i.value, i.image, i.category, inv.quantity
            FROM inventory inv JOIN items i ON i.id = inv.item_id
            WHERE inv.user_id = ? ORDER BY i.value DESC, i.name
            """,
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_inventory_item(database_path: str, user_id: int, item_id: int) -> dict[str, Any] | None:
    with get_connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT i.id, i.name, i.description, i.rarity, i.value, i.image, i.category, inv.quantity
            FROM inventory inv JOIN items i ON i.id = inv.item_id
            WHERE inv.user_id = ? AND i.id = ?
            """,
            (user_id, item_id),
        ).fetchone()
        return dict(row) if row else None
