from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
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
            ]
        ]
    )
