from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎁 КЕЙСЫ", callback_data="cases"),
            InlineKeyboardButton(text="🎒 ИНВЕНТАРЬ", callback_data="inventory")
        ],
        [
            InlineKeyboardButton(text="👤 ПРОФИЛЬ", callback_data="profile"),
            InlineKeyboardButton(text="💰 БАЛАНС", callback_data="balance")
        ],
        [
            InlineKeyboardButton(text="🎁 БОНУС", callback_data="bonus"),
            InlineKeyboardButton(text="🏆 РЕЙТИНГ", callback_data="rating")
        ],
        [
            InlineKeyboardButton(text="📊 СТАТИСТИКА", callback_data="stats"),
            InlineKeyboardButton(text="📜 ИСТОРИЯ", callback_data="history")
        ]
    ])


def back_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ ГЛАВНОЕ МЕНЮ", callback_data="home")]
    ])


def cases_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🎁 ОТКРЫТЬ SHAMA CASE — 1 000 CW",
            callback_data="open_shama_case"
        )],
        [InlineKeyboardButton(
            text="⬅️ ГЛАВНОЕ МЕНЮ",
            callback_data="home"
        )]
    ])


def stats_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 СТАТИСТИКА", callback_data="stats")],
        [InlineKeyboardButton(text="📜 ИСТОРИЯ", callback_data="history")],
        [InlineKeyboardButton(text="⬅️ ГЛАВНОЕ МЕНЮ", callback_data="home")]
    ])


def history_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 СТАТИСТИКА", callback_data="stats")],
        [InlineKeyboardButton(text="⬅️ ГЛАВНОЕ МЕНЮ", callback_data="home")]
    ])
