import sqlite3
import random
from datetime import date, datetime

DB_NAME = "shama_world.db"
CASE_PRICE = 1000

RARITIES = [
    {"key": "common", "name": "Обычный", "emoji": "⚪", "chance": 60},
    {"key": "rare", "name": "Редкий", "emoji": "🔵", "chance": 25},
    {"key": "epic", "name": "Эпический", "emoji": "🟣", "chance": 10},
    {"key": "legendary", "name": "Легендарный", "emoji": "🟡", "chance": 4},
    {"key": "mythic", "name": "Мифический", "emoji": "🔴", "chance": 1},
]

ITEMS = {
    "common": [("SHAMA STICKER", 500), ("SHAMA KEYCHAIN", 700), ("SHAMA CARD", 900)],
    "rare": [("SHAMA CAP", 1800), ("SHAMA HOODIE", 2500), ("SHAMA SIGN", 3000)],
    "epic": [("SHAMA GOLD CARD", 7000), ("SHAMA LIMITED", 10000)],
    "legendary": [("SHAMA LEGEND", 30000), ("SHAMA GOLDEN SET", 50000)],
    "mythic": [("SHAMA WORLD MYTHIC", 150000)],
}


def connect():
    c = sqlite3.connect(DB_NAME)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = connect()
    q = c.cursor()
    q.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            balance INTEGER DEFAULT 1000,
            cases_opened INTEGER DEFAULT 0,
            last_bonus TEXT,
            registered_at TEXT NOT NULL
        )
    """)
    q.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            rarity TEXT NOT NULL,
            emoji TEXT NOT NULL,
            value INTEGER NOT NULL,
            quantity INTEGER DEFAULT 1,
            UNIQUE(telegram_id, item_name)
        )
    """)
    q.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            amount INTEGER NOT NULL,
            balance_after INTEGER NOT NULL,
            emoji TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    c.commit()
    c.close()


def create_user(tid, username, first_name):
    c = connect()
    q = c.cursor()
    q.execute("SELECT telegram_id FROM users WHERE telegram_id=?", (tid,))
    if not q.fetchone():
        q.execute(
            """INSERT INTO users
               (telegram_id, username, first_name, balance, registered_at)
               VALUES (?, ?, ?, ?, ?)""",
            (tid, username, first_name, 1000, date.today().isoformat())
        )
        c.commit()
        c.close()
        return

    q.execute(
        "UPDATE users SET username=?, first_name=? WHERE telegram_id=?",
        (username, first_name, tid)
    )
    c.commit()
    c.close()


def get_user(tid):
    c = connect()
    q = c.cursor()
    q.execute("SELECT * FROM users WHERE telegram_id=?", (tid,))
    r = q.fetchone()
    c.close()
    return r


def add_transaction(q, tid, kind, title, amount, balance_after, emoji):
    q.execute(
        """INSERT INTO transactions
           (telegram_id, kind, title, amount, balance_after, emoji, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (tid, kind, title, amount, balance_after, emoji,
         datetime.now().strftime("%Y-%m-%d %H:%M"))
    )


def claim_bonus(tid):
    c = connect()
    q = c.cursor()
    today = date.today().isoformat()
    q.execute("SELECT last_bonus, balance FROM users WHERE telegram_id=?", (tid,))
    r = q.fetchone()

    if not r or r["last_bonus"] == today:
        c.close()
        return 0

    reward = 1000
    new_balance = r["balance"] + reward

    q.execute(
        "UPDATE users SET balance=?, last_bonus=? WHERE telegram_id=?",
        (new_balance, today, tid)
    )
    add_transaction(q, tid, "bonus", "Ежедневный бонус", reward, new_balance, "🎁")
    c.commit()
    c.close()
    return reward


def choose_rarity():
    roll = random.randint(1, 100)
    total = 0
    for rarity in RARITIES:
        total += rarity["chance"]
        if roll <= total:
            return rarity
    return RARITIES[0]


def open_shama_case(tid):
    c = connect()
    q = c.cursor()
    q.execute("SELECT balance FROM users WHERE telegram_id=?", (tid,))
    u = q.fetchone()

    if not u:
        c.close()
        return {"status": "not_found"}

    if u["balance"] < CASE_PRICE:
        c.close()
        return {
            "status": "not_enough",
            "need": CASE_PRICE - u["balance"]
        }

    rarity = choose_rarity()
    name, value = random.choice(ITEMS[rarity["key"]])
    new_balance = u["balance"] - CASE_PRICE

    q.execute(
        """UPDATE users
           SET balance=?, cases_opened=cases_opened+1
           WHERE telegram_id=?""",
        (new_balance, tid)
    )

    q.execute(
        """INSERT INTO inventory
           (telegram_id, item_name, rarity, emoji, value, quantity)
           VALUES (?, ?, ?, ?, ?, 1)
           ON CONFLICT(telegram_id, item_name)
           DO UPDATE SET quantity=quantity+1""",
        (tid, name, rarity["name"], rarity["emoji"], value)
    )

    add_transaction(
        q, tid, "case", "Открытие SHAMA CASE",
        -CASE_PRICE, new_balance, "🎁"
    )

    c.commit()
    c.close()

    return {
        "status": "ok",
        "rarity": rarity,
        "item": {"name": name, "value": value},
        "balance": new_balance
    }


def get_inventory(tid):
    c = connect()
    q = c.cursor()
    q.execute(
        """SELECT item_name AS name, rarity, emoji, value, quantity
           FROM inventory
           WHERE telegram_id=?
           ORDER BY value DESC""",
        (tid,)
    )
    rows = [dict(x) for x in q.fetchall()]
    c.close()
    return rows


def get_top_players(limit=10):
    c = connect()
    q = c.cursor()
    q.execute(
        """SELECT first_name, balance
           FROM users
           ORDER BY balance DESC
           LIMIT ?""",
        (limit,)
    )
    rows = [dict(x) for x in q.fetchall()]
    c.close()
    return rows


def get_stats(tid):
    c = connect()
    q = c.cursor()

    q.execute(
        "SELECT balance, cases_opened FROM users WHERE telegram_id=?",
        (tid,)
    )
    user = q.fetchone()

    q.execute(
        "SELECT COALESCE(SUM(quantity),0) AS cnt, "
        "COALESCE(SUM(quantity*value),0) AS val "
        "FROM inventory WHERE telegram_id=?",
        (tid,)
    )
    inv = q.fetchone()

    q.execute(
        "SELECT COALESCE(SUM(amount),0) AS total "
        "FROM transactions WHERE telegram_id=? AND kind='bonus'",
        (tid,)
    )
    bonus = q.fetchone()["total"]

    q.execute(
        "SELECT COALESCE(-SUM(amount),0) AS total "
        "FROM transactions WHERE telegram_id=? AND kind='case'",
        (tid,)
    )
    spent = q.fetchone()["total"]

    c.close()

    return {
        "balance": user["balance"] if user else 0,
        "cases_opened": user["cases_opened"] if user else 0,
        "items_count": inv["cnt"],
        "inventory_value": inv["val"],
        "bonus_total": bonus,
        "case_spent": spent,
    }


def get_transaction_history(tid, limit=10):
    c = connect()
    q = c.cursor()
    q.execute(
        """SELECT title, amount, balance_after, emoji, created_at
           FROM transactions
           WHERE telegram_id=?
           ORDER BY id DESC
           LIMIT ?""",
        (tid, limit)
    )
    rows = [dict(x) for x in q.fetchall()]
    c.close()
    return rows
