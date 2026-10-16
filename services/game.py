"""Authoritative draws, one payment per batch and durable response recovery."""
from __future__ import annotations
import json
import random
import uuid
from typing import Any
from database import get_connection
from services.economy import record_transaction
from services.operations import request_key, add_item


class GameError(RuntimeError):
    status_code = 400


class CaseNotFoundError(GameError):
    status_code = 404


class InsufficientBalanceError(GameError):
    pass


class EmptyDropPoolError(GameError):
    status_code = 409


class OpeningInProgressError(GameError):
    status_code = 409


_rng = random.SystemRandom()


def _choose_drop(rows: list[Any]) -> Any:
    if not rows or any(not 0 < float(r["chance"]) <= 1 for r in rows) or abs(sum(float(r["chance"]) for r in rows)-1) > 1e-8:
        raise EmptyDropPoolError("Кейс временно недоступен: вероятности наград настроены некорректно")
    roll, cursor = _rng.random(), 0.
    for row in rows:
        cursor += float(row["chance"])
        if roll < cursor:
            return row
    return rows[-1]


def _legacy_result(c: Any, user_id: int, case_id: int, quantity: int, key: str) -> dict | None:
    rows = c.execute("""SELECT o.*,i.name,i.description,i.rarity,i.value,i.image FROM case_openings o
        JOIN items i ON i.id=o.item_id WHERE o.user_id=? AND (o.request_id=? OR substr(o.request_id,1,length(?)+1)=?||':') ORDER BY o.id""", (user_id,key,key,key)).fetchall()
    if not rows:
        return None
    if len(rows) != quantity or any(r["case_id"] != case_id for r in rows):
        raise GameError("Идентификатор открытия уже использован")
    items = [{k: r[k] for k in ("name","description","rarity","value","image")} | {"id": r["item_id"], "kind": "ITEM", "legacy": True} for r in rows]
    user = c.execute("SELECT balance,xp,level FROM users WHERE id=?", (user_id,)).fetchone()
    return {"success": True,"items": items,"item": items[0],**dict(user),"idempotent": True,"quantity":quantity}


