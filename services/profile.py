"""Profile, achievements and daily bonus services."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

try:
    from database import get_connection
    from services.economy import add_balance, record_transaction
except ImportError:  # pragma: no cover
    from ..database import get_connection
    from .economy import add_balance, record_transaction


class ProfileError(RuntimeError):
    status_code = 400


def _achievement_progress(user: Any, code: str) -> int:
    return {
        "FIRST_CASE": int(user["cases_opened"]), "OPEN_10_CASES": int(user["cases_opened"]),
        "COLLECT_10_ITEMS": int(user["items_collected"]), "UPGRADE_SUCCESS": int(user["upgrades_success"]),
        "SELL_10_ITEMS": int(user["total_items_sold"]), "REACH_LEVEL_10": int(user["level"]),
        "BANK_CONTROL_PACKAGE": int(user["bank_control_package"]),
    }.get(code, 0)


def achievements(database_path: str, user_id: int) -> list[dict[str, Any]]:
    with get_connection(database_path) as connection:
        user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        rows = connection.execute(
            """SELECT a.*, ua.unlocked_at FROM achievements a LEFT JOIN user_achievements ua
               ON ua.achievement_id = a.id AND ua.user_id = ? ORDER BY a.id""", (user_id,)
        ).fetchall()
        return [{**dict(row), "progress": _achievement_progress(user, row["code"]), "unlocked": row["unlocked_at"] is not None} for row in rows]


def evaluate_achievements(connection: Any, user_id: int) -> None:
    user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    rows = connection.execute("SELECT * FROM achievements").fetchall()
    for row in rows:
        if _achievement_progress(user, row["code"]) >= int(row["requirement"]):
            connection.execute("INSERT OR IGNORE INTO user_achievements(user_id, achievement_id) VALUES (?, ?)", (user_id, row["id"]))


def profile(database_path: str, user_id: int) -> dict[str, Any]:
    with get_connection(database_path) as connection:
        user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            raise ProfileError("Пользователь не найден")
        evaluate_achievements(connection, user_id)
        connection.commit()
        data = {key: user[key] for key in user.keys() if key not in {"farm_last_claim_at", "business_last_claim_at", "bank_last_claim_at"}}
        spent = connection.execute("SELECT COALESCE(SUM(balance_before - balance_after), 0) AS total FROM transactions WHERE user_id = ? AND balance_after < balance_before", (user_id,)).fetchone()["total"]
        earned = connection.execute(
            "SELECT COALESCE(SUM(balance_after - balance_before), 0) FROM transactions "
            "WHERE user_id = ? AND balance_after > balance_before", (user_id,),
        ).fetchone()[0]
        farm_profit = connection.execute(
            "SELECT COALESCE(SUM(balance_after - balance_before), 0) FROM transactions "
            "WHERE user_id = ? AND balance_after > balance_before "
            "AND (description LIKE 'FARM%income' OR description = 'Farm passive income')", (user_id,),
        ).fetchone()[0]
        business_profit = connection.execute(
            "SELECT COALESCE(SUM(balance_after - balance_before), 0) FROM transactions "
            "WHERE user_id = ? AND balance_after > balance_before "
            "AND (description LIKE 'BUSINESS%income' OR description = 'Business passive income')", (user_id,),
        ).fetchone()[0]
        portfolio = connection.execute(
            "SELECT COALESCE(SUM(h.shares * h.average_cost), 0) AS invested, "
            "COALESCE(SUM(h.shares * (c.price - h.average_cost)), 0) AS pnl "
            "FROM bank_company_holdings h JOIN bank_companies c ON c.code = h.company_code "
            "WHERE h.user_id = ?", (user_id,),
        ).fetchone()
        crypto = connection.execute(
            "SELECT COALESCE(SUM(h.quantity * h.average_cost), 0) AS invested, "
            "COALESCE(SUM(h.quantity * (m.price - h.average_cost)), 0) AS pnl "
            "FROM bank_crypto_holdings h JOIN crypto_market m ON m.code = h.code "
            "WHERE h.user_id = ?", (user_id,),
        ).fetchone()
        bank = connection.execute("SELECT operating_profit, investment_profit FROM bank_accounts WHERE user_id = ?", (user_id,)).fetchone()
        savings_interest = connection.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM bank_ledger "
            "WHERE user_id = ? AND entry_type = 'SAVINGS_INTEREST'", (user_id,),
        ).fetchone()[0]
        cases_spent = connection.execute(
            "SELECT COALESCE(SUM(price_paid), 0) FROM case_openings WHERE user_id = ?", (user_id,),
        ).fetchone()[0]
        total_upgrades = int(user["upgrades_total"])
        data["total_sh_spent"] = int(spent)
        data["total_sh_earned"] = int(earned)
        data["total_invested"] = round(float(portfolio["invested"]) + float(crypto["invested"]), 2)
        data["farm_profit"] = int(farm_profit)
        data["business_profit"] = int(business_profit)
        data["bank_profit"] = round(
            (int(bank["operating_profit"]) + float(bank["investment_profit"]) if bank else 0)
            + float(savings_interest), 2,
        )
        data["market_pnl"] = round(float(portfolio["pnl"]) + float(crypto["pnl"]), 2)
        data["total_profit"] = round(data["farm_profit"] + data["business_profit"] + data["bank_profit"] + data["market_pnl"], 2)
        data["cases_spent"] = int(cases_spent)
        data["upgrade_success_rate"] = round((int(user["upgrades_success"]) / total_upgrades) * 100, 1) if total_upgrades else 0.0
        return {"user": data, "achievements": achievements(database_path, user_id)}


def daily_status(database_path: str, user_id: int) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    with get_connection(database_path) as connection:
        row = connection.execute("SELECT last_daily_claim FROM users WHERE id = ?", (user_id,)).fetchone()
        claimed = False
        if row and row["last_daily_claim"]:
            try:
                previous = datetime.fromisoformat(str(row["last_daily_claim"]).replace("Z", "+00:00"))
                if previous.tzinfo is None:
                    previous = previous.replace(tzinfo=timezone.utc)
                claimed = (now - previous).total_seconds() < 24 * 60 * 60
            except ValueError:
                claimed = str(row["last_daily_claim"]) == today
        return {"claimed": claimed, "reward": 100, "date": today}


def claim_daily(database_path: str, user_id: int) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            raise ProfileError("Пользователь не найден")
        previous = None
        if user["last_daily_claim"]:
            try:
                previous = datetime.fromisoformat(str(user["last_daily_claim"]).replace("Z", "+00:00"))
                if previous.tzinfo is None:
                    previous = previous.replace(tzinfo=timezone.utc)
            except ValueError:
                previous = now if str(user["last_daily_claim"]) == today else None
        if previous and (now - previous).total_seconds() < 24 * 60 * 60:
            raise ProfileError("Ежедневный бонус уже получен")
        before = int(user["balance"]); after = add_balance(connection, user_id, 100)
        new_xp = int(user["xp"]) + 10
        connection.execute("UPDATE users SET last_daily_claim = ?, xp = ?, level = ? WHERE id = ?", (now.isoformat(), new_xp, new_xp // 100 + 1, user_id))
        record_transaction(connection, user_id, "REWARD", 100, before, after, description="Daily bonus", metadata={"date": today})
        connection.commit()
        return {"success": True, "reward": 100, "xp": new_xp, "level": new_xp // 100 + 1, "balance": after, "date": today}
