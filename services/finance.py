"""Unified virtual finance. All changes share SQLite transactions and receipts.

Integer dollars for the wallet; Decimal for rates/crypto; cents for issuer profit.
No external payment, purchase or cash-out is implemented.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING
import json
import random
from zoneinfo import ZoneInfo
import os
from database import get_connection
from services.economy import EconomyError, get_balance, remove_balance, record_transaction
from services.operations import cached, receipt
import catalog_v16 as cfg

D=lambda x:Decimal(str(x))
RNG=random.SystemRandom()
EVENTS=(
 ('Туристический бум',(.10,.15,.20,.10),16),
 ('Спад потребительского спроса',(-.10,-.20,-.10,-.15),16),
 ('Технологический прорыв',(.15,.10,.10,.20),12),
 ('Энергетический кризис',(-.10,-.15,-.15,-.20),12),
 ('Общий экономический кризис',(-.20,-.15,-.15,-.20),8),
 ('Снижение процентных ставок',(-.10,.10,.15,.15),16),
 ('Промышленный бум',(.15,.10,.10,.20),12),
 ('Банковская паника',(-.20,-.10,-.10,-.15),8),
)
COMPANIES=('BANK','COFFEE','HOTELS','INDUSTRIES')

def now_utc():return datetime.now(timezone.utc)
def stamp(dt):return dt.astimezone(timezone.utc).isoformat()
def parse(s):
    dt=datetime.fromisoformat(s.replace('Z','+00:00'))
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
def floor(n):return int(D(n).to_integral_value(rounding=ROUND_FLOOR))
def ceil(n):return int(D(n).to_integral_value(rounding=ROUND_CEILING))
def positive(n,label='Сумма'):
    if type(n) is not int or not 1<=n<=10**12:raise EconomyError(f'{label}: введите положительное целое число')
    return n
def account(c,user,now):
    c.execute('INSERT OR IGNORE INTO finance_accounts(user_id,joined_at) VALUES (?,?)',(user,stamp(now)))
    return c.execute('SELECT * FROM finance_accounts WHERE user_id=?',(user,)).fetchone()
def notify(c,user,key,message,now):
    c.execute('INSERT OR IGNORE INTO finance_notifications VALUES (?,?,?,?)',(user,key,message,stamp(now)))
def ledger(c,user,kind,amount,before,after,metadata=None,key=None):
    record_transaction(c,user,'OTHER',int(amount),before,after,description=kind,metadata={'finance':True,**(metadata or {})},request_id=key)

def enterprise_value(c,row):
    from game_config import UPGRADE_COST_RATIOS
    from catalog_v16 import COFFEE_EQUIPMENT
    base=int(row['original_price'])
    equipment=sum(COFFEE_EQUIPMENT[k][1] for k,v in json.loads(row['equipment']).items() if v and k in COFFEE_EQUIPMENT)
    upgrades=sum(sum(floor(D(base)*D(v)) for v in UPGRADE_COST_RATIOS[:count]) for count in json.loads(row['upgrades']).values())
    return floor(D(base+equipment+upgrades)*D(row['condition_percent'])/100)

def capital(c,user):
    """Every account is counted once. Legacy property and debt stay in the total."""
    cash=get_balance(c,user)
    own=c.execute('SELECT savings FROM finance_accounts WHERE user_id=?',(user,)).fetchone()
    savings=int(own[0]) if own else 0
    old_savings=c.execute('SELECT balance FROM player_savings_accounts WHERE user_id=?',(user,)).fetchone()
    legacy_savings=D(old_savings[0]) if old_savings else D(0)
    deposits=c.execute("SELECT COALESCE(sum(principal),0) FROM finance_deposits WHERE user_id=? AND status='ACTIVE'",(user,)).fetchone()[0]
    deposits+=c.execute("SELECT COALESCE(sum(principal),0) FROM works_deposits WHERE user_id=? AND status='ACTIVE'",(user,)).fetchone()[0]
    stocks=c.execute('SELECT COALESCE(sum(l.quantity*s.price),0) FROM finance_stock_lots l JOIN finance_companies s ON s.code=l.company WHERE l.user_id=?',(user,)).fetchone()[0]
    legacy_stocks=c.execute('SELECT COALESCE(sum(h.shares*s.price),0) FROM bank_company_holdings h JOIN bank_companies s ON s.code=h.company_code WHERE h.user_id=?',(user,)).fetchone()[0]
    legacy_market=c.execute('SELECT COALESCE(sum(h.quantity*s.price),0) FROM player_market_holdings h JOIN game_market_assets s ON s.code=h.asset_code WHERE h.user_id=?',(user,)).fetchone()[0]
    cryptos=D(0)
    for r in c.execute('SELECT h.quantity,q.price FROM finance_crypto_holdings h JOIN finance_crypto_quotes q ON q.code=h.code WHERE h.user_id=?',(user,)):
        cryptos+=D(r['quantity'])*D(r['price'])
    legacy_crypto=c.execute('SELECT COALESCE(sum(h.quantity*q.price),0) FROM bank_crypto_holdings h JOIN crypto_market q ON q.code=h.code WHERE h.user_id=?',(user,)).fetchone()[0]
    legacy_bank=c.execute('SELECT * FROM bank_accounts WHERE user_id=?',(user,)).fetchone()
    bank_cash=0
    if legacy_bank:
        bank_cash=int(legacy_bank['cash_balance'])-int(legacy_bank['client_liabilities'])
    businesses=sum(enterprise_value(c,r) for r in c.execute('SELECT o.*,e.original_price FROM owned_enterprises o JOIN enterprise_catalog e ON e.id=o.catalog_id WHERE o.user_id=? AND o.retired=0',(user,)))
    debt=c.execute("SELECT COALESCE(sum(total_due-paid),0) FROM finance_loans WHERE user_id=? AND status!='PAID'",(user,)).fetchone()[0]
    total=D(cash+savings+deposits+stocks+legacy_stocks+legacy_market+bank_cash+businesses-debt)+legacy_savings+cryptos+D(legacy_crypto)
    return {'total':floor(total),'available':cash,'savings':savings,'legacy_savings':float(legacy_savings),'deposits':deposits,
            'stocks':stocks+legacy_stocks+legacy_market,'crypto':float(cryptos+D(legacy_crypto)),'enterprises':businesses,'debt':debt,'legacy_bank_equity':bank_cash}

def business_income(c,user,now):
    cutoff=stamp(now-timedelta(hours=24))
    amount=D(0);intervals=[]
    for r in c.execute("SELECT metadata,created_at FROM transactions WHERE user_id=? AND description LIKE 'Работа:%' AND created_at>=datetime(?)",(user,cutoff)):
        m=json.loads(r['metadata'] or '{}')
        seconds=max(D(0),D(m.get('seconds',0)));end=min(now,parse(r['created_at']));start=max(now-timedelta(hours=24),end-timedelta(seconds=float(seconds)))
        if seconds and end>start:
            fraction=D((end-start).total_seconds())/seconds
            amount+=(D(m.get('revenue',0))-D(m.get('expenses',0))-D(m.get('wages',0)))*fraction
            intervals.append((start,end))
    # Union of observed working intervals: simultaneous businesses add income,
    # without counting the same player's hour more than once.
    seconds=D(0);last=None
    for start,end in sorted(intervals):
        if last is None or start>last:seconds+=D((end-start).total_seconds())
        elif end>last:seconds+=D((end-last).total_seconds())
        last=max(last,end) if last else end
    hours=max(D(1),seconds/3600)
    return max(D(0),amount/hours)

def pay_loan(c,user,loan,amount,now,key):
    outstanding=loan['total_due']-loan['paid']
    amount=min(amount,outstanding)
    if amount<=0:return 0
    a=account(c,user,now);before=get_balance(c,user)
    # Customer deposits of the legacy bank are never a repayment source.
    legacy=c.execute('SELECT balance FROM player_savings_accounts WHERE user_id=?',(user,)).fetchone()
    legacy_take=min(amount,max(0,floor(legacy[0]))) if legacy else 0
    bank=min(amount-legacy_take,a['savings']);wallet=amount-bank-legacy_take
    if wallet>before:raise EconomyError('Недостаточно средств для платежа')
    c.execute('UPDATE finance_accounts SET savings=savings-? WHERE user_id=?',(bank,user))
    if legacy_take:c.execute('UPDATE player_savings_accounts SET balance=balance-? WHERE user_id=?',(legacy_take,user))
    if wallet:remove_balance(c,user,wallet)
    c.execute("UPDATE finance_loans SET paid=paid+?,status=CASE WHEN paid+?=total_due THEN 'PAID' ELSE status END WHERE id=?",(amount,amount,loan['id']))
    left=amount
    for part in c.execute('SELECT * FROM finance_installments WHERE loan_id=? AND paid<amount ORDER BY due_at,id',(loan['id'],)).fetchall():
        take=min(left,part['amount']-part['paid']);left-=take
        c.execute('UPDATE finance_installments SET paid=paid+? WHERE id=?',(take,part['id']))
        if not left:break
    ledger(c,user,'Погашение кредита',amount,before,before-wallet,{'loan_id':loan['id'],'bank_source':bank+legacy_take},key)
    return amount

def advance_loans(c,user,now):
    for loan in c.execute("SELECT * FROM finance_loans WHERE user_id=? AND status!='PAID' ORDER BY due_at,id",(user,)).fetchall():
        due=c.execute('SELECT COALESCE(sum(amount-paid),0) FROM finance_installments WHERE loan_id=? AND due_at<=?',(loan['id'],stamp(now))).fetchone()[0]
        if loan['autopay'] and due:
            legacy=c.execute('SELECT balance FROM player_savings_accounts WHERE user_id=?',(user,)).fetchone()
            funds=get_balance(c,user)+account(c,user,now)['savings']+(max(0,floor(legacy[0])) if legacy else 0)
            if funds:pay_loan(c,user,loan,min(due,funds),now,None)
        overdue=c.execute('SELECT 1 FROM finance_installments WHERE loan_id=? AND paid<amount AND due_at<=?',(loan['id'],stamp(now))).fetchone()
        current=c.execute('SELECT * FROM finance_loans WHERE id=?',(loan['id'],)).fetchone()
        if overdue and current['status']!='PAID':
            c.execute("UPDATE finance_loans SET status='OVERDUE',was_overdue=1 WHERE id=?",(loan['id'],))
        for hours,label in ((6,'Через 6 часов'),(3,'Через 3 часа'),(0,'Наступил срок')):
            if now>=parse(loan['due_at'])-timedelta(hours=hours) and current['status']!='PAID':
                notify(c,user,f'loan:{loan["id"]}:{hours}',f'{label} погашения кредита №{loan["id"]}',now)
        if overdue:notify(c,user,f'loan:{loan["id"]}:overdue',f'Просрочен кредит №{loan["id"]}. Новые кредиты заблокированы.',now)

def advance_market(c,now):
    """Bounded, persisted catch-up. No economic work runs on browser timers."""
    period=int(now.timestamp()//3600)
    for listing in c.execute("SELECT * FROM finance_stock_listings WHERE status='ACTIVE' AND expires_at<=?",(stamp(now),)).fetchall():
        release_listing(c,listing['id'],'EXPIRED')
    for company in c.execute('SELECT * FROM finance_companies').fetchall():
        price=company['price']
        for p in range(company['last_tick']+1,min(period,company['last_tick']+168)+1):
            tick=datetime.fromtimestamp(p*3600,timezone.utc)
            profit=c.execute('SELECT COALESCE(sum(amount_cents),0) FROM finance_company_profit WHERE company=? AND occurred_at>? AND occurred_at<=?',(company['code'],stamp(tick-timedelta(hours=1)),stamp(tick))).fetchone()[0]
            up=RNG.random()<(0.65 if profit>0 else 0.35 if profit<0 else 0.5)
            roll=RNG.random();low,high=(D(0),D('.005')) if roll<.6 else (D('.005'),D('.015')) if roll<.9 else (D('.015'),D(company['max_change']))
            change=low+(high-low)*D(RNG.random())
            price=max(1,ceil(D(price)*(1+change if up else 1-change)))
            c.execute('UPDATE finance_companies SET price=?,last_tick=? WHERE code=?',(price,p,company['code']))
        advance_dividends(c,company['code'],now)
    next_event=c.execute("SELECT value FROM finance_meta WHERE key='next_event'").fetchone()
    if next_event is None:
        c.execute("INSERT INTO finance_meta VALUES ('next_event',?)",(stamp(now+timedelta(hours=RNG.uniform(6,12))),))
    elif now>=parse(next_event[0]):
        previous=c.execute('SELECT kind FROM finance_events ORDER BY id DESC LIMIT 1').fetchone()
        candidates=[i for i in range(len(EVENTS)) if previous is None or i!=previous[0]]
        kind=RNG.choices(candidates,weights=[EVENTS[i][2] for i in candidates],k=1)[0]
        end=now+timedelta(hours=RNG.uniform(2,6))
        cur=c.execute('INSERT INTO finance_events(kind,starts_at,ends_at) VALUES (?,?,?)',(kind,stamp(now),stamp(end)))
        for code,effect in zip(COMPANIES,EVENTS[kind][1]):
            row=c.execute('SELECT price FROM finance_companies WHERE code=?',(code,)).fetchone()
            c.execute('UPDATE finance_companies SET price=? WHERE code=?',(max(1,ceil(D(row[0])*(1+D(effect)))),code))
        c.execute("UPDATE finance_meta SET value=? WHERE key='next_event'",(stamp(now+timedelta(hours=RNG.uniform(6,12))),))
    c.execute('UPDATE finance_events SET ended=1 WHERE ends_at<=?',(stamp(now),))

def advance_dividends(c,code,now):
    company=c.execute('SELECT * FROM finance_companies WHERE code=?',(code,)).fetchone()
    start=parse(company['started_at'])
    reached=int((now-start).total_seconds()//(168*3600))
    for p in range(company['dividend_period']+1,min(reached,company['dividend_period']+52)+1):
        company=c.execute('SELECT * FROM finance_companies WHERE code=?',(code,)).fetchone()
        close=start+timedelta(hours=168*p);open_at=close-timedelta(hours=168)
        profit=c.execute('SELECT COALESCE(sum(amount_cents),0) FROM finance_company_profit WHERE company=? AND occurred_at>? AND occurred_at<=?',(code,stamp(open_at),stamp(close))).fetchone()[0]
        fund=max(0,floor(D(profit)*D('.20')))
        holders=c.execute('SELECT user_id,sum(quantity) AS quantity FROM finance_stock_lots WHERE company=? AND acquired_at<=? GROUP BY user_id',(code,stamp(close-timedelta(hours=24)))).fetchall()
        dollars=fund//100;paid=0
        # A late scheduler cannot reconstruct already sold historical lots; transactions
        # call advance_market before every ownership change, so the closing snapshot
        # is settled before the first post-close trade, including after a restart.
        if dollars and holders:
            total=sum(r['quantity'] for r in holders)
            shares=[(r['user_id'],D(dollars)*r['quantity']/total) for r in holders]
            allocation={u:floor(v) for u,v in shares}
            for u,_ in sorted(shares,key=lambda r:(-(r[1]-floor(r[1])),r[0]))[:dollars-sum(allocation.values())]:allocation[u]+=1
            for user,amount in allocation.items():
                if not amount:continue
                before=get_balance(c,user);c.execute('UPDATE users SET balance=balance+? WHERE id=?',(amount,user))
                ledger(c,user,'Дивиденды',amount,before,before+amount,{'company':code,'period':p},f'finance-dividend:{code}:{p}:{user}')
                paid+=amount
            # The minimum-price boundary and expectation pricing are intentionally
            # gated until the unresolved price-base specification is approved.
            if paid and company['price']>1:
                c.execute('UPDATE finance_companies SET price=? WHERE code=?',(max(1,ceil(D(company['price'])*D('.8'))),code))
        c.execute('INSERT OR IGNORE INTO finance_dividends VALUES (?,?,?,?,?)',(code,p,fund,paid,stamp(now)))
        c.execute('UPDATE finance_companies SET dividend_period=? WHERE code=?',(p,code))

def release_listing(c,listing,status):
    for r in c.execute('SELECT * FROM finance_stock_reservations WHERE listing_id=?',(listing,)).fetchall():
        c.execute('UPDATE finance_stock_lots SET reserved=reserved-? WHERE id=?',(r['quantity'],r['lot_id']))
    c.execute('DELETE FROM finance_stock_reservations WHERE listing_id=?',(listing,))
    c.execute('UPDATE finance_stock_listings SET status=? WHERE id=?',(status,listing))

def bank_progress(c,user,now,wealth):
    a=account(c,user,now);days=(now-parse(a['joined_at'])).days
    active=c.execute('SELECT count(*) FROM finance_activity WHERE user_id=?',(user,)).fetchone()[0]
    ops=c.execute("SELECT count(*) FROM transactions WHERE user_id=? AND json_extract(metadata,'$.finance')=1",(user,)).fetchone()[0]
    overdue=c.execute("SELECT 1 FROM finance_loans WHERE user_id=? AND status='OVERDUE'",(user,)).fetchone()
    eligible=1
    for level,cap,history,activity,operations in ((2,25000,7,3,0),(3,100000,14,7,5),(4,1000000,30,15,15),(5,10000000,60,30,30)):
        if wealth>=cap and days>=history and active>=activity and ops>=operations and not overdue:eligible=level
    actual=a['bank_level'];deadline=a['downgrade_at']
    if eligible>=actual:actual=eligible;deadline=None
    elif deadline is None:deadline=stamp(now+timedelta(days=7))
    elif now>=parse(deadline):actual=eligible;deadline=None
    obligations=c.execute("SELECT count(*) FROM finance_loans WHERE user_id=? AND status='PAID' AND was_overdue=0",(user,)).fetchone()[0]
    vip=''
    for name,level,cap,history,operations,timely in (('Silver',2,50000,14,5,0),('Gold',3,500000,30,15,5),('Black',4,5000000,60,30,10)):
        if actual>=level and wealth>=cap and days>=history and ops>=operations and obligations>=timely and not overdue:vip=name
    suspend=a['vip_suspend_at']
    if a['vip'] and vip!=a['vip']:
        if not suspend:suspend=stamp(now+timedelta(days=7));vip=a['vip']
        elif now<parse(suspend):vip=a['vip']
    else:suspend=None
    c.execute('UPDATE finance_accounts SET bank_level=?,downgrade_at=?,vip=?,vip_suspend_at=? WHERE user_id=?',(actual,deadline,vip,suspend,user))
    return {'level':actual,'vip':vip,'downgrade_at':deadline,'vip_suspend_at':suspend,'history_days':days,'active_days':active,'operations':ops,'rating':None,'rating_label':'Недостаточно данных' if not obligations else 'Формула рейтинга ожидает согласования','overdue':bool(overdue)}

def make_offers(c,user,now,wealth):
    a=account(c,user,now)
    candidates=[]
    for name,(price,cap,discount,per,day) in cfg.CARDS.items():
        if list(cfg.CARDS).index(name)>list(cfg.CARDS).index(a['card']) and wealth['total']>=cap and wealth['available']>=price:
            candidates.append((f'card:{name}',f'Капитал позволяет получить карту {name.title()}. Стоимость ${price}; скидка на банковские комиссии {D(discount)*100}%.'));break
    if wealth['available']>=1000:candidates.append(('deposit:silver','Серебряный вклад: от $1 000, срок 6 часов, 2% за весь срок. Досрочно удерживается 25% начисленных процентов.'))
    if wealth['debt']:candidates.append(('repay','Есть обязательства по кредитам. Погашение уменьшит долг; дополнительных комиссий нет.'))
    for code,reason in candidates[:3]:
        c.execute('INSERT OR IGNORE INTO finance_offers(user_id,code,reason,created_at,expires_at) VALUES (?,?,?,?,?)',(user,code,reason,stamp(now),stamp(now+timedelta(hours=24))))

def goal_progress(c,user,goal):
    if goal['kind']=='capital_growth':current=capital(c,user)['total']-goal['baseline']
    elif goal['kind']=='repayment':current=c.execute('SELECT COALESCE(sum(paid),0) FROM finance_loans WHERE user_id=?',(user,)).fetchone()[0]-goal['baseline']
    else:
        current=D(0)
        for r in c.execute("SELECT metadata FROM transactions WHERE user_id=? AND description LIKE 'Работа:%' AND id>?",(user,goal['baseline'])):
            m=json.loads(r[0] or '{}');current+=D(m.get('revenue',0))-D(m.get('expenses',0))-D(m.get('wages',0))
    return max(0,floor(current))

def season_state(c,user,now):
    start=c.execute("SELECT value FROM finance_meta WHERE key='catalog_v16'").fetchone()[0]
    epoch=parse(start);period=max(0,int((now-epoch).total_seconds()//(14*86400)))
    opens=epoch+timedelta(days=period*14);ends=opens+timedelta(days=14)
    trades=0;days=set()
    for row in c.execute('SELECT description,metadata,created_at FROM transactions WHERE user_id=? AND created_at>=datetime(?) AND created_at<datetime(?)',(user,stamp(opens),stamp(ends))):
        if row['description'] in ('Сделка с акциями','Покупка акций у игрока','Продажа акций игроку'):trades+=1
        if row['description'].startswith('Работа:'):
            m=json.loads(row['metadata'] or '{}')
            if D(m.get('revenue',0))-D(m.get('expenses',0))-D(m.get('wages',0))>0:days.add(row['created_at'][:10])
    c.execute('INSERT INTO finance_seasons(user_id,period,stock_trades,profit_days) VALUES (?,?,?,?) ON CONFLICT(user_id,period) DO UPDATE SET stock_trades=excluded.stock_trades,profit_days=excluded.profit_days',(user,period,trades,json.dumps(sorted(days))))
    return {'period':period+1,'ends_at':stamp(ends),'trades':trades,'profit_days':len(days),'rewards_ready':cfg.SEASON_REWARDS is not None}

def state(path,user):
    with get_connection(path) as c:
        c.execute('BEGIN IMMEDIATE');now=now_utc();account(c,user,now)
        # Close actual enterprise periods before computing financial capacity.
        from services.businesses import settle
        for r in c.execute('SELECT id FROM owned_enterprises WHERE user_id=? AND retired=0',(user,)).fetchall():settle(c,user,r[0],now)
        advance_loans(c,user,now);advance_market(c,now)
        c.execute('INSERT OR IGNORE INTO finance_activity VALUES (?,?)',(user,now.date().isoformat()))
        wealth=capital(c,user);progress=bank_progress(c,user,now,wealth['total']);make_offers(c,user,now,wealth)
        a=dict(account(c,user,now))
        companies=[]
        for r in c.execute('SELECT * FROM finance_companies ORDER BY code'):
            entry=dict(r);entry['holding']=c.execute('SELECT COALESCE(sum(quantity),0) FROM finance_stock_lots WHERE user_id=? AND company=?',(user,r['code'])).fetchone()[0]
            companies.append(entry)
        crypto=[]
        for code in ('BTC','ETH','SOL'):
            q=c.execute('SELECT * FROM finance_crypto_quotes WHERE code=?',(code,)).fetchone();h=c.execute('SELECT quantity FROM finance_crypto_holdings WHERE user_id=? AND code=?',(user,code)).fetchone()
            crypto.append({'code':code,'price':float(q['price']) if q else None,'updated_at':q['updated_at'] if q else None,'fresh':bool(q and 0<=(now-parse(q['updated_at'])).total_seconds()<=cfg.CRYPTO_MAX_AGE_SECONDS),'holding':h[0] if h else '0'})
        loans=[]
        for r in c.execute('SELECT * FROM finance_loans WHERE user_id=? ORDER BY id DESC',(user,)):
            entry=dict(r);entry['schedule']=[dict(p) for p in c.execute('SELECT * FROM finance_installments WHERE loan_id=? ORDER BY due_at',(r['id'],))];loans.append(entry)
        next_payment=c.execute("SELECT i.due_at,i.amount-i.paid AS amount FROM finance_installments i JOIN finance_loans l ON l.id=i.loan_id WHERE l.user_id=? AND i.paid<i.amount ORDER BY i.due_at LIMIT 1",(user,)).fetchone()
        events=[{**dict(r),'name':EVENTS[r['kind']][0]} for r in c.execute('SELECT * FROM finance_events ORDER BY id DESC LIMIT 40')]
        goals=[]
        for goal in c.execute('SELECT * FROM finance_goals WHERE user_id=? ORDER BY id',(user,)).fetchall():
            completed=goal_progress(c,user,goal);goals.append({**dict(goal),'progress':completed,'achieved':completed>=goal['target']})
        season=season_state(c,user,now)
        for e in events:
            notify(c,user,f'event:{e["id"]}:start',f'Началось событие: {e["name"]}',now)
            if e['ended']:notify(c,user,f'event:{e["id"]}:end',f'Завершилось событие: {e["name"]}',now)
        result={'capital':wealth,'balance':wealth['available'],'account':a,'progress':progress,'next_payment':dict(next_payment) if next_payment else None,
          'deposits':[dict(r) for r in c.execute('SELECT * FROM finance_deposits WHERE user_id=? ORDER BY id DESC',(user,))],
          'deposit_products':cfg.DEPOSITS,'cards':cfg.CARDS,'loan_products':cfg.LOANS,'income_per_hour':float(business_income(c,user,now)),
          'legacy_deposits':[dict(r) for r in c.execute('SELECT * FROM works_deposits WHERE user_id=? ORDER BY id DESC',(user,))],
          'loans':loans,'companies':companies,'crypto':crypto,'stock_fee_ready':cfg.STOCK_FEE_ROUNDING is not None,
          'stock_listings':[dict(r) for r in c.execute("SELECT * FROM finance_stock_listings WHERE status='ACTIVE' ORDER BY id DESC LIMIT 100")],
          'events':events,'notifications':[dict(r) for r in c.execute('SELECT * FROM finance_notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 30',(user,))],
          'offers':[dict(r) for r in c.execute('SELECT * FROM finance_offers WHERE user_id=? AND dismissed_at IS NULL AND expires_at>? ORDER BY id LIMIT 3',(user,stamp(now)))],
          'goals':goals,'season':season,
          'history':[dict(r) for r in c.execute('SELECT id,type,amount,balance_before,balance_after,description,created_at FROM transactions WHERE user_id=? AND created_at>=datetime(?) ORDER BY id DESC LIMIT 500',(user,stamp(now-timedelta(days=30))))],
          'pending_parameters':{'stock_fee_rounding':cfg.STOCK_FEE_ROUNDING,'large_transfer_threshold':cfg.LARGE_TRANSFER_THRESHOLD,'credit_rating_formula':cfg.CREDIT_RATING_FORMULA},
          'server_time':stamp(now)}
        c.commit();return result

def fee(c,user,amount,rate):
    a=c.execute('SELECT * FROM finance_accounts WHERE user_id=?',(user,)).fetchone()
    discount=D(cfg.CARDS[a['card']][2])
    vip=D({'Silver':'.05','Gold':'.10','Black':'.15'}.get(a['vip'],'0'))
    # Legacy integer-dollar bank charges round up; reuse for transfer/crypto.
    return ceil(D(amount)*D(rate)*(1-discount)*(1-vip))

def stock_fee(c,user,amount):
    if cfg.STOCK_FEE_ROUNDING is None:raise EconomyError('Торговля акциями ожидает согласования округления комиссии 1%')
    a=c.execute('SELECT * FROM finance_accounts WHERE user_id=?',(user,)).fetchone()
    discount=D(cfg.CARDS[a['card']][2]) if a else D(0)
    vip=D({'Silver':'.05','Gold':'.10','Black':'.15'}.get(a['vip'],'0')) if a else D(0)
    raw=D(amount)*D('.01')*(1-discount)*(1-vip)
    if cfg.STOCK_FEE_ROUNDING=='ceil':return ceil(raw)
    if cfg.STOCK_FEE_ROUNDING=='floor':return floor(raw)
    raise EconomyError('Неизвестное правило округления комиссии')

def require_trading_hours(now):
    zone=os.getenv('GAME_TIMEZONE','UTC')
    market_time=now.astimezone(timezone.utc if zone=='UTC' else ZoneInfo(zone))
    if market_time.hour<8:raise EconomyError('Торговля акциями доступна с 08:00 до 00:00')

def trade_stock(c,user,p,now):
    require_trading_hours(now)
    company=c.execute('SELECT * FROM finance_companies WHERE code=?',(p.get('company'),)).fetchone()
    if not company:raise EconomyError('Компания не найдена')
    quantity=positive(p.get('quantity'),'Количество акций');side=p.get('side');amount=quantity*company['price']
    commission=stock_fee(c,user,amount);before=get_balance(c,user)
    if side=='buy':
        if amount<100 or quantity>company['player_supply']:raise EconomyError('Недостаточно акций компании или сумма меньше $100')
        remove_balance(c,user,amount+commission)
        c.execute('UPDATE finance_companies SET player_supply=player_supply-? WHERE code=?',(quantity,company['code']))
        c.execute('INSERT INTO finance_stock_lots(user_id,company,quantity,unit_cost,acquired_at) VALUES (?,?,?,?,?)',(user,company['code'],quantity,company['price'],stamp(now)))
    elif side=='sell':
        remaining=quantity
        for lot in c.execute('SELECT * FROM finance_stock_lots WHERE user_id=? AND company=? AND quantity>reserved ORDER BY acquired_at,id',(user,company['code'])).fetchall():
            take=min(remaining,lot['quantity']-lot['reserved']);remaining-=take
            if take==lot['quantity']:c.execute('DELETE FROM finance_stock_lots WHERE id=?',(lot['id'],))
            else:c.execute('UPDATE finance_stock_lots SET quantity=quantity-? WHERE id=?',(take,lot['id']))
            if not remaining:break
        if remaining:raise EconomyError('Недостаточно свободных акций')
        c.execute('UPDATE users SET balance=balance+? WHERE id=?',(amount-commission,user))
        c.execute('UPDATE finance_companies SET player_supply=player_supply+? WHERE code=?',(quantity,company['code']))
    else:raise EconomyError('Выберите покупку или продажу')
    ledger(c,user,'Сделка с акциями',amount,before,get_balance(c,user),{'company':company['code'],'side':side,'quantity':quantity,'fee':commission})
    return {'amount':amount,'fee':commission}

def mutate(path,user,action,p,key):
    if not isinstance(key,str) or not key.strip() or len(key)>100:raise EconomyError('Требуется постоянный идентификатор операции')
    if not isinstance(p,dict):raise EconomyError('Некорректные параметры операции')
    with get_connection(path) as c:
        c.execute('BEGIN IMMEDIATE')
        old=cached(c,user,key,'finance:'+action,p)
        if old:return old
        now=now_utc();a=account(c,user,now);advance_loans(c,user,now);advance_market(c,now)
        # Discounts must expire on the server even if the caller skips GET state.
        bank_progress(c,user,now,capital(c,user)['total']);a=account(c,user,now)
        before=get_balance(c,user);result={};amount=0
        if action=='deposit':
            product=p.get('product')
            if product not in cfg.DEPOSITS:raise EconomyError('Неизвестный вклад')
            minimum,hours,rate=cfg.DEPOSITS[product];amount=positive(p.get('amount'))
            if amount<minimum:raise EconomyError(f'Минимум для этого вклада ${minimum}')
            remove_balance(c,user,amount)
            cur=c.execute('INSERT INTO finance_deposits(user_id,product,principal,rate,started_at,due_at) VALUES (?,?,?,?,?,?)',(user,product,amount,rate,stamp(now),stamp(now+timedelta(hours=hours))))
            result={'deposit_id':cur.lastrowid};ledger(c,user,'Открытие вклада',amount,before,get_balance(c,user),result)
        elif action=='close-deposit':
            row=c.execute('SELECT * FROM finance_deposits WHERE id=? AND user_id=?',(p.get('id'),user)).fetchone()
            if not row or row['status']!='ACTIVE':raise EconomyError('Вклад уже закрыт или принадлежит другому игроку')
            duration=D((parse(row['due_at'])-parse(row['started_at'])).total_seconds())
            elapsed=min(duration,max(D(0),D((now-parse(row['started_at'])).total_seconds())))
            early=elapsed<duration;interest=floor(D(row['principal'])*D(row['rate'])*elapsed/duration*(D('.75') if early else 1))
            amount=row['principal']+interest
            c.execute("UPDATE finance_deposits SET status='CLOSED',interest_paid=? WHERE id=?",(interest,row['id']))
            c.execute('UPDATE users SET balance=balance+? WHERE id=?',(amount,user));result={'amount':amount,'interest':interest,'early':early}
            ledger(c,user,'Закрытие вклада',amount,before,before+amount,{'deposit_id':row['id'],**result})
        elif action=='card':
            card=p.get('card')
            if card not in cfg.CARDS or list(cfg.CARDS).index(card)<=list(cfg.CARDS).index(a['card']):raise EconomyError('Выберите карту выше текущей')
            amount,required,*_=cfg.CARDS[card]
            if capital(c,user)['total']<required:raise EconomyError('Недостаточный капитал для карты')
            remove_balance(c,user,amount);c.execute('UPDATE finance_accounts SET card=? WHERE user_id=?',(card,user));ledger(c,user,'Покупка банковской карты',amount,before,before-amount,{'card':card})
        elif action=='transfer':
            amount=positive(p.get('amount'));target=p.get('recipient');comment=p.get('comment','')
            if not isinstance(comment,str) or len(comment)>240:raise EconomyError('Комментарий: максимум 240 символов')
            receiver=c.execute('SELECT id,level FROM users WHERE telegram_id=?',(target,)).fetchone() if type(target) is int else None
            if not receiver or receiver['id']==user:raise EconomyError('Укажите Telegram ID другого игрока')
            if cfg.LARGE_TRANSFER_THRESHOLD is None and p.get('confirmed') is not True:raise EconomyError('Подтвердите сумму, получателя и комиссию перевода')
            if cfg.LARGE_TRANSFER_THRESHOLD is not None and amount>=cfg.LARGE_TRANSFER_THRESHOLD and p.get('confirmed') is not True:raise EconomyError('Подтвердите крупный перевод')
            sender_level=c.execute('SELECT level FROM users WHERE id=?',(user,)).fetchone()[0];ra=account(c,receiver['id'],now)
            cut=stamp(now-timedelta(hours=24))
            sent=c.execute('SELECT COALESCE(sum(amount),0) FROM finance_transfers WHERE sender_id=? AND created_at>?',(user,cut)).fetchone()[0]
            received=c.execute('SELECT COALESCE(sum(amount),0) FROM finance_transfers WHERE receiver_id=? AND created_at>?',(receiver['id'],cut)).fetchone()[0]
            out=cfg.CARDS[a['card']][4];inc=cfg.CARDS[ra['card']][4]
            for bound,receive,send in cfg.TRANSFER_LIMITS:
                if sender_level<bound:out=min(out,send);break
            for bound,receive,send in cfg.TRANSFER_LIMITS:
                if receiver['level']<bound:inc=min(inc,receive);break
            if amount>cfg.CARDS[a['card']][3] or amount>cfg.CARDS[ra['card']][3] or sent+amount>out or received+amount>inc:raise EconomyError('Превышен лимит карты или уровня за скользящие 24 часа')
            commission=fee(c,user,amount,'.02');remove_balance(c,user,amount+commission);rb=get_balance(c,receiver['id'])
            c.execute('UPDATE users SET balance=balance+? WHERE id=?',(amount,receiver['id']))
            cur=c.execute('INSERT INTO finance_transfers(sender_id,receiver_id,amount,fee,comment,created_at) VALUES (?,?,?,?,?,?)',(user,receiver['id'],amount,commission,comment,stamp(now)))
            ledger(c,user,'Исходящий перевод',amount+commission,before,get_balance(c,user),{'recipient':receiver['id'],'fee':commission,'comment':comment})
            ledger(c,receiver['id'],'Входящий перевод',amount,rb,rb+amount,{'sender':user,'comment':comment});result={'transfer_id':cur.lastrowid,'fee':commission,'received':amount}
        elif action=='loan':
            product=p.get('product');amount=positive(p.get('amount'));parts=p.get('payments',1)
            if product not in cfg.LOANS or type(parts) is not int or not 1<=parts<=24:raise EconomyError('Некорректный продукт или число платежей')
            if c.execute("SELECT 1 FROM finance_loans WHERE user_id=? AND status!='PAID'",(user,)).fetchone():raise EconomyError('Сначала погасите текущий кредит; при просрочке выдача заблокирована')
            limit,rate=cfg.LOANS[product];wealth=max(0,capital(c,user)['total']);income=business_income(c,user,now)
            approved=floor(min(D(limit),D('.25')*wealth,D(12)*income))
            if amount>approved:raise EconomyError(f'Доступный лимит кредита ${approved}. Учитывается фактический чистый доход.')
            total=ceil(D(amount)*(1+D(rate)));due=now+timedelta(hours=24)
            cur=c.execute('INSERT INTO finance_loans(user_id,product,principal,total_due,started_at,due_at) VALUES (?,?,?,?,?,?)',(user,product,amount,total,stamp(now),stamp(due)))
            for i in range(parts):
                piece=total//parts+(1 if i<total%parts else 0)
                if piece:c.execute('INSERT INTO finance_installments(loan_id,amount,due_at) VALUES (?,?,?)',(cur.lastrowid,piece,stamp(now+timedelta(seconds=24*3600*(i+1)/parts))))
            c.execute('UPDATE users SET balance=balance+? WHERE id=?',(amount,user));result={'loan_id':cur.lastrowid,'total_due':total,'due_at':stamp(due)}
            ledger(c,user,'Выдача кредита',amount,before,before+amount,result)
        elif action in ('repay','autopay','restructure'):
            loan=c.execute('SELECT * FROM finance_loans WHERE id=? AND user_id=?',(p.get('id'),user)).fetchone()
            if not loan or loan['status']=='PAID':raise EconomyError('Активный кредит не найден')
            if action=='repay':result={'paid':pay_loan(c,user,loan,positive(p.get('amount')),now,'finance-payment:'+key)}
            elif action=='autopay':
                if type(p.get('enabled')) is not bool:raise EconomyError('Некорректная настройка')
                c.execute('UPDATE finance_loans SET autopay=? WHERE id=?',(int(p['enabled']),loan['id']))
            else:
                if loan['restructured']:raise EconomyError('Повторная реструктуризация требует рассмотрения банком')
                if p.get('confirmed') is not True:raise EconomyError('Подтвердите новый график: остаток долга через 48 часов, без дополнительных процентов')
                due=now+timedelta(hours=48);left=loan['total_due']-loan['paid']
                c.execute("UPDATE finance_loans SET restructured=1,due_at=?,status='ACTIVE' WHERE id=?",(stamp(due),loan['id']))
                c.execute('DELETE FROM finance_installments WHERE loan_id=?',(loan['id'],))
                c.execute('INSERT INTO finance_installments(loan_id,amount,due_at) VALUES (?,?,?)',(loan['id'],left,stamp(due)))
                result={'due_at':stamp(due),'remaining':left};ledger(c,user,'Реструктуризация кредита',0,before,get_balance(c,user),result)
        elif action=='savings-setting':
            if type(p.get('enabled')) is not bool:raise EconomyError('Некорректная настройка накоплений')
            c.execute('UPDATE finance_accounts SET auto_savings=? WHERE user_id=?',(int(p['enabled']),user))
        elif action=='withdraw-savings':
            amount=positive(p.get('amount'));available=account(c,user,now)['savings']
            if amount>available:raise EconomyError('Недостаточно накоплений')
            c.execute('UPDATE finance_accounts SET savings=savings-? WHERE user_id=?',(amount,user));c.execute('UPDATE users SET balance=balance+? WHERE id=?',(amount,user))
            ledger(c,user,'Снятие накоплений',amount,before,before+amount)
        elif action=='withdraw-legacy-savings':
            amount=positive(p.get('amount'))
            from services.banking import _accrue,_ensure_account
            legacy,_=_accrue(c,user,_ensure_account(c,user),now)
            if amount>floor(legacy['balance']):raise EconomyError('Недостаточно средств на прежнем накопительном счёте')
            c.execute('UPDATE player_savings_accounts SET balance=balance-? WHERE user_id=?',(amount,user))
            c.execute('UPDATE users SET balance=balance+? WHERE id=?',(amount,user))
            ledger(c,user,'Снятие с прежнего накопительного счёта',amount,before,before+amount)
        elif action=='collect-legacy-deposit':
            row=c.execute('SELECT * FROM works_deposits WHERE id=? AND user_id=?',(p.get('id'),user)).fetchone()
            if not row or row['status']!='ACTIVE':raise EconomyError('Прежний вклад уже получен или принадлежит другому игроку')
            if now<parse(row['matures_at']):raise EconomyError('Срок прежнего вклада ещё не завершён')
            # Preserve the original product's annual rate and rounding, not V16 rates.
            interest=round(int(row['principal'])*float(row['annual_rate'])*int(row['term_days'])/365)
            amount=int(row['principal'])+interest
            c.execute("UPDATE works_deposits SET status='PAID',paid_at=? WHERE id=?",(stamp(now),row['id']))
            c.execute('UPDATE users SET balance=balance+? WHERE id=?',(amount,user))
            result={'amount':amount,'interest':interest}
            ledger(c,user,'Получение прежнего вклада',amount,before,before+amount,{'legacy_deposit_id':row['id'],'interest':interest})
        elif action=='stock':result=trade_stock(c,user,p,now)
        elif action=='stock-list':
            quantity=positive(p.get('quantity'));price=positive(p.get('price'));code=p.get('company')
            cur=c.execute('INSERT INTO finance_stock_listings(user_id,company,quantity,price,created_at,expires_at) VALUES (?,?,?,?,?,?)',(user,code,quantity,price,stamp(now),stamp(now+timedelta(days=7))))
            left=quantity
            for lot in c.execute('SELECT * FROM finance_stock_lots WHERE user_id=? AND company=? AND quantity>reserved ORDER BY acquired_at,id',(user,code)).fetchall():
                take=min(left,lot['quantity']-lot['reserved']);left-=take
                c.execute('UPDATE finance_stock_lots SET reserved=reserved+? WHERE id=?',(take,lot['id']))
                c.execute('INSERT INTO finance_stock_reservations VALUES (?,?,?)',(cur.lastrowid,lot['id'],take))
                if not left:break
            if left:raise EconomyError('Недостаточно свободных акций')
            result={'listing_id':cur.lastrowid}
        elif action in ('stock-cancel','stock-buy-listing'):
            listing=c.execute("SELECT * FROM finance_stock_listings WHERE id=? AND status='ACTIVE'",(p.get('id'),)).fetchone()
            if not listing:raise EconomyError('Объявление уже закрыто')
            if action=='stock-cancel':
                if listing['user_id']!=user:raise EconomyError('Это чужое объявление')
                release_listing(c,listing['id'],'CANCELLED')
            else:
                if listing['user_id']==user:raise EconomyError('Нельзя купить свои акции')
                require_trading_hours(now)
                bank_progress(c,listing['user_id'],now,capital(c,listing['user_id'])['total'])
                amount=listing['price']*listing['quantity'];buy_fee=stock_fee(c,user,amount);sell_fee=stock_fee(c,listing['user_id'],amount)
                if amount<100:raise EconomyError('Минимальная сумма покупки акций $100')
                remove_balance(c,user,amount+buy_fee)
                seller_before=get_balance(c,listing['user_id']);c.execute('UPDATE users SET balance=balance+? WHERE id=?',(amount-sell_fee,listing['user_id']))
                for lot in c.execute('SELECT r.quantity AS take,l.* FROM finance_stock_reservations r JOIN finance_stock_lots l ON l.id=r.lot_id WHERE r.listing_id=?',(listing['id'],)).fetchall():
                    c.execute('DELETE FROM finance_stock_reservations WHERE listing_id=? AND lot_id=?',(listing['id'],lot['id']))
                    if lot['take']==lot['quantity']:c.execute('DELETE FROM finance_stock_lots WHERE id=?',(lot['id'],))
                    else:c.execute('UPDATE finance_stock_lots SET quantity=quantity-?,reserved=reserved-? WHERE id=?',(lot['take'],lot['take'],lot['id']))
                c.execute('INSERT INTO finance_stock_lots(user_id,company,quantity,unit_cost,acquired_at) VALUES (?,?,?,?,?)',(user,listing['company'],listing['quantity'],listing['price'],stamp(now)))
                c.execute("UPDATE finance_stock_listings SET status='SOLD' WHERE id=?",(listing['id'],))
                ledger(c,user,'Покупка акций у игрока',amount,before,get_balance(c,user),{'fee':buy_fee})
                ledger(c,listing['user_id'],'Продажа акций игроку',amount,seller_before,get_balance(c,listing['user_id']),{'fee':sell_fee})
        elif action=='crypto':
            code=p.get('code');quote=c.execute('SELECT * FROM finance_crypto_quotes WHERE code=?',(code,)).fetchone()
            if code not in ('BTC','ETH','SOL') or not quote or not 0<=(now-parse(quote['updated_at'])).total_seconds()<=cfg.CRYPTO_MAX_AGE_SECONDS:raise EconomyError('Котировка устарела или отсутствует. Сделка заблокирована.')
            try:quantity=D(p.get('quantity','0'))
            except Exception:raise EconomyError('Некорректное количество криптовалюты')
            if not quantity.is_finite() or quantity<=0 or quantity>10**8 or quantity.as_tuple().exponent < -8:raise EconomyError('Количество: положительное число, до 8 знаков после запятой')
            holding=c.execute('SELECT * FROM finance_crypto_holdings WHERE user_id=? AND code=?',(user,code)).fetchone()
            old=D(holding['quantity']) if holding else D(0);cost=D(holding['cost_basis']) if holding else D(0)
            side=p.get('side');raw=quantity*D(quote['price']);amount=ceil(raw) if side=='buy' else floor(raw)
            if amount<1:raise EconomyError('Сумма сделки меньше $1')
            commission=fee(c,user,amount,'.02')
            if side=='buy':remove_balance(c,user,amount+commission);new=old+quantity;cost+=amount
            elif side=='sell':
                if old<quantity:raise EconomyError('Недостаточно криптовалюты')
                new=old-quantity;cost=cost*new/old;c.execute('UPDATE users SET balance=balance+? WHERE id=?',(max(0,amount-commission),user))
            else:raise EconomyError('Выберите покупку или продажу')
            if new:c.execute('INSERT INTO finance_crypto_holdings VALUES (?,?,?,?) ON CONFLICT(user_id,code) DO UPDATE SET quantity=excluded.quantity,cost_basis=excluded.cost_basis',(user,code,str(new),str(cost)))
            else:c.execute('DELETE FROM finance_crypto_holdings WHERE user_id=? AND code=?',(user,code))
            result={'amount':amount,'fee':commission};ledger(c,user,'Сделка с криптовалютой',amount,before,get_balance(c,user),{'code':code,'side':side,'quantity':str(quantity),'fee':commission})
        elif action=='goal':
            target=positive(p.get('target'));kind=p.get('kind');main=p.get('main',False)
            if kind not in ('capital_growth','repayment','profit') or type(main) is not bool:raise EconomyError('Неизвестная цель')
            count=c.execute('SELECT count(*) FROM finance_goals WHERE user_id=? AND main=? AND completed=0',(user,int(main))).fetchone()[0]
            if count>=(1 if main else 2):raise EconomyError('Доступны одна основная и две дополнительные цели')
            baseline=capital(c,user)['total'] if kind=='capital_growth' else c.execute('SELECT COALESCE(sum(paid),0) FROM finance_loans WHERE user_id=?',(user,)).fetchone()[0] if kind=='repayment' else c.execute('SELECT COALESCE(max(id),0) FROM transactions WHERE user_id=?',(user,)).fetchone()[0]
            c.execute('INSERT INTO finance_goals(user_id,kind,target,baseline,main,created_at) VALUES (?,?,?,?,?,?)',(user,kind,target,baseline,int(main),stamp(now)))
        elif action=='dismiss-offer':
            if c.execute('UPDATE finance_offers SET dismissed_at=? WHERE id=? AND user_id=?',(stamp(now),p.get('id'),user)).rowcount!=1:raise EconomyError('Предложение не найдено')
        else:raise EconomyError('Неизвестная банковская операция')
        result={'success':True,'balance':get_balance(c,user),**result};receipt(c,user,key,'finance:'+action,p,result);c.commit();return result

def refresh_crypto(path):
    """Network outside any DB transaction. Credentials are never sent to the browser."""
    from urllib.request import Request,urlopen
    with get_connection(path) as c:
        recent=c.execute('SELECT max(updated_at) FROM finance_crypto_quotes').fetchone()[0]
        if recent and (now_utc()-parse(recent)).total_seconds()<60:return
    req=Request('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd&include_last_updated_at=true',headers={'Accept':'application/json','User-Agent':'VirtualWorld/16'})
    try:
        with urlopen(req,timeout=5) as response:payload=json.loads(response.read(100000))
        now=now_utc();rows=[]
        for code,key in (('BTC','bitcoin'),('ETH','ethereum'),('SOL','solana')):
            value=payload[key];price=D(value['usd']);updated=datetime.fromtimestamp(value['last_updated_at'],timezone.utc)
            if not price.is_finite() or price<=0 or not 0<=(now-updated).total_seconds()<=cfg.CRYPTO_MAX_AGE_SECONDS:raise ValueError('Stale quote')
            rows.append((code,str(price),stamp(updated),'CoinGecko'))
    except Exception:return
    with get_connection(path) as c:
        c.executemany('INSERT INTO finance_crypto_quotes VALUES (?,?,?,?) ON CONFLICT(code) DO UPDATE SET price=excluded.price,updated_at=excluded.updated_at,source=excluded.source',rows);c.commit()
