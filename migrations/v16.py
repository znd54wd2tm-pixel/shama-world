"""Additive migration. No player rows or legacy financial obligations are removed."""
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

VERSION = '16_unified_world'

def backup_before_migration(path):
    path=Path(path)
    if not path.exists() or not path.stat().st_size:
        return
    with closing(sqlite3.connect(path)) as source:
        exists=source.execute("SELECT 1 FROM sqlite_master WHERE name='schema_migrations'").fetchone()
        if exists and source.execute('SELECT 1 FROM schema_migrations WHERE version=?',(VERSION,)).fetchone():
            return
        folder=path.parent/'backups'; folder.mkdir(exist_ok=True)
        target=folder/f'{path.stem}.before-v16.{datetime.now(timezone.utc):%Y%m%dT%H%M%S%f}.sqlite3'
        with closing(sqlite3.connect(target)) as backup:
            source.backup(backup)
            if backup.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                raise RuntimeError('Резервная копия повреждена')

def migrate(c):
    additions={
      'users':{'photo_url':'TEXT'},
      'enterprise_employees':{'employee_grade':"TEXT NOT NULL DEFAULT ''"},
      'items':{'asset_key':'TEXT','display_name':'TEXT','catalog_value':'INTEGER','sell_price':'INTEGER','asset_status':"TEXT NOT NULL DEFAULT 'existing'"},
      'owned_enterprises':{'custom_name':"TEXT NOT NULL DEFAULT ''",'equipment':"TEXT NOT NULL DEFAULT '{}'",'savings_enabled':'INTEGER NOT NULL DEFAULT 0','savings_remainder':"TEXT NOT NULL DEFAULT '0'",'condition_percent':'INTEGER NOT NULL DEFAULT 100','acquisition_cost':'INTEGER NOT NULL DEFAULT 0'},
      'enterprise_catalog':{'active':'INTEGER NOT NULL DEFAULT 1','equipment_required':'INTEGER NOT NULL DEFAULT 0','no_upgrades':'INTEGER NOT NULL DEFAULT 0'},
    }
    first=not c.execute('SELECT 1 FROM schema_migrations WHERE version=?',(VERSION,)).fetchone()
    for table,columns in additions.items():
        existing={r[1] for r in c.execute(f'PRAGMA table_info({table})')}
        for name,definition in columns.items():
            if name not in existing:c.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')
    if first:
        c.execute('UPDATE items SET sell_price=value,catalog_value=value')
        c.execute('UPDATE owned_enterprises SET acquisition_cost=(SELECT original_price FROM enterprise_catalog WHERE id=catalog_id)')
    if 'retired' not in {r[1] for r in c.execute('PRAGMA table_info(owned_enterprises)')}:
        c.execute('ALTER TABLE owned_enterprises ADD COLUMN retired INTEGER NOT NULL DEFAULT 0')
    c.executescript('''
    CREATE UNIQUE INDEX IF NOT EXISTS idx_item_asset_key ON items(asset_key) WHERE asset_key IS NOT NULL;
    CREATE TABLE IF NOT EXISTS catalogue_membership (
      collection TEXT NOT NULL, item_id INTEGER NOT NULL REFERENCES items(id), position INTEGER NOT NULL,
      proposed_chance REAL, PRIMARY KEY(collection,item_id));
    CREATE TABLE IF NOT EXISTS finance_accounts (
      user_id INTEGER PRIMARY KEY REFERENCES users(id), card TEXT NOT NULL DEFAULT 'standard',
      savings INTEGER NOT NULL DEFAULT 0 CHECK(savings>=0), auto_savings INTEGER NOT NULL DEFAULT 0,
      joined_at TEXT NOT NULL, bank_level INTEGER NOT NULL DEFAULT 1, vip TEXT NOT NULL DEFAULT '',
      downgrade_at TEXT, vip_suspend_at TEXT);
    CREATE TABLE IF NOT EXISTS finance_deposits (
      id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), product TEXT NOT NULL,
      principal INTEGER NOT NULL CHECK(principal>0), rate TEXT NOT NULL, started_at TEXT NOT NULL,
      due_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ACTIVE', interest_paid INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS finance_loans (
      id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), product TEXT NOT NULL,
      principal INTEGER NOT NULL CHECK(principal>0), total_due INTEGER NOT NULL CHECK(total_due>0),
      paid INTEGER NOT NULL DEFAULT 0 CHECK(paid>=0 AND paid<=total_due), started_at TEXT NOT NULL,
      due_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ACTIVE', autopay INTEGER NOT NULL DEFAULT 0,
      restructured INTEGER NOT NULL DEFAULT 0, was_overdue INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS finance_installments (
      id INTEGER PRIMARY KEY, loan_id INTEGER NOT NULL REFERENCES finance_loans(id),
      amount INTEGER NOT NULL CHECK(amount>0), due_at TEXT NOT NULL, paid INTEGER NOT NULL DEFAULT 0 CHECK(paid>=0 AND paid<=amount));
    CREATE TABLE IF NOT EXISTS finance_transfers (
      id INTEGER PRIMARY KEY, sender_id INTEGER NOT NULL REFERENCES users(id), receiver_id INTEGER NOT NULL REFERENCES users(id),
      amount INTEGER NOT NULL CHECK(amount>0), fee INTEGER NOT NULL CHECK(fee>=0), comment TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS idx_transfer_time ON finance_transfers(created_at,sender_id,receiver_id);
    CREATE TABLE IF NOT EXISTS finance_activity (user_id INTEGER REFERENCES users(id), day TEXT NOT NULL, PRIMARY KEY(user_id,day));
    CREATE TABLE IF NOT EXISTS finance_notifications (
      user_id INTEGER REFERENCES users(id), key TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL,
      PRIMARY KEY(user_id,key));
    CREATE TABLE IF NOT EXISTS finance_companies (
      code TEXT PRIMARY KEY, name TEXT NOT NULL, price INTEGER NOT NULL CHECK(price>=1), max_change TEXT NOT NULL,
      player_supply INTEGER NOT NULL DEFAULT 700000 CHECK(player_supply BETWEEN 0 AND 700000), treasury INTEGER NOT NULL DEFAULT 300000,
      started_at TEXT NOT NULL, last_tick INTEGER NOT NULL, dividend_period INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS finance_company_profit (
      id TEXT PRIMARY KEY, company TEXT NOT NULL REFERENCES finance_companies(code), amount_cents INTEGER NOT NULL, occurred_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS finance_stock_lots (
      id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), company TEXT NOT NULL REFERENCES finance_companies(code),
      quantity INTEGER NOT NULL CHECK(quantity>0), unit_cost INTEGER NOT NULL, acquired_at TEXT NOT NULL, reserved INTEGER NOT NULL DEFAULT 0 CHECK(reserved>=0 AND reserved<=quantity));
    CREATE TABLE IF NOT EXISTS finance_stock_listings (
      id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), company TEXT NOT NULL REFERENCES finance_companies(code),
      quantity INTEGER NOT NULL CHECK(quantity>0), price INTEGER NOT NULL CHECK(price>0), created_at TEXT NOT NULL,
      expires_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ACTIVE');
    CREATE TABLE IF NOT EXISTS finance_stock_reservations (
      listing_id INTEGER REFERENCES finance_stock_listings(id), lot_id INTEGER REFERENCES finance_stock_lots(id),
      quantity INTEGER NOT NULL CHECK(quantity>0), PRIMARY KEY(listing_id,lot_id));
    CREATE TABLE IF NOT EXISTS finance_dividends (
      company TEXT REFERENCES finance_companies(code), period INTEGER NOT NULL, fund_cents INTEGER NOT NULL, paid INTEGER NOT NULL,
      created_at TEXT NOT NULL, PRIMARY KEY(company,period));
    CREATE TABLE IF NOT EXISTS finance_crypto_quotes (code TEXT PRIMARY KEY, price TEXT NOT NULL, updated_at TEXT NOT NULL, source TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS finance_crypto_holdings (
      user_id INTEGER REFERENCES users(id), code TEXT NOT NULL, quantity TEXT NOT NULL, cost_basis TEXT NOT NULL,
      PRIMARY KEY(user_id,code));
    CREATE TABLE IF NOT EXISTS finance_events (
      id INTEGER PRIMARY KEY, kind INTEGER NOT NULL, starts_at TEXT NOT NULL, ends_at TEXT NOT NULL, ended INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS finance_meta (key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS finance_goals (
      id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id), kind TEXT NOT NULL, target INTEGER NOT NULL CHECK(target>0),
      baseline INTEGER NOT NULL, main INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, completed INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS finance_offers (
      id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id), code TEXT NOT NULL, reason TEXT NOT NULL,
      created_at TEXT NOT NULL, expires_at TEXT NOT NULL, dismissed_at TEXT, UNIQUE(user_id,code));
    CREATE TABLE IF NOT EXISTS finance_seasons (
      user_id INTEGER REFERENCES users(id), period INTEGER NOT NULL, stock_trades INTEGER NOT NULL DEFAULT 0,
      profit_days TEXT NOT NULL DEFAULT '[]', PRIMARY KEY(user_id,period));
    ''')
    # Keep historical sold objects, while permitting a later purchase of the type.
    definition=c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='owned_enterprises'").fetchone()[0]
    import re
    if re.search(r'UNIQUE\s*\(user_id\s*,\s*catalog_id\)',definition,re.I):
        c.commit();c.execute('PRAGMA foreign_keys=OFF')
        try:
            c.execute('BEGIN IMMEDIATE')
            rebuilt=re.sub(r'CREATE TABLE\s+(?:IF NOT EXISTS\s+)?owned_enterprises','CREATE TABLE owned_enterprises_v16',definition,count=1,flags=re.I)
            rebuilt=re.sub(r',\s*UNIQUE\s*\(user_id\s*,\s*catalog_id\)','',rebuilt,count=1,flags=re.I)
            c.execute(rebuilt)
            columns=','.join('"'+r[1]+'"' for r in c.execute('PRAGMA table_info(owned_enterprises)'))
            c.execute(f'INSERT INTO owned_enterprises_v16({columns}) SELECT {columns} FROM owned_enterprises')
            c.execute('DROP TABLE owned_enterprises')
            c.execute('ALTER TABLE owned_enterprises_v16 RENAME TO owned_enterprises')
            if c.execute('PRAGMA foreign_key_check').fetchall():raise RuntimeError('Нарушена связь предприятий при миграции')
            c.commit()
        except Exception:c.rollback();raise
        finally:c.execute('PRAGMA foreign_keys=ON')
    c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_owned_active_type ON owned_enterprises(user_id,catalog_id) WHERE retired=0')
    c.execute('INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)',(VERSION,))
