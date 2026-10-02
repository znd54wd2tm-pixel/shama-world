"""SHAMA WORKS progression, farms, businesses, deposits and daily quests.

The module adds a mobile-first economy on top of the pre-existing game tables.
It never clears or reinterprets legacy possessions: a player who already owns a
Farm/Business asset gets an equivalent starting SHAMA WORKS level on first use.
All wallet changes happen in SQLite transactions on the backend.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

try:
    from database import get_connection
    from services.economy import add_balance, record_transaction, remove_balance
    from services.earnings import JOB_CONFIG, list_jobs
except ImportError:  # pragma: no cover
    from ..database import get_connection
    from .economy import add_balance, record_transaction, remove_balance
    from .earnings import JOB_CONFIG, list_jobs


class WorksError(RuntimeError):
    status_code = 400


class WorksConflictError(WorksError):
    status_code = 409


FARM_LEVELS = (
    {"level": 1, "cost": 600, "name": "ПОЛЕ", "storage": 1_400},
    {"level": 2, "cost": 2_000, "name": "РАСШИРЕННАЯ ФЕРМА", "storage": 3_400},
    {"level": 3, "cost": 6_000, "name": "АГРОКОМПЛЕКС", "storage": 7_000},
    {"level": 4, "cost": 14_000, "name": "ТЕПЛИЧНЫЙ КЛАСТЕР", "storage": 13_000},
    {"level": 5, "cost": 30_000, "name": "SHAMA AGRO", "storage": 22_000},
)

BUSINESS_LEVELS = (
    {"level": 1, "cost": 1_500, "name": "ЛАРЁК", "income": 30, "storage": 1_800},
    {"level": 2, "cost": 4_500, "name": "МАГАЗИН", "income": 75, "storage": 4_200},
    {"level": 3, "cost": 12_000, "name": "КОМПАНИЯ", "income": 160, "storage": 9_000},
    {"level": 4, "cost": 30_000, "name": "ФАБРИКА", "income": 320, "storage": 18_000},
    {"level": 5, "cost": 75_000, "name": "КОРПОРАЦИЯ", "income": 600, "storage": 32_000},
)

PROGRESSION = (
    (1, "РАБОТА", "Открывает первые профессии"),
    (3, "FARM", "Собственная ферма и урожай"),
    (5, "BUSINESS", "Бизнес-империя"),
    (8, "BANK", "Вклады и финансовый центр"),
    (12, "SH MARKET", "Игровые активы SH Market"),
    (20, "SHAMA WORLD TYCOON", "Максимальная ступень мира"),
)

QUESTS = (
    ("farm_collect", "Собери доход фермы", 3, 1, 100, 10),
    ("business_upgrade", "Улучши бизнес", 5, 1, 170, 15),
    ("work_complete", "Выполни 2 работы", 1, 2, 130, 12),
    ("bank_operation", "Соверши операцию в банке", 8, 1, 220, 18),
    ("market_view", "Посети SH Market", 12, 1, 180, 15),
)

MAX_ACCRUAL_SECONDS = 12 * 60 * 60
FARM_WORKER_COST = 400
BUSINESS_WORKER_COST = 750
DEPOSIT_RATES = {7: 0.04, 14: 0.055, 30: 0.075}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _today() -> str:
    return _now().date().isoformat()


def _positive(value: Any, label: str, maximum: int = 1_000_000) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > maximum:
        raise WorksError(f"{label}: укажи положительное целое число")
    return value


def _request_id(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value or len(value) > 128:
        raise WorksError("Request ID must содержать от 1 до 128 символов")
    return value


def _cached(connection: Any, user_id: int, action: str, request_id: str | None) -> dict[str, Any] | None:
    if not request_id:
        return None
    row = connection.execute(
        "SELECT response_json FROM bank_action_requests WHERE user_id = ? AND action = ? AND request_id = ?",
        (user_id, action, request_id),
    ).fetchone()
    return json.loads(row["response_json"]) if row else None


def _save(connection: Any, user_id: int, action: str, request_id: str | None, result: dict[str, Any]) -> None:
    if request_id:
        connection.execute(
            "INSERT INTO bank_action_requests(user_id, action, request_id, response_json) VALUES (?, ?, ?, ?)",
            (user_id, action, request_id, json.dumps(result, ensure_ascii=False, separators=(",", ":"))),
        )


def _ensure_profiles(connection: Any, user_id: int) -> tuple[Any, Any, Any]:
    """Create new layer rows and make a one-time non-destructive legacy bridge."""

    user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        raise WorksError("Пользователь не найден")
    legacy = connection.execute("SELECT * FROM player_enterprises WHERE user_id = ?", (user_id,)).fetchone()
    legacy_farm = int(legacy["farm_hangar_level"]) if legacy else 0
    legacy_business = int(legacy["business_office_level"]) if legacy else 0
    connection.execute(
        "INSERT OR IGNORE INTO works_farms(user_id, level, accrued_at) VALUES (?, ?, ?)",
        (user_id, min(5, legacy_farm), _iso(_now())),
    )
    connection.execute(
        "INSERT OR IGNORE INTO works_businesses(user_id, level, accrued_at) VALUES (?, ?, ?)",
        (user_id, min(5, legacy_business), _iso(_now())),
    )
    farm = connection.execute("SELECT * FROM works_farms WHERE user_id = ?", (user_id,)).fetchone()
    business = connection.execute("SELECT * FROM works_businesses WHERE user_id = ?", (user_id,)).fetchone()
    return user, farm, business


def _farm_crops(level: int) -> list[dict[str, Any]]:
    crops = []
    if level >= 1:
        crops.append({"name": "ПШЕНИЦА", "income_per_hour": 25})
    if level >= 2:
        crops.append({"name": "КУКУРУЗА", "income_per_hour": 40})
    if level >= 4:
        crops.append({"name": "ТЕПЛИЦА", "income_per_hour": 75})
    if level >= 5:
        crops.append({"name": "ЭКО-ФЕРМА", "income_per_hour": 110})
    return crops


def _farm_rate(row: Any) -> int:
    level = int(row["level"])
    base = sum(crop["income_per_hour"] for crop in _farm_crops(level))
    return int(base * (1 + min(int(row["workers"]), level * 3) * 0.07))


def _business_rate(row: Any) -> int:
    level = int(row["level"])
    if not level:
        return 0
    base = int(BUSINESS_LEVELS[level - 1]["income"])
    return int(base * (1 + min(int(row["workers"]), level * 4) * 0.06))


def _capacity(level: int, catalog: tuple[dict[str, Any], ...]) -> int:
    return int(catalog[level - 1]["storage"]) if level else 0


def _available(row: Any, rate_per_hour: int, capacity: int, now: datetime) -> int:
    if not rate_per_hour or not capacity:
        return int(row["stored_sh"])
    last = _parse(row["accrued_at"]) or now
    elapsed = max(0, min(MAX_ACCRUAL_SECONDS, int((now - last).total_seconds())))
    return min(capacity, int(row["stored_sh"]) + int(rate_per_hour * elapsed / 3600))


def _settle(connection: Any, table: str, user_id: int, row: Any, rate: int, capacity: int, now: datetime) -> Any:
    stored = _available(row, rate, capacity, now)
    connection.execute(f"UPDATE {table} SET stored_sh = ?, accrued_at = ? WHERE user_id = ?", (stored, _iso(now), user_id))
    return connection.execute(f"SELECT * FROM {table} WHERE user_id = ?", (user_id,)).fetchone()


def _ensure_quests(connection: Any, user: Any) -> None:
    today = _today()
    level = int(user["level"])
    for code, title, unlock_level, target, reward_sh, reward_xp in QUESTS:
        if level >= unlock_level:
            connection.execute(
                """INSERT OR IGNORE INTO daily_business_quests
                   (user_id, quest_date, code, title, target_value, reward_sh, reward_xp)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user["id"], today, code, title, target, reward_sh, reward_xp),
            )


