# Render deployment

## Web Service
Build:
`pip install -r requirements.txt`

Start:
`uvicorn api.routes:app --host 0.0.0.0 --port $PORT`

## Background Worker
Build:
`pip install -r requirements.txt`

Start:
`python bot.py`

## Environment variables
- `BOT_TOKEN` — Telegram bot token
- `WEBAPP_URL` — public HTTPS URL of the Web Service
- `DATABASE_PATH` — `shama_world.db`

Do not add `TOOKEN_API_KEY`; this project does not use it.

The included `render.yaml` describes the Web Service and Worker.
