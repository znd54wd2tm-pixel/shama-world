"""Cases, enterprise ownership and player listings; no legacy rows are removed."""
from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

VERSION = "15_game_economy"


def backup_before_migration(path: Path) -> Path | None:
    if not path.exists() or not path.stat().st_size:
        return None
    with closing(sqlite3.connect(str(path))) as source:
        exists = source.execute("SELECT 1 FROM sqlite_master WHERE name='schema_migrations'").fetchone()
        if exists and source.execute("SELECT 1 FROM schema_migrations WHERE version=?", (VERSION,)).fetchone():
            return None
        directory = path.parent / "backups"
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        destination = directory / f"{path.stem}.before-v15.{stamp}.sqlite3"
        with closing(sqlite3.connect(str(destination))) as backup:
            source.backup(backup)
            if backup.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("Резервная копия базы не прошла проверку")
        return destination


def migrate(connection: sqlite3.Connection) -> None:
    connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    for table, additions in {
        "items": {"category": "TEXT NOT NULL DEFAULT 'COLLECTIBLE'"},
        "cases": {"kind": "TEXT NOT NULL DEFAULT 'ITEM'", "active": "INTEGER NOT NULL DEFAULT 1", "style": "TEXT NOT NULL DEFAULT 'carbon'"},
    }.items():
        columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        for column, definition in additions.items():
            if column not in columns:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS user_settings (
        user_id INTEGER PRIMARY KEY REFERENCES users(id),
        fast_open INTEGER NOT NULL DEFAULT 0 CHECK(fast_open IN (0,1))
    );
    CREATE TABLE IF NOT EXISTS case_batches (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        case_id INTEGER NOT NULL REFERENCES cases(id),
        quantity INTEGER NOT NULL CHECK(quantity IN (1,5,10)),
        price_paid INTEGER NOT NULL CHECK(price_paid > 0),
        request_id TEXT NOT NULL,
        response_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id,request_id)
    );
    CREATE TABLE IF NOT EXISTS enterprise_catalog (
        id INTEGER PRIMARY KEY,
        code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL UNIQUE,
        original_price INTEGER NOT NULL CHECK(original_price>0),
        revenue INTEGER NOT NULL CHECK(revenue>=0),
        expenses INTEGER NOT NULL CHECK(expenses>=0),
        capacity INTEGER NOT NULL CHECK(capacity>0),
        rarity TEXT NOT NULL,
        image TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS enterprise_drops (
        case_id INTEGER NOT NULL REFERENCES cases(id),
        enterprise_type_id INTEGER NOT NULL REFERENCES enterprise_catalog(id),
        chance REAL NOT NULL CHECK(chance>0 AND chance<=1),
        PRIMARY KEY(case_id,enterprise_type_id)
    );
    CREATE TABLE IF NOT EXISTS owned_enterprises (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        catalog_id INTEGER NOT NULL REFERENCES enterprise_catalog(id),
        status TEXT NOT NULL DEFAULT 'RUNNING' CHECK(status IN ('RUNNING','PAUSED')),
        pause_reason TEXT NOT NULL DEFAULT '',
        xp_seconds REAL NOT NULL DEFAULT 0 CHECK(xp_seconds>=0),
        work_seconds REAL NOT NULL DEFAULT 0 CHECK(work_seconds>=0),
        upgrades TEXT NOT NULL DEFAULT '{"equipment":0,"premises":0,"marketing":0,"automation":0}',
        money_remainder TEXT NOT NULL DEFAULT '0',
        last_accrued_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(user_id,catalog_id)
    );
    CREATE TABLE IF NOT EXISTS enterprise_employees (
        id INTEGER PRIMARY KEY,
        enterprise_id INTEGER NOT NULL REFERENCES owned_enterprises(id),
        role TEXT NOT NULL CHECK(role IN ('worker','manager')),
        salary INTEGER NOT NULL CHECK(salary>=0),
        bonus REAL NOT NULL CHECK(bonus>=0),
        hired_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS opening_results (
        id TEXT PRIMARY KEY,
        batch_id TEXT NOT NULL REFERENCES case_batches(id),
        slot INTEGER NOT NULL,
        user_id INTEGER NOT NULL REFERENCES users(id),
        item_id INTEGER REFERENCES items(id),
        enterprise_id INTEGER REFERENCES owned_enterprises(id),
        compensation INTEGER NOT NULL DEFAULT 0 CHECK(compensation>=0),
        status TEXT NOT NULL DEFAULT 'AVAILABLE',
        snapshot_json TEXT NOT NULL,
        UNIQUE(batch_id,slot)
    );
    CREATE INDEX IF NOT EXISTS idx_opening_result_owner ON opening_results(user_id,item_id,status);
    CREATE TABLE IF NOT EXISTS game_actions (
        user_id INTEGER NOT NULL REFERENCES users(id),
        request_id TEXT NOT NULL,
        action TEXT NOT NULL,
        fingerprint TEXT NOT NULL,
        response_json TEXT NOT NULL,
        PRIMARY KEY(user_id,request_id)
    );
    CREATE TABLE IF NOT EXISTS player_listings (
        id INTEGER PRIMARY KEY,
        seller_id INTEGER NOT NULL REFERENCES users(id),
        buyer_id INTEGER REFERENCES users(id),
        item_id INTEGER REFERENCES items(id),
        result_id TEXT REFERENCES opening_results(id),
        enterprise_id INTEGER REFERENCES owned_enterprises(id),
        price INTEGER NOT NULL CHECK(price>0),
        fee INTEGER NOT NULL DEFAULT 0 CHECK(fee>=0),
        status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','SOLD','CANCELLED')),
        created_at TEXT NOT NULL,
        closed_at TEXT,
        CHECK((item_id IS NULL) != (enterprise_id IS NULL))
    );
    CREATE UNIQUE INDEX IF NOT EXISTS idx_enterprise_listing_active ON player_listings(enterprise_id) WHERE status='ACTIVE';
    CREATE INDEX IF NOT EXISTS idx_player_listings_status ON player_listings(status,id);
    CREATE TRIGGER IF NOT EXISTS users_nonnegative_balance_insert
        BEFORE INSERT ON users WHEN NEW.balance < 0
        BEGIN SELECT RAISE(ABORT, 'Balance must be nonnegative'); END;
    CREATE TRIGGER IF NOT EXISTS users_nonnegative_balance_update
        BEFORE UPDATE OF balance ON users WHEN NEW.balance < 0
        BEGIN SELECT RAISE(ABORT, 'Balance must be nonnegative'); END;
    """)
    connection.execute("INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)", (VERSION,))