def _quest_payload(connection: Any, user: Any) -> list[dict[str, Any]]:
    _ensure_quests(connection, user)
    rows = connection.execute(
        "SELECT * FROM daily_business_quests WHERE user_id = ? AND quest_date = ? ORDER BY id",
        (user["id"], _today()),
    ).fetchall()
    unlocked = {row["code"]: dict(row) for row in rows}
    output = []
    for code, title, unlock_level, target, reward_sh, reward_xp in QUESTS:
        row = unlocked.get(code)
        output.append({
            "code": code, "title": title, "unlock_level": unlock_level, "locked": int(user["level"]) < unlock_level,
            "current": int(row["current_value"]) if row else 0, "target": target,
            "reward_sh": reward_sh, "reward_xp": reward_xp,
            "completed": bool(row and row["completed_at"]),
        })
    return output


def record_quest_event(database_path: str, user_id: int, code: str, event_key: str | None = None) -> dict[str, Any]:
    """Record one server-issued quest event and pay completion exactly once."""

    today = _today()
    event_key = (event_key or f"{code}:{today}").strip()[:128]
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            raise WorksError("Пользователь не найден")
        _ensure_quests(connection, user)
        cursor = connection.execute(
            "INSERT OR IGNORE INTO daily_quest_events(user_id, quest_date, event_key) VALUES (?, ?, ?)",
            (user_id, today, event_key),
        )
        if cursor.rowcount == 0:
            connection.commit()
            return {"completed": [], "balance": int(user["balance"]), "idempotent": True}
        row = connection.execute(
            "SELECT * FROM daily_business_quests WHERE user_id = ? AND quest_date = ? AND code = ?",
            (user_id, today, code),
        ).fetchone()
        completed: list[dict[str, Any]] = []
        if row and not row["completed_at"]:
            current = min(int(row["target_value"]), int(row["current_value"]) + 1)
            connection.execute("UPDATE daily_business_quests SET current_value = ? WHERE id = ?", (current, row["id"]))
            if current >= int(row["target_value"]):
                fresh = connection.execute("SELECT balance, xp FROM users WHERE id = ?", (user_id,)).fetchone()
                before = int(fresh["balance"])
                after = add_balance(connection, user_id, int(row["reward_sh"]))
                xp = int(fresh["xp"]) + int(row["reward_xp"])
                level = xp // 100 + 1
                connection.execute("UPDATE users SET xp = ?, level = ? WHERE id = ?", (xp, level, user_id))
                connection.execute("UPDATE daily_business_quests SET completed_at = ? WHERE id = ?", (_iso(_now()), row["id"]))
                record_transaction(
                    connection, user_id, "REWARD", int(row["reward_sh"]), before, after,
                    description=f"Daily business quest: {row['code']}", metadata={"quest": row["code"], "xp": int(row["reward_xp"])},
                )
                completed.append({"code": row["code"], "reward_sh": int(row["reward_sh"]), "reward_xp": int(row["reward_xp"]), "balance": after, "xp": xp, "level": level})
        balance = int(connection.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()["balance"])
        connection.commit()
        return {"completed": completed, "balance": balance, "idempotent": False}


