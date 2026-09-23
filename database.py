import sqlite3
from datetime import date, datetime

DB_NAME = "shama_world.db"
START_BALANCE = 1000

PACKS = {
    "starter": {
        "name": "STARTER PACK",
        "price": 500,
        "xp": 50,
        "items": [
            ("SHAMA CARD", "Обычный", "⚪", 700),
            ("SHAMA STICKER", "Обычный", "⚪", 500),
            ("SHAMA KEYCHAIN", "Редкий", "🔵", 1200),
        ],
    },
    "epic": {
        "name": "EPIC PACK",
        "price": 1500,
        "xp": 150,
        "items": [
            ("SHAMA CAP", "Редкий", "🔵", 1800),
            ("SHAMA HOODIE", "Эпический", "🟣", 3500),
            ("SHAMA GOLD CARD", "Эпический", "🟣", 5000),
        ],
    },
    "legend": {
        "name": "LEGEND PACK",
        "price": 5000,
        "xp": 500,
        "items": [
            ("SHAMA LEGEND", "Легендарный", "🟡", 12000),
            ("SHAMA GOLDEN SET", "Легендарный", "🟡", 20000),
            ("SHAMA MYTHIC CARD", "Мифический", "🔴", 50000),
        ],
    },
}

ACHIEVEMENTS = [
    ("first_pack", "Первый пак", "Открой первый игровой пак", 100),
    ("collector_5", "Коллекционер", "Собери 5 разных предметов", 250),
    ("level_5", "Пятый уровень", "Достигни 5 уровня", 500),
    ("packs_10", "Опытный игрок", "Открой 10 паков", 750),
]


def connect():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance INTEGER NOT NULL DEFAULT 1000,
            xp INTEGER NOT NULL DEFAULT 0,
            level INTEGER NOT NULL DEFAULT 1,
            packs_opened INTEGER NOT NULL DEFAULT 0,
            last_bonus TEXT,
            streak INTEGER NOT NULL DEFAULT 0,
            registered_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS inventory(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            rarity TEXT NOT NULL,
            emoji TEXT NOT NULL,
            value INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            UNIQUE(telegram_id, item_name)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions(
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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS achievements(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            achievement_key TEXT NOT NULL,
            title TEXT NOT NULL,
            reward INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY(telegram_id, achievement_key)
        )
    """)

    conn.commit()
    conn.close()


def create_user(tid, username, first_name):
    conn = connect()
    cur = conn.cursor()

    cur.execute(
        "SELECT telegram_id FROM users WHERE telegram_id=?",
        (tid,),
    )

    if not cur.fetchone():
        cur.execute(
            """
            INSERT INTO users
            (telegram_id, username, first_name, registered_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                tid,
                username,
                first_name,
                datetime.now().strftime("%Y-%m-%d"),
            ),
        )
    else:
        cur.execute(
            """
            UPDATE users
            SET username=?, first_name=?
            WHERE telegram_id=?
            """,
            (username, first_name, tid),
        )

    conn.commit()
    conn.close()


def get_user(tid):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM users WHERE telegram_id=?",
        (tid,),
    )
    row = cur.fetchone()
    conn.close()
    return row


