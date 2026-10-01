# Render Free deployment

This version is configured to run without a Render Persistent Disk.

## Render Environment Variables

Keep:
- `BOT_TOKEN` — your Telegram bot token
- `WEBAPP_URL` — `https://shama-world.onrender.com/`

`DATABASE_PATH` is no longer needed. If an old value such as
`/var/data/shama_world.db` remains in Render, the code automatically falls
back to a local SQLite file when `/var/data` is unavailable.

## Deploy

1. Replace the project files in GitHub with the files from this archive.
2. Commit and push.
3. In Render, trigger a new deploy.
4. Wait for `GET /api/health` to become healthy.

## Important

This is the free/no-disk setup. SQLite lives on Render's ephemeral filesystem.
User balances/inventory can be reset after a redeploy or instance replacement.

The application itself no longer refuses to start when `/var/data` is absent.