def _farm_payload(row: Any, now: datetime, user_level: int) -> dict[str, Any]:
    level = int(row["level"])
    rate = _farm_rate(row)
    cap = _capacity(level, FARM_LEVELS)
    current = FARM_LEVELS[level - 1] if level else None
    next_row = FARM_LEVELS[level] if level < len(FARM_LEVELS) else None
    return {
        "level": level, "unlocked": user_level >= 3, "name": current["name"] if current else "УЧАСТОК НЕ ОСВОЕН",
        "income_per_hour": rate, "storage": _available(row, rate, cap, now), "storage_capacity": cap,
        "workers": int(row["workers"]), "worker_capacity": level * 3,
        "worker_cost": FARM_WORKER_COST, "crops": _farm_crops(level),
        "next": next_row, "maxed": level >= len(FARM_LEVELS),
    }


def _business_payload(row: Any, now: datetime, user_level: int) -> dict[str, Any]:
    level = int(row["level"])
    rate = _business_rate(row)
    cap = _capacity(level, BUSINESS_LEVELS)
    current = BUSINESS_LEVELS[level - 1] if level else None
    next_row = BUSINESS_LEVELS[level] if level < len(BUSINESS_LEVELS) else None
    return {
        "level": level, "unlocked": user_level >= 5, "name": current["name"] if current else "БИЗНЕС НЕ ОТКРЫТ",
        "income_per_hour": rate, "storage": _available(row, rate, cap, now), "storage_capacity": cap,
        "workers": int(row["workers"]), "worker_capacity": level * 4,
        "worker_cost": BUSINESS_WORKER_COST, "next": next_row, "maxed": level >= len(BUSINESS_LEVELS),
    }


