"""FastAPI application and case/inventory routes."""

from __future__ import annotations

import argparse
import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from config import ConfigError, get_settings, require_persistent_database
from database import init_db
from seed_data import seed_content
from services.catalog import get_case, get_inventory_item, list_cases, list_inventory
from services.game import GameError, open_case
from services.economy import EconomyError, sell_item, transaction_history
from services.earnings import EarningsError, earnings_status, claim_passive, upgrade_passive, start_job, complete_job
from services.market import MarketError, market_data, buy_offer
from services.world import world_state
from services.profile import ProfileError, profile, achievements, daily_status, claim_daily
from services.upgrade import UpgradeError, execute_upgrade, preview_upgrade, target_options, upgrade_history
from services.enterprise import (
    EnterpriseError, enterprise_status, upgrade_enterprise, buy_animals,
    buy_computers, hire_workers, buy_advertising, claim_enterprise_income,
    bank_market, upgrade_bank_attraction, collect_bank_profit,
    process_bank_customer, trade_stock, trade_crypto, claim_bank_dividends,
    withdraw_bank_profit,
)
from services.banking import SavingsError, savings_status, move_savings, bank_transactions
from services.telegram_auth import TelegramAuthError, validate_telegram_init_data
from services.users import get_or_create_user

def _resolve_web_dir() -> Path:
    """Resolve the checked-in Mini App from the repository root."""
    web_dir = Path(__file__).resolve().parent / "web"
    if not (web_dir / "index.html").is_file():
        raise RuntimeError(f"Mini App frontend not found: {web_dir / 'index.html'}")
    return web_dir


WEB_DIR = _resolve_web_dir()


