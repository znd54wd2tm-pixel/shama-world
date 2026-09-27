import os
import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path

DB_PATH = Path(os.getenv("SHAMA_DB", "shama_world.db")) if "os" in globals() else Path("shama_world.db")

def connect():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY,
            username TEXT,
            name TEXT NOT NULL,
            balance INTEGER NOT NULL DEFAULT 1000,
            xp INTEGER NOT NULL DEFAULT 0,
            level INTEGER NOT NULL DEFAULT 1,
            last_daily TEXT,
            work_at TEXT
        );
        CREATE TABLE IF NOT EXISTS inventory(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            rarity TEXT NOT NULL,
            value INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            amount INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        """)

def ensure_user(user_id, username=None, name="Player"):
    with connect() as db:
        db.execute(
            "INSERT OR IGNORE INTO users(id,username,name) VALUES(?,?,?)",
            (user_id, username, name)
        )
        db.execute(
            "UPDATE users SET username=?, name=? WHERE id=?",
            (username, name or "Player", user_id)
        )

def get_user(user_id):
    with connect() as db:
        row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(row) if row else None

def add_balance(user_id, amount, action):
    with connect() as db:
        db.execute("UPDATE users SET balance=balance+? WHERE id=?", (amount, user_id))
        db.execute("INSERT INTO history(user_id,action,amount,created_at) VALUES(?,?,?,?)",
                   (user_id, action, amount, datetime.utcnow().isoformat()))

def add_xp(user_id, amount):
    with connect() as db:
        row = db.execute("SELECT xp, level FROM users WHERE id=?", (user_id,)).fetchone()
        xp = row["xp"] + amount
        level = max(1, xp // 500 + 1)
        db.execute("UPDATE users SET xp=?, level=? WHERE id=?", (xp, level, user_id))

def add_item(user_id, name, rarity, value):
    with connect() as db:
        db.execute(
            "INSERT INTO inventory(user_id,item_name,rarity,value,created_at) VALUES(?,?,?,?,?)",
            (user_id, name, rarity, value, datetime.utcnow().isoformat())
        )

def get_inventory(user_id):
    with connect() as db:
        return [dict(r) for r in db.execute(
            "SELECT id,item_name,rarity,value,created_at FROM inventory WHERE user_id=? ORDER BY id DESC",
            (user_id,)
        )]

def get_history(user_id):
    with connect() as db:
        return [dict(r) for r in db.execute(
            "SELECT action,amount,created_at FROM history WHERE user_id=? ORDER BY id DESC LIMIT 20",
            (user_id,)
        )]

def claim_daily(user_id):
    today = date.today().isoformat()
    with connect() as db:
        row = db.execute("SELECT last_daily FROM users WHERE id=?", (user_id,)).fetchone()
        if row["last_daily"] == today:
            return False, 0
        reward = 150
        db.execute("UPDATE users SET balance=balance+?, last_daily=? WHERE id=?", (reward, today, user_id))
        db.execute("INSERT INTO history(user_id,action,amount,created_at) VALUES(?,?,?,?)",
                   (user_id, "Ежедневная награда", reward, datetime.utcnow().isoformat()))
        return True, reward

def do_work(user_id, job_name, reward):
    now = datetime.utcnow()
    with connect() as db:
        row = db.execute("SELECT work_at FROM users WHERE id=?", (user_id,)).fetchone()
        if row["work_at"]:
            last = datetime.fromisoformat(row["work_at"])
            if now - last < timedelta(hours=4):
                left = int((timedelta(hours=4) - (now-last)).total_seconds())
                return False, left
        db.execute("UPDATE users SET balance=balance+?, work_at=? WHERE id=?",
                   (reward, now.isoformat(), user_id))
        db.execute("INSERT INTO history(user_id,action,amount,created_at) VALUES(?,?,?,?)",
                   (user_id, f"Работа: {job_name}", reward, now.isoformat()))
        return True, reward

def spend(user_id, amount, action):
    with connect() as db:
        row = db.execute("SELECT balance FROM users WHERE id=?", (user_id,)).fetchone()
        if not row or row["balance"] < amount:
            return False
        db.execute("UPDATE users SET balance=balance-? WHERE id=?", (amount, user_id))
        db.execute("INSERT INTO history(user_id,action,amount,created_at) VALUES(?,?,?,?)",
                   (user_id, action, -amount, datetime.utcnow().isoformat()))
        return True

def sell_item(user_id, item_id):
    with connect() as db:
        row = db.execute("SELECT value FROM inventory WHERE id=? AND user_id=?", (item_id,user_id)).fetchone()
        if not row:
            return None
        value = int(row["value"] * 0.7)
        db.execute("DELETE FROM inventory WHERE id=? AND user_id=?", (item_id,user_id))
        db.execute("UPDATE users SET balance=balance+? WHERE id=?", (value,user_id))
        db.execute("INSERT INTO history(user_id,action,amount,created_at) VALUES(?,?,?,?)",
                   (user_id, "Продажа предмета", value, datetime.utcnow().isoformat()))
        return value