def _bank_payload(connection: Any, user_id: int, user_level: int, now: datetime) -> dict[str, Any]:
    bank = connection.execute("SELECT * FROM bank_accounts WHERE user_id = ?", (user_id,)).fetchone()
    deposits = connection.execute(
        "SELECT * FROM works_deposits WHERE user_id = ? ORDER BY id DESC LIMIT 12", (user_id,)
    ).fetchall()
    output = []
    for row in deposits:
        mature = _parse(row["matures_at"]) or now
        interest = round(int(row["principal"]) * float(row["annual_rate"]) * int(row["term_days"]) / 365)
        output.append({
            "id": int(row["id"]), "principal": int(row["principal"]), "term_days": int(row["term_days"]),
            "annual_rate": float(row["annual_rate"]), "interest": interest, "payout": int(row["principal"]) + interest,
            "matures_at": row["matures_at"], "status": row["status"], "ready": row["status"] == "ACTIVE" and now >= mature,
        })
    return {
        "unlocked": user_level >= 8, "cash_balance": int(bank["cash_balance"]) if bank else 0,
        "client_money": int(bank["client_liabilities"]) if bank else 0,
        "profit": int(bank["operating_profit"]) + int(float(bank["investment_profit"])) if bank else 0,
        "terms": [{"days": days, "annual_rate": rate} for days, rate in DEPOSIT_RATES.items()], "deposits": output,
    }


def works_status(database_path: str, user_id: int) -> dict[str, Any]:
    now = _now()
    with get_connection(database_path) as connection:
        user, farm, business = _ensure_profiles(connection, user_id)
        farm_payload = _farm_payload(farm, now, int(user["level"]))
        business_payload = _business_payload(business, now, int(user["level"]))
        jobs = []
        for code, config in JOB_CONFIG.items():
            jobs.append({"code": code, **config, "unlocked": int(user["level"]) >= int(config["unlock_level"])})
        connection.commit()
        return {
            "balance": int(user["balance"]), "level": int(user["level"]), "xp": int(user["xp"]),
            "passive_per_hour": farm_payload["income_per_hour"] + business_payload["income_per_hour"],
            "farm": farm_payload, "business": business_payload,
            "bank": _bank_payload(connection, user_id, int(user["level"]), now),
            "jobs": jobs, "active_jobs": list_jobs(database_path, user_id),
            "quests": _quest_payload(connection, user),
            "progression": [{"level": level, "name": name, "description": description, "unlocked": int(user["level"]) >= level} for level, name, description in PROGRESSION],
        }


