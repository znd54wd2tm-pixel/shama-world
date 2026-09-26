"""Telegram bot entry point."""

from __future__ import annotations

import sys

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

try:  # Supports both `python bot.py` and `python -m shama_world.bot`.
    from config import ConfigError, get_settings
except ImportError:  # pragma: no cover - exercised when imported as a package.
    from .config import ConfigError, get_settings


MINI_APP_URL = "https://shama-world.onrender.com/"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start with a real Telegram Mini App button."""

    keyboard = [[InlineKeyboardButton("🎮 ОТКРЫТЬ SHAMA WORLD", web_app=WebAppInfo(url=MINI_APP_URL))]]
    message = "SHAMA WORLD\n\nДобро пожаловать в SHAMA WORLD."
    if update.message:
        await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard))


def build_application() -> Application:
    settings = get_settings(require_bot=True, require_webapp=False)
    application = Application.builder().token(settings.bot_token).build()
    application.add_handler(CommandHandler("start", start))
    return application



async def start_polling(application: Application) -> None:
    """Start the Telegram bot inside an already-running asyncio application.

    This is used by the single Render Web Service so the bot can run alongside
    FastAPI without requiring a separate paid Background Worker.
    """
    await application.initialize()
    await application.start()
    if application.updater is None:
        raise RuntimeError("Telegram updater is not available")
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    print("Telegram bot polling started", flush=True)


async def stop_polling(application: Application) -> None:
    """Stop the Telegram bot cleanly during FastAPI shutdown."""
    if application.updater is not None:
        await application.updater.stop()
    if application.running:
        await application.stop()
    await application.shutdown()
    print("Telegram bot polling stopped", flush=True)

def main() -> None:
    try:
        application = build_application()
    except ConfigError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from error
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
