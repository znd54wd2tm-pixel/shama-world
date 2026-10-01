"""Player savings accounts with server-side interest and atomic transfers."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any

try:
    from database import get_connection
    from services.economy import add_balance, record_transaction, remove_balance
except ImportError:  # pragma: no cover
    from ..database import get_connection
    from .economy import add_balance, record_transaction, remove_balance


SAVINGS_RATE = 0.042
SECONDS_PER_YEAR = 365.2425 * 24 * 60 * 60


class SavingsError(RuntimeError):
    status_code = 400


class SavingsConflictError(SavingsError):
    status_code = 409


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _ensure_account(connection: Any, user_id: int) -> Any:
    connection.execute(
        "INSERT OR IGNORE INTO player_savings_accounts(user_id, balance, accrued_at) VALUES (?, 0, ?)",
        (user_id, _now().isoformat()),
    )
    return connection.execute(
        "SELECT * FROM player_savings_accounts WHERE user_id = ?", (user_id,)
    ).fetchone()


def _accrue(connection: Any, user_id: int, account: Any, now: datetime) -> tuple[Any, float]:
    previous = _parse(account["accrued_at"])
    if previous is None:
        connection.execute(
            "UPDATE player_savings_accounts SET accrued_at = ? WHERE user_id = ?",
            (now.isoformat(), user_id),
        )
        return connection.execute(
            "SELECT * FROM player_savings_accounts WHERE user_id = ?", (user_id,)
        ).fetchone(), 0.0
    elapsed = max(0.0, min((now - previous).total_seconds(), 10 * SECONDS_PER_YEAR))
    balance = float(account["balance"])
    interest = balance * (math.pow(1 + SAVINGS_RATE, elapsed / SECONDS_PER_YEAR) - 1)
    connection.execute(
        "UPDATE player_savings_accounts SET balance = balance + ?, accrued_at = ? WHERE user_id = ?",
        (interest, now.isoformat(), user_id),
    )
    if interest >= 0.01:
        connection.execute(
            "INSERT INTO bank_ledger(user_id, entry_type, amount, description) VALUES (?, 'SAVINGS_INTEREST', ?, 'Savings account interest')",
            (user_id, interest),
        )
    updated = connection.execute(
        "SELECT * FROM player_savings_accounts WHERE user_id = ?", (user_id,)
    ).fetchone()
    return updated, interest


def _request_id(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value or len(value) > 128:
        raise SavingsError("Request ID must contain 1–128 characters")
    return value


def _cached(connection: Any, user_id: int, action: str, request_id: str | None) -> dict | None:
    if not request_id:
        return None
    row = connection.execute(
        "SELECT response_json FROM bank_action_requests WHERE user_id = ? AND action = ? AND request_id = ?",
        (user_id, action, request_id),
    ).fetchone()
    return json.loads(row["response_json"]) if row else None


def _save_request(connection: Any, user_id: int, action: str, request_id: str | None, result: dict) -> None:
    if request_id:
        connection.execute(
            "INSERT INTO bank_action_requests(user_id, action, request_id, response_json) VALUES (?, ?, ?, ?)",
            (user_id, action, request_id, json.dumps(result, separators=(",", ":"), ensure_ascii=False)),
        )


def savings_status(database_path: str, user_id: int) -> dict:
    now = _now()
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        user = connection.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            raise SavingsError("Пользователь не найден")
        account = _ensure_account(connection, user_id)
        account, interest = _accrue(connection, user_id, account, now)
        connection.commit()
        balance = float(account["balance"])
        daily = balance * (math.pow(1 + SAVINGS_RATE, 1 / 365.2425) - 1)
        monthly = balance * (math.pow(1 + SAVINGS_RATE, 1 / 12) - 1)
        return {
            "balance": round(balance, 2),
            "available_balance": math.floor(balance),
            "rate": SAVINGS_RATE,
            "estimated_daily": round(daily, 2),
            "estimated_monthly": round(monthly, 2),
            "interest_accrued": round(interest, 2),
            "accrued_at": account["accrued_at"],
            "current_account": int(user["balance"]),
        }


def move_savings(
    database_path: str,
    user_id: int,
    direction: str,
    amount: Any,
    request_id: str | None = None,
) -> dict:
    direction = direction.lower()
    if direction not in {"deposit", "withdraw"}:
        raise SavingsError("Операция должна быть DEPOSIT или WITHDRAW")
    if isinstance(amount, bool):
        raise SavingsError("Сумма указана неверно")
    try:
        amount = int(amount)
    except (TypeError, ValueError) as error:
        raise SavingsError("Сумма указана неверно") from error
    if amount <= 0 or amount > 2_000_000_000:
        raise SavingsError("Сумма должна быть больше нуля")
    request_id = _request_id(request_id)
    action = f"savings:{direction}"
    now = _now()
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        cached = _cached(connection, user_id, action, request_id)
        if cached is not None:
            return cached
        user = connection.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            raise SavingsError("Пользователь не найден")
        account = _ensure_account(connection, user_id)
        account, _ = _accrue(connection, user_id, account, now)
        savings_balance = float(account["balance"])
        before = int(user["balance"])
        if direction == "deposit":
            after = remove_balance(connection, user_id, amount)
            savings_balance += amount
            description = "Savings deposit"
            entry_type = "SAVINGS_DEPOSIT"
        else:
            if math.floor(savings_balance) < amount:
                raise SavingsConflictError("Недостаточно средств на накопительном счёте")
            savings_balance -= amount
            after = add_balance(connection, user_id, amount)
            description = "Savings withdrawal"
            entry_type = "SAVINGS_WITHDRAWAL"
        connection.execute(
            "UPDATE player_savings_accounts SET balance = ?, accrued_at = ? WHERE user_id = ?",
            (savings_balance, now.isoformat(), user_id),
        )
        record_transaction(
            connection, user_id, "OTHER", amount, before, after,
            description=description, metadata={"account": "SAVINGS", "direction": direction.upper()},
        )
        connection.execute(
            "INSERT INTO bank_ledger(user_id, entry_type, amount, description) VALUES (?, ?, ?, ?)",
            (user_id, entry_type, amount, description),
        )
        result = {
            "success": True,
            "direction": direction.upper(),
            "amount": amount,
            "current_account": after,
            "savings_balance": round(savings_balance, 2),
        }
        _save_request(connection, user_id, action, request_id, result)
        connection.commit()
        return result


def savings_history(database_path: str, user_id: int, limit: int = 30) -> list[dict]:
    with get_connection(database_path) as connection:
        rows = connection.execute(
            "SELECT entry_type, amount, description, created_at FROM bank_ledger "
            "WHERE user_id = ? AND entry_type IN ('SAVINGS_DEPOSIT', 'SAVINGS_WITHDRAWAL', 'SAVINGS_INTEREST') "
            "ORDER BY id DESC LIMIT ?",
            (user_id, max(1, min(int(limit), 100))),
        ).fetchall()
        return [dict(row) for row in rows]


def bank_transactions(database_path: str, user_id: int, limit: int = 40) -> list[dict]:
    with get_connection(database_path) as connection:
        rows = connection.execute(
            "SELECT entry_type, amount, description, created_at FROM bank_ledger "
            "WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, max(1, min(int(limit), 100))),
        ).fetchall()
        return [dict(row) for row in rows]
