import sqlite3
from datetime import datetime, date

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
    c = sqlite3.connect(DB_NAME)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = connect()
    q = c.cursor()
    q.execute("""CREATE TABLE IF NOT EXISTS users(
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
    )""")
    q.execute("""CREATE TABLE IF NOT EXISTS inventory(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER NOT NULL,
        item_name TEXT NOT NULL,
        rarity TEXT NOT NULL,
        emoji TEXT NOT NULL,
        value INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1,
        UNIQUE(telegram_id,item_name)
    )""")
    q.execute("""CREATE TABLE IF NOT EXISTS transactions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER NOT NULL,
        kind TEXT NOT NULL,
        title TEXT NOT NULL,
        amount INTEGER NOT NULL,
        balance_after INTEGER NOT NULL,
        emoji TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    q.execute("""CREATE TABLE IF NOT EXISTS achievements(
        telegram_id INTEGER NOT NULL,
        achievement_key TEXT NOT NULL,
        title TEXT NOT NULL,
        reward INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY(telegram_id,achievement_key)
    )""")
    c.commit()
    c.close()

def create_user(tid, username, first_name):
    c=connect(); q=c.cursor()
    q.execute("SELECT telegram_id FROM users WHERE telegram_id=?", (tid,))
    if not q.fetchone():
        q.execute("""INSERT INTO users
            (telegram_id,username,first_name,registered_at)
            VALUES(?,?,?,?,?)""".replace("VALUES(?,?,?,?,?)","VALUES(?,?,?,?)"),
            (tid, username, first_name, datetime.now().strftime("%Y-%m-%d")))
    else:
        q.execute("UPDATE users SET username=?,first_name=? WHERE telegram_id=?",
                  (username,first_name,tid))
    c.commit(); c.close()

def get_user(tid):
    c=connect(); q=c.cursor()
    q.execute("SELECT * FROM users WHERE telegram_id=?", (tid,))
    r=q.fetchone(); c.close()
    return r

def add_tx(q, tid, kind, title, amount, balance, emoji):
    q.execute("""INSERT INTO transactions
        (telegram_id,kind,title,amount,balance_after,emoji,created_at)
        VALUES(?,?,?,?,?,?,?)""",
        (tid,kind,title,amount,balance,emoji,datetime.now().strftime("%Y-%m-%d %H:%M")))

def add_xp(q, user, amount):
    old_level = user["level"]
    xp = user["xp"] + amount
    level = max(1, xp // 500 + 1)
    q.execute("UPDATE users SET xp=?,level=? WHERE telegram_id=?",
              (xp,level,user["telegram_id"]))
    return level > old_level

def claim_bonus(tid):
    c=connect(); q=c.cursor()
    q.execute("SELECT * FROM users WHERE telegram_id=?", (tid,))
    u=q.fetchone()
    if not u:
        c.close(); return {"ok":False,"reason":"user"}
    today=date.today().isoformat()
    if u["last_bonus"]==today:
        c.close(); return {"ok":False,"reason":"already"}
    reward=1000 + min(u["streak"],7)*100
    streak=u["streak"]+1
    balance=u["balance"]+reward
    q.execute("UPDATE users SET balance=?,last_bonus=?,streak=? WHERE telegram_id=?",
              (balance,today,streak,tid))
    add_tx(q,tid,"bonus","Ежедневная награда",reward,balance,"🎁")
    add_xp(q,u,50)
    c.commit(); c.close()
    return {"ok":True,"reward":reward,"balance":balance,"streak":streak}

def open_pack(tid, pack_key):
    if pack_key not in PACKS:
        return {"ok":False,"reason":"pack"}
    pack=PACKS[pack_key]
    c=connect(); q=c.cursor()
    q.execute("SELECT * FROM users WHERE telegram_id=?", (tid,))
    u=q.fetchone()
    if not u:
        c.close(); return {"ok":False,"reason":"user"}
    if u["balance"]<pack["price"]:
        c.close(); return {"ok":False,"reason":"money","need":pack["price"]-u["balance"]}

    # No betting/random odds: every pack has a guaranteed, deterministic
    # progression reward. The index rotates with the player's pack count.
    item = pack["items"][u["packs_opened"] % len(pack["items"])]
    new_balance=u["balance"]-pack["price"]
    q.execute("""UPDATE users SET balance=?,packs_opened=packs_opened+1
                 WHERE telegram_id=?""",(new_balance,tid))
    q.execute("""INSERT INTO inventory
        (telegram_id,item_name,rarity,emoji,value,quantity)
        VALUES(?,?,?,?,?,1)
        ON CONFLICT(telegram_id,item_name)
        DO UPDATE SET quantity=quantity+1""",
        (tid,item[0],item[1],item[2],item[3]))
    leveled=add_xp(q,u,pack["xp"])
    add_tx(q,tid,"pack",f"Открытие {pack['name']}",-pack["price"],new_balance,"🎁")
    c.commit()

    # Achievement checks
    q.execute("SELECT COUNT(*) AS cnt FROM inventory WHERE telegram_id=?", (tid,))
    unique_items=q.fetchone()["cnt"]
    q.execute("SELECT packs_opened FROM users WHERE telegram_id=?", (tid,))
    opened=q.fetchone()["packs_opened"]

    earned=[]
    checks=[
        ("first_pack","Первый пак",100,opened>=1),
        ("collector_5","Коллекционер",250,unique_items>=5),
        ("level_5","Пятый уровень",500,(get_user(tid)["level"] if get_user(tid) else 1)>=5),
        ("packs_10","Опытный игрок",750,opened>=10),
    ]
    for key,title,reward,condition in checks:
        q.execute("SELECT 1 FROM achievements WHERE telegram_id=? AND achievement_key=?",(tid,key))
        if condition and not q.fetchone():
            q.execute("""INSERT INTO achievements
                (telegram_id,achievement_key,title,reward,created_at)
                VALUES(?,?,?,?,?)""",
                (tid,key,title,reward,datetime.now().isoformat()))
            q.execute("UPDATE users SET balance=balance+? WHERE telegram_id=?",(reward,tid))
            add_tx(q,tid,"achievement",f"Достижение: {title}",reward,new_balance+reward,"🏆")
            new_balance += reward
            earned.append({"title":title,"reward":reward})
    c.commit(); c.close()

    fresh=get_user(tid)
    return {"ok":True,"pack":pack["name"],"price":pack["price"],
            "item":{"name":item[0],"rarity":item[1],"emoji":item[2],"value":item[3]},
            "balance":fresh["balance"],"xp":fresh["xp"],"level":fresh["level"],
            "leveled":leveled,"achievements":earned}

def get_inventory(tid):
    c=connect(); q=c.cursor()
    q.execute("""SELECT item_name name,rarity,emoji,value,quantity
                 FROM inventory WHERE telegram_id=? ORDER BY value DESC""",(tid,))
    rows=[dict(x) for x in q.fetchall()]; c.close(); return rows

def get_stats(tid):
    c=connect(); q=c.cursor()
    q.execute("SELECT * FROM users WHERE telegram_id=?",(tid,)); u=q.fetchone()
    q.execute("""SELECT COALESCE(SUM(quantity),0) cnt,
                        COALESCE(SUM(quantity*value),0) value,
                        COUNT(*) unique_count
                 FROM inventory WHERE telegram_id=?""",(tid,)); inv=q.fetchone()
    q.execute("SELECT COUNT(*) cnt FROM achievements WHERE telegram_id=?",(tid,)); ach=q.fetchone()
    c.close()
    return {"balance":u["balance"],"xp":u["xp"],"level":u["level"],
            "packs":u["packs_opened"],"streak":u["streak"],
            "items":inv["cnt"],"unique":inv["unique_count"],
            "inventory_value":inv["value"],"achievements":ach["cnt"]}

def get_history(tid,limit=15):
    c=connect(); q=c.cursor()
    q.execute("""SELECT title,amount,balance_after,emoji,created_at
                 FROM transactions WHERE telegram_id=?
                 ORDER BY id DESC LIMIT ?""",(tid,limit))
    rows=[dict(x) for x in q.fetchall()]; c.close(); return rows

def get_achievements(tid):
    c=connect(); q=c.cursor()
    q.execute("""SELECT achievement_key,title,reward,created_at
                 FROM achievements WHERE telegram_id=?
                 ORDER BY id""",(tid,))
    rows=[dict(x) for x in q.fetchall()]; c.close(); return rows

def get_leaderboard(limit=20):
    c=connect(); q=c.cursor()
    q.execute("""SELECT first_name,username,balance,level,xp,packs_opened
                 FROM users ORDER BY level DESC,xp DESC,balance DESC LIMIT ?""",(limit,))
    rows=[dict(x) for x in q.fetchall()]; c.close(); return rows
