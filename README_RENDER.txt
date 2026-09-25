SHAMA WORLD v19.0 — Render

Start command:
python bot.py

Required Environment Variable:
BOT_TOKEN=your_telegram_bot_token

Important:
- The Mini App explicitly loads Telegram WebApp JS so Telegram initData is available to the API.
- API requests remain protected by Telegram initData validation.
- Keep BOT_TOKEN only in Render Environment Variables. Do not commit it to GitHub.

For the current audit, Python and inline JavaScript syntax plus SQLite game flows were checked. Full API and Telegram runtime checks require installing `requirements.txt` and setting `BOT_TOKEN` in Render Environment Variables.


V15.0 additions:
- Pending case drops can be recovered after reload.
- Item drops require an explicit SAVE or UPGRADE action.
- Market listing uses an in-app quantity/price modal (no browser prompt).
- Case opening and sale/listing actions have duplicate-submit protection.
