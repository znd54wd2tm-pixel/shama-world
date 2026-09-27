import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
WEB_APP_URL = os.getenv("WEB_APP_URL", "").strip() or (f"{RENDER_EXTERNAL_URL}/app" if RENDER_EXTERNAL_URL else "http://localhost:10000/app")
