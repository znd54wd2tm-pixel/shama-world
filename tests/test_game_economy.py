"""Run with python -m unittest discover -s tests -v. No live credentials needed."""
from __future__ import annotations
import gc
import hashlib
import hmac
import json
import os
import sqlite3
import tempfile
import time
import unittest
import uuid
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

from database import init_db, get_connection
from seed_data import seed_content, CASES
from services.game import open_case, open_case_batch, opening_history, GameError, _choose_drop
from services.economy import EconomyError, sell_item
from services.results import result_action
from services.businesses import award_enterprise, business_action, business_state, settle, load_owned, rates, level_for
from services.market import player_market_action
from services.users import get_or_create_user
from services.upgrade import execute_upgrade
from services.telegram_auth import validate_telegram_init_data, TelegramAuthError

NOW = datetime(2026,10,16,12,tzinfo=timezone.utc)


class GameTests(unittest.TestCase):
    def setUp(self):
        test_root=Path(__file__).resolve().parents[1]/'.test-data'
        test_root.mkdir(exist_ok=True)
        self.directory=test_root/str(uuid.uuid4())
        self.directory.mkdir()
        self.path=self.directory/'world.sqlite3'
        seed_content(self.path)
        self.user=get_or_create_user(self.path,{'id':101,'first_name':'Tester'})['id']
        self.buyer=get_or_create_user(self.path,{'id':102,'first_name':'Buyer'})['id']
        self.fund(self.user,10_000_000)
        self.fund(self.buyer,10_000_000)
        self.case=self.scalar("SELECT id FROM cases WHERE name='Стартовый'")
        self.business_case=self.scalar("SELECT id FROM cases WHERE name='Начинающий бизнесмен' AND kind='BUSINESS'")

    def tearDown(self):
        gc.collect()
        assert self.directory.resolve().parent == (Path(__file__).resolve().parents[1]/'.test-data').resolve()
        shutil.rmtree(self.directory)

    def scalar(self,sql,params=()):
        with get_connection(self.path) as c:
            row=c.execute(sql,params).fetchone()
            return row[0] if row else None

    def fund(self,user,amount):
        with get_connection(self.path) as c:
            c.execute('UPDATE users SET balance=? WHERE id=?',(amount,user))

    def own(self,user=None,catalog_id=1):
        with get_connection(self.path) as c,patch('services.businesses.now_utc',return_value=NOW):
            eid=award_enterprise(c,user or self.user,(c.execute("SELECT id FROM enterprise_catalog WHERE code='coffee'").fetchone()[0] if catalog_id == 1 else catalog_id))[0]
            # Existing-economy tests use an already equipped coffee shop fixture.
            from catalog_v16 import COFFEE_EQUIPMENT
            c.execute('UPDATE owned_enterprises SET equipment=? WHERE id=?',(json.dumps({k:True for k in COFFEE_EQUIPMENT}),eid))
            return eid

    def rewind(self,enterprise,hours):
        with get_connection(self.path) as c:
            c.execute('UPDATE owned_enterprises SET last_accrued_at=? WHERE id=?',((NOW-timedelta(hours=hours)).isoformat(),enterprise))

    def test_single_open_is_persisted(self):
        result=open_case(self.path,self.user,self.case,'single')
        self.assertEqual(result['balance'],9_999_900)
        self.assertEqual(len(result['items']),1)
        self.assertEqual(self.scalar('SELECT count(*) FROM inventory'),1)
        self.assertEqual(self.scalar('SELECT count(*) FROM case_openings'),1)

    def test_ten_one_payment_ten_independent_rows(self):
        result=open_case_batch(self.path,self.user,self.case,10,'ten')
        self.assertEqual(len(result['items']),10)
        self.assertEqual(len({r['result_id'] for r in result['items']}),10)
        self.assertEqual(result['total_price'],1000)
        self.assertEqual(self.scalar("SELECT count(*) FROM transactions WHERE type='CASE_OPEN'"),1)
        self.assertEqual(self.scalar('SELECT sum(quantity) FROM inventory'),10)
        self.assertEqual(self.scalar('SELECT count(*) FROM opening_results'),10)

    def test_retry_returns_exact_snapshot(self):
        one=open_case_batch(self.path,self.user,self.case,10,'same')
        two=open_case_batch(self.path,self.user,self.case,10,'same')
        self.assertEqual(one['items'],two['items'])
        self.assertTrue(two['idempotent'])
        self.assertEqual(self.scalar('SELECT balance FROM users WHERE id=?',(self.user,)),9_999_000)

    def test_key_cannot_change_case_or_quantity(self):
        open_case(self.path,self.user,self.case,'same')
        with self.assertRaises(GameError):open_case_batch(self.path,self.user,self.case,10,'same')
        with self.assertRaises(GameError):open_case(self.path,self.user,self.case+1,'same')

    def test_keys_are_scoped_to_player(self):
        open_case(self.path,self.user,self.case,'shared')
        open_case(self.path,self.buyer,self.case,'shared')
        self.assertEqual(self.scalar('SELECT count(*) FROM case_batches'),2)

    def test_insufficient_balance_leaves_no_partial_batch(self):
        self.fund(self.user,999)
        with self.assertRaises(GameError):open_case_batch(self.path,self.user,self.case,10,'poor')
        self.assertEqual(self.scalar('SELECT balance FROM users WHERE id=?',(self.user,)),999)
        self.assertEqual(self.scalar('SELECT count(*) FROM case_batches'),0)

    def test_database_rejects_negative_balance(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with get_connection(self.path) as c:c.execute('UPDATE users SET balance=-1 WHERE id=?',(self.user,))
        self.assertEqual(self.scalar('SELECT balance FROM users WHERE id=?',(self.user,)),10_000_000)

    def test_database_failure_rolls_back_charge_and_rewards(self):
        with get_connection(self.path) as c:
            c.execute("CREATE TRIGGER fail_reward BEFORE INSERT ON opening_results BEGIN SELECT RAISE(ABORT,'failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):open_case_batch(self.path,self.user,self.case,10,'failure')
        self.assertEqual(self.scalar('SELECT balance FROM users WHERE id=?',(self.user,)),10_000_000)
        self.assertEqual(self.scalar('SELECT count(*) FROM inventory'),0)
        self.assertEqual(self.scalar('SELECT count(*) FROM transactions'),0)

    def test_concurrent_same_request_charged_once(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:open_case_batch(self.path,self.user,self.case,10,'race'),range(4)))
        self.assertEqual(len({r['operation_id'] for r in results}),1)
        self.assertEqual(self.scalar('SELECT count(*) FROM case_openings'),10)

    def test_all_pools_sum_to_one_and_legacy_weights_preserved(self):
        with get_connection(self.path) as c:
            for case in c.execute('SELECT id,kind FROM cases'):
                table='enterprise_drops' if case['kind']=='BUSINESS' else 'case_drops'
                self.assertAlmostEqual(c.execute(f'SELECT sum(chance) FROM {table} WHERE case_id=?',(case['id'],)).fetchone()[0],1)
            for case in CASES:
                if case['name'] in ('Стартовый','Неоновый','Золотой','Королевский'):continue
                saved={r['name']:r['chance'] for r in c.execute('SELECT i.name,d.chance FROM case_drops d JOIN cases k ON k.id=d.case_id JOIN items i ON i.id=d.item_id WHERE k.name=?',(case['name'],))}
                self.assertEqual(saved,dict(case['drops']))

    def test_invalid_pool_rolls_back(self):
        with get_connection(self.path) as c:c.execute('UPDATE case_drops SET chance=.01 WHERE case_id=?',(self.case,))
        with self.assertRaises(GameError):open_case(self.path,self.user,self.case,'invalid-pool')
        self.assertEqual(self.scalar('SELECT count(*) FROM case_batches'),0)

    def test_weight_boundaries(self):
        rows=[{'chance':.9,'id':1},{'chance':.1,'id':2}]
        with patch('services.game._rng.random',return_value=.8999):self.assertEqual(_choose_drop(rows)['id'],1)
        with patch('services.game._rng.random',return_value=.9):self.assertEqual(_choose_drop(rows)['id'],2)

    def test_unavailable_case(self):
        with get_connection(self.path) as c:c.execute('UPDATE cases SET active=0 WHERE id=?',(self.case,))
        with self.assertRaises(GameError):open_case(self.path,self.user,self.case,'inactive')

    def test_save_and_sell_exact_result_once(self):
        # Explicitly approved buyback values for the sale-operation fixture only.
        with get_connection(self.path) as c:c.execute('UPDATE items SET sell_price=value')
        r=open_case(self.path,self.user,self.case,'one')['item']
        kept=result_action(self.path,self.user,'keep',[r['result_id']],'keep')
        self.assertEqual(self.scalar('SELECT status FROM opening_results'),'KEPT')
        sold=result_action(self.path,self.user,'sell',[r['result_id']],'sell')
        self.assertEqual(sold['amount'],r['value'])
        self.assertTrue(result_action(self.path,self.user,'sell',[r['result_id']],'sell')['idempotent'])
        with self.assertRaises(EconomyError):result_action(self.path,self.user,'sell',[r['result_id']],'sell-again')

    def test_batch_sell_and_individual_selection(self):
        # Explicitly approved buyback values for the sale-operation fixture only.
        with get_connection(self.path) as c:c.execute('UPDATE items SET sell_price=value')
        result=open_case_batch(self.path,self.user,self.case,10,'ten')
        chosen=result['items'][:3]
        sale=result_action(self.path,self.user,'sell',[r['result_id'] for r in chosen],'sell-three')
        self.assertEqual(sale['amount'],sum(r['value'] for r in chosen))
        self.assertEqual(self.scalar('SELECT sum(quantity) FROM inventory'),7)

    def test_generic_sale_marks_reward_consumed(self):
        # Explicitly approved buyback values for the sale-operation fixture only.
        with get_connection(self.path) as c:c.execute('UPDATE items SET sell_price=value')
        r=open_case(self.path,self.user,self.case,'reward')['item']
        sell_item(self.path,self.user,r['id'],1,'legacy-sell')
        self.assertEqual(self.scalar('SELECT status FROM opening_results'),'SOLD')
        with self.assertRaises(EconomyError):result_action(self.path,self.user,'sell',[r['result_id']],'again')

    def test_upgrade_marks_reward_and_replay_no_extra_consumption(self):
        r=open_case(self.path,self.user,self.case,'reward')['item']
        target=self.scalar('SELECT id FROM items WHERE value>? ORDER BY value LIMIT 1',(r['value'],))
        first=execute_upgrade(self.path,self.user,r['id'],target,'upgrade')
        self.assertEqual(self.scalar('SELECT status FROM opening_results'),'UPGRADED')
        again=execute_upgrade(self.path,self.user,r['id'],target,'upgrade')
        self.assertEqual(first['transaction_id'],again['transaction_id'])

    def test_business_cases_archived_without_deleting_catalogue(self):
        with self.assertRaises(GameError):open_case_batch(self.path,self.user,self.business_case,10,'business-ten')
        self.assertEqual(self.scalar('SELECT balance FROM users WHERE id=?',(self.user,)),10_000_000)
        self.assertGreater(self.scalar('SELECT count(*) FROM enterprise_drops'),0)

    def test_no_staff_coffee_example(self):
        eid=self.own()
        with get_connection(self.path) as c:rate=rates(load_owned(c,self.user,eid),[])
        self.assertEqual(rate['revenue'],205)
        self.assertEqual(rate['expenses'],77)
        self.assertEqual(rate['wages'],0)
        self.assertEqual(rate['profit'],128)

    def test_offline_cap_and_no_repeat(self):
        eid=self.own();self.rewind(eid,24)
        with get_connection(self.path) as c:
            first=settle(c,self.user,eid,NOW)
            again=settle(c,self.user,eid,NOW)
        self.assertEqual(first['seconds'],43200)
        self.assertEqual(first['credited'],1536)
        self.assertEqual(again['credited'],0)
        self.assertEqual(self.scalar('SELECT work_seconds FROM owned_enterprises'),43200)
        self.assertEqual(self.scalar('SELECT xp_seconds FROM owned_enterprises'),21600)

    def test_fractional_intervals_are_not_lost(self):
        eid=self.own();self.fund(self.user,0)
        with get_connection(self.path) as c:
            for second in range(1,3601):settle(c,self.user,eid,NOW+timedelta(seconds=second))
        self.assertEqual(self.scalar('SELECT balance FROM users WHERE id=?',(self.user,)),128)

    def test_paused_business_no_income_or_experience(self):
        eid=self.own()
        with patch('services.businesses.now_utc',return_value=NOW):business_action(self.path,self.user,eid,'status',{'status':'PAUSED'},'pause')
        self.rewind(eid,12)
        with get_connection(self.path) as c:self.assertEqual(settle(c,self.user,eid,NOW)['credited'],0)
        self.assertEqual(self.scalar('SELECT xp_seconds FROM owned_enterprises'),0)

    def test_hire_salary_and_fire_settle_at_old_rate(self):
        eid=self.own();self.rewind(eid,1)
        with patch('services.businesses.now_utc',return_value=NOW):
            r=business_action(self.path,self.user,eid,'hire',{'role':'worker'},'hire')
        hourly=r['enterprise']['hourly']
        self.assertEqual(hourly['wages'],15)
        self.assertAlmostEqual(hourly['revenue'],410.0)
        employee=r['enterprise']['employees'][0]
        with patch('services.businesses.now_utc',return_value=NOW+timedelta(hours=1)):
            fired=business_action(self.path,self.user,eid,'fire',{'employee_id':employee['id']},'fire')
        self.assertEqual(fired['enterprise']['hourly']['wages'],0)
        self.assertAlmostEqual(fired['enterprise']['xp_hours'],1.5)

    def test_capacity_and_manager_unlock(self):
        eid=self.own()
        with patch('services.businesses.now_utc',return_value=NOW):
            with self.assertRaises(EconomyError):business_action(self.path,self.user,eid,'hire',{'role':'manager'},'manager')
            for i in range(5):business_action(self.path,self.user,eid,'hire',{'role':'worker'},f'hire{i}')
            with self.assertRaises(EconomyError):business_action(self.path,self.user,eid,'hire',{'role':'worker'},'over-capacity')

    def test_upgrade_price_effect_and_sequential_levels(self):
        eid=self.own()
        with patch('services.businesses.now_utc',return_value=NOW):
            r=business_action(self.path,self.user,eid,'upgrade',{'direction':'equipment','level':1},'u1')
            self.assertEqual(r['cost'],5000)
            with self.assertRaises(EconomyError):business_action(self.path,self.user,eid,'upgrade',{'direction':'equipment','level':1},'duplicate')
            with self.assertRaises(EconomyError):business_action(self.path,self.user,eid,'upgrade',{'direction':'equipment','level':2},'locked')
            with get_connection(self.path) as c:c.execute('UPDATE owned_enterprises SET xp_seconds=86400 WHERE id=?',(eid,))
            r=business_action(self.path,self.user,eid,'upgrade',{'direction':'equipment','level':2},'u2')
            self.assertEqual(r['cost'],10000)

    def test_bonus_cap_and_nonnegative_expenses(self):
        eid=self.own(catalog_id=9)
        with get_connection(self.path) as c:
            c.execute('UPDATE owned_enterprises SET xp_seconds=259200,upgrades=? WHERE id=?',(json.dumps({'equipment':3,'marketing':3,'premises':3,'automation':3}),eid))
            rate=rates(load_owned(c,self.user,eid),[{'bonus':.1,'salary':1}]*10)
        self.assertEqual(float(rate['bonus']),.5)
        self.assertGreaterEqual(rate['expenses'],0)

    def test_insufficient_operating_funds_suspend_without_negative_balance(self):
        eid=self.own();self.fund(self.user,10);self.rewind(eid,1)
        with get_connection(self.path) as c:
            c.execute("UPDATE enterprise_catalog SET revenue=0,expenses=100 WHERE code='coffee'")
            r=settle(c,self.user,eid,NOW)
        self.assertTrue(r['paused'])
        self.assertEqual(self.scalar('SELECT balance FROM users WHERE id=?',(self.user,)),0)
        self.assertEqual(self.scalar('SELECT status FROM owned_enterprises'),'PAUSED')
        self.assertLess(r['seconds'],3600)

    def test_purchase_duplicate_business_rejected(self):
        self.own()
        with self.assertRaises(EconomyError):business_action(self.path,self.user,self.scalar("SELECT id FROM enterprise_catalog WHERE code='coffee'"),'buy',{},'buy')

    def test_level_thresholds(self):
        self.assertEqual([level_for(x*3600) for x in [0,24,96,264,600]],[1,2,3,4,5])

    def test_item_market_escrow_cancel_and_fee(self):
        r=open_case(self.path,self.user,self.case,'reward')['item']
        listed=player_market_action(self.path,self.user,'list',{'item_id':r['id'],'result_id':r['result_id'],'price':10000},'list')
        self.assertIsNone(self.scalar('SELECT quantity FROM inventory WHERE user_id=?',(self.user,)))
        with self.assertRaises(EconomyError):sell_item(self.path,self.user,r['id'],1,'sell-escrow')
        bought=player_market_action(self.path,self.buyer,'buy',{'listing_id':listed['listing_id']},'buy-listing')
        self.assertEqual(bought['fee'],500)
        self.assertEqual(self.scalar('SELECT quantity FROM inventory WHERE user_id=?',(self.buyer,)),1)
        self.assertEqual(self.scalar('SELECT status FROM opening_results'),'TRANSFERRED')
        self.assertEqual(self.scalar('SELECT balance FROM users WHERE id=?',(self.user,)),10_000_000-100+9500)

    def test_cancel_listing_unlocks_exact_item(self):
        # Explicitly approved buyback values for the sale-operation fixture only.
        with get_connection(self.path) as c:c.execute('UPDATE items SET sell_price=value')
        r=open_case(self.path,self.user,self.case,'reward')['item']
        listing=player_market_action(self.path,self.user,'list',{'item_id':r['id'],'result_id':r['result_id'],'price':500},'list')
        player_market_action(self.path,self.user,'cancel',{'listing_id':listing['listing_id']},'cancel')
        self.assertEqual(self.scalar('SELECT status FROM opening_results'),'KEPT')
        result_action(self.path,self.user,'sell',[r['result_id']],'sell-cancelled')

    def test_business_sale_retains_staff_upgrades_and_checkpoint(self):
        eid=self.own()
        with patch('services.businesses.now_utc',return_value=NOW):
            business_action(self.path,self.user,eid,'hire',{'role':'worker'},'hire')
            business_action(self.path,self.user,eid,'upgrade',{'direction':'equipment','level':1},'upgrade')
            listing=player_market_action(self.path,self.user,'list',{'enterprise_id':eid,'price':100000},'list')
        self.rewind(eid,1)
        with patch('services.businesses.now_utc',return_value=NOW):
            bought=player_market_action(self.path,self.buyer,'buy',{'listing_id':listing['listing_id']},'buy')
            resale=player_market_action(self.path,self.buyer,'list',{'enterprise_id':eid,'price':110000},'resale')
        self.assertTrue(resale['success'])
        self.assertEqual(bought['fee'],10000)
        self.assertEqual(self.scalar('SELECT user_id FROM owned_enterprises'),self.buyer)
        self.assertEqual(self.scalar('SELECT count(*) FROM enterprise_employees'),1)
        self.assertEqual(json.loads(self.scalar('SELECT upgrades FROM owned_enterprises'))['equipment'],1)
        with get_connection(self.path) as c:self.assertEqual(settle(c,self.buyer,eid,NOW)['credited'],0)

    def test_market_not_enough_money_or_duplicate_owner_rollback(self):
        eid=self.own()
        listing=player_market_action(self.path,self.user,'list',{'enterprise_id':eid,'price':100000},'list')
        self.fund(self.buyer,99999)
        with self.assertRaises(EconomyError):player_market_action(self.path,self.buyer,'buy',{'listing_id':listing['listing_id']},'poor')
        self.assertEqual(self.scalar('SELECT status FROM player_listings'),'ACTIVE')
        self.fund(self.buyer,1000000);self.own(self.buyer)
        with self.assertRaises(EconomyError):player_market_action(self.path,self.buyer,'buy',{'listing_id':listing['listing_id']},'duplicate-owner')

    def test_concurrent_market_buy_only_one_transfer(self):
        eid=self.own()
        listing=player_market_action(self.path,self.user,'list',{'enterprise_id':eid,'price':100000},'list')
        def purchase(index):
            try:return player_market_action(self.path,self.buyer,'buy',{'listing_id':listing['listing_id']},f'buy{index}')['success']
            except EconomyError:return False
        with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(purchase,range(2)))
        self.assertEqual(sum(out),1)

    def test_seed_keeps_catalog_ids_custom_prices_and_weights(self):
        before=self.scalar("SELECT id FROM items WHERE name='Supercar'")
        with get_connection(self.path) as c:
            c.execute('UPDATE cases SET price=123 WHERE id=?',(self.case,))
            c.execute("UPDATE items SET value=99999 WHERE id=?",(before,))
        seed_content(self.path)
        self.assertEqual(self.scalar("SELECT id FROM items WHERE name='Supercar'"),before)
        self.assertEqual(self.scalar('SELECT price FROM cases WHERE id=?',(self.case,)),123)
        self.assertEqual(self.scalar('SELECT value FROM items WHERE id=?',(before,)),99999)

    def test_history_contains_status_after_sell(self):
        # Explicitly approved buyback values for the sale-operation fixture only.
        with get_connection(self.path) as c:c.execute('UPDATE items SET sell_price=value')
        r=open_case(self.path,self.user,self.case,'history')['item']
        result_action(self.path,self.user,'sell',[r['result_id']],'sell')
        self.assertEqual(opening_history(self.path,self.user)[0]['items'][0]['status'],'SOLD')

    def test_migration_backup_preserves_real_legacy_rows(self):
        with get_connection(self.path) as c:c.execute("DELETE FROM schema_migrations WHERE version='15_game_economy'")
        init_db(self.path)
        backups=list((self.path.parent/'backups').glob('*.sqlite3'))
        self.assertEqual(len(backups),1)
        with sqlite3.connect(backups[0]) as c:self.assertEqual(c.execute('SELECT count(*) FROM users').fetchone()[0],2)
        init_db(self.path)
        self.assertEqual(len(list((self.path.parent/'backups').glob('*.sqlite3'))),1)

    def test_real_legacy_schema_and_idempotency_survive_migration(self):
        from database import SCHEMA
        legacy=self.directory/'legacy.sqlite3'
        with sqlite3.connect(legacy) as c:
            c.executescript(SCHEMA)
            c.execute("INSERT INTO users(id,telegram_id,first_name,balance) VALUES(17,919,'Existing',54321)")
            c.execute("INSERT INTO items(id,name,description,rarity,value,image) VALUES(333,'Existing collectible','Kept','RARE',321,'/existing.svg')")
            c.execute("INSERT INTO cases(id,name,description,price,image) VALUES(444,'Existing case','Kept',100,'/case.svg')")
            c.execute('INSERT INTO case_drops(case_id,item_id,chance) VALUES(444,333,1)')
            c.execute('INSERT INTO inventory(user_id,item_id,quantity) VALUES(17,333,7)')
            c.execute("INSERT INTO case_openings(user_id,case_id,item_id,price_paid,request_id) VALUES(17,444,333,100,'legacy-key')")
        seed_content(legacy)
        with get_connection(legacy) as c:
            self.assertEqual(c.execute('SELECT balance FROM users WHERE id=17').fetchone()[0],54321)
            self.assertEqual(c.execute('SELECT quantity FROM inventory WHERE user_id=17 AND item_id=333').fetchone()[0],7)
            self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(),[])
        replay=open_case(legacy,17,444,'legacy-key')
        self.assertTrue(replay['idempotent'])
        self.assertEqual(replay['item']['id'],333)
        self.assertEqual(replay['balance'],54321)

    def test_new_player_creation_race(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            players=list(pool.map(lambda _:get_or_create_user(self.path,{'id':888,'first_name':'New'}),range(4)))
        self.assertEqual(len({r['id'] for r in players}),1)

    def test_restore_old_cloud_snapshot_before_new_catalog(self):
        from database import SCHEMA
        from services.supabase_sync import _export_state, _restore_state
        from services.content import seed_game_content
        source=self.directory/'old.sqlite3'
        with sqlite3.connect(source) as c:
            c.executescript(SCHEMA)
            c.execute("INSERT INTO users(id,telegram_id,first_name,balance) VALUES(777,777,'Recovered',98765)")
            c.execute("INSERT INTO items(id,name,description,rarity,value,image) VALUES(333,'Saved','Saved','RARE',30,'/saved.svg')")
            c.execute("INSERT INTO cases(id,name,description,price,image) VALUES(444,'Saved case','Saved',20,'/case.svg')")
            c.execute('INSERT INTO inventory(user_id,item_id,quantity) VALUES(777,333,8)')
            c.execute('INSERT INTO case_drops(case_id,item_id,chance) VALUES(444,333,1)')
        snapshot,_=_export_state(source)
        target=self.directory/'restored.sqlite3'
        init_db(target)
        self.assertEqual(_restore_state(target,snapshot),1)
        seed_content(target,ensure_schema=False)
        with get_connection(target) as c:
            self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(),[])
            self.assertEqual(c.execute('SELECT quantity FROM inventory WHERE user_id=777 AND item_id=333').fetchone()[0],8)
            self.assertEqual(c.execute('SELECT count(*) FROM cases WHERE kind="BUSINESS"').fetchone()[0],3)

    def test_invalid_snapshot_restore_rolls_back(self):
        from services.supabase_sync import _export_state, _restore_state, SupabaseSyncError
        snapshot,_=_export_state(self.path)
        snapshot['tables']['inventory']=[{'id':99,'user_id':self.user,'item_id':99999999,'quantity':1,'created_at':'2026-10-16','updated_at':'2026-10-16'}]
        with self.assertRaises(SupabaseSyncError):_restore_state(self.path,snapshot)
        self.assertEqual(self.scalar('SELECT count(*) FROM users'),2)
        self.assertEqual(self.scalar('SELECT count(*) FROM inventory'),0)