def open_cases(database_path: str, user_id: int, case_id: int, quantity: int, request_id: str | None = None) -> dict:
    if type(quantity) is not int or quantity not in (1,5,10):
        raise GameError("Открывайте 1 или 10 кейсов")
    key = request_key(request_id)
    with get_connection(database_path) as c:
        c.execute("BEGIN IMMEDIATE")
        previous = c.execute("SELECT * FROM case_batches WHERE user_id=? AND request_id=?", (user_id,key)).fetchone()
        if previous:
            if previous["case_id"] != case_id or previous["quantity"] != quantity:
                raise GameError("Идентификатор открытия уже использован")
            return {**json.loads(previous["response_json"]), "idempotent": True}
        legacy = _legacy_result(c,user_id,case_id,quantity,key)
        if legacy:
            return legacy
        case = c.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
        if not case:
            raise CaseNotFoundError("Кейс не найден")
        if not case["active"]:
            raise EmptyDropPoolError("Кейс временно недоступен")
        user = c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not user:
            raise GameError("Пользователь не найден")
        cost = int(case["price"]) * quantity
        if user["balance"] < cost:
            raise InsufficientBalanceError(f"Недостаточно средств. Нужно ${cost:,}; не хватает ${cost-user['balance']:,}".replace(",", " "))
        business = case["kind"] == "BUSINESS"
        drops = c.execute("SELECT d.chance,e.* FROM enterprise_drops d JOIN enterprise_catalog e ON e.id=d.enterprise_type_id WHERE d.case_id=? ORDER BY e.id" if business else
                          "SELECT d.chance,i.* FROM case_drops d JOIN items i ON i.id=d.item_id WHERE d.case_id=? ORDER BY d.id", (case_id,)).fetchall()
        chosen = [_choose_drop(drops) for _ in range(quantity)]
        batch_id = str(uuid.uuid4())
        c.execute("INSERT INTO case_batches(id,user_id,case_id,quantity,price_paid,request_id,response_json) VALUES (?,?,?,?,?,?,?)", (batch_id,user_id,case_id,quantity,cost,key,"{}"))
        c.execute("UPDATE users SET balance=balance-? WHERE id=? AND balance>=?", (cost,user_id,cost))
        balance = int(user["balance"]) - cost
        record_transaction(c,user_id,"CASE_OPEN",cost,user["balance"],balance,quantity=quantity,description=f"{quantity} × {case['name']}",metadata={"batch_id":batch_id,"case_id":case_id}, request_id=f"case:{batch_id}")
        results, new_types = [], 0
        for slot, row in enumerate(chosen):
            result_id = str(uuid.uuid4())
            item = {k: row[k] for k in ("id","name","rarity","image")}
            item.update(result_id=result_id, kind=case["kind"], compensation=0, status="AVAILABLE")
            enterprise_id = None
            if business:
                from services.businesses import award_enterprise
                enterprise_id, compensation = award_enterprise(c,user_id,row["id"])
                item.update(enterprise_id=enterprise_id, value=row["original_price"], compensation=compensation, description="Предприятие добавлено в раздел предприятий" if not compensation else "Повторное предприятие: компенсация 50% исходной стоимости")
                if compensation:
                    before = balance
                    balance += compensation
                    c.execute("UPDATE users SET balance=balance+? WHERE id=?", (compensation,user_id))
                    record_transaction(c,user_id,"REWARD",compensation,before,balance,description="Компенсация повторного предприятия",metadata={"batch_id":batch_id,"slot":slot},request_id=f"compensation:{result_id}")
                    item["status"] = "COMPENSATED"
            else:
                exists = c.execute("SELECT 1 FROM inventory WHERE user_id=? AND item_id=?", (user_id,row["id"])).fetchone()
                new_types += int(exists is None)
                add_item(c,user_id,row["id"])
                item.update(value=row["value"],description=row["description"],category=row["category"])
                c.execute("INSERT INTO case_openings(user_id,case_id,item_id,price_paid,request_id) VALUES (?,?,?,?,?)", (user_id,case_id,row["id"],case["price"],f"v15:{result_id}"))
            c.execute("INSERT INTO opening_results(id,batch_id,slot,user_id,item_id,enterprise_id,compensation,status,snapshot_json) VALUES (?,?,?,?,?,?,?,?,?)", (result_id,batch_id,slot,user_id,None if business else row["id"],enterprise_id,item["compensation"],item["status"],json.dumps(item,ensure_ascii=False)))
            results.append(item)
        xp = int(user["xp"]) + 10 * quantity
        c.execute("UPDATE users SET xp=?,level=?,cases_opened=cases_opened+?,items_collected=items_collected+? WHERE id=?", (xp,xp//100+1,quantity,new_types,user_id))
        result = {"success":True,"operation_id":batch_id,"request_id":key,"quantity":quantity,"total_price":cost,"items":results,"item":results[0],"balance":balance,"xp":xp,"level":xp//100+1,"idempotent":False}
        c.execute("UPDATE case_batches SET response_json=? WHERE id=?", (json.dumps(result,ensure_ascii=False),batch_id))
        c.commit()
        return result


def open_case(database_path: str,user_id: int,case_id: int,request_id: str | None = None) -> dict:
    return open_cases(database_path,user_id,case_id,1,request_id)


def open_case_batch(database_path: str,user_id: int,case_id: int,quantity: int = 10,request_id: str | None = None) -> dict:
    return open_cases(database_path,user_id,case_id,quantity,request_id)


def opening_history(path: str,user_id: int) -> list[dict]:
    with get_connection(path) as c:
        rows = c.execute("SELECT * FROM case_batches WHERE user_id=? ORDER BY created_at DESC,rowid DESC LIMIT 20", (user_id,)).fetchall()
        output = []
        for row in rows:
            result = json.loads(row["response_json"])
            statuses = {r["id"]:r["status"] for r in c.execute("SELECT id,status FROM opening_results WHERE batch_id=?", (row["id"],))}
            for item in result["items"]:
                item["status"] = statuses[item["result_id"]]
            result["created_at"] = row["created_at"]
            output.append(result)
        return output
