"""Persistent, server-authoritative Farm, Business and Bank game systems."""

from __future__ import annotations

import hashlib
import json
import math
import random
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

try:
    from database import get_connection
    from services.economy import add_balance, record_transaction, remove_balance
except ImportError:  # pragma: no cover
    from ..database import get_connection
    from .economy import add_balance, record_transaction, remove_balance


class EnterpriseError(RuntimeError):
    status_code = 400


class EnterpriseNotFoundError(EnterpriseError):
    status_code = 404


class EnterpriseConflictError(EnterpriseError):
    status_code = 409


FARM_HANGARS = (
    {"level": 1, "name": "Дешёвый ангар", "cost": 1500, "chickens": 50, "pigs": 20, "cows": 15, "multiplier": 1},
    {"level": 2, "name": "Улучшенный ангар", "cost": 15000, "chickens": 100, "pigs": 40, "cows": 30, "multiplier": 2},
    {"level": 3, "name": "МЕГА-АНГАР", "cost": 75000, "chickens": 150, "pigs": 60, "cows": 50, "multiplier": 3},
)
FARM_ANIMALS = {
    "chickens": {"label": "Куры", "unit_cost": 10, "base_income": 1, "label_one": "курицу"},
    "pigs": {"label": "Свиньи", "unit_cost": 50, "base_income": 4, "label_one": "свинью"},
    "cows": {"label": "Коровы", "unit_cost": 150, "base_income": 14, "label_one": "корову"},
}
BUSINESS_OFFICES = (
    {"level": 1, "name": "Маленький офис", "label": "Арендовать маленький офис", "cost": 3000, "computers": 10, "workers": 10},
    {"level": 2, "name": "Средний офис", "label": "Средний офис", "cost": 8000, "computers": 30, "workers": 30},
)
ADS = {
    "city": {"name": "ГОРОД", "cost": 700, "minutes": 10},
    "district": {"name": "РАЙОН", "cost": 2500, "minutes": 30},
    "region": {"name": "ОБЛАСТЬ", "cost": 5000, "minutes": 60},
}
BANK_LEVEL_COSTS = (5000, 15000, 50000, 120000, 250000)
BANK_CUSTOMER_DEPOSIT = 1000
BANK_INTEREST_PER_MINUTE = 0.0001  # 0.01% of customer liabilities each minute.
MAX_OFFLINE_SECONDS = 7 * 24 * 60 * 60
CRYPTO_IDS = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana"}
CRYPTO_NAMES = {"BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana"}
CRYPTO_SH_PER_USD = 100
CRYPTO_CACHE_SECONDS = 300


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _ensure_rows(connection: Any, user_id: int) -> tuple[Any, Any, Any]:
    connection.execute("INSERT OR IGNORE INTO player_enterprises(user_id) VALUES (?)", (user_id,))
    enterprise = connection.execute("SELECT * FROM player_enterprises WHERE user_id = ?", (user_id,)).fetchone()
    user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        raise EnterpriseNotFoundError("Пользователь не найден")
    bank = connection.execute("SELECT * FROM bank_accounts WHERE user_id = ?", (user_id,)).fetchone()
    return enterprise, user, bank


def _bank_unlock(user: Any, enterprise: Any) -> bool:
    farm_full = int(enterprise["farm_hangar_level"]) == 3 and all(
        int(enterprise[column]) >= cap for column, cap in (("chickens", 150), ("pigs", 60), ("cows", 50))
    )
    business_full = (
        int(enterprise["business_office_level"]) == 2
        and int(enterprise["computers"]) >= 30
        and int(enterprise["workers"]) >= 30
        and int(enterprise["improved_computers"]) >= 30
    )
    return farm_full and business_full


def _farm_rate(enterprise: Any) -> int:
    level = int(enterprise["farm_hangar_level"])
    if level == 0:
        return 0
    multiplier = FARM_HANGARS[level - 1]["multiplier"]
    return sum(int(enterprise[animal]) * int(config["base_income"]) * multiplier for animal, config in FARM_ANIMALS.items())


def _business_rate(enterprise: Any) -> int:
    workers = min(int(enterprise["workers"]), int(enterprise["computers"]))
    improved = min(int(enterprise["improved_computers"]), workers)
    return improved * 90 + (workers - improved) * 30


def _pending_farm(enterprise: Any, now: datetime) -> int:
    last = _parse(enterprise["farm_accrued_at"])
    if last is None:
        return 0
    elapsed = max(0, min(MAX_OFFLINE_SECONDS, int((now - last).total_seconds())))
    return int(elapsed * _farm_rate(enterprise) / 60)


def _pending_business(enterprise: Any, now: datetime) -> int:
    last = _parse(enterprise["business_accrued_at"])
    if last is None:
        return 0
    start = max(last, now - timedelta(seconds=MAX_OFFLINE_SECONDS))
    elapsed = max(0, int((now - start).total_seconds()))
    rate = _business_rate(enterprise)
    base = rate * elapsed / 60
    ad_start, ad_end = _parse(enterprise["ad_started_at"]), _parse(enterprise["ad_until"])
    boosted_seconds = 0
    if ad_start and ad_end:
        boosted_seconds = max(0, int((min(now, ad_end) - max(start, ad_start)).total_seconds()))
    return int(base + (rate * boosted_seconds / 60))


def _pending_bank(enterprise: Any, bank: Any, now: datetime) -> int:
    del enterprise
    if bank is None or not int(bank["attraction_level"]):
        return 0
    last = _parse(bank["accrued_at"])
    if last is None:
        return 0
    elapsed_minutes = max(0, min(MAX_OFFLINE_SECONDS, int((now - last).total_seconds()))) / 60
    return int(elapsed_minutes * int(bank["client_liabilities"]) * BANK_INTEREST_PER_MINUTE)


def _bank_ready_payload(user: Any, enterprise: Any, bank: Any) -> dict[str, Any]:
    unlocked = _bank_unlock(user, enterprise)
    level = int(bank["attraction_level"]) if bank else 0
    return {
        "unlocked": unlocked,
        "attraction_level": level,
        "clients": int(bank["clients"]) if bank else 0,
        "cash_balance": int(bank["cash_balance"]) if bank else 0,
        "client_liabilities": int(bank["client_liabilities"]) if bank else 0,
        "operating_profit": int(bank["operating_profit"]) if bank else 0,
        "investment_profit": round(float(bank["investment_profit"]), 2) if bank else 0,
        "profit_balance": max(0, int(bank["operating_profit"]) + int(bank["investment_profit"])) if bank else 0,
        "next_attraction_cost": BANK_LEVEL_COSTS[level] if level < len(BANK_LEVEL_COSTS) else None,
        "next_attraction_clients": 100 if level < len(BANK_LEVEL_COSTS) else 0,
        "status_text": "Банк разблокирован" if unlocked else "Нужен МЕГА-АНГАР с полной фермой и полностью улучшенный средний офис",
    }


