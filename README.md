# SHAMA WORLD

Telegram Mini App foundation with cases, weighted drops, inventory and SQLite-backed progression.

## Install

```bash
cd shama_world
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env
```

Set only these variables in `.env`:

```env
BOT_TOKEN=
WEBAPP_URL=https://your-domain.example
DATABASE_PATH=shama_world.db
```

## Run

```bash
uvicorn api.routes:app --host 0.0.0.0 --port 8000
python bot.py
```

For local browser testing outside Telegram, use the explicit development app:

```bash
python -m api.routes --dev
```

The first API startup creates/migrates SQLite and seeds five cases and 25 items idempotently. Production routes require a valid Telegram WebApp `initData`; the frontend never chooses an item, chance, balance or XP.

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

Use the start command below and configure the three environment variables above:

```bash
uvicorn api.routes:app --host 0.0.0.0 --port $PORT
```
