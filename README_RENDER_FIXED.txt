SHAMA WORLD — Render deployment

Repository structure:
bot.py
api_server.py
database.py
config.py
requirements.txt
render.yaml
web/index.html
web/assets/...

Render:
Build Command: pip install -r requirements.txt
Start Command: python bot.py

Required Environment Variable:
BOT_TOKEN = Telegram bot token

RENDER_EXTERNAL_URL is provided by Render automatically.

IMPORTANT:
- Upload ALL backend files together.
- Keep web/index.html inside the web folder.
- Do not upload BOT_TOKEN to GitHub.
