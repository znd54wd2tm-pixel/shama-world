import hashlib, hmac, json, os, time
from urllib.parse import parse_qsl
from aiohttp import web
from database import (
    create_user, get_user, get_stats, get_inventory, get_history,
    get_achievements, get_leaderboard, claim_bonus, open_pack, PACKS, public_packs,
    get_tasks, claim_task, do_work, get_farm, collect_farm, upgrade_farm,
    get_upgrade_options, upgrade_item, get_market, market_sell, market_buy, market_cancel, get_collections
)
from config import BOT_TOKEN


def validate_init_data(init_data):
    if not init_data:
        return None
    try:
        data = dict(parse_qsl(init_data, keep_blank_values=True))
        received = data.pop("hash", None)
        if not received:
            return None
        check = "\n".join(f"{k}={data[k]}" for k in sorted(data))
        secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, received):
            return None
        auth_date = int(data.get("auth_date", "0"))
        if time.time() - auth_date > 86400:
            return None
        user = json.loads(data.get("user", "{}"))
        return user
    except Exception:
        return None


@web.middleware
async def auth(request, handler):
    if request.path.startswith("/api/") and request.path != "/api/health":
        user = validate_init_data(request.headers.get("X-Telegram-Init-Data", ""))
        if not user:
            return web.json_response({"ok": False, "error": "Telegram authorization required"}, status=401)
        request["tg_user"] = user
        create_user(user["id"], user.get("username"), user.get("first_name", "Player"))
    return await handler(request)


def result(data):
    return web.json_response({"ok": True, **data})


async def health(request):
    return web.json_response({"ok": True, "version": "13.0"})


async def me(request):
    tid = request["tg_user"]["id"]
    u = get_user(tid)
    return result({"user": dict(u), "stats": get_stats(tid), "packs": public_packs(), "tasks": get_tasks(tid)})


async def inventory(request):
    return result({"items": get_inventory(request["tg_user"]["id"])})


async def history(request):
    return result({"items": get_history(request["tg_user"]["id"])})


async def achievements(request):
    return result({"items": get_achievements(request["tg_user"]["id"])})


async def leaderboard(request):
    return result({"items": get_leaderboard()})


async def tasks(request):
    return result({"items": get_tasks(request["tg_user"]["id"])})


async def bonus(request):
    r = claim_bonus(request["tg_user"]["id"])
    if not r["ok"]:
        return web.json_response(r, status=409)
    return result(r)


async def task_claim(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    r = claim_task(request["tg_user"]["id"], body.get("task"))
    if not r["ok"]:
        return web.json_response(r, status=409)
    return result(r)


async def work(request):
    r = do_work(request["tg_user"]["id"])
    if not r["ok"]:
        return web.json_response(r, status=409)
    return result(r)


async def pack(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    r = open_pack(request["tg_user"]["id"], body.get("pack"))
    if not r["ok"]:
        return web.json_response(r, status=409)
    return result(r)


async def farm(request):
    return result(get_farm(request["tg_user"]["id"]))


async def farm_collect(request):
    r = collect_farm(request["tg_user"]["id"])
    if not r["ok"]:
        return web.json_response(r, status=409)
    return result(r)


async def farm_upgrade(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    r = upgrade_farm(request["tg_user"]["id"], body.get("farm"))
    if not r["ok"]:
        return web.json_response(r, status=409)
    return result(r)


async def upgrade_options(request):
    item = request.query.get("item", "")
    r = get_upgrade_options(request["tg_user"]["id"], item)
    if not r["ok"]:
        return web.json_response(r, status=404)
    return result({"source": r["source"], "targets": r["targets"]})


async def upgrade_do(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    r = upgrade_item(request["tg_user"]["id"], body.get("source"), body.get("target"))
    if not r["ok"]:
        return web.json_response(r, status=409)
    return result(r)


async def market(request):
    return result(get_market(request["tg_user"]["id"]))


async def market_sell_route(request):
    try: body=await request.json()
    except Exception: body={}
    r=market_sell(request["tg_user"]["id"], body.get("item"), body.get("price"), body.get("quantity",1))
    if not r["ok"]: return web.json_response(r,status=409)
    return result(r)


async def market_buy_route(request):
    try: body=await request.json()
    except Exception: body={}
    r=market_buy(request["tg_user"]["id"], body.get("listing_id"))
    if not r["ok"]: return web.json_response(r,status=409)
    return result(r)


async def market_cancel_route(request):
    try: body=await request.json()
    except Exception: body={}
    r=market_cancel(request["tg_user"]["id"], body.get("listing_id"))
    if not r["ok"]: return web.json_response(r,status=409)
    return result(r)


async def collections(request):
    return result({"items":get_collections(request["tg_user"]["id"])})


def routes(app):
    app.middlewares.append(auth)
    app.router.add_get("/api/health", health)
    app.router.add_get("/api/me", me)
    app.router.add_get("/api/inventory", inventory)
    app.router.add_get("/api/history", history)
    app.router.add_get("/api/achievements", achievements)
    app.router.add_get("/api/leaderboard", leaderboard)
    app.router.add_get("/api/tasks", tasks)
    app.router.add_post("/api/bonus", bonus)
    app.router.add_post("/api/claim-task", task_claim)
    app.router.add_post("/api/work", work)
    app.router.add_post("/api/open-pack", pack)
    app.router.add_get("/api/farm", farm)
    app.router.add_post("/api/farm/collect", farm_collect)
    app.router.add_post("/api/farm/upgrade", farm_upgrade)
    app.router.add_get("/api/upgrade-options", upgrade_options)
    app.router.add_post("/api/upgrade", upgrade_do)
    app.router.add_get("/api/market", market)
    app.router.add_post("/api/market/sell", market_sell_route)
    app.router.add_post("/api/market/buy", market_buy_route)
    app.router.add_post("/api/market/cancel", market_cancel_route)
    app.router.add_get("/api/collections", collections)
