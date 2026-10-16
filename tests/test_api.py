from __future__ import annotations
import hashlib
import hmac
import json
import os
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
from fastapi.testclient import TestClient
from database import get_connection
from tests import test_game_economy as fixtures


class ApiTests(unittest.TestCase):
    setUp=fixtures.GameTests.setUp
    tearDown=fixtures.GameTests.tearDown
    scalar=fixtures.GameTests.scalar
    fund=fixtures.GameTests.fund


def signed(token='test-token',telegram_id=101):
    fields={'user':json.dumps({'id':telegram_id,'first_name':'Tester'}),'auth_date':str(int(time.time()))}
    secret=hmac.new(b'WebAppData',token.encode(),hashlib.sha256).digest()
    fields['hash']=hmac.new(secret,'\n'.join(f'{k}={fields[k]}' for k in sorted(fields)).encode(),hashlib.sha256).hexdigest()
    return urlencode(fields)


class HttpTests(ApiTests):
    def setUp(self):
        super().setUp()
        self.env=patch.dict(os.environ,{'DATABASE_PATH':str(self.path),'BOT_TOKEN':'test-token','SUPABASE_URL':'','SUPABASE_SERVICE_ROLE_KEY':''})
        self.env.start()
        from routes import create_app
        app=create_app(dev_mode=False)
        app.state.database_path=self.path
        self.client=TestClient(app)
        self.headers={'Authorization':'tma '+signed()}

    def tearDown(self):
        self.client.close();self.env.stop();super().tearDown()

    def test_production_authentication(self):
        self.assertEqual(self.client.get('/api/me').status_code,401)
        self.assertEqual(self.client.get('/api/me',headers={'X-Telegram-Init-Data':'user=101'}).status_code,401)
        response=self.client.get('/api/me',headers=self.headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['telegram_id'],101)
        self.assertNotIn('bot_token',response.text.lower())

    def test_server_fast_setting_default_toggle_and_restart(self):
        self.assertFalse(self.client.get('/api/settings',headers=self.headers).json()['fast_open'])
        self.assertTrue(self.client.patch('/api/settings',json={'fast_open':True},headers=self.headers).json()['fast_open'])
        self.assertTrue(self.client.get('/api/settings',headers=self.headers).json()['fast_open'])
        self.assertFalse(self.client.patch('/api/settings',json={'fast_open':False},headers=self.headers).json()['fast_open'])
        self.assertEqual(self.client.patch('/api/settings',json={'fast_open':'false'},headers=self.headers).status_code,400)

    def test_ten_recovery_and_disallowed_client_results(self):
        headers={**self.headers,'X-Opening-Request-Id':'http-ten'}
        response=self.client.post(f'/api/cases/{self.case}/open-ten',json={'item_id':999999,'price':0,'balance':999999},headers=headers)
        self.assertEqual(response.status_code,200,response.text)
        result=response.json()
        self.assertEqual(len(result['items']),10)
        self.assertEqual(result['total_price'],1000)
        recovered=self.client.get('/api/openings/by-request/http-ten',headers=self.headers).json()
        self.assertEqual(result['items'],recovered['items'])
        replay=self.client.post(f'/api/cases/{self.case}/open-ten',headers=headers).json()
        self.assertTrue(replay['idempotent'])
        self.assertEqual(self.client.get('/api/openings/by-request/http-ten',headers={'Authorization':'tma '+signed(telegram_id=102)}).status_code,404)

    def test_fast_mode_uses_identical_server_draw_rules(self):
        with patch('services.game._rng.random',return_value=.6):
            ordinary=self.client.post(f'/api/cases/{self.case}/open',headers={**self.headers,'X-Opening-Request-Id':'ordinary'}).json()
            self.client.patch('/api/settings',json={'fast_open':True},headers=self.headers)
            fast=self.client.post(f'/api/cases/{self.case}/open',headers={**self.headers,'X-Opening-Request-Id':'fast'}).json()
        self.assertEqual(ordinary['item']['id'],fast['item']['id'])
        self.assertEqual(ordinary['total_price'],fast['total_price'])
        self.assertEqual(ordinary['balance']-100,fast['balance'])

    def test_invalid_payloads_and_case_unavailable(self):
        self.assertEqual(self.client.post(f'/api/cases/{self.case}/open-ten',headers=self.headers).status_code,400)
        self.assertEqual(self.client.post('/api/openings/results/sell',headers=self.headers,json={'result_ids':[]} ).status_code,400)
        self.assertEqual(self.client.post('/api/market/listings/list',headers=self.headers,json={'price':-10,'item_id':1}).status_code,400)

    def test_database_error_safe_response_and_retry(self):
        import sqlite3
        with patch('routes.open_case',side_effect=sqlite3.OperationalError('private internal database details')):
            response=self.client.post(f'/api/cases/{self.case}/open',headers={**self.headers,'X-Opening-Request-Id':'failed-database'})
        self.assertEqual(response.status_code,503)
        self.assertNotIn('private internal',response.text)
        self.assertEqual(self.scalar('SELECT count(*) FROM case_batches'),0)
        response=self.client.post(f'/api/cases/{self.case}/open',headers={**self.headers,'X-Opening-Request-Id':'failed-database'})
        self.assertEqual(response.status_code,200)


if __name__=='__main__':unittest.main()
