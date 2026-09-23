SHAMA WORLD — Render-ready project

GitHub root must contain:
bot.py
api_server.py
database.py
config.py
requirements.txt
render.yaml
web/index.html
web/assets/.gitkeep

Render:
Build Command: pip install -r requirements.txt
Start Command: python bot.py
Health Check: /api/health

Required Environment Variable:
BOT_TOKEN = token from BotFather

RENDER_EXTERNAL_URL is used automatically by the bot to build the Mini App URL.

IMPORTANT:
Do not upload BOT_TOKEN to GitHub.
Upload the CONTENTS of this folder to the ROOT of the GitHub repository.
Do not upload the folder itself as a nested directory.
