import random
import sqlite3
from datetime import datetime, date, timedelta

DB_NAME = "shama_world.db"
START_BALANCE = 1000
WORK_REWARD = 250
WORK_COOLDOWN_HOURS = 4
SEASON_NAME = "SHAMA ORIGIN"
SEASON_MAX_LEVEL = 30

# All rewards are virtual SH. Odds are transparent and are not tied to real-money purchases.
PACKS = {
    "starter": {
        "name": "STARTER CASE", "price": 500, "xp": 50,
        "items": [
            ("SHAMA CARD", "Обычный", "⚪", 700, 65),
            ("SHAMA STICKER", "Обычный", "⚪", 500, 25),
            ("SHAMA KEYCHAIN", "Редкий", "🔵", 1200, 9),
            ("SHAMA HOODIE", "Эпический", "🟣", 3500, 1),
        ],
    },
    "epic": {
        "name": "EPIC CASE", "price": 1500, "xp": 150,
        "items": [
            ("SHAMA KEYCHAIN", "Редкий", "🔵", 1200, 55),
            ("SHAMA CAP", "Редкий", "🔵", 1800, 25),
            ("SHAMA HOODIE", "Эпический", "🟣", 3500, 15),
            ("SHAMA GOLD CARD", "Легендарный", "🟡", 7000, 5),
        ],
    },
    "legend": {
        "name": "LEGEND CASE", "price": 5000, "xp": 500,
        "items": [
            ("SHAMA HOODIE", "Эпический", "🟣", 3500, 50),
            ("SHAMA GOLD CARD", "Легендарный", "🟡", 7000, 30),
            ("SHAMA LEGEND", "Легендарный", "🟡", 12000, 15),
            ("SHAMA MYTHIC CARD", "Мифический", "🔴", 50000, 5),
        ],
    },
}

TASKS = {
    "daily_login": {"title":"Ежедневный вход", "description":"Забери сегодняшнюю награду", "reward":150, "xp":25, "type":"login"},
    "work_once": {"title":"Будь активным", "description":"Получи награду за активность", "reward":150, "xp":25, "type":"work_today", "target":1},
    "open_one": {"title":"Первый кейс", "description":"Открой 1 кейс сегодня", "reward":200, "xp":30, "type":"packs_today", "target":1},
    "open_three": {"title":"Три открытия", "description":"Открой 3 кейса сегодня", "reward":500, "xp":70, "type":"packs_today", "target":3},
    "earn_1000": {"title":"Большой заработок", "description":"Получи 1 000 SH сегодня", "reward":350, "xp":50, "type":"earned_today", "target":1000},
    "collector": {"title":"Коллекционер", "description":"Собери 3 разных предмета", "reward":400, "xp":60, "type":"unique_items", "target":3},
}

ACHIEVEMENTS = [
    ("first_pack", "Первый кейс", "Открой первый кейс", 100),
    ("collector_5", "Коллекционер", "Собери 5 разных предметов", 250),
    ("level_5", "Пятый уровень", "Достигни 5 уровня", 500),
    ("packs_10", "Опытный игрок", "Открой 10 кейсов", 750),
    ("mythic", "Мифическая находка", "Получи мифический предмет", 1500),
    ("season_10", "Сезонный игрок", "Достигни 10 уровня сезона", 1000),
]


