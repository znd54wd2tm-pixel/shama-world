"""Integration and adversarial regressions for the new shared economy."""
import unittest
import json
import hashlib
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from tests import test_game_economy as fixtures
NOW=fixtures.NOW
from database import get_connection,init_db
from seed_data import seed_content,CASES
from services.economy import EconomyError,sell_item
from services.finance import state,mutate,stamp,capital,advance_loans,advance_market,advance_dividends
from services.businesses import business_action,settle,load_owned,rates
from services.game import open_case_batch
from services.catalog import list_cases,get_case,list_inventory
from catalog_v16 import CATALOGS,COFFEE_EQUIPMENT

class V16Tests(unittest.TestCase):
    setUp=fixtures.GameTests.setUp;tearDown=fixtures.GameTests.tearDown;scalar=fixtures.GameTests.scalar;fund=fixtures.GameTests.fund
    def call(self,action,p,key='request',user=None,now=NOW):
        with patch('services.finance.now_utc',return_value=now):return mutate(self.path,user or self.user,action,p,key)
    def view(self,now=NOW):
        with patch('services.finance.now_utc',return_value=now):return state(self.path,self.user)
    def buy_coffee(self):
        kind=self.scalar("SELECT id FROM enterprise_catalog WHERE code='coffee'")
        with patch('services.businesses.now_utc',return_value=NOW):return business_action(self.path,self.user,kind,'buy',{},'coffee')['enterprise']['id']
    def test_catalog_sizes_and_user_images(self):
        cases=list_cases(self.path);self.assertEqual(len(cases),5)
        for name,n in (('Стартовый',15),('Неоновый',15),('Золотой',20),('Королевский',21)):
            case=get_case(self.path,next(r['id'] for r in cases if r['name']==name))
            self.assertEqual(len(case['drops']),n);self.assertAlmostEqual(sum(r['chance'] for r in case['drops']),1)
            self.assertTrue(case['image'].startswith('/assets/cases/user-'))
        self.assertEqual(self.scalar("SELECT count(*) FROM catalogue_membership WHERE collection='collection'"),7)
    def test_royal_preserves_relative_weights_and_price(self):
        royal=next(c for c in CASES if c['name']=='Королевский');rid=self.scalar("SELECT id FROM cases WHERE name='Королевский'")
        with get_connection(self.path) as c:
            weights={r['name']:r['chance'] for r in c.execute('SELECT i.name,d.chance FROM case_drops d JOIN items i ON i.id=d.item_id WHERE case_id=?',(rid,))}
        for name,chance in royal['drops']:self.assertAlmostEqual(weights[name],chance*.85)
        self.assertEqual(self.scalar('SELECT price FROM cases WHERE id=?',(rid,)),7500)
    def test_new_display_values_are_not_approved_sell_prices(self):
        item=self.scalar("SELECT id FROM items WHERE asset_key='gold_ring'")
        with get_connection(self.path) as c:c.execute('INSERT INTO inventory(user_id,item_id,quantity) VALUES (?,?,1)',(self.user,item))
        with self.assertRaises(EconomyError):sell_item(self.path,self.user,item,1,'unapproved')
        self.assertEqual(self.scalar('SELECT quantity FROM inventory WHERE item_id=?',(item,)),1)
    def test_restart_does_not_reset_weights_or_user_data(self):
        opened=open_case_batch(self.path,self.user,self.case,10,'batch')
        with get_connection(self.path) as c:before=[tuple(r) for r in c.execute('SELECT * FROM case_drops ORDER BY id')]
        seed_content(self.path);init_db(self.path)
        with get_connection(self.path) as c:after=[tuple(r) for r in c.execute('SELECT * FROM case_drops ORDER BY id')]
        self.assertEqual(before,after);self.assertEqual(opened['balance'],self.scalar('SELECT balance FROM users WHERE id=?',(self.user,)))
        self.assertEqual(self.scalar('SELECT count(*) FROM opening_results'),10)
    def test_deposit_full_term_and_retry(self):
        result=self.call('deposit',{'product':'gold','amount':10000})
        capital_before=self.view()['capital']['total'];self.assertEqual(capital_before,10000000)
        result=self.call('close-deposit',{'id':result['deposit_id']},'close',now=NOW+timedelta(hours=24))
        self.assertEqual(result['amount'],10500);self.assertEqual(result['balance'],10000500)
        self.assertEqual(self.call('close-deposit',{'id':1},'close',now=NOW+timedelta(hours=25))['amount'],10500)
        with self.assertRaises(EconomyError):self.call('close-deposit',{'id':1},'different')
    def test_early_deposit_preserves_principal_and_75_percent_interest(self):
        d=self.call('deposit',{'product':'gold','amount':10000})
        result=self.call('close-deposit',{'id':d['deposit_id']},'close',now=NOW+timedelta(hours=12))
        self.assertEqual(result['amount'],10187);self.assertTrue(result['early'])
    def test_concurrent_deposit_same_key_one_debit(self):
        with patch('services.finance.now_utc',return_value=NOW),ThreadPoolExecutor(4) as pool:
            results=list(pool.map(lambda _:mutate(self.path,self.user,'deposit',{'product':'silver','amount':1000},'same'),range(4)))
        self.assertEqual(len({r['deposit_id'] for r in results}),1)
        self.assertEqual(self.scalar('SELECT count(*) FROM finance_deposits'),1)
    def test_idempotency_fingerprint_and_authorship(self):
        d=self.call('deposit',{'product':'silver','amount':1000})
        with self.assertRaises(EconomyError):self.call('deposit',{'product':'silver','amount':2000})
        with self.assertRaises(EconomyError):self.call('close-deposit',{'id':d['deposit_id']},'steal',self.buyer)
    def test_transfers_fee_exact_amount_limits_and_rolling_window(self):
        p={'recipient':102,'amount':2500,'confirmed':True,'comment':'Gift'}
        r=self.call('transfer',p);self.assertEqual(r['fee'],50);self.assertEqual(self.scalar('SELECT balance FROM users WHERE id=?',(self.buyer,)),10002500)
        self.assertTrue(self.call('transfer',p)['idempotent'])
        with self.assertRaises(EconomyError):self.call('transfer',{**p,'amount':1},'excess')
        # Raising the level does not reset accumulated usage.
        with get_connection(self.path) as c:c.execute('UPDATE users SET level=10 WHERE id=?',(self.user,))
        with self.assertRaises(EconomyError):self.call('transfer',{**p,'amount':8000},'level')
        self.assertTrue(self.call('transfer',p,'next-day',now=NOW+timedelta(hours=24,seconds=1))['success'])
    def test_card_does_not_inflate_capital_and_discounts_fee(self):
        self.call('card',{'card':'gold'})
        self.assertEqual(self.view()['capital']['total'],9975000)
        r=self.call('transfer',{'recipient':102,'amount':100,'confirmed':True},'transfer')
        self.assertEqual(r['fee'],2)
    def test_missing_stock_rounding_blocks_before_debit(self):
        with patch('catalog_v16.STOCK_FEE_ROUNDING',None),self.assertRaises(EconomyError):self.call('stock',{'company':'BANK','quantity':1,'side':'buy'})
        self.assertEqual(self.scalar('SELECT balance FROM users WHERE id=?',(self.user,)),10000000)
    def test_stock_supply_fifo_reserved_and_closed_hours(self):
        with patch('catalog_v16.STOCK_FEE_ROUNDING','ceil'):
            self.call('stock',{'company':'BANK','quantity':4,'side':'buy'},'buy1')
            self.call('stock',{'company':'BANK','quantity':3,'side':'buy'},'buy2',now=NOW+timedelta(minutes=1))
            listing=self.call('stock-list',{'company':'BANK','quantity':2,'price':1000},'list')
            self.call('stock',{'company':'BANK','quantity':5,'side':'sell'},'sell')
            self.assertEqual(self.scalar('SELECT sum(quantity) FROM finance_stock_lots'),2)
            with self.assertRaises(EconomyError):self.call('stock',{'company':'BANK','quantity':1,'side':'sell'},'reserved')
            self.call('stock-cancel',{'id':listing['listing_id']},'cancel')
            self.call('stock',{'company':'BANK','quantity':2,'side':'sell'},'sell2')
            self.assertEqual(self.scalar("SELECT player_supply FROM finance_companies WHERE code='BANK'"),700000)
            with self.assertRaises(EconomyError):self.call('stock',{'company':'BANK','quantity':1,'side':'buy'},'closed',now=NOW.replace(hour=3))
    def test_crypto_stale_quotes_block_and_fresh_virtual_trade(self):
        p={'code':'BTC','quantity':'0.01','side':'buy'}
        with self.assertRaises(EconomyError):self.call('crypto',p)
        with get_connection(self.path) as c:c.execute('INSERT INTO finance_crypto_quotes VALUES (?,?,?,?)',('BTC','50000',stamp(NOW),'fixture'))
        r=self.call('crypto',p);self.assertEqual(r['amount'],500);self.assertEqual(r['fee'],10)
        with self.assertRaises(EconomyError):self.call('crypto',p,'stale',now=NOW+timedelta(minutes=6))
        self.call('crypto',{**p,'side':'sell'},'sell')
        self.assertEqual(self.scalar('SELECT count(*) FROM finance_crypto_holdings'),0)
    def test_p2p_stock_hours_minimum_and_rollback(self):
        self.call('stock',{'company':'BANK','quantity':2,'side':'buy'},'buy')
        listing=self.call('stock-list',{'company':'BANK','quantity':1,'price':99},'small')
        with self.assertRaises(EconomyError):self.call('stock-buy-listing',{'id':listing['listing_id']},'under-minimum',self.buyer)
        self.call('stock-cancel',{'id':listing['listing_id']},'cancel')
        listing=self.call('stock-list',{'company':'BANK','quantity':1,'price':1000},'normal')
        with self.assertRaises(EconomyError):self.call('stock-buy-listing',{'id':listing['listing_id']},'closed',self.buyer,now=NOW.replace(hour=3))
        self.assertEqual(self.scalar('SELECT balance FROM users WHERE id=?',(self.buyer,)),10000000)
        self.assertEqual(self.scalar('SELECT sum(reserved) FROM finance_stock_lots'),1)
        self.call('stock-buy-listing',{'id':listing['listing_id']},'open',self.buyer)
        self.assertEqual(self.scalar('SELECT sum(quantity) FROM finance_stock_lots WHERE user_id=?',(self.buyer,)),1)
    def test_no_loan_without_real_income(self):
        with self.assertRaises(EconomyError):self.call('loan',{'product':'starter','amount':1000})
    def test_legacy_client_liabilities_offset_invested_bank_assets(self):
        with get_connection(self.path) as c:
            c.execute('INSERT INTO bank_accounts(user_id,cash_balance,client_liabilities) VALUES (?,90,100)',(self.user,))
            c.execute("INSERT INTO bank_company_holdings(user_id,company_code,shares,average_cost,dividend_checkpoint) VALUES (?,(SELECT code FROM bank_companies LIMIT 1),1,1,?)",(self.user,stamp(NOW)))
            price=c.execute('SELECT price FROM bank_companies WHERE code=(SELECT company_code FROM bank_company_holdings WHERE user_id=?)',(self.user,)).fetchone()[0]
            wealth=capital(c,self.user)
            self.assertEqual(wealth['legacy_bank_equity'],-10)
            self.assertEqual(wealth['total'],10000000+price-10)
    def fake_actual_income(self):
        from services.economy import record_transaction
        with get_connection(self.path) as c:
            record_transaction(c,self.user,'OTHER',2000,10000000,10002000,description='Работа: fixture',metadata={'revenue':2200,'expenses':100,'wages':100,'seconds':3600})
            c.execute('UPDATE transactions SET created_at=?',(NOW.strftime('%Y-%m-%d %H:%M:%S'),))
    def test_loan_fixed_debt_restructure_autopay_partial_no_duplicate(self):
        self.fake_actual_income();loan=self.call('loan',{'product':'starter','amount':1000})
        self.assertEqual(loan['total_due'],1050)
        self.call('autopay',{'id':loan['loan_id'],'enabled':True},'auto');self.fund(self.user,400)
        self.view(NOW+timedelta(hours=24));self.assertEqual(self.scalar('SELECT paid FROM finance_loans'),400)
        self.view(NOW+timedelta(hours=25));self.assertEqual(self.scalar('SELECT paid FROM finance_loans'),400)
        self.assertEqual(self.scalar('SELECT total_due FROM finance_loans'),1050)
        self.call('restructure',{'id':loan['loan_id'],'confirmed':True},'restructure',now=NOW+timedelta(hours=25))
        with self.assertRaises(EconomyError):self.call('restructure',{'id':loan['loan_id'],'confirmed':True},'again')
        self.assertEqual(self.scalar('SELECT sum(amount) FROM finance_installments'),650)
    def test_coffee_equipment_purchase_and_no_duplicate(self):
        eid=self.buy_coffee()
        with get_connection(self.path) as c:self.assertEqual(rates(load_owned(c,self.user,eid),[])['revenue'],0)
        for key in COFFEE_EQUIPMENT:
            with patch('services.businesses.now_utc',return_value=NOW):business_action(self.path,self.user,eid,'equipment',{'key':key},key)
        with get_connection(self.path) as c:self.assertGreater(rates(load_owned(c,self.user,eid),[])['revenue'],0)
        with self.assertRaises(EconomyError):business_action(self.path,self.user,eid,'equipment',{'key':'machine'},'twice')
    def test_kiosk_worker_and_no_upgrades(self):
        kind=self.scalar("SELECT id FROM enterprise_catalog WHERE code='kiosk'")
        with patch('services.businesses.now_utc',return_value=NOW):
            e=business_action(self.path,self.user,kind,'buy',{},'buy')['enterprise']
            self.assertEqual(e['hourly']['revenue'],0)
            e=business_action(self.path,self.user,e['id'],'hire',{'role':'worker'},'worker')['enterprise']
            self.assertEqual(e['hourly']['revenue'],1000)
            with self.assertRaises(EconomyError):business_action(self.path,self.user,e['id'],'upgrade',{'direction':'equipment','level':1},'upgrade')
    def test_state_buyback_ignores_listing_and_repeated_sale(self):
        eid=self.buy_coffee()
        with patch('services.businesses.now_utc',return_value=NOW):
            r=business_action(self.path,self.user,eid,'state-sale',{'confirmed':True},'sell')
            self.assertEqual(r['amount'],10000)
            self.assertTrue(business_action(self.path,self.user,eid,'state-sale',{'confirmed':True},'sell')['idempotent'])
            with self.assertRaises(EconomyError):business_action(self.path,self.user,eid,'state-sale',{'confirmed':True},'twice')
        self.assertEqual(self.view()['capital']['enterprises'],0)
    def test_repurchase_after_state_sale_retains_historical_object(self):
        eid=self.buy_coffee()
        with patch('services.businesses.now_utc',return_value=NOW):
            business_action(self.path,self.user,eid,'state-sale',{'confirmed':True},'sell')
            catalog=self.scalar("SELECT id FROM enterprise_catalog WHERE code='coffee'")
            new=business_action(self.path,self.user,catalog,'buy',{},'rebuy')['enterprise']['id']
        self.assertNotEqual(eid,new);self.assertEqual(self.scalar('SELECT count(*) FROM owned_enterprises'),2)
        with get_connection(self.path) as c:self.assertFalse(c.execute('PRAGMA foreign_key_check').fetchall())
    def test_experienced_employee_preserves_role_and_salary(self):
        eid=self.buy_coffee()
        with patch('services.businesses.now_utc',return_value=NOW):r=business_action(self.path,self.user,eid,'hire',{'role':'experienced'},'experienced')
        self.assertEqual(r['enterprise']['employees'][0]['role'],'experienced')
        self.assertEqual(r['enterprise']['employees'][0]['salary'],40)
    def test_achievement_xp_awarded_once(self):
        from services.profile import profile
        with get_connection(self.path) as c:c.execute('UPDATE users SET cases_opened=1 WHERE id=?',(self.user,))
        first=profile(self.path,self.user)['user']['xp'];second=profile(self.path,self.user)['user']['xp']
        self.assertEqual(first,10);self.assertEqual(second,10)
    def test_auto_savings_conservation_and_restart(self):
        eid=self.buy_coffee();self.call('savings-setting',{'enabled':True})
        with get_connection(self.path) as c:
            c.execute('UPDATE owned_enterprises SET savings_enabled=1,equipment=? WHERE id=?',(json.dumps({k:True for k in COFFEE_EQUIPMENT}),eid));before=capital(c,self.user)['total']
            settle(c,self.user,eid,NOW+timedelta(hours=1));after=capital(c,self.user)
        self.assertEqual(after['savings'],25);self.assertEqual(after['total']-before,128)
        with get_connection(self.path) as c:settle(c,self.user,eid,NOW+timedelta(hours=1));self.assertEqual(capital(c,self.user)['savings'],25)
    def test_goals_baseline_requires_new_capital_growth(self):
        self.call('goal',{'kind':'capital_growth','target':1000,'main':True})
        self.assertEqual(self.view()['goals'][0]['progress'],0)
        self.assertEqual(self.view()['progress']['level'],1)
        with self.assertRaises(EconomyError):self.call('goal',{'kind':'capital_growth','target':2000,'main':True},'second')
        self.fund(self.user,10001000);self.assertTrue(self.view()['goals'][0]['achieved'])
    def test_stock_fee_ceil_and_card_vip_discount(self):
        from services.finance import stock_fee,account
        with get_connection(self.path) as c:
            account(c,self.user,NOW)
            self.assertEqual(stock_fee(c,self.user,101),2)
            c.execute("UPDATE finance_accounts SET card='gold',vip='Silver' WHERE user_id=?",(self.user,))
            self.assertEqual(stock_fee(c,self.user,1000),9)
            self.assertEqual(stock_fee(c,self.user,1),1)
    def test_expired_vip_discount_cannot_be_retained_by_skipping_state(self):
        self.call('card',{'card':'gold'})
        with get_connection(self.path) as c:
            c.execute("UPDATE finance_accounts SET vip='Silver',vip_suspend_at=? WHERE user_id=?",(stamp(NOW-timedelta(seconds=1)),self.user))
        result=self.call('transfer',{'recipient':102,'amount':2000,'confirmed':True},'expired-vip')
        self.assertEqual(result['fee'],36)
        self.assertEqual(self.scalar('SELECT vip FROM finance_accounts WHERE user_id=?',(self.user,)),'')
    def test_legacy_deposit_preserves_terms_and_cannot_pay_twice(self):
        with get_connection(self.path) as c:
            deposit=c.execute('INSERT INTO works_deposits(user_id,principal,annual_rate,term_days,started_at,matures_at) VALUES (?,10000,.12,7,?,?)',(self.user,stamp(NOW),stamp(NOW+timedelta(days=7)))).lastrowid
        with self.assertRaises(EconomyError):self.call('collect-legacy-deposit',{'id':deposit},'early')
        with self.assertRaises(EconomyError):self.call('collect-legacy-deposit',{'id':deposit},'foreign',self.buyer,now=NOW+timedelta(days=7))
        r=self.call('collect-legacy-deposit',{'id':deposit},'mature',now=NOW+timedelta(days=7))
        self.assertEqual(r['amount'],10023)
        self.assertTrue(self.call('collect-legacy-deposit',{'id':deposit},'mature')['idempotent'])
        with self.assertRaises(EconomyError):self.call('collect-legacy-deposit',{'id':deposit},'again',now=NOW+timedelta(days=8))
        self.assertEqual(self.view()['legacy_deposits'][0]['status'],'PAID')
    def test_legacy_savings_withdrawal_and_loan_source_priority(self):
        self.fake_actual_income();loan=self.call('loan',{'product':'starter','amount':1000})
        with get_connection(self.path) as c:
            c.execute('INSERT INTO player_savings_accounts(user_id,balance,accrued_at) VALUES (?,800,?)',(self.user,stamp(NOW)))
            c.execute('UPDATE finance_accounts SET savings=300 WHERE user_id=?',(self.user,))
        self.call('withdraw-legacy-savings',{'amount':100},'withdraw')
        self.assertEqual(self.scalar('SELECT balance FROM player_savings_accounts WHERE user_id=?',(self.user,)),700)
        wallet=self.scalar('SELECT balance FROM users WHERE id=?',(self.user,))
        self.call('repay',{'id':loan['loan_id'],'amount':1000},'repay')
        self.assertEqual(self.scalar('SELECT balance FROM player_savings_accounts WHERE user_id=?',(self.user,)),0)
        self.assertEqual(self.scalar('SELECT savings FROM finance_accounts WHERE user_id=?',(self.user,)),0)
        self.assertEqual(self.scalar('SELECT balance FROM users WHERE id=?',(self.user,)),wallet)
    def test_dividends_largest_remainders_and_once(self):
        start=NOW-timedelta(hours=168)
        with get_connection(self.path) as c:
            c.execute("UPDATE finance_companies SET started_at=? WHERE code='BANK'",(stamp(start),))
            c.execute('INSERT INTO finance_company_profit VALUES (?,?,?,?)',('profit','BANK',100050,stamp(NOW-timedelta(hours=1))))
            for u in (self.user,self.buyer):c.execute('INSERT INTO finance_stock_lots(user_id,company,quantity,unit_cost,acquired_at) VALUES (?,\'BANK\',1,1000,?)',(u,stamp(NOW-timedelta(hours=25))))
            advance_dividends(c,'BANK',NOW);first=get_balance(c,self.user)
            advance_dividends(c,'BANK',NOW);self.assertEqual(first,get_balance(c,self.user))
            paid=c.execute('SELECT paid FROM finance_dividends').fetchone()[0];self.assertEqual(paid,200)
    def test_populated_v15_business_table_rebuild_preserves_child_references(self):
        import sqlite3
        from database import SCHEMA
        from migrations.v15 import migrate as migrate15
        legacy=self.directory/'legacy-business.sqlite3'
        with sqlite3.connect(legacy) as c:
            c.executescript(SCHEMA);migrate15(c)
            c.execute("INSERT INTO users(id,telegram_id,first_name,balance) VALUES(17,919,'Existing',54321)")
            c.execute("INSERT INTO enterprise_catalog(id,code,name,original_price,revenue,expenses,capacity,rarity,image) VALUES(77,'coffee','Existing coffee',25000,200,30,5,'RARE','/coffee.svg')")
            c.execute('INSERT INTO owned_enterprises(id,user_id,catalog_id,last_accrued_at,created_at) VALUES(88,17,77,?,?)',(stamp(NOW),stamp(NOW)))
            c.execute("INSERT INTO enterprise_employees(id,enterprise_id,role,salary,bonus,hired_at) VALUES(99,88,'worker',20,.05,?)",(stamp(NOW),))
            c.execute("INSERT INTO player_listings(id,seller_id,enterprise_id,price,status,created_at) VALUES(111,17,88,90000,'CANCELLED',?)",(stamp(NOW),))
            c.execute("UPDATE owned_enterprises SET status='PAUSED',upgrades=? WHERE id=88",(json.dumps({'equipment':1,'premises':0,'marketing':0,'automation':0}),))
        seed_content(legacy);seed_content(legacy)
        with get_connection(legacy) as c:
            self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(),[])
            self.assertEqual(c.execute('SELECT user_id,catalog_id,status FROM owned_enterprises WHERE id=88').fetchone()[:],(17,77,'PAUSED'))
            self.assertEqual(c.execute('SELECT enterprise_id,salary FROM enterprise_employees WHERE id=99').fetchone()[:],(88,20))
            self.assertEqual(c.execute('SELECT enterprise_id,status FROM player_listings WHERE id=111').fetchone()[:],(88,'CANCELLED'))
            self.assertEqual(c.execute('SELECT balance FROM users WHERE id=17').fetchone()[0],54321)
            self.assertTrue(json.loads(c.execute('SELECT equipment FROM owned_enterprises WHERE id=88').fetchone()[0])['machine'])
        backups=list((self.directory/'backups').glob('legacy-business.before-v16.*.sqlite3'))
        self.assertEqual(len(backups),1)
        with sqlite3.connect(backups[0]) as c:self.assertEqual(c.execute('SELECT enterprise_id FROM enterprise_employees WHERE id=99').fetchone()[0],88)
    def test_startup_cloud_recovery_finishes_migration_before_new_catalog(self):
        import os,sqlite3
        from unittest.mock import AsyncMock
        from database import SCHEMA
        from migrations.v15 import migrate as migrate15
        from services.supabase_sync import _export_state,_restore_state,SyncResult
        from fastapi.testclient import TestClient
        from routes import create_app
        source=self.directory/'cloud-v15.sqlite3';target=self.directory/'recovered.sqlite3'
        with sqlite3.connect(source) as c:
            c.executescript(SCHEMA);migrate15(c)
            c.execute("INSERT INTO users(id,telegram_id,first_name,balance) VALUES(17,919,'Recovered',54321)")
        snapshot,_=_export_state(source)
        def recover(path,*args,**kwargs):
            return SyncResult(status='restored',users=_restore_state(path,snapshot))
        with patch.dict(os.environ,{'DATABASE_PATH':str(target),'SUPABASE_URL':'','SUPABASE_SERVICE_ROLE_KEY':''}),patch('routes.restore_if_empty',side_effect=recover),patch('services.finance_jobs.run',new=AsyncMock()):
            with TestClient(create_app(dev_mode=True)) as client:self.assertEqual(client.get('/api/health').status_code,200)
        seed_content(target)
        with get_connection(target) as c:
            self.assertEqual(c.execute('SELECT balance FROM users WHERE id=17').fetchone()[0],54321)
            self.assertIsNone(c.execute("SELECT sell_price FROM items WHERE asset_key='gold_ring'").fetchone()[0])
            self.assertTrue(c.execute("SELECT 1 FROM schema_migrations WHERE version='16_unified_world'").fetchone())

from services.economy import get_balance
if __name__=='__main__':unittest.main()
