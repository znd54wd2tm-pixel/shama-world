import random
import sqlite3
import json
from datetime import datetime, date, timedelta

DB_NAME = "shama_world.db"
START_BALANCE = 1000
WORK_REWARD = 300
WORK_COOLDOWN_HOURS = 1
SEASON_NAME = "SHAMA ORIGIN"
SEASON_MAX_LEVEL = 30

PACKS = {
    "starter": {
        "name": "STARTER CASE", "theme": "starter", "subtitle": "Первый шаг в SHAMA WORLD", "price": 500, "xp": 50,
        "items": [
            ("SHAMA BALL", "Обычный", "⚽", 100, 48),
            ("STREET BOOTS", "Обычный", "👟", 250, 28),
            ("PURPLE CRYSTAL", "Обычный", "💜", 150, 16),
            ("CAPTAIN ARMBAND", "Редкий", "🎽", 750, 6),
            ("TORPEDO MEDAL", "Редкий", "🏅", 1000, 1),
            ("SHAMA KEY", "Редкий", "🗝️", 1200, 1),
        ],
        "coin_drops": [(50, 2), (100, 1)],
    },
    "epic": {
        "name": "EPIC CASE", "theme": "epic", "subtitle": "Эпический уровень добычи", "price": 1500, "xp": 150,
        "items": [
            ("GOLDEN BOOTS", "Редкий", "👟", 1200, 30),
            ("SILVER MEDAL", "Редкий", "🥈", 1500, 24),
            ("VOID FRAGMENT", "Редкий", "🪐", 900, 18),
            ("PURPLE ORB", "Редкий", "🔮", 1500, 12),
            ("CHAMPION MEDAL", "Эпический", "🏅", 2500, 9),
            ("GOLDEN PHONE", "Редкий", "📱", 1000, 5),
            ("TORPEDO CUP", "Эпический", "🏆", 3500, 1),
        ],
        "coin_drops": [(100, 2), (250, 1)],
    },
    "collab": {
        "name": "COLLAB CASE", "theme": "collab", "subtitle": "Особая коллаборация", "price": 3500, "xp": 350,
        "items": [
            ("CHAMPION MEDAL", "Эпический", "🏅", 2500, 28),
            ("ENERGY CORE", "Эпический", "⚡", 3500, 24),
            ("BLACK BRIEFCASE", "Редкий", "💼", 1800, 18),
            ("GOLDEN BRIEFCASE", "Эпический", "💼", 7000, 13),
            ("SH BLACK CARD", "Легендарный", "💳", 15000, 10),
            ("SHAMA RELIC", "Легендарный", "🗿", 12000, 6),
            ("TORPEDO 2025", "Мифический", "⚽", 25000, 1),
        ],
        "coin_drops": [(250, 2), (500, 1)],
    },
    "legend": {
        "name": "LEGEND CASE", "theme": "legend", "subtitle": "Охота за легендой", "price": 8000, "xp": 500,
        "items": [
            ("STADIUM KEY", "Эпический", "🔑", 4000, 23),
            ("VOID CORE", "Эпический", "🌌", 5500, 20),
            ("GOLDEN CUP", "Легендарный", "🏆", 8000, 18),
            ("SHAMA RELIC", "Легендарный", "🗿", 12000, 15),
            ("SH BLACK CARD", "Легендарный", "💳", 15000, 10),
            ("DIAMOND BAR", "Легендарный", "💎", 18000, 7),
            ("INFINITY CORE", "Мифический", "♾️", 30000, 4),
            ("SHAMA WORLD CORE", "Секретный", "🌌", 100000, 0.2),
        ],
        "coin_drops": [(500, 2), (1000, 1), (2500, 0.5)],
    },
}


WORLD_MISSIONS = {
    "courier": {"name":"Курьерский маршрут","reward":260,"xp":45,"cooldown":600,"duration":90,"type":"route","description":"Доставь запечатанный кейс в TORPEDO STADIUM, выбрав правильный маршрут."},
    "case_factory": {"name":"Сборка кейса","reward":220,"xp":40,"cooldown":900,"duration":60,"type":"sequence","description":"Собери кейс в правильном порядке, пока конвейер не остановился."},
    "case_hunt": {"name":"Охота за печатью","reward":180,"xp":35,"cooldown":900,"duration":60,"type":"hunt","description":"Найди спрятанную SHAMA-печать среди контейнеров кейсов."},
}

TASKS = {
    "daily_login": {"title":"Ежедневный вход", "description":"Забери сегодняшнюю награду", "reward":150, "xp":25, "type":"login"},
    "work_once": {"title":"Будь активным", "description":"Получи награду за активность", "reward":150, "xp":25, "type":"work_today", "target":1},
    "open_one": {"title":"Первый кейс", "description":"Открой 1 кейс сегодня", "reward":200, "xp":30, "type":"packs_today", "target":1},
    "open_three": {"title":"Три открытия", "description":"Открой 3 кейса сегодня", "reward":500, "xp":70, "type":"packs_today", "target":3},
    "earn_1000": {"title":"Большой заработок", "description":"Получи 1 000 SH сегодня", "reward":350, "xp":50, "type":"earned_today", "target":1000},
    "collector": {"title":"Коллекционер", "description":"Собери 3 разных предмета", "reward":400, "xp":60, "type":"unique_items", "target":3},
}

