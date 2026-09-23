import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from aiohttp import web

from config import BOT_TOKEN
from database import (
    create_user,
    get_user,
    get_stats,
    get_inventory,
    get_history,
    get_achievements,
    get_leaderboard,
    claim_bonus,
    open_pack,
    PACKS,
)


def validate_init_data(init_data: str):
    """Validate Telegram Mini App initData."""
    if not init_data:
        return None

    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = pairs.pop("hash", None)

        if not received_hash:
            return None

        check_string = "\n".join(
            f"{key}={pairs[key]}" for key in sorted(pairs)
        )

        secret_key = hmac.new(
            b"WebAppData",
            BOT_TOKEN.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        calculated_hash = hmac.new(
            secret_key,
            check_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(calculated_hash, received_hash):
            return None

        auth_date = int(pairs.get("auth_date", "0"))
        if not auth_date or time.time() - auth_date > 86400:
            return None

        return json.loads(pairs.get("user", "{}"))

    except (ValueError, TypeError, json.JSONDecodeError):
        return None
    except Exception as exc:
        print(f"initData validation error: {exc}")
        return None


@web.middleware
async def auth(request, handler):
    if request.path.startswith("/api/") and request.path != "/api/health":
        user = validate_init_data(
            request.headers.get("X-Telegram-Init-Data", "")
        )

        if not user or "id" not in user:
            return web.json_response(
                {"ok": False, "error": "Telegram authorization required"},
                status=401,
            )

        request["tg_user"] = user
        create_user(
            user["id"],
            user.get("username"),
            user.get("first_name", "Player"),
        )

    return await handler(request)


def result(data):
    return web.json_response({"ok": True, **data})


async def health(request):
    return result({"version": "6.0"})


async def me(request):
    tid = request["tg_user"]["id"]
    user = get_user(tid)
    stats = get_stats(tid)

    return result({
        "user": dict(user),
        "stats": stats,
        "packs": PACKS,
    })


async def inventory(request):
    return result({
        "items": get_inventory(request["tg_user"]["id"])
    })


async def history(request):
    return result({
        "items": get_history(request["tg_user"]["id"])
    })


async def achievements(request):
    return result({
        "items": get_achievements(request["tg_user"]["id"])
    })


async def leaderboard(request):
    return result({
        "items": get_leaderboard()
    })


async def bonus(request):
    data = claim_bonus(request["tg_user"]["id"])

    if not data["ok"]:
        return web.json_response(data, status=409)

    return result(data)


async def pack(request):
    try:
        body = await request.json()
    except Exception:
        body = {}

    data = open_pack(
        request["tg_user"]["id"],
        body.get("pack"),
    )

    if not data["ok"]:
        return web.json_response(data, status=409)

    return result(data)


def routes(app):
    app.middlewares.append(auth)

    app.router.add_get("/api/health", health)
    app.router.add_get("/api/me", me)
    app.router.add_get("/api/inventory", inventory)
    app.router.add_get("/api/history", history)
    app.router.add_get("/api/achievements", achievements)
    app.router.add_get("/api/leaderboard", leaderboard)
    app.router.add_post("/api/bonus", bonus)
    app.router.add_post("/api/open-pack", pack)
