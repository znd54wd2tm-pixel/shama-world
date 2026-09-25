"""Telegram bot entry point."""

from __future__ import annotations

import sys

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

try:  # Supports both `python bot.py` and `python -m shama_world.bot`.
    from config import ConfigError, get_settings
except ImportError:  # pragma: no cover - exercised when imported as a package.
    from .config import ConfigError, get_settings


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start with a real Telegram Mini App button."""

    settings = get_settings(require_bot=True, require_webapp=True)
    keyboard = [[InlineKeyboardButton("ОТКРЫТЬ SHAMA WORLD", web_app=WebAppInfo(url=settings.webapp_url))]]
    message = "SHAMA WORLD\n\nДобро пожаловать в SHAMA WORLD."
    if update.message:
        await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard))


def build_application() -> Application:
    settings = get_settings(require_bot=True, require_webapp=True)
    application = Application.builder().token(settings.bot_token).build()
    application.add_handler(CommandHandler("start", start))
    return application


def main() -> None:
    try:
        application = build_application()
    except ConfigError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from error
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