def _init_data_from_request(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("tma "):
        return authorization[4:].strip()
    return request.headers.get("X-Telegram-Init-Data", "").strip()


def create_app(*, dev_mode: bool = False) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        started_at = time.perf_counter()
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        require_persistent_database(settings)
        init_db(settings.database_path)
        seed_content(settings.database_path, ensure_schema=False)
        application.state.database_path = settings.database_path
        application.state.persistence_ready = True
        application.state.startup_seconds = round(time.perf_counter() - started_at, 3)
        print(
            f"SHAMA WORLD: persistence ready in {application.state.startup_seconds:.3f}s "
            f"at {settings.database_path}",
            flush=True,
        )

        telegram_application = None
        stop_polling_fn = None
        bot_task: asyncio.Task[None] | None = None

        async def start_telegram_in_background() -> None:
            """Keep an unavailable Telegram transport from blocking HTTP readiness."""

            nonlocal telegram_application, stop_polling_fn
            try:
                from bot import build_application, start_polling, stop_polling
                stop_polling_fn = stop_polling
                telegram_application = build_application()
                await start_polling(telegram_application)
                print("SHAMA WORLD: Telegram bot is online", flush=True)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                # HTTP health and the Mini App remain available; Telegram will
                # retry after the next process restart instead of holding the
                # whole Render service in the startup state.
                print(f"SHAMA WORLD: Telegram polling startup error: {error}", flush=True)

        try:
            # Start serving after persistence is ready. Telegram's network
            # initialization happens independently, so a slow Bot API call
            # cannot make Render report a five-minute application startup.
            if not dev_mode:
                bot_task = asyncio.create_task(start_telegram_in_background(), name="shama-telegram-polling")
            yield
        finally:
            if telegram_application is not None:
                try:
                    if stop_polling_fn is not None:
                        await stop_polling_fn(telegram_application)
                except Exception as error:
                    print(f"SHAMA WORLD: Telegram shutdown error: {error}", flush=True)
            if bot_task is not None and not bot_task.done():
                bot_task.cancel()
                await asyncio.gather(bot_task, return_exceptions=True)

    application = FastAPI(title="SHAMA WORLD API", version="2.0.0", lifespan=lifespan)

    @application.exception_handler(ConfigError)
    async def config_error_handler(_: Request, error: ConfigError) -> JSONResponse:
        return JSONResponse(status_code=500, content={"success": False, "error": str(error), "detail": str(error)})

    @application.exception_handler(HTTPException)
    async def http_error_handler(_: Request, error: HTTPException) -> JSONResponse:
        message = str(error.detail)
        return JSONResponse(status_code=error.status_code, content={"success": False, "error": message, "detail": message})

    @application.exception_handler(GameError)
    async def game_error_handler(_: Request, error: GameError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"success": False, "error": str(error), "detail": str(error)})

    @application.exception_handler(UpgradeError)
    async def upgrade_error_handler(_: Request, error: UpgradeError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"success": False, "error": str(error), "detail": str(error)})

    @application.exception_handler(EconomyError)
    async def economy_error_handler(_: Request, error: EconomyError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"success": False, "error": str(error), "detail": str(error)})

    @application.exception_handler(EarningsError)
    async def earnings_error_handler(_: Request, error: EarningsError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"success": False, "error": str(error), "detail": str(error)})

    @application.exception_handler(MarketError)
    async def market_error_handler(_: Request, error: MarketError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"success": False, "error": str(error), "detail": str(error)})

    @application.exception_handler(ProfileError)
    async def profile_error_handler(_: Request, error: ProfileError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"success": False, "error": str(error), "detail": str(error)})

    @application.exception_handler(EnterpriseError)
    async def enterprise_error_handler(_: Request, error: EnterpriseError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"success": False, "error": str(error), "detail": str(error)})

    @application.exception_handler(SavingsError)
    async def savings_error_handler(_: Request, error: SavingsError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"success": False, "error": str(error), "detail": str(error)})

    def current_user(request: Request) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        try:
            telegram_user = validate_telegram_init_data(
                _init_data_from_request(request), settings.bot_token, allow_dev=dev_mode
            )
        except TelegramAuthError as error:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error
        return get_or_create_user(settings.database_path, telegram_user)

    @application.get("/health")
    @application.get("/api/health")
    async def health() -> dict[str, str]:
        # Deliberately performs no authentication, database work, seeding or
        # external I/O. Render uses this endpoint to see readiness quickly.
        return {"status": "ok"}

    @application.get("/api/me")
    async def me(user: dict = Depends(current_user)) -> dict:
        return {key: user[key] for key in (
            "id", "telegram_id", "username", "first_name", "balance", "xp", "level", "cases_opened", "items_collected",
            "upgrades_total", "upgrades_success", "upgrades_failed", "total_items_sold", "total_sh_earned_from_sales"
            , "farm_level", "business_level", "bank_level", "last_daily_claim"
        )}

    @application.get("/api/balance")
    async def balance(user: dict = Depends(current_user)) -> dict:
        return {"balance": int(user["balance"])}

    @application.get("/api/cases")
    async def cases() -> dict:
        settings = get_settings(require_bot=False, require_webapp=False)
        return {"cases": list_cases(settings.database_path)}

    @application.get("/api/cases/{case_id}")
    async def case_details(case_id: int) -> dict:
        settings = get_settings(require_bot=False, require_webapp=False)
        result = get_case(settings.database_path, case_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Кейс не найден")
        return result

    @application.post("/api/cases/{case_id}/open")
    async def open_case_route(
        case_id: int,
        user: dict = Depends(current_user),
        request_id: str | None = Header(default=None, alias="X-Opening-Request-Id"),
    ) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return open_case(settings.database_path, user["id"], case_id, request_id=request_id)

    @application.get("/api/inventory")
    async def inventory(user: dict = Depends(current_user)) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return {"items": list_inventory(settings.database_path, user["id"]), "balance": user["balance"]}

    @application.post("/api/inventory/sell")
    async def sell_inventory_item(
        payload: dict = Body(...),
        user: dict = Depends(current_user),
        request_id: str | None = Header(default=None, alias="X-Sell-Request-Id"),
    ) -> dict:
        try:
            item_id = payload["item_id"]
            quantity = payload["quantity"]
        except (KeyError, TypeError) as error:
            raise HTTPException(status_code=400, detail="item_id и quantity обязательны") from error
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return sell_item(settings.database_path, user["id"], item_id, quantity, request_id=request_id)

    @application.get("/api/transactions")
    async def transactions(user: dict = Depends(current_user)) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return {"transactions": transaction_history(settings.database_path, user["id"])}

    @application.get("/api/earnings")
    async def earnings(user: dict = Depends(current_user)) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return earnings_status(settings.database_path, user["id"])

    @application.get("/api/earnings/{system}")
    async def earnings_system(system: str, user: dict = Depends(current_user)) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        if system.lower() == "jobs":
            return {"jobs": earnings_status(settings.database_path, user["id"])["jobs"]}
        if system.lower() in {"courier", "factory", "hunt"}:
            return {"kind": system.upper(), "jobs": earnings_status(settings.database_path, user["id"])["jobs"]}
        result = earnings_status(settings.database_path, user["id"])
        if system.lower() not in result["systems"]:
            raise HTTPException(status_code=404, detail="Система заработка не найдена")
        return result["systems"][system.lower()]

    @application.post("/api/earnings/{system}/claim")
    async def earnings_claim(
        system: str,
        user: dict = Depends(current_user),
        request_id: str | None = Header(default=None, alias="X-Earnings-Request-Id"),
    ) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return claim_passive(settings.database_path, user["id"], system.lower(), request_id=request_id)

    @application.post("/api/earnings/{system}/upgrade")
    async def earnings_upgrade(
        system: str,
        user: dict = Depends(current_user),
        request_id: str | None = Header(default=None, alias="X-Earnings-Request-Id"),
    ) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return upgrade_passive(settings.database_path, user["id"], system.lower(), request_id=request_id)

    @application.get("/api/enterprise")
    async def enterprise(user: dict = Depends(current_user)) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return enterprise_status(settings.database_path, user["id"])

    @application.post("/api/enterprise/{system}/upgrade")
    async def enterprise_upgrade(
        system: str,
        user: dict = Depends(current_user),
        request_id: str | None = Header(default=None, alias="X-Enterprise-Request-Id"),
    ) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return upgrade_enterprise(settings.database_path, user["id"], system, request_id=request_id)

    @application.post("/api/enterprise/farm/animals")
    async def enterprise_buy_animals(
        payload: dict = Body(...),
        user: dict = Depends(current_user),
        request_id: str | None = Header(default=None, alias="X-Enterprise-Request-Id"),
    ) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return buy_animals(settings.database_path, user["id"], str(payload.get("animal", "")), payload.get("quantity", 1), request_id=request_id)

    @application.post("/api/enterprise/business/computers")
    async def enterprise_buy_computers(
        payload: dict = Body(...),
        user: dict = Depends(current_user),
        request_id: str | None = Header(default=None, alias="X-Enterprise-Request-Id"),
    ) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return buy_computers(
            settings.database_path, user["id"], payload.get("quantity", 1),
            improved=payload.get("improved", False) is True,
            upgrade_existing=payload.get("upgrade_existing", False) is True,
            request_id=request_id,
        )

    @application.post("/api/enterprise/business/workers")
    async def enterprise_hire_workers(
        payload: dict = Body(...),
        user: dict = Depends(current_user),
        request_id: str | None = Header(default=None, alias="X-Enterprise-Request-Id"),
    ) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return hire_workers(settings.database_path, user["id"], payload.get("quantity", 1), request_id=request_id)

    @application.post("/api/enterprise/business/advertising")
    async def enterprise_advertising(
        payload: dict = Body(...),
        user: dict = Depends(current_user),
        request_id: str | None = Header(default=None, alias="X-Enterprise-Request-Id"),
    ) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return buy_advertising(settings.database_path, user["id"], str(payload.get("campaign", "")), request_id=request_id)

    @application.post("/api/enterprise/{system}/claim")
    async def enterprise_claim(
        system: str,
        user: dict = Depends(current_user),
        request_id: str | None = Header(default=None, alias="X-Enterprise-Request-Id"),
    ) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return claim_enterprise_income(settings.database_path, user["id"], system.lower(), request_id=request_id)

    @application.get("/api/enterprise/bank/market")
    async def enterprise_bank_market(
        period: str = Query(default="1D"),
        user: dict = Depends(current_user),
    ) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return bank_market(settings.database_path, user["id"], period)

    @application.post("/api/enterprise/bank/attraction/upgrade")
    async def enterprise_bank_attraction(
        user: dict = Depends(current_user),
        request_id: str | None = Header(default=None, alias="X-Bank-Request-Id"),
    ) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return upgrade_bank_attraction(settings.database_path, user["id"], request_id=request_id)

    @application.post("/api/enterprise/bank/profit/collect")
    async def enterprise_bank_collect(
        user: dict = Depends(current_user),
        request_id: str | None = Header(default=None, alias="X-Bank-Request-Id"),
    ) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return collect_bank_profit(settings.database_path, user["id"], request_id=request_id)

    @application.post("/api/enterprise/bank/customer")
    async def enterprise_bank_customer(
        user: dict = Depends(current_user),
        request_id: str | None = Header(default=None, alias="X-Bank-Request-Id"),
    ) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return process_bank_customer(settings.database_path, user["id"], request_id=request_id)

    @application.post("/api/enterprise/bank/dividends/claim")
    async def enterprise_bank_dividends(
        user: dict = Depends(current_user),
        request_id: str | None = Header(default=None, alias="X-Bank-Request-Id"),
    ) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return claim_bank_dividends(settings.database_path, user["id"], request_id=request_id)

    @application.post("/api/enterprise/bank/withdraw")
    async def enterprise_bank_withdraw(
        payload: dict = Body(...),
        user: dict = Depends(current_user),
        request_id: str | None = Header(default=None, alias="X-Bank-Request-Id"),
    ) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return withdraw_bank_profit(settings.database_path, user["id"], payload.get("amount", 0), request_id=request_id)

    @application.post("/api/enterprise/bank/stocks/{code}/trade")
    async def enterprise_stock_trade(
        code: str,
        payload: dict = Body(...),
        user: dict = Depends(current_user),
        request_id: str | None = Header(default=None, alias="X-Bank-Request-Id"),
    ) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return trade_stock(settings.database_path, user["id"], code, str(payload.get("side", "")), payload.get("quantity", 0), payload.get("price"), request_id=request_id)

    @application.post("/api/enterprise/bank/crypto/{code}/trade")
    async def enterprise_crypto_trade(
        code: str,
        payload: dict = Body(...),
        user: dict = Depends(current_user),
        request_id: str | None = Header(default=None, alias="X-Bank-Request-Id"),
    ) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return trade_crypto(settings.database_path, user["id"], code, str(payload.get("side", "")), payload.get("quantity", 0), payload.get("price"), request_id=request_id)

    @application.get("/api/enterprise/bank/savings")
    async def enterprise_bank_savings(user: dict = Depends(current_user)) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return {"account": savings_status(settings.database_path, user["id"])}

    @application.get("/api/enterprise/bank/transactions")
    async def enterprise_bank_transactions(user: dict = Depends(current_user)) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return {"transactions": bank_transactions(settings.database_path, user["id"])}

    @application.post("/api/enterprise/bank/savings/{direction}")
    async def enterprise_bank_savings_move(
        direction: str,
        payload: dict = Body(...),
        user: dict = Depends(current_user),
        request_id: str | None = Header(default=None, alias="X-Bank-Request-Id"),
    ) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return move_savings(
            settings.database_path, user["id"], direction, payload.get("amount", 0), request_id=request_id
        )

    @application.get("/api/earnings/jobs")
    async def earning_jobs(user: dict = Depends(current_user)) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return {"jobs": earnings_status(settings.database_path, user["id"])["jobs"]}

    @application.post("/api/earnings/{kind}/start")
    async def earning_job_start(kind: str, user: dict = Depends(current_user)) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return start_job(settings.database_path, user["id"], kind)

    @application.post("/api/earnings/jobs/{session_id}/complete")
    async def earning_job_complete(session_id: int, user: dict = Depends(current_user)) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return complete_job(settings.database_path, user["id"], session_id)

    @application.get("/api/market")
    @application.get("/api/market/offers")
    async def market(user: dict = Depends(current_user)) -> dict:
        settings = get_settings(require_bot=False, require_webapp=False)
        return market_data(settings.database_path, user["id"])

    @application.post("/api/market/buy")
    async def market_buy(
        payload: dict = Body(...), user: dict = Depends(current_user),
        request_id: str | None = Header(default=None, alias="X-Market-Request-Id"),
    ) -> dict:
        try:
            offer_id = payload["offer_id"]
            quantity = payload.get("quantity", 1)
        except (KeyError, TypeError) as error:
            raise HTTPException(status_code=400, detail="offer_id обязателен") from error
        if isinstance(offer_id, bool) or not isinstance(offer_id, int):
            raise HTTPException(status_code=400, detail="offer_id должен быть целым числом")
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return buy_offer(settings.database_path, user["id"], offer_id, quantity, request_id=request_id)

    @application.get("/api/world")
    async def world(user: dict = Depends(current_user)) -> dict:
        settings = get_settings(require_bot=False, require_webapp=False)
        return world_state(settings.database_path, user["id"])

    @application.get("/api/world/locations")
    async def world_locations(user: dict = Depends(current_user)) -> dict:
        settings = get_settings(require_bot=False, require_webapp=False)
        return world_state(settings.database_path, user["id"])

    @application.get("/api/profile")
    async def profile_route(user: dict = Depends(current_user)) -> dict:
        settings = get_settings(require_bot=False, require_webapp=False)
        return profile(settings.database_path, user["id"])

    @application.get("/api/achievements")
    async def achievements_route(user: dict = Depends(current_user)) -> dict:
        settings = get_settings(require_bot=False, require_webapp=False)
        return {"achievements": achievements(settings.database_path, user["id"])}

    @application.get("/api/daily")
    async def daily_route(user: dict = Depends(current_user)) -> dict:
        settings = get_settings(require_bot=False, require_webapp=False)
        return daily_status(settings.database_path, user["id"])

    @application.post("/api/daily/claim")
    async def daily_claim_route(user: dict = Depends(current_user)) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return claim_daily(settings.database_path, user["id"])

    @application.get("/api/inventory/{item_id}")
    async def inventory_item(item_id: int, user: dict = Depends(current_user)) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        result = get_inventory_item(settings.database_path, user["id"], item_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Предмет не найден в инвентаре")
        return result

    def upgrade_ids(payload: dict) -> tuple[int, int]:
        try:
            return int(payload["source_item_id"]), int(payload["target_item_id"])
        except (KeyError, TypeError, ValueError) as error:
            raise HTTPException(status_code=400, detail="source_item_id и target_item_id обязательны") from error

    @application.get("/api/upgrade/targets")
    async def upgrade_targets(source_item_id: int = Query(...), user: dict = Depends(current_user)) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return {"items": target_options(settings.database_path, user["id"], source_item_id)}

    @application.post("/api/upgrade/preview")
    async def upgrade_preview(payload: dict = Body(...), user: dict = Depends(current_user)) -> dict:
        source_id, target_id = upgrade_ids(payload)
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return preview_upgrade(settings.database_path, user["id"], source_id, target_id)

    @application.post("/api/upgrade/execute")
    async def upgrade_execute(
        payload: dict = Body(...),
        user: dict = Depends(current_user),
        request_id: str | None = Header(default=None, alias="X-Upgrade-Request-Id"),
    ) -> dict:
        source_id, target_id = upgrade_ids(payload)
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return execute_upgrade(settings.database_path, user["id"], source_id, target_id, request_id=request_id)

    @application.get("/api/upgrade/history")
    async def upgrade_history_route(user: dict = Depends(current_user)) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return {"transactions": upgrade_history(settings.database_path, user["id"])}

    application.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
    return application


app = create_app()
dev_app = create_app(dev_mode=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run SHAMA WORLD API")
    parser.add_argument("--dev", action="store_true", help="allow local development user")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    import uvicorn
    uvicorn.run("routes:dev_app" if args.dev else "routes:app", host=args.host, port=args.port, reload=False)
