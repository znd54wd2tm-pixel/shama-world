import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN environment variable is not set. "
        "Add BOT_TOKEN in Render -> Environment."
    )
