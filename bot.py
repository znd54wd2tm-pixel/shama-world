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
        raise RuntimeError("RENDER_EXTERNAL_URL is not set in Render")
    return f"{base}/app"


@dp.message(CommandStart())
async def start(message: Message):
    u = message.from_user
    create_user(u.id, u.username, u.first_name or "Player")
    user = get_user(u.id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🎮 ОТКРЫТЬ SHAMA WORLD",
            web_app=WebAppInfo(url=app_url())
        )],
        [InlineKeyboardButton(text="📖 Как играть", callback_data="how_to")]
    ])

    text = (
        "🎮 <b>SHAMA WORLD</b>\n\n"
        f"Привет, <b>{u.first_name or 'Player'}</b>! 👋\n\n"
        "Добро пожаловать в игровую вселенную SHAMA WORLD.\n\n"
        f"💰 Баланс: <b>{user['balance']:,} CW</b>\n"
        f"⭐ Уровень: <b>{user['level']}</b>\n\n"
        "Открой мини-приложение, чтобы продолжить."
    ).replace(",", " ")

    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@dp.callback_query(F.data == "how_to")
async def how_to(c):
    await c.message.answer(
        "🎮 <b>Как играть</b>\n\n"
        "• Получай CW за ежедневные награды и задания.\n"
        "• Открывай игровые паки за заработанные CW.\n"
        "• Собирай коллекцию предметов.\n"
        "• Получай XP и повышай уровень.\n"
        "• Выполняй достижения и поднимайся в рейтинге.\n\n"
        "CW — только виртуальная валюта SHAMA WORLD. "
        "Реальных ставок, вывода денег и покупки CW нет.",
        parse_mode="HTML"
    )
    await c.answer()


async def root(request):
    return web.Response(text="SHAMA WORLD is running")


async def index(request):
    path = os.path.join(os.path.dirname(__file__), "web", "index.html")
    if not os.path.isfile(path):
        return web.Response(text="web/index.html not found", status=500)
    return web.FileResponse(path)


async def start_server():
    app = web.Application()

    app.router.add_get("/", root)
    app.router.add_get("/app", index)

    assets_dir = os.path.join(os.path.dirname(__file__), "web", "assets")
    if os.path.isdir(assets_dir):
        app.router.add_static("/assets", assets_dir)

    routes(app)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", "10000"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    print(f"SHAMA WORLD web server started on 0.0.0.0:{port}")
    print(f"Mini App URL: {os.getenv('RENDER_EXTERNAL_URL', 'http://localhost:'+str(port))}/app")
    return runner


async def main():
    init_db()
    runner = await start_server()

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        print("Telegram polling started")
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
