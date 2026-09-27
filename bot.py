import asyncio
import json
import logging
import os
from aiohttp import web, ClientSession
from config import BOT_TOKEN, WEB_APP_URL
from database import init_db, ensure_user, get_user

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("shama-world")

API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""

async def tg_call(session, method, payload=None):
    if not API:
        raise RuntimeError("BOT_TOKEN is not configured")
    async with session.post(f"{API}/{method}", json=payload or {}) as r:
        return await r.json()

async def telegram_loop():
    if not BOT_TOKEN:
        log.warning("BOT_TOKEN is not set. Web Mini App can still be tested locally.")
        return
    offset = 0
    async with ClientSession() as session:
        while True:
            try:
                data = await tg_call(session, "getUpdates", {
                    "timeout": 25,
                    "offset": offset,
                    "allowed_updates": ["message", "callback_query"],
                })
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    await handle_update(session, update)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Telegram polling error")
                await asyncio.sleep(3)

async def handle_update(session, update):
    message = update.get("message")
    if message and message.get("text") == "/start":
        user = message.get("from", {})
        uid = int(user["id"])
        ensure_user(uid, user.get("username"), user.get("first_name") or "Player")
        me = get_user(uid)
        keyboard = {
            "inline_keyboard": [[{
                "text": "🎮 ОТКРЫТЬ SHAMA WORLD",
                "web_app": {"url": WEB_APP_URL}
            }]]
        }
        text = (
            f"🎮 <b>SHAMA WORLD</b>\n\n"
            f"Привет, <b>{user.get('first_name') or 'Player'}</b>!\n\n"
            f"💰 Баланс: <b>{me['balance']} SH</b>\n"
            f"⭐ Уровень: <b>{me['level']}</b>\n\n"
            "Зарабатывай SH, выполняй работы, открывай кейсы и развивай свой мир."
        )
        await tg_call(session, "sendMessage", {
            "chat_id": message["chat"]["id"],
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": keyboard,
        })

async def index(request):
    return web.FileResponse(Path("web/index.html"))

async def health(request):
    return web.json_response({"ok": True, "service": "shama-world", "version": "clean-1.0"})

async def create_app():
    init_db()
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/app", index)
    app.router.add_get("/api/health", health)
    app.router.add_static("/assets", "web/assets", show_index=False)
    from routes import setup_routes
    setup_routes(app)
    return app

async def main():
    app = await create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "10000"))
    await web.TCPSite(runner, "0.0.0.0", port).start()
    log.info("SHAMA WORLD Mini App listening on port %s", port)
    task = asyncio.create_task(telegram_loop())
    try:
        await asyncio.Event().wait()
    finally:
        task.cancel()
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
