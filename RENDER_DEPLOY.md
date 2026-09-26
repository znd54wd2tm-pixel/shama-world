# SHAMA WORLD — Render deployment

This version uses ONE Render Web Service for both:
- FastAPI / Telegram Mini App
- Telegram bot via webhook

## Render
Build Command:
`pip install --upgrade pip && pip install -r requirements.txt`

Start Command:
`uvicorn api.routes:app --host 0.0.0.0 --port $PORT`

Environment variables:
- `BOT_TOKEN` = your Telegram bot token
- `WEBAPP_URL` = the exact public HTTPS URL of this Render Web Service
- `DATABASE_PATH` = `/tmp/shama_world.db`

Example:
`WEBAPP_URL=https://shama-world.onrender.com`

Do NOT create a separate Background Worker for this version.
Do NOT use `python bot.py` as the Web Service start command.

The API starts the Telegram bot with a webhook at:
`/telegram/webhook`

Important:
SQLite in `/tmp` is temporary and is not persistent storage. For production, migrate to PostgreSQL.