def enterprise_status(database_path: str, user_id: int) -> dict[str, Any]:
    now = _now()
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        _refresh_company_prices(connection, now)
        connection.commit()
        enterprise, user, bank = _ensure_rows(connection, user_id)
        farm_level = int(enterprise["farm_hangar_level"])
        farm_next = FARM_HANGARS[farm_level] if farm_level < len(FARM_HANGARS) else None
        office_level = int(enterprise["business_office_level"])
        office_next = BUSINESS_OFFICES[office_level] if office_level < len(BUSINESS_OFFICES) else None
        farm_multiplier = FARM_HANGARS[farm_level - 1]["multiplier"] if farm_level else 1
        farm_animals = {}
        for key, config in FARM_ANIMALS.items():
            count = int(enterprise[key])
            cap = FARM_HANGARS[farm_level - 1][key] if farm_level else 0
            farm_animals[key] = {
                "name": config["label"], "count": count, "capacity": cap,
                "unit_cost": config["unit_cost"], "income_per_minute": config["base_income"] * farm_multiplier,
                "max_income_per_minute": cap * config["base_income"] * farm_multiplier,
                "progress": round(count / cap * 100) if cap else 0,
            }
        ad_until = _parse(enterprise["ad_until"])
        ad_remaining = max(0, int((ad_until - now).total_seconds())) if ad_until else 0
        companies = _company_payload(connection, user_id, bank)
        crypto = _crypto_payload(connection, user_id, bank)
        latest_events = connection.execute(
            "SELECT id, event_type, amount, message, status, created_at FROM bank_customer_events WHERE user_id = ? ORDER BY id DESC LIMIT 8",
            (user_id,),
        ).fetchall()
        return {
            "balance": int(user["balance"]),
            "farm": {
                "level": farm_level, "unlocked": farm_level > 0,
                "name": FARM_HANGARS[farm_level - 1]["name"] if farm_level else "Ферма не построена",
                "next": farm_next, "animals": farm_animals, "income_per_minute": _farm_rate(enterprise),
                "available": _pending_farm(enterprise, now),
                "is_max": farm_level == 3 and all(farm_animals[k]["count"] >= farm_animals[k]["capacity"] for k in farm_animals),
            },
            "business": {
                "level": office_level, "unlocked": office_level > 0,
                "name": BUSINESS_OFFICES[office_level - 1]["name"] if office_level else "Офис не арендован",
                "next": office_next, "computers": int(enterprise["computers"]),
                "improved_computers": int(enterprise["improved_computers"]), "workers": int(enterprise["workers"]),
                "computer_capacity": BUSINESS_OFFICES[office_level - 1]["computers"] if office_level else 0,
                "worker_capacity": BUSINESS_OFFICES[office_level - 1]["workers"] if office_level else 0,
                "computer_cost": 250, "improved_computer_cost": 500, "worker_cost": 200,
                "upgrade_old_computer_cost": 250, "income_per_minute": _business_rate(enterprise),
                "available": _pending_business(enterprise, now), "ad_remaining_seconds": ad_remaining,
                "ad_multiplier": 2 if ad_remaining else 1,
                "ad_started_at": enterprise["ad_started_at"], "ad_until": enterprise["ad_until"],
                "ads": [{"code": code, **data, "active": ad_remaining > 0} for code, data in ADS.items()],
                "is_max": office_level == 2 and int(enterprise["computers"]) == 30 and int(enterprise["workers"]) == 30 and int(enterprise["improved_computers"]) == 30,
            },
            "stadium": {"available": True, "status": "COMING_SOON", "title": "TORPEDO STADIUM"},
            "bank": {
                **_bank_ready_payload(user, enterprise, bank),
                "pending_profit": _pending_bank(enterprise, bank, now),
                "dividend_pending": int(_pending_dividends(connection, user_id, bank, now, update=False)),
                "companies": companies, "crypto": crypto, "events": [dict(row) for row in latest_events],
                "portfolio": _portfolio_summary(user, bank, companies, crypto),
            },
        }


def _record_wallet_change(connection: Any, user_id: int, action: str, amount: int, before: int, after: int, extra: dict[str, Any] | None = None) -> None:
    record_transaction(connection, user_id, "OTHER", max(0, int(amount)), before, after,
                       description=action, metadata=extra or {})


def _settle_income(connection: Any, user_id: int, enterprise: Any, systems: tuple[str, ...], now: datetime) -> int:
    user = connection.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()
    total = 0
    for system in systems:
        column = "farm_accrued_at" if system == "farm" else "business_accrued_at"
        amount = _pending_farm(enterprise, now) if system == "farm" else _pending_business(enterprise, now)
        connection.execute(f"UPDATE player_enterprises SET {column} = ? WHERE user_id = ?", (_iso(now), user_id))
        enterprise = connection.execute("SELECT * FROM player_enterprises WHERE user_id = ?", (user_id,)).fetchone()
        if amount:
            before = int(user["balance"])
            after = add_balance(connection, user_id, amount)
            _record_wallet_change(connection, user_id, f"{system.upper()} income", amount, before, after, {"system": system})
            user = connection.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()
            total += amount
    return total


def _spend_wallet(connection: Any, user_id: int, amount: int, description: str, metadata: dict[str, Any]) -> int:
    before = int(connection.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()["balance"])
    after = remove_balance(connection, user_id, amount)
    _record_wallet_change(connection, user_id, description, amount, before, after, metadata)
    return after


def _positive_int(value: Any, field: str, maximum: int = 100_000) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0 or value > maximum:
        raise EnterpriseError(f"{field}: укажи положительное целое число")
    return value