# Three permanent passive-income businesses. Each level has an explicit SH/min rate and price.
FARM = {
    "club": {
        "name": "Свой футбольный клуб", "icon": "⚽", "max_level": 10,
        "income": [50, 55, 60, 65, 70, 75, 80, 90, 95, 100],
        "costs": [0, 100, 220, 400, 700, 1100, 1600, 2300, 3200, 4500],
        "description": "Начни с маленького клуба и постепенно построй TORPEDO STADIUM.",
        "milestones": ["Маленькое поле", "Раздевалка", "Тренировочная база", "Молодёжная академия", "Трибуны", "Освещение", "Расширенный стадион", "Профессиональная база", "Большой стадион", "TORPEDO STADIUM"],
    },
    "shop": {
        "name": "Магазин", "icon": "🏪", "max_level": 15,
        "income": [100, 110, 120, 135, 150, 165, 180, 195, 210, 225, 240, 260, 280, 300, 325],
        "costs": [0, 900, 1300, 1800, 2400, 3200, 4200, 5500, 7000, 8800, 11000, 13500, 16500, 20000, 24000],
        "description": "Открой первый настоящий бизнес и увеличивай ежедневный денежный поток.",
    },
    "business": {
        "name": "Бизнес", "icon": "🏢", "max_level": 20,
        "income": [200, 215, 230, 245, 260, 280, 300, 320, 340, 360, 380, 400, 420, 440, 460, 475, 485, 490, 495, 500],
        "costs": [0, 5000, 6500, 8000, 10000, 12500, 15000, 18000, 21500, 25500, 30000, 35000, 40500, 46500, 53000, 60000, 67500, 75500, 84000, 93000],
        "description": "Масштабируй бизнес до стабильных 100 SH в минуту.",
    },
    "bank": {
        "name": "Банк", "icon": "🏦", "max_level": 30,
        "income": [0] * 30,
        "costs": [0, 7000, 9000, 11000, 13500, 16500, 20000, 24000, 28500, 33500, 39000, 45000, 51500, 58500, 66000, 74000, 82500, 91500, 101000, 111000, 121500, 132500, 144000, 156000, 168500, 181500, 195000, 209000, 223500, 238500],
        "description": "Банк усиливает экономику: увеличивает хранилище и снижает комиссию рынка.",
        "storage": [5000,7000,9000,11000,14000,17000,20000,24000,28000,33000,38000,44000,50000,57000,64000,72000,80000,89000,98000,100000,110000,120000,130000,140000,150000,160000,170000,180000,190000,200000],
        "fee": [5,5,5,4.9,4.8,4.7,4.6,4.5,4.4,4.3,4.2,4.1,4,3.9,3.8,3.7,3.6,3.5,3.4,3.3,3.2,3.1,3,2.9,2.8,2.6,2.4,2.2,2,2],
    },
}

FARM_ORDER = ["club", "shop", "business", "bank"]

UPGRADE_BASES = []
for p in PACKS.values():
    for item in p["items"]:
        UPGRADE_BASES.append(item)
# Deduplicate by name, keep the highest value/version.
_upgrade_map = {}
for item in UPGRADE_BASES:
    if item[0] not in _upgrade_map or item[3] > _upgrade_map[item[0]][3]:
        _upgrade_map[item[0]] = item
UPGRADE_BASES = sorted(_upgrade_map.values(), key=lambda x: x[3])


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
    q.execute("""CREATE TABLE IF NOT EXISTS farm_levels(
        telegram_id INTEGER NOT NULL, farm_key TEXT NOT NULL, level INTEGER NOT NULL DEFAULT 1,
        last_collect TEXT NOT NULL, PRIMARY KEY(telegram_id,farm_key))""")
    q.execute("""CREATE TABLE IF NOT EXISTS upgrade_history(
        id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL,
        source_name TEXT NOT NULL, source_value INTEGER NOT NULL,
        target_name TEXT NOT NULL, target_value INTEGER NOT NULL,
        chance REAL NOT NULL, success INTEGER NOT NULL, created_at TEXT NOT NULL)""")
    q.execute("""CREATE TABLE IF NOT EXISTS market_listings(
        id INTEGER PRIMARY KEY AUTOINCREMENT, seller_id INTEGER NOT NULL,
        item_name TEXT NOT NULL, rarity TEXT NOT NULL, emoji TEXT NOT NULL,
        value INTEGER NOT NULL, price INTEGER NOT NULL, quantity INTEGER NOT NULL DEFAULT 1,
        status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL)""")
    q.execute("""CREATE TABLE IF NOT EXISTS market_sales(
        id INTEGER PRIMARY KEY AUTOINCREMENT, listing_id INTEGER NOT NULL, seller_id INTEGER NOT NULL,
        buyer_id INTEGER NOT NULL, item_name TEXT NOT NULL, price INTEGER NOT NULL,
        fee INTEGER NOT NULL, created_at TEXT NOT NULL)""")
    q.execute("""CREATE TABLE IF NOT EXISTS pending_drops(
        id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL,
        kind TEXT NOT NULL, item_name TEXT, rarity TEXT, emoji TEXT, value INTEGER,
        chance REAL, pack_name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL)""")
    q.execute("""CREATE TABLE IF NOT EXISTS world_missions(
        telegram_id INTEGER NOT NULL, mission_key TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ready',
        challenge TEXT, started_at TEXT, completed_at TEXT, PRIMARY KEY(telegram_id, mission_key))""")
    c.commit(); c.close()


