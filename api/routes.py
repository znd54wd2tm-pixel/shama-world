"""FastAPI application and case/inventory routes."""

from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

try:
    from config import ConfigError, get_settings
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
    from services.telegram_auth import TelegramAuthError, validate_telegram_init_data
    from services.users import get_or_create_user
except ImportError:  # pragma: no cover
    from ..config import ConfigError, get_settings
    from ..database import init_db
    from ..seed_data import seed_content
    from ..services.catalog import get_case, get_inventory_item, list_cases, list_inventory
    from ..services.game import GameError, open_case
    from ..services.economy import EconomyError, sell_item, transaction_history
    from ..services.earnings import EarningsError, earnings_status, claim_passive, upgrade_passive, start_job, complete_job
    from ..services.market import MarketError, market_data, buy_offer
    from ..services.world import world_state
    from ..services.profile import ProfileError, profile, achievements, daily_status, claim_daily
    from ..services.upgrade import UpgradeError, execute_upgrade, preview_upgrade, target_options, upgrade_history
    from ..services.telegram_auth import TelegramAuthError, validate_telegram_init_data
    from ..services.users import get_or_create_user


def _resolve_web_dir() -> Path:
    """Find the checked-in Mini App relative to this module, independent of cwd."""
    module_path = Path(__file__).resolve()
    candidates = (
        module_path.parent.parent / "web",
        module_path.parent.parent.parent / "web",
        module_path.parent / "web",
    )
    checked: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in checked:
            continue
        checked.add(resolved)
        if (resolved / "index.html").is_file():
            return resolved
    paths = ", ".join(str(path) for path in checked)
    raise RuntimeError(f"Mini App frontend not found (expected index.html in one of: {paths})")


WEB_DIR = _resolve_web_dir()


def _init_data_from_request(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("tma "):
        return authorization[4:].strip()
    return request.headers.get("X-Telegram-Init-Data", "").strip()


def create_app(*, dev_mode: bool = False) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        settings = get_settings(require_bot=False, require_webapp=False)
        init_db(settings.database_path)
        seed_content(settings.database_path)
        yield

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

    def current_user(request: Request) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        try:
            telegram_user = validate_telegram_init_data(
                _init_data_from_request(request), settings.bot_token, allow_dev=dev_mode
            )
        except TelegramAuthError as error:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error
        return get_or_create_user(settings.database_path, telegram_user)

    @application.get("/api/health")
    async def health() -> dict[str, str]:
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
    async def earnings_claim(system: str, user: dict = Depends(current_user)) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return claim_passive(settings.database_path, user["id"], system.lower())

    @application.post("/api/earnings/{system}/upgrade")
    async def earnings_upgrade(system: str, user: dict = Depends(current_user)) -> dict:
        settings = get_settings(require_bot=not dev_mode, require_webapp=False)
        return upgrade_passive(settings.database_path, user["id"], system.lower())

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
    uvicorn.run("api.routes:dev_app" if args.dev else "api.routes:app", host=args.host, port=args.port, reload=False)