def connect():
    c = sqlite3.connect(DB_NAME)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = connect(); q = c.cursor()
    q.execute("""CREATE TABLE IF NOT EXISTS users(
        telegram_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        balance INTEGER NOT NULL DEFAULT 1000, xp INTEGER NOT NULL DEFAULT 0,
        level INTEGER NOT NULL DEFAULT 1, packs_opened INTEGER NOT NULL DEFAULT 0,
        last_bonus TEXT, streak INTEGER NOT NULL DEFAULT 0, registered_at TEXT NOT NULL)""")
    q.execute("""CREATE TABLE IF NOT EXISTS inventory(
        id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL,
        item_name TEXT NOT NULL, rarity TEXT NOT NULL, emoji TEXT NOT NULL,
        value INTEGER NOT NULL, quantity INTEGER NOT NULL DEFAULT 1,
        UNIQUE(telegram_id,item_name))""")
    q.execute("""CREATE TABLE IF NOT EXISTS transactions(
        id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL,
        kind TEXT NOT NULL, title TEXT NOT NULL, amount INTEGER NOT NULL,
        balance_after INTEGER NOT NULL, emoji TEXT NOT NULL, created_at TEXT NOT NULL)""")
    q.execute("""CREATE TABLE IF NOT EXISTS achievements(
        telegram_id INTEGER NOT NULL, achievement_key TEXT NOT NULL,
        title TEXT NOT NULL, reward INTEGER NOT NULL, created_at TEXT NOT NULL,
        PRIMARY KEY(telegram_id,achievement_key))""")
    q.execute("""CREATE TABLE IF NOT EXISTS task_claims(
        telegram_id INTEGER NOT NULL, task_key TEXT NOT NULL, claim_date TEXT NOT NULL,
        PRIMARY KEY(telegram_id,task_key,claim_date))""")
    q.execute("""CREATE TABLE IF NOT EXISTS activity(
        telegram_id INTEGER PRIMARY KEY, last_work TEXT)""")
    c.commit(); c.close()


def create_user(tid, username, first_name):
    c=connect(); q=c.cursor()
    row=q.execute("SELECT telegram_id FROM users WHERE telegram_id=?",(tid,)).fetchone()
    if not row:
        q.execute("INSERT INTO users(telegram_id,username,first_name,registered_at) VALUES(?,?,?,?)",(tid,username,first_name,datetime.now().strftime("%Y-%m-%d")))
    else:
        q.execute("UPDATE users SET username=?,first_name=? WHERE telegram_id=?",(username,first_name,tid))
    c.commit(); c.close()


def get_user(tid):
    c=connect(); r=c.execute("SELECT * FROM users WHERE telegram_id=?",(tid,)).fetchone(); c.close(); return r


def add_tx(q,tid,kind,title,amount,balance,emoji):
    q.execute("INSERT INTO transactions(telegram_id,kind,title,amount,balance_after,emoji,created_at) VALUES(?,?,?,?,?,?,?)",
              (tid,kind,title,amount,balance,emoji,datetime.now().strftime("%Y-%m-%d %H:%M:%S")))


