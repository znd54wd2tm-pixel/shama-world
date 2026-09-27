# SHAMA WORLD V2 — GitHub upload order

1. Delete the old project contents from the GitHub repository. Keep `.git` itself; only delete repository files.
2. Upload the contents of `PART1_CODE` first.
3. Upload the contents of `PART2_ASSETS` second.
4. Render must use:
   - Build: `pip install -r requirements.txt`
   - Start: `python -m uvicorn routes:app --host 0.0.0.0 --port $PORT`
5. Environment: `BOT_TOKEN`, `WEBAPP_URL`, `DATABASE_PATH=shama_world.db`.

Do not mix the old `routes.py`, old `web/`, old `services/` or old `render.yaml` with this version.
