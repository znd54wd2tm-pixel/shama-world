import asyncio
import os

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, Update

from config import BOT_TOKEN
from database import init_db, create_user, get_user, add_balance, update_bonus_date
from keyboards import main_menu
from datetime import date

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def start(message: Message):
    user = message.from_user
    create_user(user.id, user.username, user.first_name)
    db_user = get_user(user.id)
    balance = db_user[3]
    text = (
        "🎮 <b>SHAMA WORLD</b>\n\n"
        f"Добро пожаловать, <b>{user.first_name}</b>!\n\n"
        f"💰 Баланс: <b>{balance:,} CW</b>\n\n"
        "Добро пожаловать в первую версию проекта."
    ).replace(",", " ")
    await message.answer(text, reply_markup=main_menu(), parse_mode="HTML")

@dp.callback_query(F.data == "profile")
async def profile(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user:
        await callback.answer("Сначала нажми /start")
        return
    username = user[1] or "не указан"
    text = (
        "👤 <b>ПРОФИЛЬ</b>\n\n"
        f"Имя: <b>{user[2]}</b>\n"
        f"Username: @{username}\n"
        f"ID: <code>{user[0]}</code>\n\n"
        f"💰 Баланс: <b>{user[3]:,} CW</b>\n"
        f"🎁 Кейсов открыто: <b>{user[4]}</b>\n"
        f"📅 Регистрация: <b>{user[6]}</b>"
    ).replace(",", " ")
    await callback.message.edit_text(text, reply_markup=main_menu(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "balance")
async def balance(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user:
        await callback.answer("Сначала нажми /start")
        return
    await callback.message.edit_text(
        f"💰 <b>ТВОЙ БАЛАНС</b>\n\n<b>{user[3]:,} CW</b>".replace(",", " "),
        reply_markup=main_menu(), parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "bonus")
async def bonus(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user:
        await callback.answer("Сначала нажми /start")
        return
    today = date.today().isoformat()
    if user[5] == today:
        await callback.answer("🎁 Бонус уже получен сегодня!", show_alert=True)
        return
    reward = 1000
    add_balance(callback.from_user.id, reward)
    update_bonus_date(callback.from_user.id)
    await callback.message.edit_text(
        f"🎁 <b>БОНУС</b>\n\nПолучено: <b>+{reward} CW</b>",
        reply_markup=main_menu(), parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "cases")
async def cases(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎁 <b>КЕЙСЫ</b>\n\nРаздел готов для добавления безопасной игровой механики.",
        reply_markup=main_menu(), parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "inventory")
async def inventory(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎒 <b>ИНВЕНТАРЬ</b>\n\nПока пуст.",
        reply_markup=main_menu(), parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "rating")
async def rating(callback: CallbackQuery):
    await callback.message.edit_text(
        "🏆 <b>РЕЙТИНГ</b>\n\nРаздел готов к подключению.",
        reply_markup=main_menu(), parse_mode="HTML"
    )
    await callback.answer()

async def health(request):
    return web.Response(text="SHAMA WORLD is running")

async def on_startup(app):
    init_db()
    base_url = os.environ["RENDER_EXTERNAL_URL"]
    await bot.set_webhook(f"{base_url}/webhook")

async def on_cleanup(app):
    await bot.delete_webhook()
    await bot.session.close()

async def webhook(request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return web.Response(text="OK")

def main():
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_post("/webhook", webhook)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    port = int(os.environ.get("PORT", "10000"))
    web.run_app(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
