import os
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, Update
from aiogram.exceptions import TelegramBadRequest

from config import BOT_TOKEN
from database import init_db, create_user, get_user, claim_bonus, get_inventory, open_shama_case, get_top_players
from keyboards import main_menu, cases_menu, back_menu

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


async def safe_edit(callback: CallbackQuery, text: str, markup, parse_mode="HTML"):
    try:
        await callback.message.edit_text(
            text, reply_markup=markup, parse_mode=parse_mode
        )
    except TelegramBadRequest as e:
        # Telegram returns "message is not modified" when the user
        # presses the same button while the message already has
        # exactly the same text and keyboard.
        if "message is not modified" not in str(e):
            raise


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


@dp.callback_query(F.data == "profile")
async def profile(c: CallbackQuery):
    u = get_user(c.from_user.id)
    if not u:
        await c.answer("Сначала нажми /start", show_alert=True)
        return
    username = u["username"] or "не указан"
    text = (
        f"👤 <b>ПРОФИЛЬ</b>\n\n"
        f"Имя: <b>{u['first_name']}</b>\n"
        f"Username: @{username}\n"
        f"ID: <code>{u['telegram_id']}</code>\n\n"
        f"💰 Баланс: <b>{u['balance']:,} CW</b>\n"
        f"🎁 Кейсов открыто: <b>{u['cases_opened']}</b>\n"
        f"📅 Регистрация: <b>{u['registered_at']}</b>"
    ).replace(",", " ")
    await safe_edit(c, text, back_menu())
    await c.answer()


@dp.callback_query(F.data == "balance")
async def balance(c: CallbackQuery):
    u = get_user(c.from_user.id)
    await safe_edit(
        c,
        f"💰 <b>ТВОЙ БАЛАНС</b>\n\n<b>{u['balance']:,} CW</b>".replace(",", " "),
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
    text = (
        f"🎁 <b>ЕЖЕДНЕВНЫЙ БОНУС</b>\n\n"
        f"Ты получил <b>+{reward:,} CW</b>!\n"
        f"💰 Баланс: <b>{u['balance']:,} CW</b>"
    ).replace(",", " ")
    await safe_edit(c, text, back_menu())
    await c.answer()


@dp.callback_query(F.data == "cases")
async def cases(c: CallbackQuery):
    text = (
        "🎁 <b>КЕЙСЫ</b>\n\n"
        "🔥 <b>SHAMA CASE</b>\n"
        "Стоимость: <b>1 000 CW</b>\n\n"
        "⚪ Обычный — 60%\n"
        "🔵 Редкий — 25%\n"
        "🟣 Эпический — 10%\n"
        "🟡 Легендарный — 4%\n"
        "🔴 Мифический — 1%"
    )
    await safe_edit(c, text, cases_menu())
    await c.answer()


@dp.callback_query(F.data == "open_shama_case")
async def open_case(c: CallbackQuery):
    r = open_shama_case(c.from_user.id)
    if r["status"] == "not_enough":
        await c.answer(
            f"Не хватает {r['need']:,} CW".replace(",", " "),
            show_alert=True
        )
        return

    text = (
        f"🎁 <b>SHAMA CASE</b>\n\n"
        "✨ <b>КЕЙС ОТКРЫТ!</b>\n\n"
        f"{r['rarity']['emoji']} <b>{r['rarity']['name']}</b>\n"
        f"📦 {r['item']['name']}\n"
        f"💎 Ценность: <b>{r['item']['value']:,} CW</b>\n\n"
        f"💰 Баланс: <b>{r['balance']:,} CW</b>"
    ).replace(",", " ")
    await safe_edit(c, text, cases_menu())
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
                f"   {x['rarity']} · {x['value']:,} CW".replace(",", " ")
            )
        text = "\n".join(lines)
    await safe_edit(c, text, back_menu())
    await c.answer()


@dp.callback_query(F.data == "rating")
async def rating(c: CallbackQuery):
    ps = get_top_players()
    lines = ["🏆 <b>ТОП ИГРОКОВ</b>\n"]
    medals = ["🥇", "🥈", "🥉"]
    if not ps:
        lines.append("Пока здесь никого нет.")
    else:
        for i, p in enumerate(ps, 1):
            pref = medals[i - 1] if i <= 3 else f"{i}."
            lines.append(
                f"{pref} <b>{p['first_name']}</b> — {p['balance']:,} CW".replace(",", " ")
            )
    await safe_edit(c, "\n".join(lines), back_menu())
    await c.answer()


@dp.callback_query(F.data == "home")
async def home(c: CallbackQuery):
    u = get_user(c.from_user.id)
    text = (
        f"🎮 <b>SHAMA WORLD</b>\n\n"
        f"💰 Баланс: <b>{u['balance']:,} CW</b>\n\n"
        "Выбирай раздел ниже."
    ).replace(",", " ")
    await safe_edit(c, text, main_menu())
    await c.answer()


async def health(request):
    return web.Response(text="SHAMA WORLD v2.0 is running")


async def on_startup(app):
    init_db()
    await bot.set_webhook(f"{os.environ['RENDER_EXTERNAL_URL']}/webhook")


async def on_cleanup(app):
    await bot.delete_webhook()
    await bot.session.close()


async def webhook(request):
    update = Update.model_validate(await request.json())
    await dp.feed_update(bot, update)
    return web.Response(text="OK")


def main():
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_post("/webhook", webhook)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    web.run_app(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "10000"))
    )


if __name__ == "__main__":
    main()
