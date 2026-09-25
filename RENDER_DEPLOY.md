# SHAMA WORLD — Render

This archive is configured for two Render services.

## 1) Web Service
Build Command:
`pip install --upgrade pip && pip install -r requirements.txt`

Start Command:
`uvicorn api.routes:app --host 0.0.0.0 --port $PORT`

Environment:
- BOT_TOKEN = your Telegram bot token
- WEBAPP_URL = the public HTTPS URL of this Web Service
- DATABASE_PATH = /tmp/shama_world.db

## 2) Background Worker
Build Command:
`pip install --upgrade pip && pip install -r requirements.txt`

Start Command:
`python bot.py`

Environment:
- BOT_TOKEN = your Telegram bot token
- WEBAPP_URL = the public HTTPS URL of the Web Service
- DATABASE_PATH = /tmp/shama_world.db

Important:
- Do not put `python bot.py` in the Web Service Start Command.
- Do not put the uvicorn command in the Worker Start Command.
- Do not add an environment variable named `TOOKEN_API_KEY`; this project does not require it.
- SQLite in /tmp is only suitable for temporary deployment/testing. Use PostgreSQL for persistent production data.