def _finalize_action(database_path: str, user_id: int, quest_code: str, event_key: str, result: dict[str, Any]) -> dict[str, Any]:
    quest = record_quest_event(database_path, user_id, quest_code, event_key)
    result["quest_completed"] = quest["completed"]
    result["balance"] = quest["balance"]
    return result


def upgrade_farm(database_path: str, user_id: int, request_id: str | None = None) -> dict[str, Any]:
    request_id = _request_id(request_id)
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        cached = _cached(connection, user_id, "works-farm-upgrade", request_id)
        if cached is not None:
            return cached
        user, farm, _ = _ensure_profiles(connection, user_id)
        if int(user["level"]) < 3:
            raise WorksError("FARM откроется на LVL 3")
        level = int(farm["level"])
        if level >= len(FARM_LEVELS):
            raise WorksConflictError("Ферма уже достигла максимального уровня")
        target = FARM_LEVELS[level]
        now = _now()
        farm = _settle(connection, "works_farms", user_id, farm, _farm_rate(farm), _capacity(level, FARM_LEVELS), now)
        before = int(connection.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()["balance"])
        after = remove_balance(connection, user_id, int(target["cost"]))
        connection.execute("UPDATE works_farms SET level = ?, accrued_at = ? WHERE user_id = ?", (level + 1, _iso(now), user_id))
        record_transaction(connection, user_id, "OTHER", int(target["cost"]), before, after, description="SHAMA WORKS farm upgrade", metadata={"level": level + 1})
        result = {"success": True, "level": level + 1, "cost": int(target["cost"]), "balance": after}
        _save(connection, user_id, "works-farm-upgrade", request_id, result)
        connection.commit()
    return result


def collect_farm(database_path: str, user_id: int, request_id: str | None = None) -> dict[str, Any]:
    request_id = _request_id(request_id)
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        cached = _cached(connection, user_id, "works-farm-collect", request_id)
        if cached is not None:
            return cached
        user, farm, _ = _ensure_profiles(connection, user_id)
        if int(user["level"]) < 3 or not int(farm["level"]):
            raise WorksError("Сначала открой и развей FARM")
        now = _now(); rate = _farm_rate(farm); cap = _capacity(int(farm["level"]), FARM_LEVELS)
        farm = _settle(connection, "works_farms", user_id, farm, rate, cap, now)
        amount = int(farm["stored_sh"])
        before = int(connection.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()["balance"])
        after = before if not amount else add_balance(connection, user_id, amount)
        connection.execute("UPDATE works_farms SET stored_sh = 0, accrued_at = ? WHERE user_id = ?", (_iso(now), user_id))
        if amount:
            record_transaction(connection, user_id, "FARM_REWARD", amount, before, after, description="SHAMA WORKS farm harvest", metadata={"rate_per_hour": rate})
        result = {"success": True, "amount": amount, "balance": after}
        _save(connection, user_id, "works-farm-collect", request_id, result)
        connection.commit()
    return _finalize_action(database_path, user_id, "farm_collect", f"farm-collect:{request_id or now.date().isoformat()}", result)


def hire_farm_workers(database_path: str, user_id: int, quantity: int, request_id: str | None = None) -> dict[str, Any]:
    quantity = _positive(quantity, "Количество работников", 30); request_id = _request_id(request_id)
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        cached = _cached(connection, user_id, "works-farm-workers", request_id)
        if cached is not None: return cached
        user, farm, _ = _ensure_profiles(connection, user_id)
        level = int(farm["level"])
        if int(user["level"]) < 3 or not level: raise WorksError("Сначала построй FARM")
        cap = level * 3
        if int(farm["workers"]) + quantity > cap: raise WorksConflictError(f"Доступно работников: {cap - int(farm['workers'])}")
        now = _now(); farm = _settle(connection, "works_farms", user_id, farm, _farm_rate(farm), _capacity(level, FARM_LEVELS), now)
        cost = quantity * FARM_WORKER_COST; before = int(connection.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()["balance"]); after = remove_balance(connection, user_id, cost)
        connection.execute("UPDATE works_farms SET workers = workers + ? WHERE user_id = ?", (quantity, user_id))
        record_transaction(connection, user_id, "OTHER", cost, before, after, description="SHAMA WORKS farm workers", metadata={"quantity": quantity})
        result = {"success": True, "workers": int(farm["workers"]) + quantity, "cost": cost, "balance": after}
        _save(connection, user_id, "works-farm-workers", request_id, result); connection.commit()
    return result


