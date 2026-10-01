"""SQLite connection and schema management."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL UNIQUE,
    username TEXT,
    first_name TEXT NOT NULL,
    last_name TEXT,
    balance INTEGER NOT NULL DEFAULT 100,
    xp INTEGER NOT NULL DEFAULT 0,
    level INTEGER NOT NULL DEFAULT 1,
    cases_opened INTEGER NOT NULL DEFAULT 0,
    items_collected INTEGER NOT NULL DEFAULT 0,
    upgrades_total INTEGER NOT NULL DEFAULT 0,
    upgrades_success INTEGER NOT NULL DEFAULT 0,
    upgrades_failed INTEGER NOT NULL DEFAULT 0,
    total_items_sold INTEGER NOT NULL DEFAULT 0,
    total_sh_earned_from_sales INTEGER NOT NULL DEFAULT 0,
    farm_level INTEGER NOT NULL DEFAULT 1,
    farm_last_claim_at TEXT,
    business_level INTEGER NOT NULL DEFAULT 0,
    business_last_claim_at TEXT,
    bank_level INTEGER NOT NULL DEFAULT 0,
    bank_last_claim_at TEXT,
    last_daily_claim TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    rarity TEXT NOT NULL CHECK (rarity IN ('COMMON', 'UNCOMMON', 'RARE', 'EPIC', 'LEGENDARY', 'MYTHIC')),
    value INTEGER NOT NULL CHECK (value >= 0),
    image TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    price INTEGER NOT NULL CHECK (price > 0),
    image TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS case_drops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    chance REAL NOT NULL CHECK (chance > 0 AND chance <= 1),
    UNIQUE (case_id, item_id)
);

CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, item_id)
);

CREATE TABLE IF NOT EXISTS case_openings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE RESTRICT,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE RESTRICT,
    price_paid INTEGER NOT NULL CHECK (price_paid > 0),
    request_id TEXT UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS upgrade_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE RESTRICT,
    target_item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE RESTRICT,
    source_value INTEGER NOT NULL CHECK (source_value >= 0),
    target_value INTEGER NOT NULL CHECK (target_value > source_value),
    chance REAL NOT NULL CHECK (chance >= 1 AND chance <= 95),
    result TEXT NOT NULL CHECK (result IN ('SUCCESS', 'FAIL')),
    request_id TEXT UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('SELL', 'ITEM_SELL', 'CASE_OPEN', 'UPGRADE_SUCCESS', 'UPGRADE_FAIL', 'JOB_REWARD', 'FARM_REWARD', 'MARKET_PURCHASE', 'REWARD', 'FARM', 'JOB', 'OTHER')),
    item_id INTEGER REFERENCES items(id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    amount INTEGER NOT NULL CHECK (amount >= 0),
    balance_before INTEGER NOT NULL CHECK (balance_before >= 0),
    balance_after INTEGER NOT NULL CHECK (balance_after >= 0),
    description TEXT NOT NULL DEFAULT '',
    metadata TEXT NOT NULL DEFAULT '{}',
    request_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS passive_levels (
    system TEXT NOT NULL,
    level INTEGER NOT NULL,
    income_per_minute INTEGER NOT NULL CHECK (income_per_minute >= 0),
    upgrade_cost INTEGER NOT NULL CHECK (upgrade_cost >= 0),
    unlock_level INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (system, level)
);

CREATE TABLE IF NOT EXISTS world_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL,
    position_x REAL NOT NULL,
    position_y REAL NOT NULL,
    position_z REAL NOT NULL,
    description TEXT NOT NULL,
    unlock_level INTEGER NOT NULL DEFAULT 1,
    image TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS market_rotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    ends_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS market_offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rotation_id INTEGER NOT NULL REFERENCES market_rotations(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE RESTRICT,
    price INTEGER NOT NULL CHECK (price > 0),
    stock INTEGER NOT NULL CHECK (stock >= 0),
    UNIQUE (rotation_id, item_id)
);

CREATE TABLE IF NOT EXISTS earning_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('COURIER', 'FACTORY', 'HUNT')),
    seed INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'SUCCESS', 'FAILED')) DEFAULT 'ACTIVE',
    reward INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS achievements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    requirement INTEGER NOT NULL DEFAULT 1,
    reward_xp INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_achievements (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    achievement_id INTEGER NOT NULL REFERENCES achievements(id) ON DELETE CASCADE,
    unlocked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, achievement_id)
);

CREATE TABLE IF NOT EXISTS player_enterprises (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    farm_hangar_level INTEGER NOT NULL DEFAULT 0,
    chickens INTEGER NOT NULL DEFAULT 0,
    pigs INTEGER NOT NULL DEFAULT 0,
    cows INTEGER NOT NULL DEFAULT 0,
    business_office_level INTEGER NOT NULL DEFAULT 0,
    computers INTEGER NOT NULL DEFAULT 0,
    improved_computers INTEGER NOT NULL DEFAULT 0,
    workers INTEGER NOT NULL DEFAULT 0,
    ad_started_at TEXT,
    ad_until TEXT,
    farm_accrued_at TEXT,
    business_accrued_at TEXT
);

CREATE TABLE IF NOT EXISTS bank_accounts (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    attraction_level INTEGER NOT NULL DEFAULT 0,
    clients INTEGER NOT NULL DEFAULT 0,
    cash_balance INTEGER NOT NULL DEFAULT 0 CHECK (cash_balance >= 0),
    client_liabilities INTEGER NOT NULL DEFAULT 0 CHECK (client_liabilities >= 0),
    operating_profit INTEGER NOT NULL DEFAULT 0,
    investment_profit INTEGER NOT NULL DEFAULT 0,
    accrued_at TEXT,
    last_dividend_at TEXT
);

CREATE TABLE IF NOT EXISTS bank_companies (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    price REAL NOT NULL CHECK (price > 0),
    previous_price REAL NOT NULL CHECK (previous_price > 0),
    dividend_rate REAL NOT NULL CHECK (dividend_rate >= 0),
    total_supply INTEGER NOT NULL CHECK (total_supply > 0),
    shares_sold INTEGER NOT NULL DEFAULT 0 CHECK (shares_sold >= 0),
    updated_period INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS bank_company_history (
    company_code TEXT NOT NULL REFERENCES bank_companies(code) ON DELETE CASCADE,
    period INTEGER NOT NULL,
    price REAL NOT NULL CHECK (price > 0),
    PRIMARY KEY (company_code, period)
);

CREATE TABLE IF NOT EXISTS bank_company_holdings (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    company_code TEXT NOT NULL REFERENCES bank_companies(code) ON DELETE RESTRICT,
    shares INTEGER NOT NULL CHECK (shares > 0),
    average_cost REAL NOT NULL CHECK (average_cost > 0),
    dividend_checkpoint TEXT NOT NULL,
    PRIMARY KEY (user_id, company_code)
);

CREATE TABLE IF NOT EXISTS crypto_market (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    price REAL NOT NULL CHECK (price > 0),
    change_percent REAL NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    fetched_at TEXT
);

CREATE TABLE IF NOT EXISTS crypto_market_history (
    code TEXT NOT NULL REFERENCES crypto_market(code) ON DELETE CASCADE,
    recorded_at TEXT NOT NULL,
    price REAL NOT NULL CHECK (price > 0),
    PRIMARY KEY (code, recorded_at)
);

CREATE TABLE IF NOT EXISTS bank_crypto_holdings (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code TEXT NOT NULL REFERENCES crypto_market(code) ON DELETE RESTRICT,
    quantity REAL NOT NULL CHECK (quantity > 0),
    average_cost REAL NOT NULL CHECK (average_cost > 0),
    PRIMARY KEY (user_id, code)
);

CREATE TABLE IF NOT EXISTS bank_customer_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL CHECK (event_type IN ('DEPOSIT', 'WITHDRAWAL')),
    amount INTEGER NOT NULL CHECK (amount > 0),
    message TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('COMPLETED', 'PENALTY')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bank_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    entry_type TEXT NOT NULL,
    amount REAL NOT NULL,
    description TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bank_customer_events_user ON bank_customer_events(user_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_bank_ledger_user ON bank_ledger(user_id, id DESC);

CREATE TABLE IF NOT EXISTS player_savings_accounts (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    balance REAL NOT NULL DEFAULT 0 CHECK (balance >= 0),
    accrued_at TEXT
);

CREATE TABLE IF NOT EXISTS bank_action_requests (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    request_id TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, action, request_id)
);

CREATE TABLE IF NOT EXISTS bank_portfolio_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recorded_at TEXT NOT NULL,
    total_assets REAL NOT NULL,
    portfolio_value REAL NOT NULL,
    client_liabilities REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bank_portfolio_snapshots_user_time
    ON bank_portfolio_snapshots(user_id, recorded_at DESC);
"""


