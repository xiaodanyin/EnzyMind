"""Quota races, cross-session persistence and request-only provider keys."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
import time
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
from fastapi import HTTPException
from gateway import workspace, agent_quota
from gateway.model_relay import ModelRelay, ERRORS
from gateway.workspace_store import WorkspaceStore
import test_workspace

KEY = 'sk-test-only-never-a-real-provider-key'


class BillingTests(unittest.TestCase):
    setUp = test_workspace.APITests.setUp
    tearDown = test_workspace.APITests.tearDown

    def test_legacy_chat_cannot_bypass_workspace_allowance(self):
        with patch.object(workspace.httpx, 'AsyncClient', side_effect=AssertionError('Unmetered model call')):
            result = self.client.post('/api/agent/chat', json={'chatInput':'hello'})
        self.assertEqual(result.status_code,410)
        self.assertEqual(result.json()['detail']['url'],'/enzymind/agent')

    def new_turn(self, mode='free'):
        store=workspace.store();session=store.create_session(self.key)
        turn,_=store.begin(self.key,session['id'],str(uuid4()),'Question',[],billing_mode=mode)
        return turn

    def test_ten_turns_shared_by_sessions_and_survive_restart_and_deletion(self):
        store=workspace.store()
        for _ in range(10):
            turn=self.new_turn();store.status(self.key,turn['id'],'completed',output='Answer')
        with store.db() as db:
            db.execute('DELETE FROM turns');db.execute('DELETE FROM sessions')
        reopened=WorkspaceStore(store.path)
        self.assertEqual(reopened.usage(self.key)['remaining'],0)
        with self.assertRaises(HTTPException) as denied:self.new_turn()
        self.assertEqual(denied.exception.status_code,402)
        self.assertEqual(denied.exception.detail['code'],'daily_limit')
        self.assertEqual(self.new_turn('byok')['billing_mode'],'byok')
        self.assertEqual(store.usage(self.key)['used'],10)

    def test_reservations_are_atomic_under_concurrent_sessions(self):
        def submit(_):
            try:return self.new_turn()['id']
            except HTTPException as error:return error.status_code
        with ThreadPoolExecutor(max_workers=12) as pool:results=list(pool.map(submit,range(16)))
        self.assertEqual(sum(isinstance(r,str) for r in results),10)
        self.assertEqual(results.count(402),6)
        self.assertEqual(workspace.store().usage(self.key)['reserved'],10)

    def test_idempotency_refunds_cancellation_and_expired_worker(self):
        store=workspace.store();turn=self.new_turn()
        repeated,token=store.begin(self.key,turn['session_id'],turn['request_id'],turn['message'],[])
        self.assertEqual(repeated['id'],turn['id']);self.assertIsNone(token)
        self.assertEqual(store.usage(self.key)['used'],1)
        store.status(self.key,turn['id'],'cancelled')
        self.assertEqual(store.usage(self.key)['used'],0)
        turn=self.new_turn();store.status(self.key,turn['id'],'failed',error='temporary failure')
        self.assertEqual(store.usage(self.key)['used'],0)
        turn=self.new_turn()
        with store.db() as db:db.execute('UPDATE turns SET lease_expires=0 WHERE id=?',(turn['id'],))
        store.recover();self.assertEqual(store.usage(self.key)['used'],0)

    def test_midnight_reset_and_short_lived_accounting(self):
        store=workspace.store();turn=self.new_turn();store.status(self.key,turn['id'],'completed',output='Answer')
        now=time.time()
        with patch('gateway.agent_quota.time.time',return_value=now+86400):
            self.assertEqual(store.usage(self.key)['remaining'],10)
        with store.db() as db:
            agent_quota.reconcile(db,now+172801)
            self.assertEqual(db.execute('SELECT count(*) FROM agent_usage').fetchone()[0],0)
        self.assertEqual(agent_quota.period(0)[2],'Asia/Shanghai')

    def test_http_billing_is_server_selected_and_headers_never_saved(self):
        store=workspace.store();session=store.create_session(self.key)
        with patch.object(workspace,'run_turn',new=AsyncMock()) as worker:
            response=self.client.post('/api/workspace/sessions/'+session['id']+'/turns',headers={**self.headers,'X-DeepSeek-API-Key':KEY},json={'message':'Question','request_id':str(uuid4()),'billing_mode':'free'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['billing_mode'],'byok')
            self.assertEqual(worker.call_args.args[3],KEY)
        self.assertEqual(store.usage(self.key)['used'],0)
        self.assertNotIn(KEY,store.path.read_bytes().decode('latin1'))
        self.assertNotIn(KEY,json.dumps(self.client.get('/api/workspace/sessions/'+session['id'],headers=self.headers).json()))
        bad=self.client.post('/api/workspace/sessions/'+session['id']+'/turns',headers={**self.headers,'X-DeepSeek-API-Key':'bad'},json={'message':'Q','request_id':str(uuid4())})
        self.assertEqual(bad.status_code,422)
        other=store.create_session(self.key)
        with patch.object(workspace,'run_turn',new=AsyncMock()):
            spoof=self.client.post('/api/workspace/sessions/'+other['id']+'/turns',headers=self.headers,json={'message':'Q','request_id':str(uuid4()),'billing_mode':'byok'})
        self.assertEqual(spoof.json()['billing_mode'],'free')
        self.assertEqual(self.client.get('/api/workspace/usage',headers=self.headers).json()['used'],1)

    def test_relay_json_and_stream_use_only_deepseek_and_bound_model(self):
        store=workspace.store();turn=self.new_turn('byok');store.status(self.key,turn['id'],'running')
        relay=ModelRelay();token=relay.register(KEY,self.key,turn['id']);seen=[]
        real_client=httpx.AsyncClient
        def handler(request):
            body=json.loads(request.content);seen.append(body)
            self.assertEqual(str(request.url),'https://api.deepseek.com/chat/completions')
            self.assertEqual(request.headers['authorization'],'Bearer '+KEY)
            self.assertEqual(body['model'],'deepseek-chat');self.assertEqual(body['max_tokens'],4096)
            self.assertNotIn('base_url',body)
            if body.get('stream'):return httpx.Response(200,text='data: {"choices":[{"delta":{"content":"enzyme"}}]}\n\ndata: [DONE]\n\n')
            return httpx.Response(200,json={'choices':[{'message':{'content':'enzyme'}}]})
        async def run():
            with patch('gateway.model_relay.httpx.AsyncClient',side_effect=lambda **kw:real_client(transport=httpx.MockTransport(handler),**kw)):
                for stream in (False,True):
                    result=await relay.forward(token,{'messages':[{'role':'user','content':'Q'}],'stream':stream,'max_tokens':99999,'model':'wrong','base_url':'http://invalid'},store)
                    content=b''.join([chunk async for chunk in result.body_iterator]) if stream else result.body
                    self.assertIn(b'enzyme',content)
            await relay.revoke(token)
            with self.assertRaises(HTTPException):relay.get(token,store)
        asyncio.run(run());self.assertEqual(len(seen),2);self.assertFalse(relay.leases)

    def test_provider_errors_are_sanitized_and_no_free_fallback(self):
        store=workspace.store();turn=self.new_turn('byok');store.status(self.key,turn['id'],'running')
        relay=ModelRelay();token=relay.register(KEY,self.key,turn['id']);real_client=httpx.AsyncClient;calls=[]
        async def run():
            for code in (401,402,429,500):
                def handler(request):
                    calls.append(str(request.url));return httpx.Response(code,text='unsafe '+KEY)
                with patch('gateway.model_relay.httpx.AsyncClient',side_effect=lambda **kw:real_client(transport=httpx.MockTransport(handler),**kw)):
                    result=await relay.forward(token,{'messages':[{'role':'user','content':'Q'}]},store)
                    self.assertEqual(result.status_code,code if code in ERRORS else 502)
                    self.assertNotIn(KEY,result.body.decode())
            store.status(self.key,turn['id'],'cancelled')
            with self.assertRaises(HTTPException):relay.get(token,store)
            await relay.revoke(token)
        asyncio.run(run());self.assertEqual(len(calls),4);self.assertEqual(store.usage(self.key)['used'],0)

    def test_turn_clears_key_even_when_n8n_fails(self):
        store=workspace.store();turn=self.new_turn('byok');real_client=httpx.AsyncClient;payloads=[]
        def handler(request):
            body=json.loads(request.content);payloads.append(body)
            self.assertNotIn(KEY,request.content.decode());self.assertNotIn('x-deepseek-api-key',request.headers)
            self.assertEqual(body['billing_mode'],'byok');self.assertEqual(len(body['model_relay_token']),64)
            return httpx.Response(500,text='workflow unavailable')
        with patch('gateway.workspace.httpx.AsyncClient',side_effect=lambda **kw:real_client(transport=httpx.MockTransport(handler),**kw)):
            asyncio.run(workspace.run_turn(self.key,turn,'execution-capability',KEY))
        self.assertFalse(workspace.relay.leases)
        self.assertEqual(store.turn(self.key,turn['id'])['status'],'failed')
        self.assertEqual(store.usage(self.key)['used'],0)
        self.assertEqual(len(payloads),1)
