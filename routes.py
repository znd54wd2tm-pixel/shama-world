import hashlib
import hmac
import json
import random
from urllib.parse import parse_qsl
from aiohttp import web
from config import BOT_TOKEN
from database import ensure_user, get_user, get_inventory, get_history, claim_daily, do_work, spend, add_item, add_xp, sell_item

CASES = {
    "starter": {
        "name": "STARTER CASE", "price": 500,
        "items": [
            ("SHAMA CARD", "Обычный", 700, 65),
            ("SHAMA STICKER", "Обычный", 500, 25),
            ("SHAMA KEYCHAIN", "Редкий", 1200, 9),
            ("SHAMA HOODIE", "Эпический", 3500, 1),
        ],
    },
    "epic": {
        "name": "EPIC CASE", "price": 1500,
        "items": [
            ("SHAMA KEYCHAIN", "Редкий", 1200, 55),
            ("SHAMA CAP", "Редкий", 1800, 25),
            ("SHAMA HOODIE", "Эпический", 3500, 15),
            ("SHAMA GOLD CARD", "Легендарный", 7000, 5),
        ],
    },
    "legend": {
        "name": "LEGEND CASE", "price": 5000,
        "items": [
            ("SHAMA HOODIE", "Эпический", 3500, 50),
            ("SHAMA GOLD CARD", "Легендарный", 7000, 30),
            ("SHAMA LEGEND", "Легендарный", 12000, 15),
            ("SHAMA MYTHIC CARD", "Мифический", 50000, 5),
        ],
    },
}

JOBS = {
    "courier": ("Курьер", 250, "Доставляй посылки по SHAMA WORLD"),
    "factory": ("Рабочий CASE FACTORY", 300, "Производи новые кейсы"),
    "stadium": ("Сотрудник TORPEDO STADIUM", 350, "Помогай на стадионе"),
    "market": ("Работник SH MARKET", 275, "Обслуживай торговую зону"),
}

def telegram_user(request):
    raw = request.headers.get("X-Telegram-Init-Data", "")
    if not raw:
        # Local testing only: browser gets a stable demo account.
        return {"id": 999999999, "username": "demo", "first_name": "Demo"}
    if not BOT_TOKEN:
        raise web.HTTPUnauthorized(text="BOT_TOKEN is not configured")
    pairs = dict(parse_qsl(raw, keep_blank_values=True))
    received = pairs.pop("hash", "")
    if not received:
        raise web.HTTPUnauthorized(text="Invalid Telegram initData")
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(digest, received):
        raise web.HTTPUnauthorized(text="Invalid Telegram signature")
    user = json.loads(pairs.get("user", "{}"))
    if not user.get("id"):
        raise web.HTTPUnauthorized(text="Telegram user not found")
    return user

async def me(request):
    u = telegram_user(request)
    ensure_user(int(u["id"]), u.get("username"), u.get("first_name") or "Player")
    return web.json_response({"user": get_user(int(u["id"])), "inventory": get_inventory(int(u["id"]))})

async def daily(request):
    u = telegram_user(request)
    ok, reward = claim_daily(int(u["id"]))
    if not ok:
        return web.json_response({"ok": False, "message": "Награда уже получена сегодня."})
    add_xp(int(u["id"]), 25)
    return web.json_response({"ok": True, "reward": reward})

async def work(request):
    u = telegram_user(request)
    data = await request.json()
    key = data.get("job", "courier")
    if key not in JOBS:
        raise web.HTTPBadRequest(text="Unknown job")
    name, reward, _ = JOBS[key]
    ok, value = do_work(int(u["id"]), name, reward)
    if not ok:
        return web.json_response({"ok": False, "cooldown": value, "message": "Работа пока на перезарядке."})
    add_xp(int(u["id"]), 40)
    return web.json_response({"ok": True, "reward": value})

async def open_case(request):
    u = telegram_user(request)
    data = await request.json()
    key = data.get("case")
    if key not in CASES:
        raise web.HTTPBadRequest(text="Unknown case")
    case = CASES[key]
    if not spend(int(u["id"]), case["price"], f"Открытие {case['name']}"):
        return web.json_response({"ok": False, "message": "Недостаточно SH."})
    roll = random.randint(1, 100)
    total = 0
    chosen = case["items"][-1]
    for item in case["items"]:
        total += item[3]
        if roll <= total:
            chosen = item
            break
    add_item(int(u["id"]), chosen[0], chosen[1], chosen[2])
    add_xp(int(u["id"]), 50 if key == "starter" else 150 if key == "epic" else 500)
    return web.json_response({"ok": True, "item": {
        "name": chosen[0], "rarity": chosen[1], "value": chosen[2]
    }})

async def inventory(request):
    u = telegram_user(request)
    return web.json_response({"items": get_inventory(int(u["id"]))})

async def sell(request):
    u = telegram_user(request)
    data = await request.json()
    value = sell_item(int(u["id"]), int(data.get("id", 0)))
    if value is None:
        return web.json_response({"ok": False, "message": "Предмет не найден."})
    return web.json_response({"ok": True, "value": value})

async def history(request):
    u = telegram_user(request)
    return web.json_response({"history": get_history(int(u["id"]))})

async def cases(request):
    return web.json_response({"cases": [
        {"id": k, "name": v["name"], "price": v["price"], "items": len(v["items"])}
        for k,v in CASES.items()
    ]})

async def world(request):
    return web.json_response({
        "locations": [
            {"id":"stadium","title":"TORPEDO STADIUM","type":"stadium"},
            {"id":"market","title":"SH MARKET","type":"market"},
            {"id":"courier","title":"COURIER HUB","type":"jobs"},
            {"id":"factory","title":"CASE FACTORY","type":"factory"},
            {"id":"bank","title":"SHAMA BANK","type":"bank"},
        ]
    })

def setup_routes(app):
    app.router.add_get("/api/me", me)
    app.router.add_get("/api/cases", cases)
    app.router.add_get("/api/world", world)
    app.router.add_get("/api/inventory", inventory)
    app.router.add_get("/api/history", history)
    app.router.add_post("/api/daily", daily)
    app.router.add_post("/api/work", work)
    app.router.add_post("/api/open-case", open_case)
    app.router.add_post("/api/sell", sell)
