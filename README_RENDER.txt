SHAMA WORLD v14.1 — Render

Start command:
python bot.py

Required Environment Variable:
BOT_TOKEN=your_telegram_bot_token

Important:
- The Mini App explicitly loads Telegram WebApp JS so Telegram initData is available to the API.
- API requests remain protected by Telegram initData validation.
- Keep BOT_TOKEN only in Render Environment Variables. Do not commit it to GitHub.

This build was checked for Python syntax, JavaScript syntax, API route availability, Telegram init-data authentication, farm/market/collections endpoints, case opening and upgrade options.


V14.1 additions:
- Pending case drops can be recovered after reload.
- Item drops require an explicit SAVE or UPGRADE action.
- Market listing uses an in-app quantity/price modal (no browser prompt).
- Case opening and sale/listing actions have duplicate-submit protection.
