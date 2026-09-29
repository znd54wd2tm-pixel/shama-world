# SHAMA WORLD — deployment checklist

## Render environment
Set `BOT_TOKEN` as a Render secret.
`WEBAPP_URL` should match the public Mini App URL.
`DATABASE_PATH` should point to the mounted persistent disk, as in `render.yaml`.

## Important
- Do not commit `*.db`, `*.sqlite3*`, `.env`, or `__pycache__`.
- The production SQLite database must live on Render's persistent disk at `/var/data/shama_world.db`.
- Never run destructive database reset commands during deploy.
- `seed_data.py` is intended to be idempotent for catalog/content, while user data stays in the persistent database.
- Keep the existing Render persistent disk attached when deploying a new version.

## Local test
```bash
python -m compileall -q .
pip install -r requirements.txt
uvicorn routes:app --host 0.0.0.0 --port 8000
```

## Release contents
This GitHub-ready package intentionally excludes local runtime databases, test SQLite files, Python bytecode caches, and the nested Render-ready ZIP. The source code and all required web assets remain included.
