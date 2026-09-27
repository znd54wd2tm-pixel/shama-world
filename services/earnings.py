"""Server-authoritative passive income and interactive earning sessions."""

from __future__ import annotations

import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

try:
    from database import get_connection
    from services.economy import add_balance, record_transaction, remove_balance
except ImportError:  # pragma: no cover
    from ..database import get_connection
    from .economy import add_balance, record_transaction, remove_balance


class EarningsError(RuntimeError):
    status_code = 400


class SessionNotFoundError(EarningsError):
    status_code = 404


class SessionAlreadyActiveError(EarningsError):
    status_code = 409


SYSTEM_COLUMNS = {"farm": "farm_level", "business": "business_level", "bank": "bank_level"}
CLAIM_COLUMNS = {"farm": "farm_last_claim_at", "business": "business_last_claim_at", "bank": "bank_last_claim_at"}
MAX_ACCRUAL_SECONDS = 24 * 60 * 60
JOB_CONFIG = {
    "courier": ("COURIER", 60, 120),
    "factory": ("FACTORY", 30, 90),
    "hunt": ("HUNT", 45, 75),
}
logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _level_row(connection: Any, system: str, level: int) -> Any:
    return connection.execute(
        "SELECT * FROM passive_levels WHERE system = ? AND level = ?", (system, level)
    ).fetchone()


def _passive_payload(connection: Any, user: Any, system: str) -> dict[str, Any]:
    if system not in SYSTEM_COLUMNS:
        raise EarningsError("Неизвестная система заработка")
    level = int(user[SYSTEM_COLUMNS[system]])
    current = _level_row(connection, system, level) if level else None
    next_level = _level_row(connection, system, level + 1)
    last = _parse(user[CLAIM_COLUMNS[system]])
    now = _now()
    elapsed = 0 if last is None else max(0, min(MAX_ACCRUAL_SECONDS, int((now - last).total_seconds())))
    available = int((elapsed / 60) * (current["income_per_minute"] if current else 0))
    unlocked = int(user["level"]) >= int((next_level or current or {"unlock_level": 1})["unlock_level"])
    if system == "business":
        unlocked = unlocked and int(user["farm_level"]) >= 10
    if system == "bank":
        unlocked = unlocked and int(user["business_level"]) >= 20
    return {
        "system": system, "level": level, "income_per_minute": int(current["income_per_minute"]) if current else 0,
        "available": available, "last_claim_at": user[CLAIM_COLUMNS[system]], "unlocked": unlocked,
        "next": ({"level": int(next_level["level"]), "income_per_minute": int(next_level["income_per_minute"]),
                   "upgrade_cost": int(next_level["upgrade_cost"])} if next_level else None),
    }


def earnings_status(database_path: str, user_id: int) -> dict[str, Any]:
    with get_connection(database_path) as connection:
        user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            raise EarningsError("Пользователь не найден")
        return {"balance": int(user["balance"]), "systems": {name: _passive_payload(connection, user, name) for name in SYSTEM_COLUMNS},
                "jobs": list_jobs(database_path, user_id)}


def claim_passive(database_path: str, user_id: int, system: str) -> dict[str, Any]:
    if system not in SYSTEM_COLUMNS:
        raise EarningsError("Неизвестная система заработка")
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            raise EarningsError("Пользователь не найден")
        state = _passive_payload(connection, user, system)
        if not state["unlocked"]:
            raise EarningsError("Система заработка пока заблокирована")
        now = _now()
        before = int(user["balance"])
        amount = int(state["available"])
        after = before
        if amount:
            after = add_balance(connection, user_id, amount)
            record_transaction(connection, user_id, "FARM_REWARD", amount, before, after,
                               description=f"{system.title()} passive income", metadata={"system": system})
        connection.execute(f"UPDATE users SET {CLAIM_COLUMNS[system]} = ? WHERE id = ?", (now.isoformat(), user_id))
        connection.commit()
        return {"success": True, "system": system, "amount": amount, "balance": after,
                "available": 0, "claimed_at": now.isoformat()}


