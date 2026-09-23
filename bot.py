import asyncio
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery

from config import BOT_TOKEN
from database import (
    init_db, create_user, get_user, claim_bonus, get_inventory,
    open_shama_case, get_top_players, get_stats, get_transaction_history
)
from keyboards import main_menu, cases_menu, back_menu, stats_menu, history_menu

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def money(n):
    return f"{n:,}".replace(",", " ")


async def edit(callback: CallbackQuery, text: str, markup):
    try:
        await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            raise


@dp.message(CommandStart())
async def start(message: Message):
    u = message.from_user
    create_user(u.id, u.username, u.first_name)
    db = get_user(u.id)
    text = (
        f"🎮 <b>SHAMA WORLD</b>\n\n"
        f"Добро пожаловать, <b>{u.first_name}</b>!\n\n"
        f"💰 Баланс: <b>{money(db['balance'])} CW</b>\n"
        f"🎁 Кейсов открыто: <b>{db['cases_opened']}</b>\n\n"
        "Выбирай раздел ниже."
    )
    await message.answer(text, reply_markup=main_menu(), parse_mode="HTML")


@dp.message(Command("balance"))
async def balance_command(message: Message):
    create_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    u = get_user(message.from_user.id)
    await message.answer(
        f"💰 <b>ТВОЙ БАЛАНС</b>\n\n<b>{money(u['balance'])} CW</b>",
        reply_markup=back_menu(), parse_mode="HTML"
    )


@dp.message(Command("bonus"))
async def bonus_command(message: Message):
    create_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    reward = claim_bonus(message.from_user.id)
    if not reward:
        await message.answer("🎁 Бонус уже получен сегодня.")
        return
    u = get_user(message.from_user.id)
    await message.answer(
        f"🎁 <b>ЕЖЕДНЕВНЫЙ БОНУС</b>\n\n"
        f"Ты получил <b>+{money(reward)} CW</b>!\n"
        f"💰 Баланс: <b>{money(u['balance'])} CW</b>",
        reply_markup=back_menu(), parse_mode="HTML"
    )


@dp.callback_query(F.data == "profile")
async def profile(c: CallbackQuery):
    u = get_user(c.from_user.id)
    username = u["username"] or "не указан"
    text = (
        f"👤 <b>ПРОФИЛЬ</b>\n\n"
        f"Имя: <b>{u['first_name']}</b>\n"
        f"Username: @{username}\n\n"
        f"💰 Баланс: <b>{money(u['balance'])} CW</b>\n"
        f"🎁 Кейсов открыто: <b>{u['cases_opened']}</b>\n"
        f"📅 Регистрация: <b>{u['registered_at']}</b>"
    )
    await edit(c, text, stats_menu())
    await c.answer()


@dp.callback_query(F.data == "balance")
async def balance(c: CallbackQuery):
    u = get_user(c.from_user.id)
    await edit(
        c,
        f"💰 <b>ТВОЙ БАЛАНС</b>\n\n<b>{money(u['balance'])} CW</b>\n\n"
        "CW — внутренняя валюта SHAMA WORLD.",
        back_menu()
    )
    await c.answer()


@dp.callback_query(F.data == "bonus")
async def bonus(c: CallbackQuery):
    reward = claim_bonus(c.from_user.id)
    if not reward:
        await c.answer("🎁 Бонус уже получен сегодня!", show_alert=True)
        return
    u = get_user(c.from_user.id)
    await edit(
        c,
        f"🎁 <b>ЕЖЕДНЕВНЫЙ БОНУС</b>\n\n"
        f"Ты получил <b>+{money(reward)} CW</b>!\n"
        f"💰 Баланс: <b>{money(u['balance'])} CW</b>",
        back_menu()
    )
    await c.answer()


@dp.callback_query(F.data == "cases")
async def cases(c: CallbackQuery):
    await edit(
        c,
        "🎁 <b>КЕЙСЫ</b>\n\n"
        "🔥 <b>SHAMA CASE</b>\n"
        "Стоимость: <b>1 000 CW</b>\n\n"
        "⚪ Обычный — 60%\n"
        "🔵 Редкий — 25%\n"
        "🟣 Эпический — 10%\n"
        "🟡 Легендарный — 4%\n"
        "🔴 Мифический — 1%\n\n"
        "CW нельзя купить за реальные деньги — это внутриигровая валюта.",
        cases_menu()
    )
    await c.answer()