def create_user(tid, username, first_name):
    c=connect(); q=c.cursor()
    row=q.execute("SELECT telegram_id FROM users WHERE telegram_id=?",(tid,)).fetchone()
    if not row:
        q.execute("INSERT INTO users(telegram_id,username,first_name,registered_at) VALUES(?,?,?,?)",(tid,username,first_name,datetime.now().strftime("%Y-%m-%d")))
    else:
        q.execute("UPDATE users SET username=?,first_name=? WHERE telegram_id=?",(username,first_name,tid))
    now=datetime.now().isoformat()
    for key in FARM:
        q.execute("INSERT OR IGNORE INTO farm_levels(telegram_id,farm_key,level,last_collect) VALUES(?,?,1,?)",(tid,key,now))
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
    return bool(t and _task_progress(q,tid,key) >= t.get("target",1))


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


def do_work(tid, job_key=None):
    jobs = {
        "delivery": {"title":"Курьерская доставка", "emoji":"📦", "reward":(180,320)},
        "scout": {"title":"Скаут для TORPEDO", "emoji":"⚽", "reward":(220,380)},
        "freelance": {"title":"Фриланс-заказ", "emoji":"💻", "reward":(250,450)},
    }
    job = jobs.get(job_key) or jobs["delivery"]
    c=connect(); q=c.cursor(); u=q.execute("SELECT * FROM users WHERE telegram_id=?",(tid,)).fetchone()
    if not u: c.close(); return {"ok":False,"reason":"user"}
    now=datetime.now()
    row=q.execute("SELECT last_work FROM activity WHERE telegram_id=?",(tid,)).fetchone()
    if row and row["last_work"]:
        try:
            last=datetime.fromisoformat(row["last_work"]); remaining=max(0,int(WORK_COOLDOWN_HOURS*3600-(now-last).total_seconds()))
        except ValueError: remaining=0
        if remaining>0:
            c.close(); return {"ok":False,"reason":"cooldown","remaining":remaining}
    reward=random.randint(*job["reward"])
    balance=u["balance"]+reward
    q.execute("INSERT INTO activity(telegram_id,last_work) VALUES(?,?) ON CONFLICT(telegram_id) DO UPDATE SET last_work=excluded.last_work",(tid,now.isoformat()))
    q.execute("UPDATE users SET balance=? WHERE telegram_id=?",(balance,tid)); add_xp(q,u,20); add_tx(q,tid,"activity",job["title"],reward,balance,job["emoji"])
    c.commit(); c.close(); return {"ok":True,"reward":reward,"balance":balance,"cooldown":WORK_COOLDOWN_HOURS*3600,"job":job["title"],"emoji":job["emoji"]}


def _weighted_drop(pack):
    pool=[]
    for item in pack["items"]:
        pool.append(("item", item, float(item[4])))
    for amount, weight in pack.get("coin_drops", []):
        pool.append(("coin", (amount,), float(weight)))
    total=sum(x[2] for x in pool)
    if total<=0: raise ValueError("empty drop table")
    roll=random.uniform(0,total); cursor=0.0
    for kind,payload,weight in pool:
        cursor += weight
        if roll <= cursor:
            return kind,payload,round(weight/total*100,3)
    kind,payload,weight=pool[-1]
    return kind,payload,round(weight/total*100,3)