def add_xp(q,user,amount):
    old=user["level"]; xp=user["xp"]+amount; level=max(1,xp//500+1)
    q.execute("UPDATE users SET xp=?,level=? WHERE telegram_id=?",(xp,level,user["telegram_id"]))
    return level>old


def claim_bonus(tid):
    c=connect(); q=c.cursor(); u=q.execute("SELECT * FROM users WHERE telegram_id=?",(tid,)).fetchone()
    if not u: c.close(); return {"ok":False,"reason":"user"}
    today=date.today().isoformat()
    if u["last_bonus"]==today: c.close(); return {"ok":False,"reason":"already"}
    prev=None
    if u["last_bonus"]:
        try: prev=date.fromisoformat(u["last_bonus"])
        except ValueError: pass
    streak=(u["streak"]+1) if prev==date.today()-timedelta(days=1) else 1
    reward=150+min(streak,7)*50
    balance=u["balance"]+reward
    q.execute("UPDATE users SET balance=?,last_bonus=?,streak=? WHERE telegram_id=?",(balance,today,streak,tid))
    add_tx(q,tid,"bonus","Ежедневная награда",reward,balance,"🎁"); add_xp(q,u,25)
    c.commit(); c.close(); return {"ok":True,"reward":reward,"balance":balance,"streak":streak}


def _day_start(): return datetime.combine(date.today(),datetime.min.time())

def _today_openings(q,tid):
    r=q.execute("SELECT COUNT(*) cnt FROM transactions WHERE telegram_id=? AND kind='pack' AND amount<0 AND created_at>=?",(tid,_day_start().strftime("%Y-%m-%d %H:%M:%S"))).fetchone(); return r["cnt"]

def _today_earned(q,tid):
    r=q.execute("SELECT COALESCE(SUM(amount),0) total FROM transactions WHERE telegram_id=? AND amount>0 AND created_at>=?",(tid,_day_start().strftime("%Y-%m-%d %H:%M:%S"))).fetchone(); return r["total"]

def _today_work(q,tid):
    r=q.execute("SELECT COUNT(*) cnt FROM transactions WHERE telegram_id=? AND kind='activity' AND created_at>=?",(tid,_day_start().strftime("%Y-%m-%d %H:%M:%S"))).fetchone(); return r["cnt"]

def _task_progress(q,tid,key):
    t=TASKS.get(key)
    if not t: return 0
    u=get_user(tid)
    if t["type"]=="login": return 1 if u and u["last_bonus"]==date.today().isoformat() else 0
    if t["type"]=="packs_today": return _today_openings(q,tid)
    if t["type"]=="earned_today": return _today_earned(q,tid)
    if t["type"]=="unique_items": return q.execute("SELECT COUNT(*) cnt FROM inventory WHERE telegram_id=?",(tid,)).fetchone()["cnt"]
    if t["type"]=="work_today": return _today_work(q,tid)
    return 0

def _task_ready(q,tid,key):
    t=TASKS.get(key)
    if not t: return False
    return _task_progress(q,tid,key) >= t.get("target",1)


def get_tasks(tid):
    c=connect(); q=c.cursor(); today=date.today().isoformat(); out=[]
    for key,t in TASKS.items():
        claimed=bool(q.execute("SELECT 1 FROM task_claims WHERE telegram_id=? AND task_key=? AND claim_date=?",(tid,key,today)).fetchone())
        progress=min(_task_progress(q,tid,key), t.get("target",1))
        out.append({"key":key,"title":t["title"],"description":t["description"],"reward":t["reward"],"xp":t["xp"],"claimed":claimed,"ready":False if claimed else _task_ready(q,tid,key),"progress":progress,"target":t.get("target",1)})
    week_start=date.today()-timedelta(days=date.today().weekday())
    q.execute("SELECT COUNT(*) cnt FROM task_claims WHERE telegram_id=? AND task_key!='weekly' AND claim_date>=?",(tid,week_start.isoformat()))
    weekly=min(q.fetchone()["cnt"],7)
    week_claimed=bool(q.execute("SELECT 1 FROM task_claims WHERE telegram_id=? AND task_key='weekly' AND claim_date=?",(tid,week_start.isoformat())).fetchone())
    out.append({"key":"weekly","title":"Недельный марафон","description":"Выполни 7 заданий за текущую неделю","reward":1000,"xp":150,"claimed":week_claimed,"ready":weekly>=7 and not week_claimed,"progress":weekly,"target":7})
    c.close(); return out


def claim_task(tid,key):
    c=connect(); q=c.cursor(); today=date.today().isoformat()
    if key=="weekly":
        week_start=date.today()-timedelta(days=date.today().weekday())
        if q.execute("SELECT 1 FROM task_claims WHERE telegram_id=? AND task_key='weekly' AND claim_date=?",(tid,week_start.isoformat())).fetchone(): c.close(); return {"ok":False,"reason":"already"}
        count=q.execute("SELECT COUNT(*) cnt FROM task_claims WHERE telegram_id=? AND task_key!='weekly' AND claim_date>=?",(tid,week_start.isoformat())).fetchone()["cnt"]
        if count<7: c.close(); return {"ok":False,"reason":"not_ready"}
        claim_date=week_start.isoformat(); reward,xp,title=1000,150,"Недельный марафон"
    elif key in TASKS:
        if q.execute("SELECT 1 FROM task_claims WHERE telegram_id=? AND task_key=? AND claim_date=?",(tid,key,today)).fetchone(): c.close(); return {"ok":False,"reason":"already"}
        if not _task_ready(q,tid,key): c.close(); return {"ok":False,"reason":"not_ready"}
        t=TASKS[key]; claim_date=today; reward,xp,title=t["reward"],t["xp"],t["title"]
    else:
        c.close(); return {"ok":False,"reason":"task"}
    u=q.execute("SELECT * FROM users WHERE telegram_id=?",(tid,)).fetchone(); balance=u["balance"]+reward
    q.execute("UPDATE users SET balance=? WHERE telegram_id=?",(balance,tid))
    q.execute("INSERT INTO task_claims(telegram_id,task_key,claim_date) VALUES(?,?,?)",(tid,key,claim_date))
    add_xp(q,u,xp); add_tx(q,tid,"task",f"Задание: {title}",reward,balance,"🎯")
    c.commit(); c.close(); return {"ok":True,"reward":reward,"xp":xp,"balance":balance,"task":title}


def do_work(tid):
    c=connect(); q=c.cursor(); u=q.execute("SELECT * FROM users WHERE telegram_id=?",(tid,)).fetchone()
    if not u: c.close(); return {"ok":False,"reason":"user"}
    row=q.execute("SELECT last_work FROM activity WHERE telegram_id=?",(tid,)).fetchone(); now=datetime.now()
    if row and row["last_work"]:
        last=datetime.fromisoformat(row["last_work"]); remaining=max(0,int(WORK_COOLDOWN_HOURS*3600-(now-last).total_seconds()))
        if remaining>0: c.close(); return {"ok":False,"reason":"cooldown","remaining":remaining}
    balance=u["balance"]+WORK_REWARD
    q.execute("INSERT INTO activity(telegram_id,last_work) VALUES(?,?) ON CONFLICT(telegram_id) DO UPDATE SET last_work=excluded.last_work",(tid,now.isoformat()))
    q.execute("UPDATE users SET balance=? WHERE telegram_id=?",(balance,tid)); add_xp(q,u,20); add_tx(q,tid,"activity","Активность",WORK_REWARD,balance,"⚡")
    c.commit(); c.close(); return {"ok":True,"reward":WORK_REWARD,"balance":balance,"cooldown":WORK_COOLDOWN_HOURS*3600}


def _weighted_item(pack):
    items=pack["items"]; return random.choices(items, weights=[x[4] for x in items], k=1)[0]


def open_pack(tid,pack_key):
    if pack_key not in PACKS: return {"ok":False,"reason":"pack"}
    pack=PACKS[pack_key]; c=connect(); q=c.cursor(); u=q.execute("SELECT * FROM users WHERE telegram_id=?",(tid,)).fetchone()
    if not u: c.close(); return {"ok":False,"reason":"user"}
    if u["balance"]<pack["price"]: c.close(); return {"ok":False,"reason":"money","need":pack["price"]-u["balance"]}
    item=_weighted_item(pack)
    new_balance=u["balance"]-pack["price"]
    q.execute("UPDATE users SET balance=?,packs_opened=packs_opened+1 WHERE telegram_id=?",(new_balance,tid))
    q.execute("INSERT INTO inventory(telegram_id,item_name,rarity,emoji,value,quantity) VALUES(?,?,?,?,?,1) ON CONFLICT(telegram_id,item_name) DO UPDATE SET quantity=quantity+1",(tid,item[0],item[1],item[2],item[3]))
    leveled=add_xp(q,u,pack["xp"]); add_tx(q,tid,"pack",f"Открытие {pack['name']}",-pack["price"],new_balance,"🎁")
    c.commit()
    fresh=q.execute("SELECT * FROM users WHERE telegram_id=?",(tid,)).fetchone()
    unique_items=q.execute("SELECT COUNT(*) cnt FROM inventory WHERE telegram_id=?",(tid,)).fetchone()["cnt"]
    checks=[
        ("first_pack","Первый кейс",100,fresh["packs_opened"]>=1),
        ("collector_5","Коллекционер",250,unique_items>=5),
        ("level_5","Пятый уровень",500,fresh["level"]>=5),
        ("packs_10","Опытный игрок",750,fresh["packs_opened"]>=10),
        ("mythic","Мифическая находка",1500,item[1]=="Мифический"),
        ("season_10","Сезонный игрок",1000,get_season(fresh["xp"])["level"]>=10),
    ]
    earned=[]
    for key,title,reward,condition in checks:
        if condition and not q.execute("SELECT 1 FROM achievements WHERE telegram_id=? AND achievement_key=?",(tid,key)).fetchone():
            q.execute("INSERT INTO achievements(telegram_id,achievement_key,title,reward,created_at) VALUES(?,?,?,?,?)",(tid,key,title,reward,datetime.now().isoformat()))
            q.execute("UPDATE users SET balance=balance+? WHERE telegram_id=?",(reward,tid)); new_balance+=reward
            add_tx(q,tid,"achievement",f"Достижение: {title}",reward,new_balance,"🏆"); earned.append({"title":title,"reward":reward})
    c.commit(); fresh=q.execute("SELECT * FROM users WHERE telegram_id=?",(tid,)).fetchone(); c.close()
    return {"ok":True,"pack":pack["name"],"price":pack["price"],"item":{"name":item[0],"rarity":item[1],"emoji":item[2],"value":item[3],"chance":item[4]},"balance":fresh["balance"],"xp":fresh["xp"],"level":fresh["level"],"leveled":leveled,"achievements":earned}


def public_packs():
    out={}
    for key,p in PACKS.items():
        out[key]={"name":p["name"],"price":p["price"],"xp":p["xp"],"items":[{"name":x[0],"rarity":x[1],"emoji":x[2],"value":x[3],"chance":x[4]} for x in p["items"]]}
    return out


def get_season(xp):
    level=min(SEASON_MAX_LEVEL, max(1, xp//250+1)); current=(xp%250); need=250
    if level>=SEASON_MAX_LEVEL: current=need
    return {"name":SEASON_NAME,"level":level,"max_level":SEASON_MAX_LEVEL,"progress":current,"need":need}


def get_inventory(tid):
    c=connect(); rows=[dict(x) for x in c.execute("SELECT item_name name,rarity,emoji,value,quantity FROM inventory WHERE telegram_id=? ORDER BY value DESC",(tid,)).fetchall()]; c.close(); return rows


def get_stats(tid):
    c=connect(); u=c.execute("SELECT * FROM users WHERE telegram_id=?",(tid,)).fetchone(); inv=c.execute("SELECT COALESCE(SUM(quantity),0) cnt,COALESCE(SUM(quantity*value),0) value,COUNT(*) unique_count FROM inventory WHERE telegram_id=?",(tid,)).fetchone(); ach=c.execute("SELECT COUNT(*) cnt FROM achievements WHERE telegram_id=?",(tid,)).fetchone(); c.close();
    season=get_season(u["xp"])
    return {"balance":u["balance"],"xp":u["xp"],"level":u["level"],"packs":u["packs_opened"],"streak":u["streak"],"items":inv["cnt"],"unique":inv["unique_count"],"inventory_value":inv["value"],"achievements":ach["cnt"],"season":season}


def get_history(tid,limit=20):
    c=connect(); rows=[dict(x) for x in c.execute("SELECT title,amount,balance_after,emoji,created_at FROM transactions WHERE telegram_id=? ORDER BY id DESC LIMIT ?",(tid,limit)).fetchall()]; c.close(); return rows


def get_achievements(tid):
    c=connect(); rows=[dict(x) for x in c.execute("SELECT achievement_key,title,reward,created_at FROM achievements WHERE telegram_id=? ORDER BY created_at",(tid,)).fetchall()]; c.close(); return rows


def get_leaderboard(limit=20):
    c=connect(); rows=[dict(x) for x in c.execute("SELECT first_name,username,balance,level,xp,packs_opened FROM users ORDER BY level DESC,xp DESC LIMIT ?",(limit,)).fetchall()]; c.close(); return rows