@dp.callback_query(F.data == "open_shama_case")
async def open_case(c: CallbackQuery):
    r = open_shama_case(c.from_user.id)
    if r["status"] == "not_enough":
        await c.answer(
            f"Не хватает {money(r['need'])} CW",
            show_alert=True
        )
        return

    text = (
        "🎁 <b>SHAMA CASE</b>\n\n"
        "✨ <b>КЕЙС ОТКРЫТ!</b>\n\n"
        f"{r['rarity']['emoji']} <b>{r['rarity']['name']}</b>\n"
        f"📦 {r['item']['name']}\n"
        f"💎 Ценность: <b>{money(r['item']['value'])} CW</b>\n\n"
        f"💰 Баланс: <b>{money(r['balance'])} CW</b>"
    )
    await edit(c, text, cases_menu())
    await c.answer("Предмет добавлен в инвентарь!")


@dp.callback_query(F.data == "inventory")
async def inventory(c: CallbackQuery):
    items = get_inventory(c.from_user.id)
    if not items:
        text = "🎒 <b>ИНВЕНТАРЬ</b>\n\nПока пуст.\nОткрой первый кейс!"
    else:
        lines = ["🎒 <b>ИНВЕНТАРЬ</b>\n"]
        for x in items:
            lines.append(
                f"{x['emoji']} <b>{x['name']}</b> ×{x['quantity']}\n"
                f"   {x['rarity']} · {money(x['value'])} CW"
            )
        text = "\n".join(lines)
    await edit(c, text, back_menu())
    await c.answer()


@dp.callback_query(F.data == "rating")
async def rating(c: CallbackQuery):
    ps = get_top_players()
    lines = ["🏆 <b>ТОП ИГРОКОВ</b>\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, p in enumerate(ps, 1):
        pref = medals[i - 1] if i <= 3 else f"{i}."
        lines.append(f"{pref} <b>{p['first_name']}</b> — {money(p['balance'])} CW")
    if not ps:
        lines.append("Пока игроков нет.")
    await edit(c, "\n".join(lines), back_menu())
    await c.answer()


@dp.callback_query(F.data == "stats")
async def stats(c: CallbackQuery):
    s = get_stats(c.from_user.id)
    text = (
        "📊 <b>МОЯ СТАТИСТИКА</b>\n\n"
        f"💰 Баланс: <b>{money(s['balance'])} CW</b>\n"
        f"🎁 Кейсов открыто: <b>{s['cases_opened']}</b>\n"
        f"📦 Предметов: <b>{s['items_count']}</b>\n"
        f"💎 Стоимость инвентаря: <b>{money(s['inventory_value'])} CW</b>\n"
        f"🎁 Получено бонусами: <b>{money(s['bonus_total'])} CW</b>\n"
        f"💸 Потрачено на кейсы: <b>{money(s['case_spent'])} CW</b>"
    )
    await edit(c, text, stats_menu())
    await c.answer()


@dp.callback_query(F.data == "history")
async def history(c: CallbackQuery):
    rows = get_transaction_history(c.from_user.id, 10)
    if not rows:
        text = "📜 <b>ИСТОРИЯ</b>\n\nОпераций пока нет."
    else:
        lines = ["📜 <b>ПОСЛЕДНИЕ ОПЕРАЦИИ</b>\n"]
        for r in rows:
            sign = "+" if r["amount"] > 0 else ""
            lines.append(
                f"{r['emoji']} {r['title']}  <b>{sign}{money(r['amount'])} CW</b>\n"
                f"   Баланс: {money(r['balance_after'])} CW"
            )
        text = "\n\n".join(lines)
    await edit(c, text, history_menu())
    await c.answer()


@dp.callback_query(F.data == "home")
async def home(c: CallbackQuery):
    u = get_user(c.from_user.id)
    text = (
        f"🎮 <b>SHAMA WORLD</b>\n\n"
        f"💰 Баланс: <b>{money(u['balance'])} CW</b>\n\n"
        "Выбирай раздел ниже."
    )
    await edit(c, text, main_menu())
    await c.answer()


async def health(request):
    return web.Response(text="SHAMA WORLD v3 is running")


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
