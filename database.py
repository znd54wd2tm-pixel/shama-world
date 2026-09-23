import sqlite3, random
from datetime import date
DB_NAME="shama_world.db"; CASE_PRICE=1000
RARITIES=[
 {"key":"common","name":"Обычный","emoji":"⚪","chance":60},
 {"key":"rare","name":"Редкий","emoji":"🔵","chance":25},
 {"key":"epic","name":"Эпический","emoji":"🟣","chance":10},
 {"key":"legendary","name":"Легендарный","emoji":"🟡","chance":4},
 {"key":"mythic","name":"Мифический","emoji":"🔴","chance":1}]
ITEMS={
 "common":[("SHAMA STICKER",500),("SHAMA KEYCHAIN",700),("SHAMA CARD",900)],
 "rare":[("SHAMA CAP",1800),("SHAMA HOODIE",2500),("SHAMA SIGN",3000)],
 "epic":[("SHAMA GOLD CARD",7000),("SHAMA LIMITED",10000)],
 "legendary":[("SHAMA LEGEND",30000),("SHAMA GOLDEN SET",50000)],
 "mythic":[("SHAMA WORLD MYTHIC",150000)]}
def connect():
    c=sqlite3.connect(DB_NAME); c.row_factory=sqlite3.Row; return c
def init_db():
    c=connect(); q=c.cursor()
    q.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER UNIQUE NOT NULL, username TEXT, first_name TEXT, balance INTEGER DEFAULT 1000, cases_opened INTEGER DEFAULT 0, last_bonus TEXT, registered_at TEXT NOT NULL)")
    q.execute("CREATE TABLE IF NOT EXISTS inventory (id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL, item_name TEXT NOT NULL, rarity TEXT NOT NULL, emoji TEXT NOT NULL, value INTEGER NOT NULL, quantity INTEGER DEFAULT 1, UNIQUE(telegram_id,item_name))")
    c.commit(); c.close()
def create_user(tid,username,first_name):
    c=connect(); q=c.cursor(); q.execute("SELECT telegram_id FROM users WHERE telegram_id=?",(tid,))
    if not q.fetchone(): q.execute("INSERT INTO users (telegram_id,username,first_name,balance,registered_at) VALUES (?,?,?,?,?)",(tid,username,first_name,1000,date.today().isoformat()))
    else: q.execute("UPDATE users SET username=?,first_name=? WHERE telegram_id=?",(username,first_name,tid))
    c.commit(); c.close()
def get_user(tid):
    c=connect(); q=c.cursor(); q.execute("SELECT * FROM users WHERE telegram_id=?",(tid,)); r=q.fetchone(); c.close(); return r
def claim_bonus(tid):
    c=connect(); q=c.cursor(); today=date.today().isoformat(); q.execute("SELECT last_bonus FROM users WHERE telegram_id=?",(tid,)); r=q.fetchone()
    if not r or r["last_bonus"]==today: c.close(); return 0
    reward=1000; q.execute("UPDATE users SET balance=balance+?,last_bonus=? WHERE telegram_id=?",(reward,today,tid)); c.commit(); c.close(); return reward
def choose_rarity():
    roll=random.randint(1,100); n=0
    for r in RARITIES:
        n+=r["chance"]
        if roll<=n: return r
    return RARITIES[0]
def open_shama_case(tid):
    c=connect(); q=c.cursor(); q.execute("SELECT balance FROM users WHERE telegram_id=?",(tid,)); u=q.fetchone()
    if not u: c.close(); return {"status":"not_found"}
    if u["balance"]<CASE_PRICE: c.close(); return {"status":"not_enough","need":CASE_PRICE-u["balance"]}
    rarity=choose_rarity(); name,value=random.choice(ITEMS[rarity["key"]])
    q.execute("UPDATE users SET balance=balance-?,cases_opened=cases_opened+1 WHERE telegram_id=?",(CASE_PRICE,tid))
    q.execute("INSERT INTO inventory (telegram_id,item_name,rarity,emoji,value,quantity) VALUES (?,?,?,?,?,1) ON CONFLICT(telegram_id,item_name) DO UPDATE SET quantity=quantity+1",(tid,name,rarity["name"],rarity["emoji"],value))
    c.commit(); q.execute("SELECT balance FROM users WHERE telegram_id=?",(tid,)); bal=q.fetchone()["balance"]; c.close()
    return {"status":"ok","rarity":rarity,"item":{"name":name,"value":value},"balance":bal}
def get_inventory(tid):
    c=connect(); q=c.cursor(); q.execute("SELECT item_name AS name,rarity,emoji,value,quantity FROM inventory WHERE telegram_id=? ORDER BY value DESC",(tid,)); r=[dict(x) for x in q.fetchall()]; c.close(); return r
def get_top_players(limit=10):
    c=connect(); q=c.cursor(); q.execute("SELECT first_name,balance FROM users ORDER BY balance DESC LIMIT ?",(limit,)); r=[dict(x) for x in q.fetchall()]; c.close(); return r
