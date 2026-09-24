import asyncio
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from config import BOT_TOKEN
from database import init_db, create_user, get_user
from api_server import routes

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def app_url():
    base = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    if not base:
        raise RuntimeError("RENDER_EXTERNAL_URL is not set")
    return f"{base}/app"

@dp.message(CommandStart())
async def start(message: Message):
    u = message.from_user
    create_user(u.id, u.username, u.first_name or "Player")
    user = get_user(u.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 ОТКРЫТЬ SHAMA WORLD", web_app=WebAppInfo(url=app_url()))],
        [InlineKeyboardButton(text="📖 Как играть", callback_data="how_to")]
    ])
    text = (
        "🎮 <b>SHAMA WORLD</b>\n\n"
        f"Привет, <b>{u.first_name or 'Player'}</b>! 👋\n\n"
        "Зарабатывай SH, выполняй задания, открывай кейсы и собирай коллекцию.\n\n"
        f"💰 Баланс: <b>{user['balance']:,} SH</b>\n"
        f"⭐ Уровень: <b>{user['level']}</b>\n\n"
        "Открой мини-приложение и начинай играть."
    ).replace(",", " ")
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "how_to")
async def how_to(c):
    await c.message.answer(
        "🎮 <b>Как играть</b>\n\n"
        "• Зарабатывай SH за задания, активность и ежедневные награды.\n"
        "• Открывай кейсы за SH и получай гарантированные предметы.\n"
        "• Собирай коллекцию, XP и повышай уровень.\n"
        "• Выполняй дневные и недельные цели.\n\n"
        "SH — виртуальная валюта SHAMA WORLD. Реальных ставок, вывода денег и покупки SH нет.",
        parse_mode="HTML"
    )
    await c.answer()

async def health(request):
    return web.Response(text="SHAMA WORLD is running")

async def index(request):
    return web.FileResponse(os.path.join("web", "index.html"))

async def start_server():
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/app", index)
    assets_dir = os.path.join("web", "assets")
    if os.path.isdir(assets_dir):
        app.router.add_static("/assets", assets_dir)
    routes(app)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "10000"))
    await web.TCPSite(runner, "0.0.0.0", port).start()
    print(f"Mini App server started on port {port}")
    return runner

async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    print("Webhook removed. Starting Telegram polling...")
    runner = await start_server()
    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