def _validated_request_id(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value or len(value) > 128:
        raise EnterpriseError("Request ID must contain 1–128 characters")
    return value


def _cached_action(connection: Any, user_id: int, action: str, request_id: str | None) -> dict[str, Any] | None:
    if not request_id:
        return None
    row = connection.execute(
        "SELECT response_json FROM bank_action_requests WHERE user_id = ? AND action = ? AND request_id = ?",
        (user_id, action, request_id),
    ).fetchone()
    return json.loads(row["response_json"]) if row else None


def _save_action(connection: Any, user_id: int, action: str, request_id: str | None, result: dict[str, Any]) -> None:
    if request_id:
        connection.execute(
            "INSERT INTO bank_action_requests(user_id, action, request_id, response_json) VALUES (?, ?, ?, ?)",
            (user_id, action, request_id, json.dumps(result, separators=(",", ":"), ensure_ascii=False)),
        )


def upgrade_enterprise(database_path: str, user_id: int, system: str, *, request_id: str | None = None) -> dict[str, Any]:
    now = _now()
    system = system.lower()
    if system not in {"farm", "business"}:
        raise EnterpriseError("Неизвестное направление")
    request_id = _validated_request_id(request_id)
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        cached = _cached_action(connection, user_id, f"enterprise-upgrade:{system}", request_id)
        if cached is not None:
            return cached
        enterprise, user, _ = _ensure_rows(connection, user_id)
        level_column = "farm_hangar_level" if system == "farm" else "business_office_level"
        current = int(enterprise[level_column])
        catalog = FARM_HANGARS if system == "farm" else BUSINESS_OFFICES
        if current >= len(catalog):
            raise EnterpriseConflictError("Достигнут максимальный уровень")
        target = catalog[current]
        _settle_income(connection, user_id, enterprise, ("farm", "business"), now)
        cost = int(target["cost"])
        after = _spend_wallet(connection, user_id, cost, f"{system.upper()} upgrade", {"level": current + 1})
        connection.execute(f"UPDATE player_enterprises SET {level_column} = ? WHERE user_id = ?", (current + 1, user_id))
        if system == "farm":
            connection.execute("UPDATE player_enterprises SET farm_accrued_at = ? WHERE user_id = ?", (_iso(now), user_id))
        else:
            connection.execute("UPDATE player_enterprises SET business_accrued_at = ? WHERE user_id = ?", (_iso(now), user_id))
        result = {"success": True, "system": system, "level": current + 1, "balance": after, "cost": cost, "name": target["name"]}
        _save_action(connection, user_id, f"enterprise-upgrade:{system}", request_id, result)
        connection.commit()
        return result


def buy_animals(database_path: str, user_id: int, animal: str, quantity: int, *, request_id: str | None = None) -> dict[str, Any]:
    if animal not in FARM_ANIMALS:
        raise EnterpriseError("Неизвестное животное")
    quantity = _positive_int(quantity, "Количество", 150)
    request_id = _validated_request_id(request_id)
    action = f"farm-animals:{animal}"
    now = _now()
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        cached = _cached_action(connection, user_id, action, request_id)
        if cached is not None:
            return cached
        enterprise, _, _ = _ensure_rows(connection, user_id)
        level = int(enterprise["farm_hangar_level"])
        if not level:
            raise EnterpriseConflictError("Сначала построй ангар")
        config = FARM_ANIMALS[animal]
        cap = int(FARM_HANGARS[level - 1][animal])
        current = int(enterprise[animal])
        if current + quantity > cap:
            raise EnterpriseConflictError(f"В ангаре свободно мест: {cap - current}")
        _settle_income(connection, user_id, enterprise, ("farm", "business"), now)
        total = int(config["unit_cost"]) * quantity
        after = _spend_wallet(connection, user_id, total, f"FARM {animal}", {"quantity": quantity, "animal": animal})
        connection.execute(f"UPDATE player_enterprises SET {animal} = ?, farm_accrued_at = ? WHERE user_id = ?", (current + quantity, _iso(now), user_id))
        result = {"success": True, "animal": animal, "quantity": quantity, "count": current + quantity, "capacity": cap, "cost": total, "balance": after}
        _save_action(connection, user_id, action, request_id, result)
        connection.commit()
        return result


def buy_computers(database_path: str, user_id: int, quantity: int, *, improved: bool = False, upgrade_existing: bool = False, request_id: str | None = None) -> dict[str, Any]:
    quantity = _positive_int(quantity, "Количество", 30)
    request_id = _validated_request_id(request_id)
    action = f"business-computers:{'upgrade' if upgrade_existing else ('improved' if improved else 'standard')}"
    now = _now()
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        cached = _cached_action(connection, user_id, action, request_id)
        if cached is not None:
            return cached
        enterprise, _, _ = _ensure_rows(connection, user_id)
        level = int(enterprise["business_office_level"])
        if not level:
            raise EnterpriseConflictError("Сначала арендуй офис")
        cap = int(BUSINESS_OFFICES[level - 1]["computers"])
        current = int(enterprise["computers"])
        existing_improved = int(enterprise["improved_computers"])
        _settle_income(connection, user_id, enterprise, ("farm", "business"), now)
        if upgrade_existing:
            upgradeable = current - existing_improved
            if quantity > upgradeable:
                raise EnterpriseConflictError(f"Дешёвых компьютеров для улучшения: {upgradeable}")
            cost = quantity * 250
            after = _spend_wallet(connection, user_id, cost, "BUSINESS computer upgrade", {"quantity": quantity})
            new_count, new_improved = current, existing_improved + quantity
        else:
            if current + quantity > cap:
                raise EnterpriseConflictError(f"В офисе свободно мест для компьютеров: {cap - current}")
            if improved and level < 2:
                raise EnterpriseConflictError("Улучшенные компьютеры откроются в среднем офисе")
            cost = quantity * (500 if improved else 250)
            after = _spend_wallet(connection, user_id, cost, "BUSINESS computer purchase", {"quantity": quantity, "improved": improved})
            new_count = current + quantity
            new_improved = existing_improved + quantity if improved else existing_improved
        connection.execute("UPDATE player_enterprises SET computers = ?, improved_computers = ?, business_accrued_at = ? WHERE user_id = ?", (new_count, new_improved, _iso(now), user_id))
        result = {"success": True, "computers": new_count, "improved_computers": new_improved, "cost": cost, "balance": after}
        _save_action(connection, user_id, action, request_id, result)
        connection.commit()
        return result


def hire_workers(database_path: str, user_id: int, quantity: int, *, request_id: str | None = None) -> dict[str, Any]:
    quantity = _positive_int(quantity, "Количество", 30)
    request_id = _validated_request_id(request_id)
    now = _now()
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        cached = _cached_action(connection, user_id, "business-workers", request_id)
        if cached is not None:
            return cached
        enterprise, _, _ = _ensure_rows(connection, user_id)
        level = int(enterprise["business_office_level"])
        if not level:
            raise EnterpriseConflictError("Сначала арендуй офис")
        workers, computers = int(enterprise["workers"]), int(enterprise["computers"])
        cap = min(int(BUSINESS_OFFICES[level - 1]["workers"]), computers)
        if workers + quantity > cap:
            raise EnterpriseConflictError(f"Нужно купить компьютеры. Доступно рабочих мест: {max(0, cap - workers)}")
        _settle_income(connection, user_id, enterprise, ("farm", "business"), now)
        cost = quantity * 200
        after = _spend_wallet(connection, user_id, cost, "BUSINESS worker hiring", {"quantity": quantity})
        connection.execute("UPDATE player_enterprises SET workers = ?, business_accrued_at = ? WHERE user_id = ?", (workers + quantity, _iso(now), user_id))
        result = {"success": True, "workers": workers + quantity, "cost": cost, "balance": after}
        _save_action(connection, user_id, "business-workers", request_id, result)
        connection.commit()
        return result


def buy_advertising(database_path: str, user_id: int, campaign: str, *, request_id: str | None = None) -> dict[str, Any]:
    campaign = campaign.lower()
    if campaign not in ADS:
        raise EnterpriseError("Неизвестная рекламная кампания")
    request_id = _validated_request_id(request_id)
    action = f"business-advertising:{campaign}"
    now = _now()
    ad = ADS[campaign]
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        cached = _cached_action(connection, user_id, action, request_id)
        if cached is not None:
            return cached
        enterprise, _, _ = _ensure_rows(connection, user_id)
        if not int(enterprise["business_office_level"]):
            raise EnterpriseConflictError("Сначала арендуй офис")
        current_until = _parse(enterprise["ad_until"])
        if current_until and current_until > now:
            raise EnterpriseConflictError(f"Реклама активна ещё {int((current_until - now).total_seconds())} сек.")
        _settle_income(connection, user_id, enterprise, ("farm", "business"), now)
        after = _spend_wallet(connection, user_id, int(ad["cost"]), f"BUSINESS AD {campaign}", {"duration_minutes": ad["minutes"]})
        end = now + timedelta(minutes=int(ad["minutes"]))
        connection.execute("UPDATE player_enterprises SET ad_started_at = ?, ad_until = ?, business_accrued_at = ? WHERE user_id = ?", (_iso(now), _iso(end), _iso(now), user_id))
        result = {"success": True, "campaign": campaign, "cost": ad["cost"], "ends_at": _iso(end), "balance": after}
        _save_action(connection, user_id, action, request_id, result)
        connection.commit()
        return result


def claim_enterprise_income(database_path: str, user_id: int, system: str, *, request_id: str | None = None) -> dict[str, Any]:
    if system not in {"farm", "business"}:
        raise EnterpriseError("Неизвестный источник дохода")
    request_id = _validated_request_id(request_id)
    now = _now()
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        cached = _cached_action(connection, user_id, f"enterprise-claim:{system}", request_id)
        if cached is not None:
            return cached
        enterprise, _, _ = _ensure_rows(connection, user_id)
        if system == "farm" and not int(enterprise["farm_hangar_level"]):
            raise EnterpriseConflictError("Ферма ещё не построена")
        if system == "business" and not int(enterprise["business_office_level"]):
            raise EnterpriseConflictError("Офис ещё не арендован")
        amount = _pending_farm(enterprise, now) if system == "farm" else _pending_business(enterprise, now)
        column = "farm_accrued_at" if system == "farm" else "business_accrued_at"
        connection.execute(f"UPDATE player_enterprises SET {column} = ? WHERE user_id = ?", (_iso(now), user_id))
        balance = int(connection.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()["balance"])
        after = add_balance(connection, user_id, amount) if amount else balance
        if amount:
            _record_wallet_change(connection, user_id, f"{system.upper()} income", amount, balance, after, {"system": system})
        result = {"success": True, "system": system, "amount": amount, "balance": after, "claimed_at": _iso(now)}
        _save_action(connection, user_id, f"enterprise-claim:{system}", request_id, result)
        connection.commit()
        return result


def _ensure_bank(connection: Any, user_id: int) -> tuple[Any, Any, Any]:
    enterprise, user, bank = _ensure_rows(connection, user_id)
    if not _bank_unlock(user, enterprise):
        raise EnterpriseConflictError("Банк откроется после полной прокачки FARM и BUSINESS")
    connection.execute("INSERT OR IGNORE INTO bank_accounts(user_id) VALUES (?)", (user_id,))
    bank = connection.execute("SELECT * FROM bank_accounts WHERE user_id = ?", (user_id,)).fetchone()
    return enterprise, user, bank


def upgrade_bank_attraction(database_path: str, user_id: int, *, request_id: str | None = None) -> dict[str, Any]:
    request_id = _validated_request_id(request_id)
    now = _now()
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        cached = _cached_action(connection, user_id, "bank-attraction-upgrade", request_id)
        if cached is not None:
            return cached
        _, _, bank = _ensure_bank(connection, user_id)
        level = int(bank["attraction_level"])
        if level >= len(BANK_LEVEL_COSTS):
            raise EnterpriseConflictError("Достигнут максимальный уровень привлечения")
        cost, clients = BANK_LEVEL_COSTS[level], 100
        wallet = _spend_wallet(connection, user_id, cost, "BANK customer acquisition", {"level": level + 1})
        principal = clients * BANK_CUSTOMER_DEPOSIT
        connection.execute(
            """UPDATE bank_accounts SET attraction_level = ?, clients = clients + ?,
               cash_balance = cash_balance + ?, client_liabilities = client_liabilities + ?,
               accrued_at = COALESCE(accrued_at, ?) WHERE user_id = ?""",
            (level + 1, clients, principal, principal, _iso(now), user_id),
        )
        connection.execute("INSERT INTO bank_ledger(user_id, entry_type, amount, description) VALUES (?, 'CLIENT_DEPOSITS', ?, ?)", (user_id, principal, f"{clients} initial customers"))
        result = {"success": True, "level": level + 1, "clients_added": clients, "client_deposits": principal, "balance": wallet}
        _save_action(connection, user_id, "bank-attraction-upgrade", request_id, result)
        connection.commit()
        return result


def collect_bank_profit(database_path: str, user_id: int, *, request_id: str | None = None) -> dict[str, Any]:
    request_id = _validated_request_id(request_id)
    now = _now()
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        cached = _cached_action(connection, user_id, "bank-profit-collect", request_id)
        if cached is not None:
            return cached
        enterprise, user, bank = _ensure_bank(connection, user_id)
        pending = _pending_bank(enterprise, bank, now)
        connection.execute("UPDATE bank_accounts SET accrued_at = ? WHERE user_id = ?", (_iso(now), user_id))
        if pending:
            connection.execute("UPDATE bank_accounts SET cash_balance = cash_balance + ?, operating_profit = operating_profit + ? WHERE user_id = ?", (pending, pending, user_id))
            connection.execute("INSERT INTO bank_ledger(user_id, entry_type, amount, description) VALUES (?, 'OPERATING_PROFIT', ?, 'Customer credit interest')", (user_id, pending))
        result = {"success": True, "amount": pending, "bank": _bank_ready_payload(user, enterprise, connection.execute("SELECT * FROM bank_accounts WHERE user_id = ?", (user_id,)).fetchone())}
        _save_action(connection, user_id, "bank-profit-collect", request_id, result)
        connection.commit()
        return result


def _customer_event_inner(connection: Any, user_id: int, now: datetime) -> dict[str, Any]:
    enterprise, user, bank = _ensure_bank(connection, user_id)
    if not int(bank["attraction_level"]):
        raise EnterpriseConflictError("Сначала привлеки клиентов в банк")
    deposit = random.random() < 0.55 or int(bank["clients"]) < 1 or int(bank["client_liabilities"]) < 1
    amount = random.randint(500, 2500)
    if deposit:
        connection.execute("UPDATE bank_accounts SET clients = clients + 1, cash_balance = cash_balance + ?, client_liabilities = client_liabilities + ? WHERE user_id = ?", (amount, amount, user_id))
        message, status = "Клиент пришёл положить деньги", "COMPLETED"
        connection.execute("INSERT INTO bank_ledger(user_id, entry_type, amount, description) VALUES (?, 'CLIENT_DEPOSIT', ?, ?)", (user_id, amount, message))
    else:
        amount = min(amount, int(bank["client_liabilities"]))
        if amount <= int(bank["cash_balance"]):
            connection.execute("UPDATE bank_accounts SET clients = MAX(0, clients - 1), cash_balance = cash_balance - ?, client_liabilities = client_liabilities - ? WHERE user_id = ?", (amount, amount, user_id))
            message, status = "Клиент пришёл забрать деньги · депозит возвращён", "COMPLETED"
            connection.execute("INSERT INTO bank_ledger(user_id, entry_type, amount, description) VALUES (?, 'CLIENT_WITHDRAWAL', ?, ?)", (user_id, amount, message))
        else:
            wallet_before = int(user["balance"])
            penalty = min(500, wallet_before)
            if penalty:
                wallet_after = max(0, wallet_before - penalty)
                connection.execute("UPDATE users SET balance = ? WHERE id = ?", (wallet_after, user_id))
                _record_wallet_change(connection, user_id, "BANK customer reserve penalty", penalty, wallet_before, wallet_after, {"requested_refund": amount})
            message, status = "Клиент пришёл забрать деньги · недостаточно средств, штраф 500 SH", "PENALTY"
            connection.execute("INSERT INTO bank_ledger(user_id, entry_type, amount, description) VALUES (?, 'CLIENT_DEFAULT', ?, ?)", (user_id, amount, message))
    connection.execute("INSERT INTO bank_customer_events(user_id, event_type, amount, message, status, created_at) VALUES (?, ?, ?, ?, ?, ?)", (user_id, "DEPOSIT" if deposit else "WITHDRAWAL", amount, message, status, _iso(now)))
    return {"success": True, "event": "DEPOSIT" if deposit else "WITHDRAWAL", "amount": amount, "message": message, "status": status}


def process_bank_customer(database_path: str, user_id: int, *, request_id: str | None = None) -> dict[str, Any]:
    request_id = _validated_request_id(request_id)
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        cached = _cached_action(connection, user_id, "bank-customer-event", request_id)
        if cached is not None:
            return cached
        result = _customer_event_inner(connection, user_id, _now())
        _save_action(connection, user_id, "bank-customer-event", request_id, result)
        connection.commit()
        return result


def _stable_hour_change(code: str, period: int) -> float:
    digest = hashlib.sha256(f"{code}:{period}".encode()).digest()
    value = int.from_bytes(digest[:8], "big") / (2**64 - 1)
    return -0.20 + value * 0.40


def _refresh_company_prices(connection: Any, now: datetime) -> None:
    current_period = int(now.timestamp() // 3600)
    rows = connection.execute("SELECT * FROM bank_companies").fetchall()
    for row in rows:
        last_period = int(row["updated_period"])
        if current_period <= last_period:
            continue
        price = float(row["price"])
        previous = price
        first = last_period + 1
        for period in range(first, current_period + 1):
            previous = price
            price = max(1, round(price * (1 + _stable_hour_change(row["code"], period)), 2))
            connection.execute("INSERT OR REPLACE INTO bank_company_history(company_code, period, price) VALUES (?, ?, ?)", (row["code"], period, price))
        connection.execute("UPDATE bank_companies SET price = ?, previous_price = ?, updated_period = ? WHERE code = ?", (price, previous, current_period, row["code"]))
        connection.execute("DELETE FROM bank_company_history WHERE company_code = ? AND period < ?", (row["code"], current_period - 24 * 365))


def _crypto_refresh_due(connection: Any, now: datetime) -> bool:
    row = connection.execute("SELECT MIN(fetched_at) AS last FROM crypto_market").fetchone()
    last = _parse(row["last"]) if row and row["last"] else None
    return last is None or (now - last).total_seconds() >= CRYPTO_CACHE_SECONDS


def _fetch_crypto_prices() -> dict[str, tuple[float, float]]:
    ids = ",".join(CRYPTO_IDS.values())
    url = "https://api.coingecko.com/api/v3/simple/price?" + urllib.parse.urlencode({"ids": ids, "vs_currencies": "usd", "include_24hr_change": "true"})
    request = urllib.request.Request(url, headers={"User-Agent": "SHAMA-WORLD/9.0", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=2.0) as response:
        payload = json.loads(response.read(64_000).decode("utf-8"))
    results: dict[str, tuple[float, float]] = {}
    for code, api_id in CRYPTO_IDS.items():
        entry = payload[api_id]
        price = float(entry["usd"]) * CRYPTO_SH_PER_USD
        change = float(entry.get("usd_24h_change", 0))
        if math.isfinite(price) and price > 0 and math.isfinite(change):
            results[code] = (round(price, 2), max(-99.9, min(999.9, change)))
    return results


def refresh_crypto_prices(database_path: str) -> None:
    now = _now()
    with get_connection(database_path) as connection:
        if not _crypto_refresh_due(connection, now):
            return
    try:
        prices = _fetch_crypto_prices()
    except Exception:
        # Keep the last saved price and cool down failed requests as well, so
        # an unavailable provider cannot stall every visit to the Bank screen.
        with get_connection(database_path) as connection:
            connection.execute("UPDATE crypto_market SET fetched_at = ?", (_iso(now),))
            connection.commit()
        return
    if not prices:
        return
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        for code, (price, change) in prices.items():
            connection.execute("UPDATE crypto_market SET price = ?, change_percent = ?, updated_at = ?, fetched_at = ? WHERE code = ?", (price, change, _iso(now), _iso(now), code))
            connection.execute("INSERT OR REPLACE INTO crypto_market_history(code, recorded_at, price) VALUES (?, ?, ?)", (code, _iso(now), price))
        connection.commit()


def _price_history(connection: Any, code: str) -> list[float]:
    rows = connection.execute("SELECT price FROM bank_company_history WHERE company_code = ? ORDER BY period DESC LIMIT 12", (code,)).fetchall()
    return [float(row["price"]) for row in reversed(rows)]


def _company_payload(connection: Any, user_id: int, bank: Any) -> list[dict[str, Any]]:
    del bank
    rows = connection.execute("SELECT * FROM bank_companies ORDER BY CASE code WHEN 'SH_COMPANY' THEN 1 WHEN 'TORPEDO' THEN 2 ELSE 3 END").fetchall()
    output = []
    for row in rows:
        holding = connection.execute("SELECT shares, average_cost FROM bank_company_holdings WHERE user_id = ? AND company_code = ?", (user_id, row["code"])).fetchone()
        price = float(row["price"])
        previous = float(row["previous_price"])
        output.append({
            "code": row["code"], "name": row["name"], "price": price,
            "change_percent": round((price / previous - 1) * 100, 2) if previous else 0,
            "source": "DEMO", "risk": "MEDIUM",
            "dividend_rate": float(row["dividend_rate"]), "total_supply": int(row["total_supply"]),
            "available": int(row["total_supply"] - row["shares_sold"]),
            "owned": int(holding["shares"]) if holding else 0,
            "average_cost": round(float(holding["average_cost"]), 2) if holding else 0,
            "history": _price_history(connection, row["code"]),
            "value": round(int(holding["shares"]) * price, 2) if holding else 0,
        })
    return output


def _crypto_payload(connection: Any, user_id: int, bank: Any) -> list[dict[str, Any]]:
    del bank
    now = _now()
    rows = connection.execute("SELECT * FROM crypto_market ORDER BY CASE code WHEN 'BTC' THEN 1 WHEN 'ETH' THEN 2 ELSE 3 END").fetchall()
    output = []
    for row in rows:
        holding = connection.execute("SELECT quantity, average_cost FROM bank_crypto_holdings WHERE user_id = ? AND code = ?", (user_id, row["code"])).fetchone()
        history = connection.execute("SELECT price FROM crypto_market_history WHERE code = ? ORDER BY recorded_at DESC LIMIT 12", (row["code"],)).fetchall()
        updated = _parse(row["updated_at"])
        fetched = _parse(row["fetched_at"])
        age = max(0.0, (now - updated).total_seconds()) if updated else float("inf")
        source = "DEMO" if not fetched else ("LIVE" if age <= CRYPTO_CACHE_SECONDS * 3 else "CACHED")
        output.append({
            "code": row["code"], "name": row["name"], "price": float(row["price"]),
            "change_percent": float(row["change_percent"]), "owned": float(holding["quantity"]) if holding else 0,
            "average_cost": float(holding["average_cost"]) if holding else 0,
            "history": [float(entry["price"]) for entry in reversed(history)],
            "source": source, "risk": "HIGH", "last_updated": row["updated_at"],
        })
    return output


def _portfolio_summary(user: Any, bank: Any, companies: list[dict], crypto: list[dict]) -> dict[str, Any]:
    invested = 0.0
    market_value = 0.0
    unrealized = 0.0
    recent_pnl = 0.0
    equity = []
    for asset_type, assets in (("stock", companies), ("crypto", crypto)):
        for asset in assets:
            quantity = float(asset.get("owned", 0) or 0)
            price = float(asset.get("price", 0) or 0)
            average = float(asset.get("average_cost", 0) or 0)
            value = quantity * price
            cost = quantity * average
            change = float(asset.get("change_percent", 0) or 0)
            previous = price / (1 + change / 100) if change > -99 else price
            invested += cost
            market_value += value
            unrealized += value - cost
            recent_pnl += value - quantity * previous
            if value > 0:
                equity.append({
                    "code": asset["code"], "name": asset["name"], "type": asset_type,
                    "value": round(value, 2), "invested": round(cost, 2),
                    "pnl": round(value - cost, 2), "risk": asset.get("risk", "MEDIUM"),
                })
    cash = int(bank["cash_balance"]) if bank else 0
    liabilities = int(bank["client_liabilities"]) if bank else 0
    available_cash = max(0, cash - liabilities)
    bank_assets = cash + market_value
    own_capital = bank_assets - liabilities
    total_assets = int(user["balance"]) + own_capital
    allocation = [{"code": "BANK_CASH", "name": "Свободный капитал банка", "type": "cash", "value": available_cash}]
    allocation.extend({"code": item["code"], "name": item["name"], "type": item["type"], "value": item["value"]} for item in equity)
    allocation_total = sum(item["value"] for item in allocation)
    for item in allocation:
        item["percent"] = round(item["value"] / allocation_total * 100, 2) if allocation_total else 0
    realized = float(bank["investment_profit"]) if bank else 0
    return {
        "total_assets": round(total_assets, 2),
        "current_account": int(user["balance"]),
        "client_money": liabilities,
        "own_capital": round(own_capital, 2),
        "available_cash": available_cash,
        "total_invested": round(invested, 2),
        "portfolio_value": round(market_value, 2),
        "unrealized_pnl": round(unrealized, 2),
        "realized_profit": round(realized, 2),
        "total_pnl": round(unrealized + realized, 2),
        "recent_market_pnl": round(recent_pnl, 2),
        "allocation": allocation,
        "assets": equity,
        "stocks_source": "DEMO",
        "crypto_source": "LIVE" if crypto and all(item["source"] == "LIVE" for item in crypto) else (
            "DEMO" if crypto and all(item["source"] == "DEMO" for item in crypto) else "CACHED"
        ),
    }


def _pending_dividends(connection: Any, user_id: int, bank: Any, now: datetime, *, update: bool) -> float:
    if bank is None or not int(bank["attraction_level"]):
        return 0
    holdings = connection.execute(
        """SELECT h.*, c.price, c.dividend_rate FROM bank_company_holdings h
           JOIN bank_companies c ON c.code = h.company_code WHERE h.user_id = ?""", (user_id,)
    ).fetchall()
    total = 0.0
    updates = []
    for holding in holdings:
        checkpoint = _parse(holding["dividend_checkpoint"])
        if checkpoint is None:
            continue
        periods = max(0, int((now - checkpoint).total_seconds() // (4 * 3600)))
        if not periods:
            continue
        value = int(holding["shares"]) * float(holding["price"]) * float(holding["dividend_rate"]) * periods
        total += value
        updates.append((holding["company_code"], _iso(checkpoint + timedelta(hours=4 * periods))))
    if update and total:
        for code, checkpoint in updates:
            connection.execute("UPDATE bank_company_holdings SET dividend_checkpoint = ? WHERE user_id = ? AND company_code = ?", (checkpoint, user_id, code))
    return total


MARKET_PERIOD_HOURS = {
    "1H": 1, "1D": 24, "1W": 168, "1M": 720, "3M": 2160, "1Y": 8760,
}


def _market_history(connection: Any, asset_type: str, code: str, period: str, now: datetime) -> list[dict[str, Any]]:
    period = period.upper()
    if period not in MARKET_PERIOD_HOURS:
        raise EnterpriseError("Неизвестный период графика")
    start = now - timedelta(hours=MARKET_PERIOD_HOURS[period])
    if asset_type == "stock":
        start_period = int(start.timestamp() // 3600)
        rows = connection.execute(
            "SELECT period, price FROM bank_company_history WHERE company_code = ? AND period >= ? ORDER BY period",
            (code, start_period),
        ).fetchall()
        points = [
            {"time": datetime.fromtimestamp(int(row["period"]) * 3600, timezone.utc).isoformat(), "value": float(row["price"])}
            for row in rows
        ]
    else:
        rows = connection.execute(
            "SELECT recorded_at, price FROM crypto_market_history WHERE code = ? AND recorded_at >= ? ORDER BY recorded_at",
            (code, _iso(start)),
        ).fetchall()
        points = [{"time": row["recorded_at"], "value": float(row["price"])} for row in rows]
    if len(points) > 160:
        indexes = [round(index * (len(points) - 1) / 159) for index in range(160)]
        points = [points[index] for index in indexes]
    return points


def bank_market(database_path: str, user_id: int, period: str = "1D") -> dict[str, Any]:
    period = period.upper()
    if period not in MARKET_PERIOD_HOURS:
        raise EnterpriseError("Неизвестный период графика")
    refresh_crypto_prices(database_path)
    now = _now()
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        _refresh_company_prices(connection, now)
        enterprise, user, bank = _ensure_bank(connection, user_id)
        connection.commit()
        companies = _company_payload(connection, user_id, bank)
        crypto = _crypto_payload(connection, user_id, bank)
        for asset in companies:
            asset["history_points"] = _market_history(connection, "stock", asset["code"], period, now)
        for asset in crypto:
            asset["history_points"] = _market_history(connection, "crypto", asset["code"], period, now)
        portfolio = _portfolio_summary(user, bank, companies, crypto)
        connection.execute(
            "INSERT INTO bank_portfolio_snapshots(user_id, recorded_at, total_assets, portfolio_value, client_liabilities) VALUES (?, ?, ?, ?, ?)",
            (user_id, _iso(now), portfolio["total_assets"], portfolio["portfolio_value"], portfolio["client_money"]),
        )
        history_start = _iso(now - timedelta(hours=MARKET_PERIOD_HOURS[period]))
        history_rows = connection.execute(
            "SELECT recorded_at, total_assets FROM bank_portfolio_snapshots WHERE user_id = ? AND recorded_at >= ? ORDER BY recorded_at",
            (user_id, history_start),
        ).fetchall()
        portfolio["history"] = [{"time": row["recorded_at"], "value": float(row["total_assets"])} for row in history_rows[-160:]]
        portfolio["period"] = period
        connection.commit()
        return {
            "bank": _bank_ready_payload(user, enterprise, bank),
            "companies": companies,
            "crypto": crypto,
            "portfolio": portfolio,
        }


def _bank_buy_cash(connection: Any, user_id: int, cost: float) -> Any:
    _, _, bank = _ensure_bank(connection, user_id)
    cost_ceil = math.ceil(cost)
    available_cash = int(bank["cash_balance"]) - int(bank["client_liabilities"])
    if available_cash < cost_ceil:
        raise EnterpriseConflictError("Недостаточно свободного капитала банка после резервирования денег клиентов")
    connection.execute("UPDATE bank_accounts SET cash_balance = cash_balance - ? WHERE user_id = ?", (cost_ceil, user_id))
    return connection.execute("SELECT * FROM bank_accounts WHERE user_id = ?", (user_id,)).fetchone()


def _trade_price(market_price: float, requested_price: Any = None) -> float:
    # Trade execution always uses the current server-side quote. Keep the
    # optional argument for older clients, but never accept a client price.
    del requested_price
    return round(market_price, 2)


def _unlock_control_package(connection: Any, user_id: int, company_code: str) -> bool:
    company = connection.execute("SELECT total_supply FROM bank_companies WHERE code = ?", (company_code,)).fetchone()
    holding = connection.execute("SELECT shares FROM bank_company_holdings WHERE user_id = ? AND company_code = ?", (user_id, company_code)).fetchone()
    if not company or not holding or int(holding["shares"]) * 2 < int(company["total_supply"]):
        return False
    connection.execute("UPDATE users SET bank_control_package = 1 WHERE id = ?", (user_id,))
    achievement = connection.execute("SELECT id FROM achievements WHERE code = 'BANK_CONTROL_PACKAGE'").fetchone()
    if achievement:
        connection.execute("INSERT OR IGNORE INTO user_achievements(user_id, achievement_id) VALUES (?, ?)", (user_id, achievement["id"]))
    return True


def trade_stock(database_path: str, user_id: int, code: str, side: str, quantity: int, price: Any = None, *, request_id: str | None = None) -> dict[str, Any]:
    code, side = code.upper(), side.lower()
    if side not in {"buy", "sell"}:
        raise EnterpriseError("Операция должна быть BUY или SELL")
    quantity = _positive_int(quantity, "Количество", 200_000)
    request_id = _validated_request_id(request_id)
    action = f"bank-stock:{code}:{side}"
    now = _now()
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        cached = _cached_action(connection, user_id, action, request_id)
        if cached is not None:
            return cached
        _refresh_company_prices(connection, now)
        _, _, bank = _ensure_bank(connection, user_id)
        pending_dividends = math.floor(_pending_dividends(connection, user_id, bank, now, update=True))
        if pending_dividends:
            connection.execute("UPDATE bank_accounts SET cash_balance = cash_balance + ?, investment_profit = investment_profit + ? WHERE user_id = ?", (pending_dividends, pending_dividends, user_id))
            connection.execute("INSERT INTO bank_ledger(user_id, entry_type, amount, description) VALUES (?, 'DIVIDEND', ?, 'Equity dividends')", (user_id, pending_dividends))
        company = connection.execute("SELECT * FROM bank_companies WHERE code = ?", (code,)).fetchone()
        if company is None:
            raise EnterpriseNotFoundError("Компания не найдена")
        trade_price = _trade_price(float(company["price"]), price)
        holding = connection.execute("SELECT * FROM bank_company_holdings WHERE user_id = ? AND company_code = ?", (user_id, code)).fetchone()
        value = trade_price * quantity
        if side == "buy":
            if quantity > int(company["total_supply"] - company["shares_sold"]):
                raise EnterpriseConflictError("Столько акций больше не осталось")
            _bank_buy_cash(connection, user_id, value)
            total_owned = int(holding["shares"]) if holding else 0
            old_cost = float(holding["average_cost"]) if holding else 0
            average = ((old_cost * total_owned) + value) / (total_owned + quantity)
            connection.execute("UPDATE bank_companies SET shares_sold = shares_sold + ? WHERE code = ?", (quantity, code))
            connection.execute(
                """INSERT INTO bank_company_holdings(user_id, company_code, shares, average_cost, dividend_checkpoint)
                   VALUES (?, ?, ?, ?, ?) ON CONFLICT(user_id, company_code) DO UPDATE SET
                   shares=excluded.shares, average_cost=excluded.average_cost""",
                (user_id, code, total_owned + quantity, average, _iso(now)),
            )
            connection.execute("INSERT INTO bank_ledger(user_id, entry_type, amount, description) VALUES (?, 'STOCK_BUY', ?, ?)", (user_id, math.ceil(value), f"Bought {quantity} shares of {code}"))
        else:
            if not holding or int(holding["shares"]) < quantity:
                raise EnterpriseConflictError("Недостаточно акций для продажи")
            realized = value - float(holding["average_cost"]) * quantity
            connection.execute("UPDATE bank_accounts SET cash_balance = cash_balance + ?, investment_profit = investment_profit + ? WHERE user_id = ?", (math.floor(value), realized, user_id))
            remaining = int(holding["shares"]) - quantity
            if remaining:
                connection.execute("UPDATE bank_company_holdings SET shares = ? WHERE user_id = ? AND company_code = ?", (remaining, user_id, code))
            else:
                connection.execute("DELETE FROM bank_company_holdings WHERE user_id = ? AND company_code = ?", (user_id, code))
            connection.execute("UPDATE bank_companies SET shares_sold = shares_sold - ? WHERE code = ?", (quantity, code))
            connection.execute("INSERT INTO bank_ledger(user_id, entry_type, amount, description) VALUES (?, 'STOCK_SALE', ?, ?)", (user_id, math.floor(value), f"{code} realized P/L {realized:.2f}"))
        control = _unlock_control_package(connection, user_id, code) if side == "buy" else False
        result = {"success": True, "side": side, "code": code, "quantity": quantity, "price": trade_price, "value": round(value, 2), "investment_profit_delta": round(value - float(holding["average_cost"]) * quantity, 2) if side == "sell" and holding else 0, "control_package_unlocked": control}
        _save_action(connection, user_id, action, request_id, result)
        connection.commit()
        return result


def trade_crypto(database_path: str, user_id: int, code: str, side: str, quantity: Any, price: Any = None, *, request_id: str | None = None) -> dict[str, Any]:
    code, side = code.upper(), side.lower()
    if side not in {"buy", "sell"}:
        raise EnterpriseError("Операция должна быть BUY или SELL")
    try:
        amount = float(quantity)
    except (TypeError, ValueError) as error:
        raise EnterpriseError("Количество монет указано неверно") from error
    if isinstance(quantity, bool) or not math.isfinite(amount) or amount <= 0 or amount > 1_000_000:
        raise EnterpriseError("Количество монет должно быть больше нуля")
    amount = round(amount, 8)
    request_id = _validated_request_id(request_id)
    action = f"bank-crypto:{code}:{side}"
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        cached = _cached_action(connection, user_id, action, request_id)
        if cached is not None:
            return cached
        _, _, _ = _ensure_bank(connection, user_id)
        market = connection.execute("SELECT * FROM crypto_market WHERE code = ?", (code,)).fetchone()
        if market is None:
            raise EnterpriseNotFoundError("Криптовалюта не найдена")
        trade_price = _trade_price(float(market["price"]), price)
        holding = connection.execute("SELECT * FROM bank_crypto_holdings WHERE user_id = ? AND code = ?", (user_id, code)).fetchone()
        value = amount * trade_price
        if value < 1:
            raise EnterpriseError("Минимальная сумма сделки — 1 SH")
        if side == "buy":
            _bank_buy_cash(connection, user_id, value)
            old_quantity = float(holding["quantity"]) if holding else 0
            old_cost = float(holding["average_cost"]) if holding else 0
            avg = (old_quantity * old_cost + value) / (old_quantity + amount)
            connection.execute("INSERT INTO bank_crypto_holdings(user_id, code, quantity, average_cost) VALUES (?, ?, ?, ?) ON CONFLICT(user_id, code) DO UPDATE SET quantity=excluded.quantity, average_cost=excluded.average_cost", (user_id, code, old_quantity + amount, avg))
            connection.execute("INSERT INTO bank_ledger(user_id, entry_type, amount, description) VALUES (?, 'CRYPTO_BUY', ?, ?)", (user_id, math.ceil(value), f"Bought {amount} {code}"))
        else:
            if not holding or float(holding["quantity"]) + 1e-9 < amount:
                raise EnterpriseConflictError("Недостаточно монет для продажи")
            realized = value - amount * float(holding["average_cost"])
            connection.execute("UPDATE bank_accounts SET cash_balance = cash_balance + ?, investment_profit = investment_profit + ? WHERE user_id = ?", (math.floor(value), realized, user_id))
            remaining = round(float(holding["quantity"]) - amount, 8)
            if remaining > 0:
                connection.execute("UPDATE bank_crypto_holdings SET quantity = ? WHERE user_id = ? AND code = ?", (remaining, user_id, code))
            else:
                connection.execute("DELETE FROM bank_crypto_holdings WHERE user_id = ? AND code = ?", (user_id, code))
            connection.execute("INSERT INTO bank_ledger(user_id, entry_type, amount, description) VALUES (?, 'CRYPTO_SALE', ?, ?)", (user_id, math.floor(value), f"{code} realized P/L {realized:.2f}"))
        result = {"success": True, "side": side, "code": code, "quantity": amount, "price": trade_price, "value": round(value, 2), "investment_profit_delta": round(value - amount * float(holding["average_cost"]) if side == "sell" and holding else 0, 2)}
        _save_action(connection, user_id, action, request_id, result)
        connection.commit()
        return result


def claim_bank_dividends(database_path: str, user_id: int, *, request_id: str | None = None) -> dict[str, Any]:
    request_id = _validated_request_id(request_id)
    now = _now()
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        cached = _cached_action(connection, user_id, "bank-dividend-claim", request_id)
        if cached is not None:
            return cached
        enterprise, user, bank = _ensure_bank(connection, user_id)
        amount = _pending_dividends(connection, user_id, bank, now, update=True)
        rounded = math.floor(amount)
        if rounded:
            connection.execute("UPDATE bank_accounts SET cash_balance = cash_balance + ?, investment_profit = investment_profit + ? WHERE user_id = ?", (rounded, rounded, user_id))
            connection.execute("INSERT INTO bank_ledger(user_id, entry_type, amount, description) VALUES (?, 'DIVIDEND', ?, 'Equity dividends')", (user_id, rounded))
        result = {"success": True, "amount": rounded, "bank": _bank_ready_payload(user, enterprise, connection.execute("SELECT * FROM bank_accounts WHERE user_id = ?", (user_id,)).fetchone())}
        _save_action(connection, user_id, "bank-dividend-claim", request_id, result)
        connection.commit()
        return result


def withdraw_bank_profit(database_path: str, user_id: int, amount: int, *, request_id: str | None = None) -> dict[str, Any]:
    amount = _positive_int(amount, "Сумма", 2_000_000_000)
    request_id = _validated_request_id(request_id)
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        cached = _cached_action(connection, user_id, "bank-profit-withdraw", request_id)
        if cached is not None:
            return cached
        enterprise, user, bank = _ensure_bank(connection, user_id)
        profit = int(bank["operating_profit"]) + int(bank["investment_profit"])
        if amount > profit:
            raise EnterpriseConflictError("Можно вывести только заработанную прибыль, не клиентский депозит")
        reserve = int(bank["cash_balance"]) - int(bank["client_liabilities"])
        if amount > reserve:
            raise EnterpriseConflictError("В банке недостаточно свободной ликвидности для вывода")
        op_profit, inv_profit = int(bank["operating_profit"]), float(bank["investment_profit"])
        from_investment = min(amount, max(0, math.floor(inv_profit)))
        remaining = amount - from_investment
        connection.execute("UPDATE bank_accounts SET cash_balance = cash_balance - ?, investment_profit = investment_profit - ?, operating_profit = operating_profit - ? WHERE user_id = ?", (amount, from_investment, remaining, user_id))
        before = int(user["balance"])
        after = add_balance(connection, user_id, amount)
        _record_wallet_change(connection, user_id, "BANK earned profit withdrawal", amount, before, after, {"operating_profit": remaining, "investment_profit": from_investment})
        connection.execute("INSERT INTO bank_ledger(user_id, entry_type, amount, description) VALUES (?, 'PROFIT_WITHDRAWAL', ?, 'Earned profit transferred to player balance')", (user_id, amount))
        result = {"success": True, "amount": amount, "balance": after, "bank": _bank_ready_payload(user, enterprise, connection.execute("SELECT * FROM bank_accounts WHERE user_id = ?", (user_id,)).fetchone())}
        _save_action(connection, user_id, "bank-profit-withdraw", request_id, result)
        connection.commit()
        return result
