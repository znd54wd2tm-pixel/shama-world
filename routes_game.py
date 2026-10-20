"""Additional routes registered before the existing static mount."""
from __future__ import annotations
import json
from fastapi import Body, Depends, Header, HTTPException
from config import get_settings
from database import get_connection
from services.game import open_case_batch, opening_history
from services.businesses import business_state, business_action
from services.results import result_action
from services.market import player_market, player_market_action


def register_game_routes(app, current_user):
    def path():
        return get_settings(require_bot=False,require_webapp=False).database_path

    @app.get('/api/finance')
    def finance_state(user: dict = Depends(current_user)):
        from services.finance import state
        return state(path(),user['id'])

    @app.post('/api/finance/{action}')
    def finance_action(action: str,payload: dict = Body(default={}),user: dict = Depends(current_user),request_id: str | None = Header(None,alias='X-Game-Request-Id')):
        from services.finance import mutate
        return mutate(path(),user['id'],action,payload,request_id)

    @app.get('/api/collection')
    def collection(user: dict = Depends(current_user)):
        from services.item_view import present
        with get_connection(path()) as c:
            return {'items':[present(r) for r in c.execute("SELECT i.*,COALESCE(inv.quantity,0) AS quantity FROM catalogue_membership m JOIN items i ON i.id=m.item_id LEFT JOIN inventory inv ON inv.item_id=i.id AND inv.user_id=? WHERE m.collection='collection' ORDER BY m.position",(user['id'],))]}

    @app.get("/api/settings")
    def settings(user: dict = Depends(current_user)):
        with get_connection(path()) as c:
            row = c.execute("SELECT fast_open FROM user_settings WHERE user_id=?", (user["id"],)).fetchone()
            return {"fast_open":bool(row[0]) if row else False}

    @app.patch("/api/settings")
    def save_settings(payload: dict = Body(...),user: dict = Depends(current_user)):
        value = payload.get("fast_open")
        if type(value) is not bool:
            raise HTTPException(400,"fast_open должен быть логическим значением")
        with get_connection(path()) as c:
            c.execute("INSERT INTO user_settings(user_id,fast_open) VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET fast_open=excluded.fast_open", (user["id"],int(value)))
            c.commit()
        return {"fast_open":value}

    @app.post("/api/cases/{case_id}/open-ten")
    def open_ten(case_id: int,user: dict = Depends(current_user),request_id: str | None = Header(None,alias="X-Opening-Request-Id")):
        if not request_id:
            raise HTTPException(400,"Требуется идентификатор операции")
        return open_case_batch(path(),user["id"],case_id,10,request_id)

    @app.get("/api/openings")
    def history(user: dict = Depends(current_user)):
        return {"operations":opening_history(path(),user["id"])}

    @app.get("/api/openings/by-request/{request_id}")
    def recovery(request_id: str,user: dict = Depends(current_user)):
        with get_connection(path()) as c:
            row = c.execute("SELECT response_json,id FROM case_batches WHERE user_id=? AND request_id=?", (user["id"],request_id)).fetchone()
            if not row:
                raise HTTPException(404,"Операция ещё не сохранена. Повторите запрос с тем же идентификатором")
            result = json.loads(row["response_json"])
            states = {r["id"]:r["status"] for r in c.execute("SELECT id,status FROM opening_results WHERE batch_id=?", (row["id"],))}
            for item in result["items"]:
                item["status"] = states[item["result_id"]]
            return result

    @app.post("/api/openings/results/{action}")
    def results(action: str,payload: dict = Body(...),user: dict = Depends(current_user),request_id: str | None = Header(None,alias="X-Game-Request-Id")):
        if not request_id:raise HTTPException(400,'Требуется идентификатор операции')
        return result_action(path(),user["id"],action,payload.get("result_ids"),request_id)

    @app.get("/api/businesses")
    def businesses(user: dict = Depends(current_user)):
        return business_state(path(),user["id"])

    @app.post("/api/businesses/{enterprise_id}/{action}")
    def business(enterprise_id: int,action: str,payload: dict = Body(default={}),user: dict = Depends(current_user),request_id: str | None = Header(None,alias="X-Game-Request-Id")):
        if not request_id:raise HTTPException(400,'Требуется идентификатор операции')
        return business_action(path(),user["id"],enterprise_id,action,payload,request_id)

    @app.get("/api/market/listings")
    def listings(user: dict = Depends(current_user)):
        return player_market(path(),user["id"])

    @app.post("/api/market/listings/{action}")
    def listings_action(action: str,payload: dict = Body(...),user: dict = Depends(current_user),request_id: str | None = Header(None,alias="X-Game-Request-Id")):
        if not request_id:raise HTTPException(400,'Требуется идентификатор операции')
        return player_market_action(path(),user["id"],action,payload,request_id)