def upgrade_business(database_path: str, user_id: int, request_id: str | None = None) -> dict[str, Any]:
    request_id = _request_id(request_id)
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        cached = _cached(connection, user_id, "works-business-upgrade", request_id)
        if cached is not None: return cached
        user, _, business = _ensure_profiles(connection, user_id)
        if int(user["level"]) < 5: raise WorksError("BUSINESS откроется на LVL 5")
        level = int(business["level"])
        if level >= len(BUSINESS_LEVELS): raise WorksConflictError("Бизнес уже достиг максимального уровня")
        target = BUSINESS_LEVELS[level]; now = _now()
        business = _settle(connection, "works_businesses", user_id, business, _business_rate(business), _capacity(level, BUSINESS_LEVELS), now)
        before = int(connection.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()["balance"]); after = remove_balance(connection, user_id, int(target["cost"]))
        connection.execute("UPDATE works_businesses SET level = ?, accrued_at = ? WHERE user_id = ?", (level + 1, _iso(now), user_id))
        record_transaction(connection, user_id, "OTHER", int(target["cost"]), before, after, description="SHAMA WORKS business upgrade", metadata={"level": level + 1})
        result = {"success": True, "level": level + 1, "cost": int(target["cost"]), "balance": after}
        _save(connection, user_id, "works-business-upgrade", request_id, result); connection.commit()
    return _finalize_action(database_path, user_id, "business_upgrade", f"business-upgrade:{request_id or level + 1}", result)


def collect_business(database_path: str, user_id: int, request_id: str | None = None) -> dict[str, Any]:
    request_id = _request_id(request_id)
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        cached = _cached(connection, user_id, "works-business-collect", request_id)
        if cached is not None: return cached
        user, _, business = _ensure_profiles(connection, user_id)
        if int(user["level"]) < 5 or not int(business["level"]): raise WorksError("Сначала открой и развей BUSINESS")
        now = _now(); level = int(business["level"]); rate = _business_rate(business); business = _settle(connection, "works_businesses", user_id, business, rate, _capacity(level, BUSINESS_LEVELS), now)
        amount = int(business["stored_sh"]); before = int(connection.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()["balance"]); after = before if not amount else add_balance(connection, user_id, amount)
        connection.execute("UPDATE works_businesses SET stored_sh = 0, accrued_at = ? WHERE user_id = ?", (_iso(now), user_id))
        if amount: record_transaction(connection, user_id, "FARM_REWARD", amount, before, after, description="SHAMA WORKS business income", metadata={"rate_per_hour": rate})
        result = {"success": True, "amount": amount, "balance": after}; _save(connection, user_id, "works-business-collect", request_id, result); connection.commit()
    return result