def open_pack(tid,pack_key):
    if pack_key not in PACKS: return {"ok":False,"reason":"pack"}
    pack=PACKS[pack_key]; c=connect(); q=c.cursor(); u=q.execute("SELECT * FROM users WHERE telegram_id=?",(tid,)).fetchone()
    if not u: c.close(); return {"ok":False,"reason":"user"}
    if u["balance"]<pack["price"]: c.close(); return {"ok":False,"reason":"money","need":pack["price"]-u["balance"]}
    drop_kind, drop, drop_chance = _weighted_drop(pack)
    new_balance=u["balance"]-pack["price"]
    q.execute("UPDATE users SET balance=?,packs_opened=packs_opened+1 WHERE telegram_id=?",(new_balance,tid))
    if drop_kind == "item":
        item=drop
        # The item is intentionally held as a pending drop until the player
        # explicitly chooses SAVE TO INVENTORY or ADD TO UPGRADE.
        q.execute("INSERT INTO pending_drops(telegram_id,kind,item_name,rarity,emoji,value,chance,pack_name,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (tid,"item",item[0],item[1],item[2],item[3],drop_chance,pack["name"],"pending",datetime.now().isoformat()))
    else:
        item=None
        new_balance += drop[0]
        q.execute("UPDATE users SET balance=? WHERE telegram_id=?",(new_balance,tid))
        add_tx(q,tid,"case_coin",f"Монеты из {pack['name']}",drop[0],new_balance,"💠")
    leveled=add_xp(q,u,pack["xp"]); add_tx(q,tid,"pack",f"Открытие {pack['name']}",-pack["price"],new_balance,"🎁")
    c.commit()
    fresh=q.execute("SELECT * FROM users WHERE telegram_id=?",(tid,)).fetchone()
    unique_items=q.execute("SELECT COUNT(*) cnt FROM inventory WHERE telegram_id=?",(tid,)).fetchone()["cnt"]
    checks=[
        ("first_pack","Первый кейс",100,fresh["packs_opened"]>=1),
        ("collector_5","Коллекционер",250,unique_items>=5),
        ("level_5","Пятый уровень",500,fresh["level"]>=5),
        ("packs_10","Опытный игрок",750,fresh["packs_opened"]>=10),
        ("mythic","Мифическая находка",1500,drop_kind=="item" and item[1]=="Мифический"),
        ("season_10","Сезонный игрок",1000,get_season(fresh["xp"])["level"]>=10),
    ]
    earned=[]
    for key,title,reward,condition in checks:
        if condition and not q.execute("SELECT 1 FROM achievements WHERE telegram_id=? AND achievement_key=?",(tid,key)).fetchone():
            q.execute("INSERT INTO achievements(telegram_id,achievement_key,title,reward,created_at) VALUES(?,?,?,?,?)",(tid,key,title,reward,datetime.now().isoformat()))
            q.execute("UPDATE users SET balance=balance+? WHERE telegram_id=?",(reward,tid)); new_balance+=reward
            add_tx(q,tid,"achievement",f"Достижение: {title}",reward,new_balance,"🏆"); earned.append({"title":title,"reward":reward})
    c.commit(); fresh=q.execute("SELECT * FROM users WHERE telegram_id=?",(tid,)).fetchone()
    pending_row=q.execute("SELECT id FROM pending_drops WHERE telegram_id=? AND status='pending' ORDER BY id DESC LIMIT 1",(tid,)).fetchone() if drop_kind=="item" else None
    pending_id=pending_row["id"] if pending_row else None
    c.close()
    drop_payload = ({"kind":"item","name":item[0],"rarity":item[1],"emoji":item[2],"value":item[3],"chance":drop_chance,"drop_id":pending_id} if drop_kind=="item" else {"kind":"coin","name":f"{drop[0]} SH","rarity":"Монеты","emoji":"💠","value":drop[0],"chance":drop_chance})
    return {"ok":True,"pack":pack["name"],"price":pack["price"],"drop":drop_payload,"balance":fresh["balance"],"xp":fresh["xp"],"level":fresh["level"],"leveled":leveled,"achievements":earned,"drop_id":pending_id}


def public_packs():
    out={}
    for key,p in PACKS.items():
        total=sum(x[4] for x in p["items"])+sum(x[1] for x in p.get("coin_drops",[]))
        out[key]={"name":p["name"],"theme":p.get("theme","starter"),"subtitle":p.get("subtitle",""),"price":p["price"],"xp":p["xp"],
                  "items":[{"name":x[0],"rarity":x[1],"emoji":x[2],"value":x[3],"chance":round(x[4]/total*100,3) if total else 0} for x in p["items"]],
                  "coin_drops":[{"amount":x[0],"chance":round(x[1]/total*100,3) if total else 0} for x in p.get("coin_drops",[])]}
    return out


def get_pending_drops(tid):
    c=connect()
    rows=[dict(r) for r in c.execute(
        "SELECT id,kind,item_name name,rarity,emoji,value,chance,pack_name,created_at FROM pending_drops WHERE telegram_id=? AND status=\'pending\' ORDER BY id ASC",
        (tid,)
    ).fetchall()]
    c.close()
    return rows


def claim_pending_drop(tid, drop_id, action="save"):
    if action not in ("save", "upgrade"):
        return {"ok":False,"reason":"action"}
    c=connect(); q=c.cursor()
    row=q.execute("SELECT * FROM pending_drops WHERE id=? AND telegram_id=? AND status='pending'",(drop_id,tid)).fetchone()
    if not row:
        c.close(); return {"ok":False,"reason":"drop"}
    if row["kind"] != "item":
        q.execute("UPDATE pending_drops SET status='saved' WHERE id=?",(drop_id,))
        c.commit(); c.close(); return {"ok":True,"action":"saved"}
    q.execute("INSERT INTO inventory(telegram_id,item_name,rarity,emoji,value,quantity) VALUES(?,?,?,?,?,1) ON CONFLICT(telegram_id,item_name) DO UPDATE SET quantity=quantity+1",
              (tid,row["item_name"],row["rarity"],row["emoji"],row["value"]))
    q.execute("UPDATE pending_drops SET status=? WHERE id=?",("moved_to_upgrade" if action=="upgrade" else "saved",drop_id))
    c.commit(); c.close()
    return {"ok":True,"action":"upgrade" if action=="upgrade" else "saved",
            "name":row["item_name"],"rarity":row["rarity"],"emoji":row["emoji"],"value":row["value"]}


def get_season(xp):
    level=min(SEASON_MAX_LEVEL, max(1, xp//250+1)); current=xp%250; need=250
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


def _farm_row(q, tid, key):
    row=q.execute("SELECT * FROM farm_levels WHERE telegram_id=? AND farm_key=?",(tid,key)).fetchone()
    if not row:
        now=datetime.now().isoformat(); q.execute("INSERT INTO farm_levels(telegram_id,farm_key,level,last_collect) VALUES(?,?,1,?)",(tid,key,now)); return q.execute("SELECT * FROM farm_levels WHERE telegram_id=? AND farm_key=?",(tid,key)).fetchone()
    return row


def _farm_pending(row, now=None):
    now=now or datetime.now(); last=datetime.fromisoformat(row["last_collect"]); seconds=max(0,(now-last).total_seconds()); return min(240,int(seconds//60))


def _farm_unlock(q, tid, idx):
    if idx == 0: return True
    prev = FARM_ORDER[idx-1]
    row = q.execute("SELECT level FROM farm_levels WHERE telegram_id=? AND farm_key=?", (tid, prev)).fetchone()
    return bool(row and row["level"] >= FARM[prev]["max_level"])


def get_farm(tid):
    c=connect(); q=c.cursor(); now=datetime.now(); out=[]; total=0
    for idx,key in enumerate(FARM_ORDER):
        cfg=FARM[key]; row=_farm_row(q,tid,key); unlocked=_farm_unlock(q,tid,idx)
        pending=_farm_pending(row,now) * cfg["income"][row["level"]-1] if unlocked else 0
        total += pending
        level=row["level"]; maxed=level>=cfg["max_level"]
        extra={"storage":cfg.get("storage",[None]*cfg["max_level"])[level-1] if "storage" in cfg else None,"fee":cfg.get("fee",[None]*cfg["max_level"])[level-1] if "fee" in cfg else None}
        out.append({"key":key,"name":cfg["name"],"icon":cfg["icon"],"description":cfg["description"],"level":level,"max_level":cfg["max_level"],"income":cfg["income"][level-1],"next_income":None if maxed else cfg["income"][level],"next_cost":None if maxed else cfg["costs"][level],"pending":pending,"unlocked":unlocked,"milestone":cfg.get("milestones",[])[level-1] if cfg.get("milestones") else None,**extra})
    bank_level=q.execute("SELECT level FROM farm_levels WHERE telegram_id=? AND farm_key='bank'",(tid,)).fetchone()["level"]
    bank=FARM["bank"]
    storage=bank.get("storage",[5000]*30)[bank_level-1]; fee=bank.get("fee",[5]*30)[bank_level-1]
    c.close(); return {"farms":out,"total_pending":total,"bank_storage":storage,"market_fee":fee}


def collect_farm(tid):
    c=connect(); q=c.cursor(); now=datetime.now(); total=0
    for idx,key in enumerate(FARM_ORDER):
        cfg=FARM[key]; row=_farm_row(q,tid,key)
        if not _farm_unlock(q,tid,idx): continue
        mins=_farm_pending(row,now); amount=mins*cfg["income"][row["level"]-1]
        if mins>0:
            q.execute("UPDATE farm_levels SET last_collect=? WHERE telegram_id=? AND farm_key=?",(now.isoformat(),tid,key)); total+=amount
    if total<=0: c.close(); return {"ok":False,"reason":"empty"}
    u=q.execute("SELECT * FROM users WHERE telegram_id=?",(tid,)).fetchone(); balance=u["balance"]+total
    q.execute("UPDATE users SET balance=? WHERE telegram_id=?",(balance,tid)); add_tx(q,tid,"farm","Доход с фермы",total,balance,"FARM")
    c.commit(); c.close(); return {"ok":True,"reward":total,"balance":balance}


def upgrade_farm(tid,key):
    if key not in FARM: return {"ok":False,"reason":"farm"}
    c=connect(); q=c.cursor(); cfg=FARM[key]; row=_farm_row(q,tid,key); level=row["level"]; idx=FARM_ORDER.index(key)
    if not _farm_unlock(q,tid,idx): c.close(); return {"ok":False,"reason":"locked"}
    if level>=cfg["max_level"]: c.close(); return {"ok":False,"reason":"max"}
    cost=cfg["costs"][level]; u=q.execute("SELECT * FROM users WHERE telegram_id=?",(tid,)).fetchone()
    if u["balance"]<cost: c.close(); return {"ok":False,"reason":"money","need":cost-u["balance"]}
    balance=u["balance"]-cost; new_level=level+1
    q.execute("UPDATE users SET balance=? WHERE telegram_id=?",(balance,tid)); q.execute("UPDATE farm_levels SET level=? WHERE telegram_id=? AND farm_key=?",(new_level,tid,key))
    add_tx(q,tid,"farm_upgrade",f"Улучшение: {cfg['name']} · уровень {new_level}",-cost,balance,"⬆️")
    c.commit(); c.close(); return {"ok":True,"balance":balance,"level":new_level,"income":cfg["income"][new_level-1],"milestone":cfg.get("milestones",[])[new_level-1] if cfg.get("milestones") else None}


# ----- OPEN WORLD MISSIONS -----
def _mission_row(q, tid, key):
    row=q.execute("SELECT * FROM world_missions WHERE telegram_id=? AND mission_key=?",(tid,key)).fetchone()
    if not row:
        q.execute("INSERT INTO world_missions(telegram_id,mission_key,status) VALUES(?,?,?)",(tid,key,"ready"))
        return q.execute("SELECT * FROM world_missions WHERE telegram_id=? AND mission_key=?",(tid,key)).fetchone()
    return row

def get_world_missions(tid):
    c=connect(); q=c.cursor(); now=datetime.now(); out=[]
    for key,cfg in WORLD_MISSIONS.items():
        row=_mission_row(q,tid,key); status=row["status"]; remaining=0
        if status=="active" and row["started_at"]:
            elapsed=(now-datetime.fromisoformat(row["started_at"])).total_seconds(); remaining=max(0,int(cfg["duration"]-elapsed))
            if remaining<=0:
                q.execute("UPDATE world_missions SET status='ready',challenge=NULL,started_at=NULL WHERE telegram_id=? AND mission_key=?",(tid,key)); status="ready"
        if row["completed_at"]:
            elapsed=(now-datetime.fromisoformat(row["completed_at"])).total_seconds(); remaining_cd=max(0,int(cfg["cooldown"]-elapsed))
        else: remaining_cd=0
        out.append({"key":key,**cfg,"status":status,"remaining":remaining,"cooldown_remaining":remaining_cd})
    c.commit(); c.close(); return {"missions":out}

def start_world_mission(tid,key):
    if key not in WORLD_MISSIONS: return {"ok":False,"reason":"mission"}
    cfg=WORLD_MISSIONS[key]; c=connect(); q=c.cursor(); row=_mission_row(q,tid,key); now=datetime.now()
    if row["status"]=="active": c.close(); return {"ok":False,"reason":"active"}
    if row["completed_at"]:
        rem=cfg["cooldown"]-(now-datetime.fromisoformat(row["completed_at"])).total_seconds()
        if rem>0: c.close(); return {"ok":False,"reason":"cooldown","remaining":int(rem)}
    if cfg["type"]=="route": challenge={"answer":random.randrange(3)}
    elif cfg["type"]=="sequence": challenge={"sequence":random.sample([0,1,2,3],4)}
    else: challenge={"answer":random.randrange(9)}
    q.execute("UPDATE world_missions SET status='active',challenge=?,started_at=? WHERE telegram_id=? AND mission_key=?",(json.dumps(challenge),now.isoformat(),tid,key))
    c.commit(); c.close(); return {"ok":True,"mission":key,"type":cfg["type"],"duration":cfg["duration"],"reward":cfg["reward"],"xp":cfg["xp"],"challenge":challenge}

def complete_world_mission(tid,key,proof=None):
    if key not in WORLD_MISSIONS: return {"ok":False,"reason":"mission"}
    cfg=WORLD_MISSIONS[key]; c=connect(); q=c.cursor(); row=_mission_row(q,tid,key); now=datetime.now()
    if row["status"]!="active" or not row["started_at"]: c.close(); return {"ok":False,"reason":"inactive"}
    elapsed=(now-datetime.fromisoformat(row["started_at"])).total_seconds()
    if elapsed>cfg["duration"]: q.execute("UPDATE world_missions SET status='ready',challenge=NULL,started_at=NULL WHERE telegram_id=? AND mission_key=?",(tid,key)); c.commit(); c.close(); return {"ok":False,"reason":"expired"}
    try: challenge=json.loads(row["challenge"] or "{}")
    except: challenge={}
    if cfg["type"]=="sequence": ok=list(map(int,proof or []))==challenge.get("sequence")
    else: ok=int(proof)==int(challenge.get("answer",-999))
    if not ok: c.close(); return {"ok":False,"reason":"wrong"}
    u=q.execute("SELECT * FROM users WHERE telegram_id=?",(tid,)).fetchone(); balance=u["balance"]+cfg["reward"]
    q.execute("UPDATE users SET balance=? WHERE telegram_id=?",(balance,tid)); add_xp(q,u,cfg["xp"]); add_tx(q,tid,"world_mission",f"Миссия: {cfg['name']}",cfg["reward"],balance,"WORLD")
    q.execute("UPDATE world_missions SET status='ready',challenge=NULL,started_at=NULL,completed_at=? WHERE telegram_id=? AND mission_key=?",(now.isoformat(),tid,key))
    c.commit(); c.close(); return {"ok":True,"reward":cfg["reward"],"xp":cfg["xp"],"balance":balance}


# ----- PLAYER MARKET -----
def _bank_fee(q,tid):
    row=q.execute("SELECT level FROM farm_levels WHERE telegram_id=? AND farm_key='bank'",(tid,)).fetchone(); level=row["level"] if row else 1
    return FARM["bank"].get("fee",[5]*30)[level-1]


def get_market(tid):
    c=connect(); q=c.cursor()
    rows=q.execute("SELECT m.*,u.first_name FROM market_listings m LEFT JOIN users u ON u.telegram_id=m.seller_id WHERE m.status='active' AND m.seller_id!=? ORDER BY m.created_at DESC LIMIT 60",(tid,)).fetchall()
    own=q.execute("SELECT m.*,u.first_name FROM market_listings m LEFT JOIN users u ON u.telegram_id=m.seller_id WHERE m.status='active' AND m.seller_id=? ORDER BY m.created_at DESC",(tid,)).fetchall()
    fee=_bank_fee(q,tid); c.close()
    return {"items":[dict(x) for x in rows],"own":[dict(x) for x in own],"fee":fee}


def market_sell(tid,item_name,price,quantity=1):
    try: price=int(price); quantity=int(quantity)
    except: return {"ok":False,"reason":"price"}
    if price<=0 or quantity<=0: return {"ok":False,"reason":"price"}
    c=connect(); q=c.cursor(); inv=q.execute("SELECT * FROM inventory WHERE telegram_id=? AND item_name=?",(tid,item_name)).fetchone()
    if not inv or inv["quantity"]<quantity: c.close(); return {"ok":False,"reason":"item"}
    active=q.execute("SELECT COALESCE(SUM(quantity),0) qty FROM market_listings WHERE seller_id=? AND item_name=? AND status='active'",(tid,item_name)).fetchone()["qty"]
    if active+quantity>inv["quantity"]: c.close(); return {"ok":False,"reason":"listed"}
    q.execute("INSERT INTO market_listings(seller_id,item_name,rarity,emoji,value,price,quantity,status,created_at) VALUES(?,?,?,?,?,?,?,?,?)",(tid,item_name,inv["rarity"],inv["emoji"],inv["value"],price,quantity,"active",datetime.now().isoformat()))
    c.commit(); c.close(); return {"ok":True,"quantity":quantity,"total_price":price}


def market_cancel(tid,listing_id):
    c=connect(); q=c.cursor(); r=q.execute("SELECT * FROM market_listings WHERE id=? AND seller_id=? AND status='active'",(listing_id,tid)).fetchone()
    if not r: c.close(); return {"ok":False,"reason":"listing"}
    q.execute("UPDATE market_listings SET status='cancelled' WHERE id=?",(listing_id,)); c.commit(); c.close(); return {"ok":True}


def market_buy(tid,listing_id):
    c=connect(); q=c.cursor(); r=q.execute("SELECT * FROM market_listings WHERE id=? AND status='active'",(listing_id,)).fetchone()
    if not r: c.close(); return {"ok":False,"reason":"listing"}
    if r["seller_id"]==tid: c.close(); return {"ok":False,"reason":"self"}
    u=q.execute("SELECT * FROM users WHERE telegram_id=?",(tid,)).fetchone()
    if not u or u["balance"]<r["price"]: c.close(); return {"ok":False,"reason":"money","need":r["price"]-(u["balance"] if u else 0)}
    fee_pct=_bank_fee(q,r["seller_id"]); fee=round(r["price"]*fee_pct/100); seller_get=r["price"]-fee
    q.execute("UPDATE users SET balance=balance-? WHERE telegram_id=?",(r["price"],tid))
    seller=q.execute("SELECT * FROM users WHERE telegram_id=?",(r["seller_id"],)).fetchone(); q.execute("UPDATE users SET balance=balance+? WHERE telegram_id=?",(seller_get,r["seller_id"]))
    q.execute("UPDATE market_listings SET status='sold' WHERE id=?",(listing_id,))
    q.execute("INSERT INTO inventory(telegram_id,item_name,rarity,emoji,value,quantity) VALUES(?,?,?,?,?,?) ON CONFLICT(telegram_id,item_name) DO UPDATE SET quantity=quantity+excluded.quantity",(tid,r["item_name"],r["rarity"],r["emoji"],r["value"],r["quantity"]))
    inv=q.execute("SELECT quantity FROM inventory WHERE telegram_id=? AND item_name=?",(r["seller_id"],r["item_name"])).fetchone()
    if inv and inv["quantity"]<=r["quantity"]: q.execute("DELETE FROM inventory WHERE telegram_id=? AND item_name=?",(r["seller_id"],r["item_name"]))
    else: q.execute("UPDATE inventory SET quantity=quantity-? WHERE telegram_id=? AND item_name=?",(r["quantity"],r["seller_id"],r["item_name"]))
    add_tx(q,tid,"market_buy",f"Покупка: {r['item_name']}",-r["price"],u["balance"]-r["price"],"🛒")
    add_tx(q,r["seller_id"],"market_sell",f"Продажа: {r['item_name']}",seller_get,seller["balance"]+seller_get,"💰")
    q.execute("INSERT INTO market_sales(listing_id,seller_id,buyer_id,item_name,price,fee,created_at) VALUES(?,?,?,?,?,?,?)",(listing_id,r["seller_id"],tid,r["item_name"],r["price"],fee,datetime.now().isoformat()))
    c.commit(); c.close(); return {"ok":True,"price":r["price"],"fee":fee,"seller_get":seller_get}



def sell_inventory_item(tid, item_name, quantity=1):
    """Instant NPC sale from inventory. Market-reserved quantity cannot be sold."""
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        return {"ok": False, "reason": "quantity"}
    if quantity <= 0:
        return {"ok": False, "reason": "quantity"}

    c = connect(); q = c.cursor()
    try:
        inv = q.execute(
            "SELECT * FROM inventory WHERE telegram_id=? AND item_name=?",
            (tid, item_name)
        ).fetchone()
        if not inv:
            return {"ok": False, "reason": "item"}

        reserved = q.execute(
            """SELECT COALESCE(SUM(quantity),0) qty
               FROM market_listings
               WHERE seller_id=? AND item_name=? AND status='active'""",
            (tid, item_name)
        ).fetchone()["qty"]

        available = inv["quantity"] - reserved
        if available < quantity:
            return {"ok": False, "reason": "listed" if reserved else "item",
                    "available": max(0, available)}

        # Fast-sale value is intentionally below the normal item value so Market
        # remains the better option when a player is willing to wait for a buyer.
        unit_price = max(1, int(round(inv["value"] * 0.70)))
        reward = unit_price * quantity

        if inv["quantity"] == quantity:
            q.execute(
                "DELETE FROM inventory WHERE telegram_id=? AND item_name=?",
                (tid, item_name)
            )
        else:
            q.execute(
                "UPDATE inventory SET quantity=quantity-? WHERE telegram_id=? AND item_name=?",
                (quantity, tid, item_name)
            )

        u = q.execute("SELECT * FROM users WHERE telegram_id=?", (tid,)).fetchone()
        balance = u["balance"] + reward
        q.execute("UPDATE users SET balance=? WHERE telegram_id=?", (balance, tid))
        add_tx(q, tid, "inventory_sale",
               f"Быстрая продажа: {item_name} ×{quantity}",
               reward, balance, "💰")
        add_xp(q, u, min(50, max(5, quantity * 5)))
        c.commit()
        return {
            "ok": True,
            "item": item_name,
            "quantity": quantity,
            "unit_price": unit_price,
            "reward": reward,
            "balance": balance
        }
    finally:
        c.close()


def get_collections(tid):
    collections={
      "SHAMA FOOTBALL":["SHAMA BALL","STREET BOOTS","CAPTAIN ARMBAND","GOLDEN BOOTS","SILVER MEDAL","CHAMPION MEDAL","STADIUM KEY","GOLDEN CUP","TORPEDO MEDAL","TORPEDO CUP","TORPEDO 2025"],
      "SHAMA ENERGY":["PURPLE CRYSTAL","ENERGY SHARD","VOID FRAGMENT","PURPLE ORB","ENERGY CORE","VOID CORE","SHAMA RELIC","INFINITY CORE"],
      "SHAMA BUSINESS":["OLD WALLET","BUSINESS CARD","GOLDEN PHONE","BLACK BRIEFCASE","EXECUTIVE WATCH","GOLDEN BRIEFCASE","SH BLACK CARD","PRIVATE VAULT KEY"],
      "SHAMA BANK":["BANK KEY","SILVER BAR","GOLD BAR","VAULT KEY","DIAMOND BAR","GOLDEN VAULT","BANK MASTER KEY","SH TREASURY"],
      "SECRET WORLD":["MYSTERY BOX","ANCIENT KEY","WATCHER EYE","VOID CUBE","UNKNOWN MASK","SHAMA PORTAL","WORLD FRAGMENT","SHAMA WORLD CORE"],
    }
    c=connect(); inv={r["item_name"]:r["quantity"] for r in c.execute("SELECT item_name,quantity FROM inventory WHERE telegram_id=?",(tid,)).fetchall()}; c.close(); out=[]
    for name,items in collections.items():
        owned=sum(1 for x in items if x in inv and inv[x]>0); out.append({"name":name,"owned":owned,"total":len(items),"complete":owned==len(items) and len(items)>0,"items":[{"name":x,"quantity":inv.get(x,0)} for x in items]})
    return out

def _upgrade_chance(source_value,target_value):
    ratio=target_value/max(1,source_value)
    # Easier targets are intentionally more likely; a very expensive jump bottoms out at 10%.
    return round(max(10.0,min(80.0,85.0-30.0*(ratio-1.0))),1)


def get_upgrade_options(tid,item_name):
    c=connect(); q=c.cursor(); row=c.execute("SELECT item_name name,rarity,emoji,value,quantity FROM inventory WHERE telegram_id=? AND item_name=?",(tid,item_name)).fetchone()
    if not row or row["quantity"]<=0: c.close(); return {"ok":False,"reason":"item"}
    candidates_map={}
    # Main catalog.
    for item in UPGRADE_BASES:
        candidates_map[item[0]]={"name":item[0],"rarity":item[1],"emoji":item[2],"value":item[3]}
    # Also include every item the player actually owns. This keeps older/legacy items
    # upgradeable even if they are no longer present in the current case catalog.
    owned=q.execute("SELECT item_name name,rarity,emoji,value FROM inventory WHERE telegram_id=?",(tid,)).fetchall()
    for item in owned:
        candidates_map[item["name"]]={"name":item["name"],"rarity":item["rarity"],"emoji":item["emoji"],"value":item["value"]}
    candidates=[]
    for item in candidates_map.values():
        if item["value"] <= row["value"]: continue
        item=dict(item); item["chance"]=_upgrade_chance(row["value"],item["value"]); candidates.append(item)
    candidates.sort(key=lambda x:x["value"])
    # Always expose owned higher-value items first, then fill with graduated catalog targets.
    owned_names={x["name"] for x in owned if x["name"] != row["name"] and x["value"] > row["value"]}
    chosen=[x for x in candidates if x["name"] in owned_names][:3]
    for x in candidates:
        if len(chosen)>=5: break
        if x["name"] not in {z["name"] for z in chosen}: chosen.append(x)
    if candidates and candidates[-1]["name"] not in {x["name"] for x in chosen}: chosen.append(candidates[-1])
    c.close(); return {"ok":True,"source":dict(row),"targets":chosen}


def upgrade_item(tid,source_name,target_name):
    c=connect(); q=c.cursor(); src=q.execute("SELECT * FROM inventory WHERE telegram_id=? AND item_name=?",(tid,source_name)).fetchone()
    target=next((x for x in UPGRADE_BASES if x[0]==target_name),None)
    if target is None:
        owned_target=q.execute("SELECT item_name,rarity,emoji,value FROM inventory WHERE telegram_id=? AND item_name=?",(tid,target_name)).fetchone()
        if owned_target:
            target=(owned_target["item_name"],owned_target["rarity"],owned_target["emoji"],owned_target["value"],0)
    if not src or src["quantity"]<=0: c.close(); return {"ok":False,"reason":"item"}
    reserved=q.execute("SELECT COALESCE(SUM(quantity),0) qty FROM market_listings WHERE seller_id=? AND item_name=? AND status='active'",(tid,source_name)).fetchone()["qty"]
    if src["quantity"]-reserved <= 0: c.close(); return {"ok":False,"reason":"listed"}
    if not target or target[3] <= src["value"]: c.close(); return {"ok":False,"reason":"target"}
    chance=_upgrade_chance(src["value"],target[3]); success=random.random()*100 < chance
    new_qty=src["quantity"]-1
    if new_qty<=0: q.execute("DELETE FROM inventory WHERE telegram_id=? AND item_name=?",(tid,source_name))
    else: q.execute("UPDATE inventory SET quantity=? WHERE telegram_id=? AND item_name=?",(new_qty,tid,source_name))
    if success:
        q.execute("INSERT INTO inventory(telegram_id,item_name,rarity,emoji,value,quantity) VALUES(?,?,?,?,?,1) ON CONFLICT(telegram_id,item_name) DO UPDATE SET quantity=quantity+1",(tid,target[0],target[1],target[2],target[3]))
    q.execute("INSERT INTO upgrade_history(telegram_id,source_name,source_value,target_name,target_value,chance,success,created_at) VALUES(?,?,?,?,?,?,?,?)",(tid,source_name,src["value"],target[0],target[3],chance,1 if success else 0,datetime.now().isoformat()))
    c.commit(); c.close(); return {"ok":True,"success":success,"chance":chance,"source":source_name,"target":target[0],"target_value":target[3]}