class AuthTests(unittest.TestCase):
    def test_signed_telegram_data_and_forgery(self):
        token='test-token-not-real'
        data={'user':json.dumps({'id':123,'first_name':'Player'}),'auth_date':str(int(time.time()))}
        secret=hmac.new(b'WebAppData',token.encode(),hashlib.sha256).digest()
        check='\n'.join(f'{k}={data[k]}' for k in sorted(data))
        data['hash']=hmac.new(secret,check.encode(),hashlib.sha256).hexdigest()
        self.assertEqual(validate_telegram_init_data(urlencode(data),token)['id'],123)
        data['user']=json.dumps({'id':999,'first_name':'Attacker'})
        with self.assertRaises(TelegramAuthError):validate_telegram_init_data(urlencode(data),token)

    def test_missing_auth_fails_closed(self):
        with self.assertRaises(TelegramAuthError):validate_telegram_init_data('','fake-token')


if __name__=='__main__':unittest.main()

class ApprovedCatalogTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(__file__).resolve().parents[1]/'.test-data'
        self.root.mkdir(exist_ok=True)
        self.directory=self.root/str(uuid.uuid4()); self.directory.mkdir()
        self.path=self.directory/'catalog.sqlite3'
        seed_content(self.path)
    def tearDown(self):
        gc.collect(); shutil.rmtree(self.directory)
    def test_approved_case_names_prices_and_probabilities(self):
        expected={"Стартовый":100,"Неоновый":350,"Золотой":5000,"Легендарный":2500,"Королевский":7500}
        with get_connection(self.path) as c:
            actual={r['name']:r['price'] for r in c.execute('SELECT name,price FROM cases WHERE active=1')}
            for name,price in expected.items(): self.assertEqual(actual.get(name),price)
            self.assertEqual(set(actual),set(expected))
            for row in c.execute('SELECT id,kind FROM cases WHERE active=1'):
                table='enterprise_drops' if row['kind']=='BUSINESS' else 'case_drops'
                self.assertAlmostEqual(c.execute(f'SELECT SUM(chance) FROM {table} WHERE case_id=?',(row['id'],)).fetchone()[0],1)
    def test_approved_business_catalog_has_14_rows(self):
        from game_config import ENTERPRISES
        with get_connection(self.path) as c:
            codes={r['code'] for r in c.execute('SELECT code FROM enterprise_catalog')}
            self.assertTrue({r[0] for r in ENTERPRISES}.issubset(codes))
            self.assertEqual(len(ENTERPRISES),14)
    def test_employee_configuration_matches_spec(self):
        from game_config import EMPLOYEES
        self.assertEqual((EMPLOYEES['worker']['hire_cost'],EMPLOYEES['worker']['salary'],EMPLOYEES['worker']['bonus']),(150,15,0))
        self.assertEqual((EMPLOYEES['experienced']['hire_cost'],EMPLOYEES['experienced']['salary'],EMPLOYEES['experienced']['bonus']),(400,40,.08))
        self.assertEqual((EMPLOYEES['manager']['hire_cost'],EMPLOYEES['manager']['salary'],EMPLOYEES['manager']['bonus']),(1000,100,.15))