def upgrade_passive(database_path: str, user_id: int, system: str) -> dict[str, Any]:
    if system not in SYSTEM_COLUMNS:
        raise EarningsError("Неизвестная система заработка")
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            raise EarningsError("Пользователь не найден")
        current_level = int(user[SYSTEM_COLUMNS[system]])
        next_row = _level_row(connection, system, current_level + 1)
        if next_row is None:
            raise EarningsError("Достигнут максимальный уровень")
        if system == "business" and int(user["farm_level"]) < 10:
            raise EarningsError("Бизнес откроется после полной прокачки фермы")
        if system == "bank" and int(user["business_level"]) < 20:
            raise EarningsError("Банк откроется после полной прокачки бизнеса")
        before = int(user["balance"])
        after = remove_balance(connection, user_id, int(next_row["upgrade_cost"]))
        connection.execute(f"UPDATE users SET {SYSTEM_COLUMNS[system]} = ? WHERE id = ?", (current_level + 1, user_id))
        record_transaction(connection, user_id, "OTHER", int(next_row["upgrade_cost"]), before, after,
                           description=f"{system.title()} upgrade", metadata={"system": system, "level": current_level + 1})
        connection.commit()
        return {"success": True, "system": system, "level": current_level + 1,
                "income_per_minute": int(next_row["income_per_minute"]), "balance": after}


def list_jobs(database_path: str, user_id: int) -> list[dict[str, Any]]:
    with get_connection(database_path) as connection:
        rows = connection.execute(
            "SELECT id, kind, seed, started_at, expires_at, completed_at, status, reward FROM earning_sessions WHERE user_id = ? ORDER BY id DESC LIMIT 10",
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def start_job(database_path: str, user_id: int, kind: str) -> dict[str, Any]:
    config = JOB_CONFIG.get(kind.lower())
    if config is None:
        raise EarningsError("Неизвестная работа")
    job_kind, duration, reward = config
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        active = connection.execute("SELECT id FROM earning_sessions WHERE user_id = ? AND kind = ? AND status = 'ACTIVE'", (user_id, job_kind)).fetchone()
        if active:
            raise SessionAlreadyActiveError("Такая работа уже выполняется")
        now = _now(); expires = now + timedelta(seconds=duration)
        seed = secrets.randbelow(2**31 - 1)
        cursor = connection.execute(
            "INSERT INTO earning_sessions(user_id, kind, seed, started_at, expires_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, job_kind, seed, now.isoformat(), expires.isoformat()),
        )
        connection.commit()
        return {"success": True, "session_id": int(cursor.lastrowid), "kind": job_kind, "seed": seed,
                "started_at": now.isoformat(), "expires_at": expires.isoformat(), "duration_seconds": duration, "reward_preview": reward}


def complete_job(database_path: str, user_id: int, session_id: int) -> dict[str, Any]:
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        session = connection.execute("SELECT * FROM earning_sessions WHERE id = ? AND user_id = ?", (session_id, user_id)).fetchone()
        if session is None:
            raise SessionNotFoundError("Рабочая сессия не найдена")
        if session["status"] != "ACTIVE":
            return {"success": session["status"] == "SUCCESS", "status": session["status"], "reward": int(session["reward"]), "idempotent": True}
        now = _now()
        if now > _parse(session["expires_at"]):
            connection.execute("UPDATE earning_sessions SET status = 'FAILED', completed_at = ? WHERE id = ?", (now.isoformat(), session_id))
            connection.commit()
            return {"success": False, "status": "FAILED", "reward": 0, "message": "Время задания истекло"}
        reward = dict((value[0], value[2]) for value in JOB_CONFIG.values()).get(session["kind"], 0)
        user = connection.execute("SELECT balance, xp FROM users WHERE id = ?", (user_id,)).fetchone()
        before = int(user["balance"]); after = add_balance(connection, user_id, int(reward))
        new_xp = int(user["xp"]) + 5
        new_level = new_xp // 100 + 1
        connection.execute("UPDATE users SET xp = ?, level = ? WHERE id = ?", (new_xp, new_level, user_id))
        record_transaction(connection, user_id, "JOB_REWARD", int(reward), before, after,
                           description=f"{session['kind'].title()} reward", metadata={"session_id": session_id})
        connection.execute("UPDATE earning_sessions SET status = 'SUCCESS', reward = ?, completed_at = ? WHERE id = ?", (reward, now.isoformat(), session_id))
        connection.commit()
        logger.info("job_reward_success user_id=%s session_id=%s reward=%s", user_id, session_id, reward)
        return {"success": True, "status": "SUCCESS", "reward": int(reward), "balance": after, "xp": new_xp, "level": new_level, "session_id": session_id}
