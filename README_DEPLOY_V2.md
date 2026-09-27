# SHAMA WORLD V2 — Render

This build restores the real SHAMA WORLD city artwork and the item/case art from the full project.

## Render
Build: `pip install -r requirements.txt`
Start: `python -m uvicorn routes:app --host 0.0.0.0 --port $PORT`

Environment:
- `BOT_TOKEN` — Telegram bot token
- `WEBAPP_URL` — `https://shama-world.onrender.com/` (or your actual Mini App URL)
- `DATABASE_PATH` — `shama_world.db`

## Important
Replace the old repository contents with this build. Do not leave old `routes.py`, `web/`, `services/`, or `render.yaml` files mixed with this version.