def get_connection(database_path: Path | str) -> sqlite3.Connection:
    connection = sqlite3.connect(str(database_path), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def init_db(database_path: Path | str) -> None:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with get_connection(path) as connection:
        # WAL keeps reads responsive while a game transaction is being
        # committed, which matters when the bot and Mini App share SQLite.
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        connection.executescript(SCHEMA)
        _seed_investment_markets(connection)
        _migrate_users(connection)
        _migrate_transactions_constraint(connection)
        connection.commit()


def _seed_investment_markets(connection: sqlite3.Connection) -> None:
    """Create stable starting prices; later prices are persisted by the market services."""

    import time
    from datetime import datetime, timezone

    period = int(time.time() // 3600)
    for code, name, price, dividend, supply in (
        ("SH_COMPANY", "SH COMPANY", 1000, 0.14, 100_000),
        ("TORPEDO", "TORPEDO", 500, 0.05, 100_000),
        ("MAKAROV", "MAKAROV COMPANY", 300, 0.08, 200_000),
    ):
        connection.execute(
            """INSERT OR IGNORE INTO bank_companies
               (code, name, price, previous_price, dividend_rate, total_supply, updated_period)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (code, name, price, price, dividend, supply, period),
        )
        connection.execute(
            "INSERT OR IGNORE INTO bank_company_history(company_code, period, price) VALUES (?, ?, ?)",
            (code, period, price),
        )
    now = datetime.now(timezone.utc).isoformat()
    for code, name, price in (("BTC", "Bitcoin", 6_500_000), ("ETH", "Ethereum", 350_000), ("SOL", "Solana", 15_000)):
        connection.execute(
            "INSERT OR IGNORE INTO crypto_market(code, name, price, change_percent, updated_at) VALUES (?, ?, ?, 0, ?)",
            (code, name, price, now),
        )
        connection.execute(
            "INSERT OR IGNORE INTO crypto_market_history(code, recorded_at, price) VALUES (?, ?, ?)",
            (code, now, price),
        )


def _migrate_users(connection: sqlite3.Connection) -> None:
    """Add new statistics columns without changing existing user data."""

    columns = {row[1] for row in connection.execute("PRAGMA table_info(users)").fetchall()}
    if "cases_opened" not in columns:
        connection.execute("ALTER TABLE users ADD COLUMN cases_opened INTEGER NOT NULL DEFAULT 0")
    if "items_collected" not in columns:
        connection.execute("ALTER TABLE users ADD COLUMN items_collected INTEGER NOT NULL DEFAULT 0")
    if "upgrades_total" not in columns:
        connection.execute("ALTER TABLE users ADD COLUMN upgrades_total INTEGER NOT NULL DEFAULT 0")
    if "upgrades_success" not in columns:
        connection.execute("ALTER TABLE users ADD COLUMN upgrades_success INTEGER NOT NULL DEFAULT 0")
    if "upgrades_failed" not in columns:
        connection.execute("ALTER TABLE users ADD COLUMN upgrades_failed INTEGER NOT NULL DEFAULT 0")
    if "total_items_sold" not in columns:
        connection.execute("ALTER TABLE users ADD COLUMN total_items_sold INTEGER NOT NULL DEFAULT 0")
    if "total_sh_earned_from_sales" not in columns:
        connection.execute("ALTER TABLE users ADD COLUMN total_sh_earned_from_sales INTEGER NOT NULL DEFAULT 0")
    for column, definition in {
        "farm_level": "INTEGER NOT NULL DEFAULT 1",
        "farm_last_claim_at": "TEXT",
        "business_level": "INTEGER NOT NULL DEFAULT 0",
        "business_last_claim_at": "TEXT",
        "bank_level": "INTEGER NOT NULL DEFAULT 0",
        "bank_last_claim_at": "TEXT",
        "last_daily_claim": "TEXT",
    }.items():
        if column not in columns:
            connection.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")
    if "bank_control_package" not in columns:
        connection.execute("ALTER TABLE users ADD COLUMN bank_control_package INTEGER NOT NULL DEFAULT 0")
    opening_columns = {row[1] for row in connection.execute("PRAGMA table_info(case_openings)").fetchall()}
    if "request_id" not in opening_columns:
        connection.execute("ALTER TABLE case_openings ADD COLUMN request_id TEXT")
    connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_case_openings_request_id ON case_openings(request_id)")
    connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_upgrade_transactions_request_id ON upgrade_transactions(request_id)")
    transaction_columns = {row[1] for row in connection.execute("PRAGMA table_info(transactions)").fetchall()}
    if "description" not in transaction_columns:
        connection.execute("ALTER TABLE transactions ADD COLUMN description TEXT NOT NULL DEFAULT ''")
    if "metadata" not in transaction_columns:
        connection.execute("ALTER TABLE transactions ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}'")
    if "request_id" not in transaction_columns:
        connection.execute("ALTER TABLE transactions ADD COLUMN request_id TEXT")
    connection.execute("DROP INDEX IF EXISTS idx_transactions_request_id")
    connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_user_request_id ON transactions(user_id, request_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON transactions(created_at)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_inventory_user_item ON inventory(user_id, item_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_case_drops_case_item ON case_drops(case_id, item_id)")


def _migrate_transactions_constraint(connection: sqlite3.Connection) -> None:
    """Rebuild a legacy ledger table when its CHECK lacks new transaction types."""
    row = connection.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'transactions'").fetchone()
    sql = (row[0] or "") if row else ""
    if "MARKET_PURCHASE" in sql and "FARM_REWARD" in sql:
        return
    connection.execute("PRAGMA foreign_keys = OFF")
    connection.execute("ALTER TABLE transactions RENAME TO transactions_legacy")
    connection.execute(
        """CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            type TEXT NOT NULL CHECK (type IN ('SELL', 'ITEM_SELL', 'CASE_OPEN', 'UPGRADE_SUCCESS', 'UPGRADE_FAIL', 'JOB_REWARD', 'FARM_REWARD', 'MARKET_PURCHASE', 'REWARD', 'FARM', 'JOB', 'OTHER')),
            item_id INTEGER REFERENCES items(id) ON DELETE RESTRICT,
            quantity INTEGER NOT NULL CHECK (quantity > 0), amount INTEGER NOT NULL CHECK (amount >= 0),
            balance_before INTEGER NOT NULL CHECK (balance_before >= 0), balance_after INTEGER NOT NULL CHECK (balance_after >= 0),
            description TEXT NOT NULL DEFAULT '', metadata TEXT NOT NULL DEFAULT '{}', request_id TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    legacy_columns = {item[1] for item in connection.execute("PRAGMA table_info(transactions_legacy)").fetchall()}
    description_expr = "description" if "description" in legacy_columns else "''"
    metadata_expr = "metadata" if "metadata" in legacy_columns else "'{}'"
    request_expr = "request_id" if "request_id" in legacy_columns else "NULL"
    connection.execute(
        f"""INSERT INTO transactions(id, user_id, type, item_id, quantity, amount, balance_before, balance_after, description, metadata, request_id, created_at)
            SELECT id, user_id, type, item_id, quantity, amount, balance_before, balance_after,
                   {description_expr}, {metadata_expr}, {request_expr}, created_at FROM transactions_legacy"""
    )
    connection.execute("DROP TABLE transactions_legacy")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON transactions(created_at)")
    connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_user_request_id ON transactions(user_id, request_id)")
    connection.execute("PRAGMA foreign_keys = ON")


def iter_rows(cursor: sqlite3.Cursor) -> Iterator[sqlite3.Row]:
    yield from cursor.fetchall()