def hire_business_workers(database_path: str, user_id: int, quantity: int, request_id: str | None = None) -> dict[str, Any]:
    quantity = _positive(quantity, "Количество работников", 40); request_id = _request_id(request_id)
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        cached = _cached(connection, user_id, "works-business-workers", request_id)
        if cached is not None: return cached
        user, _, business = _ensure_profiles(connection, user_id); level = int(business["level"])
        if int(user["level"]) < 5 or not level: raise WorksError("Сначала построй BUSINESS")
        cap = level * 4
        if int(business["workers"]) + quantity > cap: raise WorksConflictError(f"Доступно работников: {cap - int(business['workers'])}")
        now = _now(); business = _settle(connection, "works_businesses", user_id, business, _business_rate(business), _capacity(level, BUSINESS_LEVELS), now)
        cost = quantity * BUSINESS_WORKER_COST; before = int(connection.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()["balance"]); after = remove_balance(connection, user_id, cost)
        connection.execute("UPDATE works_businesses SET workers = workers + ? WHERE user_id = ?", (quantity, user_id)); record_transaction(connection, user_id, "OTHER", cost, before, after, description="SHAMA WORKS business workers", metadata={"quantity": quantity})
        result = {"success": True, "workers": int(business["workers"]) + quantity, "cost": cost, "balance": after}; _save(connection, user_id, "works-business-workers", request_id, result); connection.commit()
    return result


def create_deposit(database_path: str, user_id: int, amount: int, term_days: int, request_id: str | None = None) -> dict[str, Any]:
    amount = _positive(amount, "Сумма вклада"); request_id = _request_id(request_id)
    if term_days not in DEPOSIT_RATES: raise WorksError("Выбери срок вклада: 7, 14 или 30 дней")
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        cached = _cached(connection, user_id, "works-bank-deposit", request_id)
        if cached is not None: return cached
        user, _, _ = _ensure_profiles(connection, user_id)
        if int(user["level"]) < 8: raise WorksError("BANK откроется на LVL 8")
        now = _now(); maturity = now + timedelta(days=term_days); rate = DEPOSIT_RATES[term_days]
        before = int(user["balance"]); after = remove_balance(connection, user_id, amount)
        cursor = connection.execute("INSERT INTO works_deposits(user_id, principal, annual_rate, term_days, started_at, matures_at) VALUES (?, ?, ?, ?, ?, ?)", (user_id, amount, rate, term_days, _iso(now), _iso(maturity)))
        record_transaction(connection, user_id, "OTHER", amount, before, after, description="SHAMA WORKS term deposit", metadata={"deposit_id": int(cursor.lastrowid), "term_days": term_days})
        result = {"success": True, "deposit_id": int(cursor.lastrowid), "balance": after, "matures_at": _iso(maturity)}; _save(connection, user_id, "works-bank-deposit", request_id, result); connection.commit()
    return _finalize_action(database_path, user_id, "bank_operation", f"bank-deposit:{request_id or result['deposit_id']}", result)


def collect_deposit(database_path: str, user_id: int, deposit_id: int, request_id: str | None = None) -> dict[str, Any]:
    deposit_id = _positive(deposit_id, "Вклад"); request_id = _request_id(request_id)
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        cached = _cached(connection, user_id, "works-bank-deposit-collect", request_id)
        if cached is not None: return cached
        row = connection.execute("SELECT * FROM works_deposits WHERE id = ? AND user_id = ?", (deposit_id, user_id)).fetchone()
        if row is None: raise WorksError("Вклад не найден")
        if row["status"] == "PAID": raise WorksConflictError("Вклад уже выплачен")
        now = _now()
        if now < (_parse(row["matures_at"]) or now): raise WorksConflictError("Срок вклада ещё не завершён")
        interest = round(int(row["principal"]) * float(row["annual_rate"]) * int(row["term_days"]) / 365); payout = int(row["principal"]) + interest
        before = int(connection.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()["balance"]); after = add_balance(connection, user_id, payout)
        connection.execute("UPDATE works_deposits SET status = 'PAID', paid_at = ? WHERE id = ?", (_iso(now), deposit_id)); record_transaction(connection, user_id, "REWARD", payout, before, after, description="SHAMA WORKS deposit payout", metadata={"deposit_id": deposit_id, "interest": interest})
        result = {"success": True, "amount": payout, "interest": interest, "balance": after}; _save(connection, user_id, "works-bank-deposit-collect", request_id, result); connection.commit()
    return _finalize_action(database_path, user_id, "bank_operation", f"bank-collect:{request_id or deposit_id}", result)