def add_tx(cur, tid, kind, title, amount, balance, emoji):
    cur.execute(
        """
        INSERT INTO transactions
        (telegram_id, kind, title, amount, balance_after, emoji, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            tid,
            kind,
            title,
            amount,
            balance,
            emoji,
            datetime.now().strftime("%Y-%m-%d %H:%M"),
        ),
    )


def add_xp(cur, user, amount):
    old_level = user["level"]
    xp = user["xp"] + amount
    level = max(1, xp // 500 + 1)

    cur.execute(
        "UPDATE users SET xp=?, level=? WHERE telegram_id=?",
        (xp, level, user["telegram_id"]),
    )

    return level > old_level


def claim_bonus(tid):
    conn = connect()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM users WHERE telegram_id=?",
        (tid,),
    )
    user = cur.fetchone()

    if not user:
        conn.close()
        return {"ok": False, "reason": "user"}

    today = date.today().isoformat()

    if user["last_bonus"] == today:
        conn.close()
        return {"ok": False, "reason": "already"}

    reward = 1000 + min(user["streak"], 7) * 100
    streak = user["streak"] + 1
    balance = user["balance"] + reward

    cur.execute(
        """
        UPDATE users
        SET balance=?, last_bonus=?, streak=?
        WHERE telegram_id=?
        """,
        (balance, today, streak, tid),
    )

    add_tx(
        cur,
        tid,
        "bonus",
        "Ежедневная награда",
        reward,
        balance,
        "🎁",
    )
    add_xp(cur, user, 50)

    conn.commit()
    conn.close()

    return {
        "ok": True,
        "reward": reward,
        "balance": balance,
        "streak": streak,
    }


def open_pack(tid, pack_key):
    if pack_key not in PACKS:
        return {"ok": False, "reason": "pack"}

    pack = PACKS[pack_key]

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM users WHERE telegram_id=?",
        (tid,),
    )
    user = cur.fetchone()

    if not user:
        conn.close()
        return {"ok": False, "reason": "user"}

    if user["balance"] < pack["price"]:
        conn.close()
        return {
            "ok": False,
            "reason": "money",
            "need": pack["price"] - user["balance"],
        }

    item = pack["items"][user["packs_opened"] % len(pack["items"])]
    new_balance = user["balance"] - pack["price"]

    cur.execute(
        """
        UPDATE users
        SET balance=?, packs_opened=packs_opened+1
        WHERE telegram_id=?
        """,
        (new_balance, tid),
    )

    cur.execute(
        """
        INSERT INTO inventory
        (telegram_id, item_name, rarity, emoji, value, quantity)
        VALUES (?, ?, ?, ?, ?, 1)
        ON CONFLICT(telegram_id, item_name)
        DO UPDATE SET quantity=quantity+1
        """,
        (tid, item[0], item[1], item[2], item[3]),
    )

    leveled = add_xp(cur, user, pack["xp"])

    add_tx(
        cur,
        tid,
        "pack",
        f"Открытие {pack['name']}",
        -pack["price"],
        new_balance,
        "🎁",
    )

    cur.execute(
        "SELECT COUNT(*) AS cnt FROM inventory WHERE telegram_id=?",
        (tid,),
    )
    unique_items = cur.fetchone()["cnt"]

    cur.execute(
        "SELECT packs_opened FROM users WHERE telegram_id=?",
        (tid,),
    )
    opened = cur.fetchone()["packs_opened"]

    earned = []

    checks = [
        ("first_pack", "Первый пак", 100, opened >= 1),
        ("collector_5", "Коллекционер", 250, unique_items >= 5),
        ("level_5", "Пятый уровень", 500, False),
        ("packs_10", "Опытный игрок", 750, opened >= 10),
    ]

    # Check level using the updated value.
    cur.execute(
        "SELECT level FROM users WHERE telegram_id=?",
        (tid,),
    )
    current_level = cur.fetchone()["level"]
    checks[2] = (
        "level_5",
        "Пятый уровень",
        500,
        current_level >= 5,
    )

    for key, title, reward, condition in checks:
        cur.execute(
            """
            SELECT 1 FROM achievements
            WHERE telegram_id=? AND achievement_key=?
            """,
            (tid, key),
        )

        if condition and not cur.fetchone():
            cur.execute(
                """
                INSERT INTO achievements
                (telegram_id, achievement_key, title, reward, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    tid,
                    key,
                    title,
                    reward,
                    datetime.now().isoformat(),
                ),
            )

            cur.execute(
                "UPDATE users SET balance=balance+? WHERE telegram_id=?",
                (reward, tid),
            )

            new_balance += reward

            add_tx(
                cur,
                tid,
                "achievement",
                f"Достижение: {title}",
                reward,
                new_balance,
                "🏆",
            )

            earned.append({
                "title": title,
                "reward": reward,
            })

    conn.commit()
    conn.close()

    fresh = get_user(tid)

    return {
        "ok": True,
        "pack": pack["name"],
        "price": pack["price"],
        "item": {
            "name": item[0],
            "rarity": item[1],
            "emoji": item[2],
            "value": item[3],
        },
        "balance": fresh["balance"],
        "xp": fresh["xp"],
        "level": fresh["level"],
        "leveled": leveled,
        "achievements": earned,
    }


def get_inventory(tid):
    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT item_name AS name, rarity, emoji, value, quantity
        FROM inventory
        WHERE telegram_id=?
        ORDER BY value DESC
        """,
        (tid,),
    )

    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_stats(tid):
    conn = connect()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM users WHERE telegram_id=?",
        (tid,),
    )
    user = cur.fetchone()

    if not user:
        conn.close()
        return {}

    cur.execute(
        """
        SELECT
            COALESCE(SUM(quantity), 0) AS cnt,
            COALESCE(SUM(quantity * value), 0) AS value,
            COUNT(*) AS unique_count
        FROM inventory
        WHERE telegram_id=?
        """,
        (tid,),
    )
    inv = cur.fetchone()

    cur.execute(
        "SELECT COUNT(*) AS cnt FROM achievements WHERE telegram_id=?",
        (tid,),
    )
    achievements = cur.fetchone()

    conn.close()

    return {
        "balance": user["balance"],
        "xp": user["xp"],
        "level": user["level"],
        "packs": user["packs_opened"],
        "streak": user["streak"],
        "items": inv["cnt"],
        "unique": inv["unique_count"],
        "inventory_value": inv["value"],
        "achievements": achievements["cnt"],
    }


def get_history(tid, limit=15):
    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT title, amount, balance_after, emoji, created_at
        FROM transactions
        WHERE telegram_id=?
        ORDER BY id DESC
        LIMIT ?
        """,
        (tid, limit),
    )

    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_achievements(tid):
    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT achievement_key, title, reward, created_at
        FROM achievements
        WHERE telegram_id=?
        ORDER BY created_at DESC
        """,
        (tid,),
    )

    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_leaderboard(limit=20):
    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT first_name, username, balance, level, xp, packs_opened
        FROM users
        ORDER BY level DESC, xp DESC, balance DESC
        LIMIT ?
        """,
        (limit,),
    )

    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows
