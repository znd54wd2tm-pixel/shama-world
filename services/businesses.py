"""Owned businesses. Settlement precedes every change to time-dependent rates."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR
from typing import Any
from database import get_connection
from game_config import OFFLINE_HOURS, LEVEL_HOURS, LEVEL_BONUSES, UPGRADES, UPGRADE_COST_RATIOS, EMPLOYEES
from services.economy import EconomyError, get_balance, remove_balance, record_transaction
from services.operations import request_key, cached, receipt

D = lambda value: Decimal(str(value))
HOUR = D(3600)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def level_for(xp_seconds: float) -> int:
    return sum(D(xp_seconds) >= D(h) * HOUR for h in LEVEL_HOURS)


def award_enterprise(c: Any, user_id: int, catalog_id: int) -> tuple[int, int]:
    catalog = c.execute("SELECT * FROM enterprise_catalog WHERE id=?", (catalog_id,)).fetchone()
    existing = c.execute("SELECT id,retired FROM owned_enterprises WHERE user_id=? AND catalog_id=? AND retired=0", (user_id,catalog_id)).fetchone()
    if existing:
        return int(existing["id"]), int(catalog["original_price"]) // 2
    stamp = now_utc().isoformat()
    cursor = c.execute("INSERT INTO owned_enterprises(user_id,catalog_id,last_accrued_at,created_at,acquisition_cost) VALUES (?,?,?,?,?)", (user_id,catalog_id,stamp,stamp,catalog['original_price']))
    return int(cursor.lastrowid), 0


def load_owned(c: Any, user_id: int, enterprise_id: int) -> Any:
    row = c.execute("""SELECT o.*,e.code,e.name,e.original_price,e.revenue,e.expenses,e.capacity,e.rarity,e.image,e.equipment_required,e.no_upgrades
        FROM owned_enterprises o JOIN enterprise_catalog e ON e.id=o.catalog_id WHERE o.id=? AND o.user_id=? AND o.retired=0""", (enterprise_id,user_id)).fetchone()
    if not row:
        raise EconomyError("Предприятие не найдено или принадлежит другому игроку")
    return row


def staff(c: Any, enterprise_id: int) -> list[dict]:
    result=[dict(r) for r in c.execute("SELECT * FROM enterprise_employees WHERE enterprise_id=? ORDER BY id", (enterprise_id,))]
    for row in result:
        if row.get('employee_grade')=='experienced':row['role']='experienced'
    return result


def rates(row: Any, employees: list[dict], xp: Decimal | None = None) -> dict[str, Decimal]:
    upgrades = json.loads(row["upgrades"])
    level = level_for(row["xp_seconds"] if xp is None else xp)
    effect = lambda key: D(UPGRADES[key]["effects"][upgrades[key]-1]) if upgrades[key] else D(0)
    bonus = min(D('.50'), sum((D(e["bonus"]) for e in employees), D(0)) + D(LEVEL_BONUSES[level-1]) + effect("equipment") + effect("marketing"))
    revenue = D(row["revenue"]) * (1 + bonus) * (1 if employees else D('.5'))
    expenses = D(row["expenses"]) * max(D(0), 1-effect("premises")-effect("automation")) * (1 if employees else D('.7'))
    wages = sum((D(e["salary"]) for e in employees), D(0))
    if row['code']=='kiosk':
        revenue=D(row['revenue']) if employees else D(0)
    if row['equipment_required']:
        from catalog_v16 import COFFEE_EQUIPMENT
        equipment=json.loads(row['equipment'])
        if not all(equipment.get(k) for k in COFFEE_EQUIPMENT):
            revenue=D(0);expenses=D(0)
    return {"revenue":revenue,"expenses":expenses,"wages":wages,"profit":revenue-expenses-wages,"bonus":bonus}


def settle(c: Any, user_id: int, enterprise_id: int, now: datetime | None = None) -> dict:
    now = now or now_utc()
    row = load_owned(c,user_id,enterprise_id)
    checkpoint = datetime.fromisoformat(row["last_accrued_at"])
    if checkpoint.tzinfo is None:
        checkpoint = checkpoint.replace(tzinfo=timezone.utc)
    elapsed = min(D(OFFLINE_HOURS)*HOUR,max(D(0),D((now-checkpoint).total_seconds())))
    if elapsed <= 0:
        return {"credited":0,"seconds":0}
    if row["status"] != "RUNNING":
        c.execute("UPDATE owned_enterprises SET last_accrued_at=? WHERE id=?", (now.isoformat(),enterprise_id))
        return {"credited":0,"seconds":0}
    employees = staff(c,enterprise_id)
    xp, work = D(row["xp_seconds"]), D(row["work_seconds"])
    factor = D(1) if employees else D('.5')
    before = get_balance(c,user_id)
    available = D(before) + D(row["money_remainder"])
    remaining, running = elapsed, D(0)
    totals = {key:D(0) for key in ("revenue","expenses","wages")}
    paused = False
    # Split at level boundaries so new bonuses never apply retroactively.
    while remaining > D('0.0000001'):
        level = level_for(xp)
        duration = remaining
        if level < 5:
            duration = min(duration, (D(LEVEL_HOURS[level])*HOUR-xp)/factor)
        rate = rates(row,employees,xp)
        if rate["profit"] < 0:
            affordable = max(D(0),available)*HOUR/(-rate["profit"])
            if affordable < duration:
                duration, paused = affordable, True
        for key in totals:
            totals[key] += rate[key]*duration/HOUR
        available += rate["profit"]*duration/HOUR
        xp += duration*factor
        work += duration
        running += duration
        remaining -= duration
        if paused:
            break
    # Keep sub-dollar precision per business, including small negative intervals.
    integer_balance = max(0,int(available.to_integral_value(rounding=ROUND_FLOOR)))
    remainder = max(D(0),available-D(integer_balance))
    credited = integer_balance-before
    saved=0
    setting=c.execute('SELECT auto_savings FROM finance_accounts WHERE user_id=?',(user_id,)).fetchone()
    if credited>0 and row['savings_enabled'] and setting and setting[0]:
        share=D(credited)*D('.20')+D(row['savings_remainder'])
        saved=int(share.to_integral_value(rounding=ROUND_FLOOR));integer_balance-=saved
        c.execute('UPDATE finance_accounts SET savings=savings+? WHERE user_id=?',(saved,user_id))
        c.execute('UPDATE owned_enterprises SET savings_remainder=? WHERE id=?',(str(share-saved),enterprise_id))
    c.execute("UPDATE users SET balance=? WHERE id=?", (integer_balance,user_id))
    c.execute("""UPDATE owned_enterprises SET xp_seconds=?,work_seconds=?,money_remainder=?,last_accrued_at=?,status=?,pause_reason=? WHERE id=?""",
              (float(xp),float(work),str(remainder),now.isoformat(),"PAUSED" if paused else "RUNNING","Недостаточно средств на расходы и зарплату" if paused else "",enterprise_id))
    if running:
        record_transaction(c,user_id,"OTHER",abs(credited),before,integer_balance,description=f"Работа: {row['name']}",metadata={"enterprise_id":enterprise_id,"seconds":float(running),"offline_cap_hours":OFFLINE_HOURS,'auto_saved':saved,**{k:float(v) for k,v in totals.items()}},request_id=None)
    if saved:
        record_transaction(c,user_id,'OTHER',saved,integer_balance,integer_balance,description='Автоматические накопления',metadata={'enterprise_id':enterprise_id,'internal_transfer':True},request_id=None)
    return {"credited":credited,"seconds":float(running),"paused":paused}


def is_listed(c: Any, enterprise_id: int) -> bool:
    return bool(c.execute("SELECT 1 FROM player_listings WHERE enterprise_id=? AND status='ACTIVE'", (enterprise_id,)).fetchone())


def enterprise_payload(c: Any, row: Any) -> dict:
    employees = staff(c,row["id"])
    rate = rates(row,employees)
    level = level_for(row["xp_seconds"])
    upgrades = json.loads(row["upgrades"])
    options = []
    for key, config in ({} if row['no_upgrades'] else UPGRADES).items():
        current = upgrades[key]
        options.append({"key":key,"name":config["name"],"level":current,"effect":config["effects"][current-1] if current else 0,
                        "next_level":current+1 if current < 3 else None,
                        "cost":int(D(row["original_price"])*D(UPGRADE_COST_RATIOS[current])) if current < 3 else None,
                        "required_level":config["levels"][current] if current < 3 else None,
                        "next_effect":config["effects"][current] if current < 3 else None})
    roles = [{"role":key,**config,"hire_cost":int(config["hire_cost"]),"salary":int(config["salary"])} for key,config in EMPLOYEES.items()]
    from catalog_v16 import COFFEE_EQUIPMENT
    from services.finance import enterprise_value
    equipment=json.loads(row['equipment'])
    return {**dict(row),'name':row['custom_name'] or row['name'],'equipment_options':[{'key':k,'name':v[0],'price':v[1],'owned':bool(equipment.get(k))} for k,v in COFFEE_EQUIPMENT.items()] if row['equipment_required'] else [],'state_buyback':enterprise_value(c,row)//5,"level":level,"employees":employees,"employee_count":len(employees),"upgrades":options,"roles":roles,
            "next_level_hours":LEVEL_HOURS[level] if level<5 else None,"xp_hours":float(D(row["xp_seconds"])/HOUR),
            "work_hours":float(D(row["work_seconds"])/HOUR),"listed":is_listed(c,row["id"]),"premium":level==5,
            "hourly":{key:round(float(value),4) for key,value in rate.items()}}


def business_state(path: str, user_id: int) -> dict:
    with get_connection(path) as c:
        c.execute("BEGIN IMMEDIATE")
        ids = [r[0] for r in c.execute("SELECT id FROM owned_enterprises WHERE user_id=? AND retired=0 ORDER BY id", (user_id,))]
        now = now_utc()
        income = sum(settle(c,user_id,i,now)["credited"] for i in ids)
        enterprises = [enterprise_payload(c,load_owned(c,user_id,i)) for i in ids]
        catalog_codes = tuple(item[0] for item in __import__("game_config").ENTERPRISES)
        placeholders = ",".join("?" for _ in catalog_codes)
        catalog = [dict(r) for r in c.execute(f"SELECT * FROM enterprise_catalog WHERE code IN ({placeholders}) ORDER BY original_price", catalog_codes)]
        result = {"enterprises":enterprises,"catalog":catalog,"balance":get_balance(c,user_id),"offline_income":income,"offline_cap_hours":OFFLINE_HOURS}
        c.commit()
        return result


def business_action(path: str, user_id: int, enterprise_id: int, action: str, payload: dict, request_id: str | None) -> dict:
    key = request_key(request_id)
    data = {"enterprise_id":enterprise_id,"action":action,**payload}
    with get_connection(path) as c:
        c.execute("BEGIN IMMEDIATE")
        previous = cached(c,user_id,key,"business",data)
        if previous:
            return previous
        before = get_balance(c,user_id)
        cost = 0
        if action == "buy":
            catalog = c.execute("SELECT * FROM enterprise_catalog WHERE id=?", (enterprise_id,)).fetchone()
            if not catalog:
                raise EconomyError("Предприятие не найдено")
            if c.execute("SELECT 1 FROM owned_enterprises WHERE user_id=? AND catalog_id=? AND retired=0", (user_id,enterprise_id)).fetchone():
                raise EconomyError("У вас уже есть такое предприятие")
            cost = catalog["original_price"]
            remove_balance(c,user_id,cost)
            owned_id,_ = award_enterprise(c,user_id,enterprise_id)
        else:
            owned_id = enterprise_id
            load_owned(c,user_id,owned_id)
            if is_listed(c,owned_id):
                raise EconomyError("Сначала снимите предприятие с SH MARKET")
            settle(c,user_id,owned_id)
            row = load_owned(c,user_id,owned_id)
            before = get_balance(c,user_id)
            if action == "status":
                status = payload.get("status")
                if status not in ("RUNNING","PAUSED"):
                    raise EconomyError("Некорректный статус")
                c.execute("UPDATE owned_enterprises SET status=?,pause_reason='' WHERE id=?", (status,owned_id))
            elif action=='rename':
                name=payload.get('name')
                if not isinstance(name,str) or not 1<=len(name.strip())<=60 or any(ord(ch)<32 for ch in name):raise EconomyError('Название: от 1 до 60 символов')
                c.execute('UPDATE owned_enterprises SET custom_name=? WHERE id=?',(name.strip(),owned_id))
            elif action=='savings':
                if type(payload.get('enabled')) is not bool:raise EconomyError('Некорректная настройка накоплений')
                c.execute('UPDATE owned_enterprises SET savings_enabled=? WHERE id=?',(int(payload['enabled']),owned_id))
            elif action=='equipment':
                from catalog_v16 import COFFEE_EQUIPMENT
                equipment=json.loads(row['equipment']);part=payload.get('key')
                if not row['equipment_required'] or part not in COFFEE_EQUIPMENT:raise EconomyError('Оборудование не найдено')
                if equipment.get(part):raise EconomyError('Оборудование уже куплено')
                cost=COFFEE_EQUIPMENT[part][1];remove_balance(c,user_id,cost);equipment[part]=True
                c.execute('UPDATE owned_enterprises SET equipment=? WHERE id=?',(json.dumps(equipment),owned_id))
            elif action=='state-sale':
                if payload.get('confirmed') is not True:raise EconomyError('Подтвердите продажу государству за 20% расчётной стоимости')
                from services.finance import enterprise_value
                amount=enterprise_value(c,row)//5
                c.execute("UPDATE owned_enterprises SET retired=1,status='PAUSED' WHERE id=?",(owned_id,))
                c.execute("UPDATE opening_results SET status='TRANSFERRED' WHERE enterprise_id=? AND status IN ('AVAILABLE','KEPT')",(owned_id,))
                c.execute('DELETE FROM enterprise_employees WHERE enterprise_id=?',(owned_id,))
                c.execute('UPDATE users SET balance=balance+? WHERE id=?',(amount,user_id))
                record_transaction(c,user_id,'SELL',amount,before,before+amount,description='Государственный выкуп предприятия',metadata={'enterprise_id':owned_id,'snapshot':dict(row)},request_id=f'business:{key}')
                result={'success':True,'balance':before+amount,'amount':amount,'retired_id':owned_id}
                receipt(c,user_id,key,'business',data,result);c.commit();return result
            elif action == "hire":
                role = payload.get("role","worker")
                if role not in EMPLOYEES:
                    raise EconomyError("Неизвестная должность")
                config = EMPLOYEES[role]
                if level_for(row["xp_seconds"]) < config["level"]:
                    raise EconomyError(f"Требуется уровень {config['level']}")
                employees = staff(c,owned_id)
                if len(employees) >= row["capacity"]:
                    raise EconomyError("Все рабочие места заняты")
                if role == "manager" and any(e["role"] == "manager" for e in employees):
                    raise EconomyError("Менеджер уже нанят")
                cost = int(config["hire_cost"])
                remove_balance(c,user_id,cost)
                # The original V15 schema supports worker/manager roles. Store experienced hires as workers,
                # while preserving their agreed salary and revenue bonus in the employee row.
                stored_role = "manager" if role == "manager" else "worker"
                c.execute("INSERT INTO enterprise_employees(enterprise_id,role,salary,bonus,hired_at,employee_grade) VALUES (?,?,?,?,?,?)", (owned_id,stored_role,int(config["salary"]),config["bonus"],now_utc().isoformat(),'experienced' if role=='experienced' else ''))
            elif action == "fire":
                employee_id = payload.get("employee_id")
                if type(employee_id) is not int or c.execute("DELETE FROM enterprise_employees WHERE id=? AND enterprise_id=?", (employee_id,owned_id)).rowcount != 1:
                    raise EconomyError("Сотрудник не найден")
            elif action == "upgrade":
                if row['no_upgrades']:raise EconomyError('Для уличного киоска улучшения не предусмотрены')
                direction, target = payload.get("direction"), payload.get("level")
                if direction not in UPGRADES or type(target) is not int or not 1 <= target <= 3:
                    raise EconomyError("Некорректное улучшение")
                upgrades = json.loads(row["upgrades"])
                if target != upgrades[direction]+1:
                    raise EconomyError("Улучшения покупаются последовательно и только один раз")
                if level_for(row["xp_seconds"]) < UPGRADES[direction]["levels"][target-1]:
                    raise EconomyError("Для улучшения требуется повысить уровень предприятия")
                cost = int(D(row["original_price"])*D(UPGRADE_COST_RATIOS[target-1]))
                remove_balance(c,user_id,cost)
                upgrades[direction] = target
                c.execute("UPDATE owned_enterprises SET upgrades=? WHERE id=?", (json.dumps(upgrades),owned_id))
            else:
                raise EconomyError("Неизвестное действие")
        after = get_balance(c,user_id)
        if cost:
            record_transaction(c,user_id,"OTHER",cost,before,after,description=f"Предприятие: {action}",metadata={"enterprise_id":owned_id,**payload},request_id=f"business:{key}")
        result = {"success":True,"balance":after,"cost":cost,"enterprise":enterprise_payload(c,load_owned(c,user_id,owned_id))}
        receipt(c,user_id,key,"business",data,result)
        c.commit()
        return result
