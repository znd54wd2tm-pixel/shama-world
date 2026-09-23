SHAMA WORLD v6 — Render fixed build

GitHub structure:
bot.py
api_server.py
database.py
config.py
requirements.txt
web/index.html
web/assets/.gitkeep

Render:
Build Command: pip install -r requirements.txt
Start Command: python bot.py

Environment variable:
BOT_TOKEN = your Telegram bot token

Important:
- Do not put BOT_TOKEN into GitHub.
- RENDER_EXTERNAL_URL is provided by Render automatically.
- Open the Mini App from Telegram using the bot's /start button.
