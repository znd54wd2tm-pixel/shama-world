"""Actions refer to exact reward ids, including ten copies of the same item."""
from __future__ import annotations
from database import get_connection
from services.operations import request_key, cached, receipt, consume_item
from services.economy import EconomyError, get_balance, record_transaction


def result_action(path: str, user_id: int, action: str, ids: list[str], request_id: str | None) -> dict:
    if action not in ("keep", "sell") or not isinstance(ids,list) or not 1 <= len(ids) <= 10 or any(not isinstance(i,str) for i in ids) or len(set(ids)) != len(ids):
        raise EconomyError("Выберите от 1 до 10 разных результатов")
    key = request_key(request_id)
    payload = {"ids":sorted(ids),"action":action}
    with get_connection(path) as c:
        c.execute("BEGIN IMMEDIATE")
        previous = cached(c,user_id,key,"result_action",payload)
        if previous:
            return previous
        amount, sold = 0, 0
        for result_id in ids:
            row = c.execute("SELECT r.*,i.value FROM opening_results r LEFT JOIN items i ON i.id=r.item_id WHERE r.id=? AND r.user_id=?", (result_id,user_id)).fetchone()
            if not row:
                raise EconomyError("Результат не найден")
            if row["status"] not in ("AVAILABLE","KEPT"):
                raise EconomyError("Предмет уже продан, использован или выставлен на рынок")
            if action == "sell":
                if not row["item_id"]:
                    raise EconomyError("Предприятия продаются через SH MARKET")
                consume_item(c,user_id,row["item_id"],1,"SOLD",[result_id])
                amount += int(row["value"])
                sold += 1
            else:
                c.execute("UPDATE opening_results SET status='KEPT' WHERE id=?", (result_id,))
        before = get_balance(c,user_id)
        if action == "sell":
            c.execute("UPDATE users SET balance=balance+?,total_items_sold=total_items_sold+?,total_sh_earned_from_sales=total_sh_earned_from_sales+? WHERE id=?", (amount,sold,amount,user_id))
            record_transaction(c,user_id,"SELL",amount,before,before+amount,quantity=sold,description="Мгновенный выкуп результатов",metadata={"result_ids":ids},request_id=f"results:{key}")
        result = {"success":True,"balance":before+amount,"amount":amount,"result_ids":ids,"action":action}
        receipt(c,user_id,key,"result_action",payload,result)
        c.commit()
        return result
