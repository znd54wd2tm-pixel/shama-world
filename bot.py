import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery

from config import BOT_TOKEN
from database import (
    init_db, create_user, get_user, claim_bonus,
    get_inventory, open_shama_case, get_top_players
)
from keyboards import main_menu, cases_menu, back_menu

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: Message):
    u = message.from_user
    create_user(u.id, u.username, u.first_name)
    db = get_user(u.id)

    text = (
        f"🎮 <b>SHAMA WORLD</b>\n\n"
        f"Добро пожаловать, <b>{u.first_name}</b>!\n\n"
        f"💰 Баланс: <b>{db['balance']:,} CW</b>\n"
        f"🎁 Кейсов открыто: <b>{db['cases_opened']}</b>\n\n"
        "Выбирай раздел ниже."
    ).replace(",", " ")

    await message.answer(text, reply_markup=main_menu(), parse_mode="HTML")


async def edit(callback, text, markup):
    try:
        await callback.message.edit_text(
            text, reply_markup=markup, parse_mode="HTML"
        )
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            raise


@dp.callback_query(F.data == "cases")
async def cases(callback: CallbackQuery):
    await edit(
        callback,
        "🎁 <b>КЕЙСЫ</b>\n\n"
        "🔥 <b>SHAMA CASE</b>\n"
        "Стоимость: <b>1 000 CW</b>\n\n"
        "⚪ Обычный — 60%\n"
        "🔵 Редкий — 25%\n"
        "🟣 Эпический — 10%\n"
        "🟡 Легендарный — 4%\n"
        "🔴 Мифический — 1%",
        cases_menu()
    )
    await callback.answer()


@dp.callback_query(F.data == "profile")
async def profile(callback: CallbackQuery):
    u = get_user(callback.from_user.id)
    if not u:
        await callback.answer("Сначала нажми /start", show_alert=True)
        return

    text = (
        f"👤 <b>ПРОФИЛЬ</b>\n\n"
        f"Имя: <b>{u['first_name']}</b>\n"
        f"💰 Баланс: <b>{u['balance']:,} CW</b>\n"
        f"🎁 Кейсов открыто: <b>{u['cases_opened']}</b>"
    ).replace(",", " ")

    await edit(callback, text, back_menu())
    await callback.answer()


@dp.callback_query(F.data == "balance")
async def balance(callback: CallbackQuery):
    u = get_user(callback.from_user.id)
    await edit(
        callback,
        f"💰 <b>БАЛАНС</b>\n\n<b>{u['balance']:,} CW</b>".replace(",", " "),
        back_menu()
    )
    await callback.answer()


@dp.callback_query(F.data == "bonus")
async def bonus(callback: CallbackQuery):
    reward = claim_bonus(callback.from_user.id)
    if not reward:
        await callback.answer("🎁 Бонус уже получен сегодня!", show_alert=True)
        return

    u = get_user(callback.from_user.id)
    await edit(
        callback,
        f"🎁 <b>БОНУС ПОЛУЧЕН</b>\n\n"
        f"+<b>{reward:,} CW</b>\n"
        f"💰 Баланс: <b>{u['balance']:,} CW</b>".replace(",", " "),
        back_menu()
    )
    await callback.answer()


@dp.callback_query(F.data == "open_shama_case")
async def open_case(callback: CallbackQuery):
    result = open_shama_case(callback.from_user.id)

    if result["status"] == "not_enough":
        await callback.answer(
            f"Не хватает {result['need']:,} CW".replace(",", " "),
            show_alert=True
        )
        return

    item = result["item"]
    rarity = result["rarity"]

    text = (
        "🎁 <b>SHAMA CASE</b>\n\n"
        "✨ <b>КЕЙС ОТКРЫТ!</b>\n\n"
        f"{rarity['emoji']} <b>{rarity['name']}</b>\n"
        f"📦 {item['name']}\n"
        f"💎 Ценность: <b>{item['value']:,} CW</b>\n\n"
        f"💰 Баланс: <b>{result['balance']:,} CW</b>"
    ).replace(",", " ")

    await edit(callback, text, cases_menu())
    await callback.answer("Предмет добавлен в инвентарь!")


@dp.callback_query(F.data == "inventory")
async def inventory(callback: CallbackQuery):
    items = get_inventory(callback.from_user.id)

    if not items:
        text = "🎒 <b>ИНВЕНТАРЬ</b>\n\nПока пуст.\nОткрой первый кейс!"
    else:
        lines = ["🎒 <b>ИНВЕНТАРЬ</b>\n"]
        for item in items:
            lines.append(
                f"{item['emoji']} <b>{item['name']}</b> ×{item['quantity']}\n"
                f"{item['rarity']} · {item['value']:,} CW".replace(",", " ")
            )
        text = "\n".join(lines)

    await edit(callback, text, back_menu())
    await callback.answer()


@dp.callback_query(F.data == "rating")
async def rating(callback: CallbackQuery):
    players = get_top_players()
    lines = ["🏆 <b>ТОП ИГРОКОВ</b>\n"]

    for i, player in enumerate(players, 1):
        lines.append(
            f"{i}. <b>{player['first_name']}</b> — "
            f"{player['balance']:,} CW".replace(",", " ")
        )

    if len(lines) == 1:
        lines.append("Пока игроков нет.")

    await edit(callback, "\n".join(lines), back_menu())
    await callback.answer()


@dp.callback_query(F.data == "home")
async def home(callback: CallbackQuery):
    u = get_user(callback.from_user.id)
    text = (
        f"🎮 <b>SHAMA WORLD</b>\n\n"
        f"💰 Баланс: <b>{u['balance']:,} CW</b>\n\n"
        "Выбирай раздел ниже."
    ).replace(",", " ")

    await edit(callback, text, main_menu())
    await callback.answer()


async def health(request):
    return web.Response(text="SHAMA WORLD is running")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", "10000"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    print(f"Health server started on port {port}")
    return runner


async def main():
    init_db()

    # Important: remove any old webhook so Telegram delivers updates
    # directly to long polling.
    await bot.delete_webhook(drop_pending_updates=True)
    print("Webhook removed. Starting Telegram polling...")

    runner = await start_web_server()

    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
