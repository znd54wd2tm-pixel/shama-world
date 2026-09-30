# SHAMA WORLD

Telegram Mini App foundation with cases, weighted drops, inventory and SQLite-backed progression.

## Install

```bash
cd .
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env
```

Set only these variables in `.env`:

```env
BOT_TOKEN=
WEBAPP_URL=https://shama-world.onrender.com/
DATABASE_PATH=shama_world.db
```

## Run

```bash
uvicorn routes:app --host 0.0.0.0 --port 8000
python bot.py
```

For local browser testing outside Telegram, use the explicit development app:

```bash
python routes.py --dev
```

The first API startup creates/migrates SQLite and seeds five cases and the current item catalog idempotently. Production routes require a valid Telegram WebApp `initData`; the frontend never chooses an item, chance, balance or XP.

## API

- `GET /api/health`
- `GET /api/me`
- `GET /api/cases`
- `GET /api/cases/{case_id}`
- `POST /api/cases/{case_id}/open`
- `GET /api/inventory`
- `GET /api/inventory/{item_id}`
- `GET /api/balance`
- `POST /api/inventory/sell`
- `GET /api/transactions`
- `GET /api/upgrade/targets?source_item_id=...`
- `POST /api/upgrade/preview`
- `POST /api/upgrade/execute`
- `GET /api/upgrade/history`
- `GET /api/earnings`
- `GET /api/earnings/{system}`
- `POST /api/earnings/{system}/claim`
- `POST /api/earnings/{system}/upgrade`
- `GET /api/earnings/jobs`
- `POST /api/earnings/{kind}/start`
- `POST /api/earnings/jobs/{session_id}/complete`
- `GET /api/market` (also `/api/market/offers`)
- `POST /api/market/buy`
- `GET /api/world` (also `/api/world/locations`)
- `GET /api/profile`
- `GET /api/achievements`
- `GET /api/daily`
- `POST /api/daily/claim`

Opening a case is one SQLite transaction: balance deduction, weighted drop selection from that case's own `case_drops`, `case_openings` history, inventory quantity, XP and statistics are committed together. A per-user non-blocking lock rejects concurrent duplicate clicks while the transaction protects database integrity.

Upgrade chance is calculated only in `services/upgrade.py`: `90 / (target_value / source_value)^1.25`, rounded to one decimal and bounded to 1%-95%. The execute route recalculates the chance from database values and accepts no chance/value from the frontend. Source ownership, target price, request idempotency, inventory changes, XP (+5), user statistics and `upgrade_transactions` are handled in one transaction.

Sales use `services/economy.py`. The backend reads the real item value, validates owned quantity, atomically removes inventory units, adds integer SH, updates sale statistics and writes a `SELL` row to `transactions`. `X-Sell-Request-Id` prevents duplicate confirmation requests from creating a second sale.

## Stage 5 systems

`services/earnings.py` owns Farm, Business and Bank progression. Income is calculated from the server-side `last_claim_at` timestamp with a 24-hour cap, and claims/upgrades are atomic ledger operations. Business unlocks after Farm level 10; Bank unlocks after Business level 20. Courier, Case Factory and Hunt use `earning_sessions`: the server creates the session seed and expiry, and completion can only pay once before expiry.

`services/market.py` maintains one backend-generated four-hour MAC rotation in `market_rotations` and `market_offers`. A purchase validates the active rotation, stock, real price and balance, then deducts SH, adds one inventory unit and records `MARKET_PURCHASE` in the same transaction.

`services/profile.py` exposes profile statistics, achievement progress and one daily UTC bonus. World locations and unlock levels are stored in `world_locations`; all content is seeded idempotently by `seed_data.py`.

The frontend only renders server results. It never supplies balances, prices, rewards, chances or item ownership. Run the API with `--dev` only for local development without Telegram `initData`.

## Render

The included `render.yaml` must live at the repository root and defines one Python web service. It serves FastAPI and the static Mini App from the same origin; the FastAPI lifespan also starts and stops Telegram polling, so a separate background worker is not required.

Create the service from the Blueprint and set `BOT_TOKEN` as a Render secret. `WEBAPP_URL` is set to the canonical Mini App URL. `DATABASE_PATH` points to `/var/data/shama_world.db`, on the service's persistent disk mounted at `/var/data`; this keeps the SQLite database across service restarts and deploys. The Blueprint uses the always-on `starter` plan because a sleeping free instance cannot guarantee a prompt Telegram response or persistent SQLite storage.

At startup, SHAMA WORLD refuses to run on Render if `DATABASE_PATH` is outside `/var/data` or the disk is unavailable. This prevents an accidental deployment from silently creating a fresh, temporary user database. Migrations and catalog seeding run once per process start, do not run per API request, and never delete player accounts, inventory, transactions, progression, or portfolios. Telegram polling starts in the background after persistence is ready, so a slow Telegram Bot API connection cannot block `/health` or the Mini App web server.

The project pins Python 3.12.14 with `.python-version`. The production service command is:

```bash
python -m uvicorn routes:app --host 0.0.0.0 --port $PORT
```

Render supplies `PORT`; the service binds to `0.0.0.0` and serves API, static assets and the Mini App on that port. Telegram `initData` is validated on the backend using `BOT_TOKEN`. The token is never sent to the frontend. Frontend API calls and asset URLs use the same origin, so no localhost address or separate API URL is needed in production.


## V3 UI fixes
- Removed the interactive/3D world viewport from the Mini App. The World tab is now a static city overview with direct section buttons.
- Inventory item taps open the item modal only; the Upgrade screen is opened only by the explicit Upgrade button.
- Upgrade state is cleared when leaving the Upgrade section, so stale source/target cards cannot remain.
- SH Market now uses a dedicated generated artwork set and a curated eight-item rotation.


## V9 stability fixes

- Case result is locked inside a fixed Telegram Mini App modal and cannot push the page downward.
- The dropped item image uses a contained, bounded frame so the artwork stays fully visible.
- Closing the case modal fully resets its stage, reel and result state.
- Upgrade pointer is a real two-phase animation: exactly five complete fast turns, then a separate slow ease-out to a random point inside the server-selected SUCCESS/RISK sector.
- The final pointer position is based on the authoritative server result and displayed only after the animation finishes.
- Leaving any modal now uses one cleanup path, preventing stale item/upgrade/case state.
- Development mode no longer requires a Telegram bot token; production still starts bot polling from the FastAPI lifespan.
- No artificial file-count restriction is applied to this build.


## Deployment sanity

- `render.yaml` is intentionally at the repository root so Render can detect the Blueprint without an extra root directory setting.
- Production SQLite must use `/var/data/shama_world.db` on the Render persistent disk.
- Do not commit a replacement production database over the persistent disk. The bundled `shama_world.db` is only a local/demo database and is not used when `DATABASE_PATH=/var/data/shama_world.db` is configured.
- Keep exactly one Render instance when using the SQLite persistent disk.
