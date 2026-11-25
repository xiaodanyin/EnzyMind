import asyncio
import base64
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException
from starlette.requests import Request

from gateway import workspace
from gateway.python_sandbox import PythonSandbox, source_ip, normalize, WORKSPACE_BYTES
from gateway.retention import run_cleanup
from gateway.retention_policy import RETENTION_SECONDS
from gateway.workspace_store import WorkspaceStore, digest


def request(peer='203.0.113.8', forwarded=''):
    req = Request({'type':'http', 'client':(peer,1234), 'headers':[(b'x-forwarded-for', forwarded.encode())]})
    req.is_disconnected = AsyncMock(return_value=False)
    return req


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = WorkspaceStore(Path(self.temp.name) / 'test.sqlite')
        self.sandbox = PythonSandbox(self.store)
        self.turn, self.token = self.new_turn()
        self.body = normalize({'code':'result = 1'})

    def new_turn(self, owner='a' * 64, ip='same-ip'):
        session = self.store.create_session(owner)
        turn, token = self.store.begin(owner, session['id'], str(uuid4()), 'compute', [], source_ip_hash=ip, billing_mode='byok')
        self.store.status(owner, turn['id'], 'running')
        return self.store.authorize_turn(token), token

    def admit(self, code='result = 1', turn=None):
        return self.sandbox.admit(turn or self.turn, normalize({'code':code}), [])

    def finish(self, run, turn=None, files=None):
        self.sandbox.finish(turn or self.turn, run, {'success':True, 'execution_status':'completed',
            'duration':.1, 'result':{'x':1}, 'files':files or []})

    def test_duplicate_reuses_execution_but_cannot_bypass_shared_tool_budget(self):
        run, reused = self.admit()
        self.assertFalse(reused)
        self.assertEqual(self.admit()[0]['id'], run['id'])
        self.finish(run)
        self.assertTrue(self.admit()[1])
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM python_attempts').fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT count(*) FROM events WHERE kind='tool_start'").fetchone()[0], 3)
        for _ in range(9):
            self.assertTrue(self.admit()[1])
        with self.assertRaises(HTTPException) as exc:
            self.admit()
        self.assertEqual(exc.exception.status_code, 429)

    def test_cancelled_turn_cannot_admit(self):
        self.store.status(self.turn['owner'], self.turn['id'], 'cancelled')
        with self.assertRaises(HTTPException) as exc:
            self.admit()
        self.assertEqual(exc.exception.status_code, 403)

    def test_python_and_shared_budget(self):
        for i in range(3):
            run, _ = self.admit(f'result={i}')
            self.finish(run)
        with self.assertRaises(HTTPException) as exc:
            self.admit('result=4')
        self.assertEqual(exc.exception.status_code, 429)
        other, _ = self.new_turn('b'*64)
        for i in range(12):
            self.store.event(other['id'], 'tool_start', {'tool':'read-result'})
        with self.assertRaises(HTTPException):
            self.admit(turn=other)

    def test_concurrency_is_global_and_owner_scoped_and_busy_counts(self):
        self.admit()
        same_owner, _ = self.new_turn()
        self.assertEqual(self.admit(turn=same_owner)[0]['state'], 'busy')
        second, _ = self.new_turn('b'*64)
        self.assertEqual(self.admit(turn=second)[0]['state'], 'running')
        third, _ = self.new_turn('c'*64)
        self.assertEqual(self.admit(turn=third)[0]['state'], 'busy')
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM python_attempts').fetchone()[0], 4)

    def test_hourly_workspace_ip_and_global_limits_survive_new_store(self):
        for kind, limit, owner, ip in [('workspace',10,self.turn['owner'],'other'), ('ip',20,'other','same-ip'), ('global',120,'other','other')]:
            with self.subTest(kind=kind):
                with self.store.db() as db:
                    db.execute('DELETE FROM python_attempts')
                    db.executemany('INSERT INTO python_attempts VALUES(?,?,?,?)', [(str(uuid4()),owner,ip,time.time()) for _ in range(limit)])
                reopened = PythonSandbox(WorkspaceStore(self.store.path))
                with self.assertRaises(HTTPException) as exc:
                    reopened.admit(self.turn,self.body,[])
                self.assertEqual(exc.exception.status_code,429)

    def test_inputs_files_and_retention_preserve_ownership(self):
        run, _ = self.admit()
        self.finish(run, files=[{'name':'table.csv','content':base64.b64encode(b'name,value\na,1\n').decode()}])
        record = self.store.result(self.turn['owner'],run['result_id'])
        file_id = record['payload']['files'][0]['id']
        inputs, files, sources = self.sandbox.inputs(self.turn['owner'],normalize({'code':'pass','result_ids':[record['id']], 'file_ids':[file_id]}))
        self.assertIn(record['id'],inputs['results'])
        self.assertTrue(inputs['files'][file_id].startswith('/work/inputs/'))
        self.assertEqual(len(sources),2)
        with self.assertRaises(HTTPException):
            self.sandbox.file('b'*64,file_id)
        with self.assertRaises(HTTPException):
            self.sandbox.inputs('b'*64,normalize({'code':'pass','result_ids':[record['id']]}))
        self.store.status(self.turn['owner'],self.turn['id'],'completed')
        future = time.time()+RETENTION_SECONDS+10
        run_cleanup(self.store,now=future,dry_run=True,artifact_roots=[])
        self.assertEqual(self.sandbox.file(self.turn['owner'],file_id)['name'],'table.csv')
        run_cleanup(self.store,now=future,artifact_roots=[])
        with self.assertRaises(HTTPException):
            self.sandbox.file(self.turn['owner'],file_id)
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM python_runs').fetchone()[0],0)

    def test_multi_source_analysis_preserves_all_records_and_ownership(self):
        records = [self.store.save_result(self.turn['owner'], 'km', {},
                   {'success': True, 'km': i + 1, 'unit': 'mM'}) for i in range(12)]
        body = normalize({'code': 'pass', 'result_ids': [r['id'] for r in records]})
        inputs, files, sources = self.sandbox.inputs(self.turn['owner'], body)
        self.assertEqual(inputs['results'], {r['id']: r['payload'] for r in records})
        self.assertEqual({s['result_id'] for s in sources}, set(inputs['results']))
        self.assertEqual(files, [])
        foreign = self.store.save_result('b' * 64, 'km', {}, {'success': True, 'km': 100})
        body['result_ids'][-1] = foreign['id']
        with self.assertRaises(HTTPException) as exc:
            self.sandbox.inputs(self.turn['owner'], body)
        self.assertEqual(exc.exception.status_code, 404)
        with self.assertRaises(HTTPException) as exc:
            normalize({'code': 'pass', 'result_ids': [r['id'] for r in records] + [foreign['id']]})
        self.assertEqual(exc.exception.status_code, 422)

    def test_multi_source_analysis_still_enforces_total_input_bytes(self):
        records = [self.store.save_result(self.turn['owner'], 'km', {},
                   {'success': True, 'text': 'x' * (1024 ** 2)}) for _ in range(6)]
        body = normalize({'code': 'pass', 'result_ids': [r['id'] for r in records]})
        with self.assertRaises(HTTPException) as exc:
            self.sandbox.inputs(self.turn['owner'], body)
        self.assertEqual(exc.exception.status_code, 413)

    def test_storage_reservation_and_restart_do_not_rerun(self):
        run, _ = self.admit()
        self.sandbox.recover()
        old, reused = self.admit()
        self.assertTrue(reused)
        self.assertEqual(old['state'],'interrupted')
        record = self.store.result(self.turn['owner'],run['result_id'])
        self.assertEqual(record['status'],'failed')
        with self.store.db() as db:
            db.execute('INSERT INTO python_files VALUES(?,?,?,?,?,?,?,?)',
                       (str(uuid4()),record['id'],self.turn['owner'],'x.txt','text/plain',WORKSPACE_BYTES,'hash',b''))
        self.assertEqual(self.admit('result=2')[0]['state'],'storage_quota')

    def test_forwarded_ip_only_uses_configured_proxy_chain(self):
        with patch.dict(os.environ,{'ENZYMIND_TRUSTED_PROXIES':'127.0.0.1/32,10.0.0.0/8'}):
            self.assertEqual(source_ip(request('203.0.113.8','1.1.1.1')),digest('203.0.113.8'))
            self.assertEqual(source_ip(request('127.0.0.1','1.1.1.1,203.0.113.8,10.0.0.1')),digest('203.0.113.8'))
            self.assertNotEqual(source_ip(request('127.0.0.1','garbage')),digest('garbage'))

    def test_input_rejects_host_paths_options_and_nonfinite_data(self):
        for body in [{'code':'pass','image':'evil'}, {'code':'pass','file_ids':['/etc/passwd']}, {'code':'\ud800'},
                     {'code':'pass','data':{'x':float('nan')}}, {'code':'pass','network':'host'}]:
            with self.assertRaises(HTTPException):
                normalize(body)


class APITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = workspace._store
        workspace._store = WorkspaceStore(Path(self.temp.name)/'workspace.sqlite')
        self.env = patch.dict(os.environ,{'ENZYMIND_PYTHON_ENABLED':'true','PYTHON_SANDBOX_TOKEN':'s'*48,
                                         'ENZYMIND_PYTHON_AGENT_IPS':'127.0.0.1'})
        self.env.start()
        self.key = digest('a'*64)
        session=workspace.store().create_session(self.key)
        turn,self.token=workspace.store().begin(self.key,session['id'],str(uuid4()),'compute',[],billing_mode='byok')
        workspace.store().status(self.key,turn['id'],'running')
        self.turn_id=turn['id']
        self.app=FastAPI(); self.app.include_router(workspace.router)
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url='http://test')

    async def asyncTearDown(self):
        await self.client.aclose()
        self.env.stop()
        workspace._store=self.old
        self.temp.cleanup()

    async def call(self, code='result=1', **extra):
        return await self.client.post('/api/workspace/tools/python',json={'code':code,**extra},headers={'X-Enzymind-Turn':self.token})

    async def test_public_and_proxy_calls_are_denied_even_with_a_valid_turn(self):
        mock=AsyncMock()
        with patch.object(workspace.python_sandbox(),'invoke',mock):
            for peer in ['203.0.113.8','172.17.0.3','::ffff:203.0.113.8']:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app,client=(peer,1234)),base_url='http://test') as client:
                    response=await client.post('/api/workspace/tools/python',json={'code':'result=1'},headers={'X-Enzymind-Turn':self.token})
                    self.assertEqual(response.status_code,403)
            for name in ['X-Forwarded-For','X-Real-IP','Forwarded','Origin','Sec-Fetch-Site','X-Forwarded-Host']:
                response=await self.client.post('/api/workspace/tools/python',json={'code':'result=1'},headers={'X-Enzymind-Turn':self.token,name:'127.0.0.1'})
                self.assertEqual(response.status_code,403)
            for peers in ['', '0.0.0.0/0', '127.0.0.1,invalid']:
                with patch.dict(os.environ,{'ENZYMIND_PYTHON_AGENT_IPS':peers}):
                    self.assertEqual((await self.call()).status_code,403)
            mock.assert_not_awaited()
        with workspace.store().db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM python_runs').fetchone()[0],0)

    async def test_agent_address_alone_never_grants_execution(self):
        for headers in [{}, {'X-Enzymind-Client':'a'*64}, {'X-Enzymind-Turn':'f'*48}]:
            response=await self.client.post('/api/workspace/tools/python',json={'code':'result=1'},headers=headers)
            self.assertEqual(response.status_code,403)
        workspace.store().status(self.key,self.turn_id,'cancelled')
        self.assertEqual((await self.call()).status_code,403)

    async def test_feature_flag_auth_and_file_download(self):
        self.assertEqual((await self.client.post('/api/workspace/tools/python',json={'code':'pass'})).status_code,403)
        with patch.dict(os.environ,{'ENZYMIND_PYTHON_ENABLED':'false'}):
            self.assertEqual((await self.call()).status_code,503)
        mock=AsyncMock(return_value={'success':True,'execution_status':'completed','result':{'sum':2},'duration':.1,
             'files':[{'name':'x.txt','content':base64.b64encode(b'<script>alert(1)</script>').decode()}]})
        with patch.object(workspace.python_sandbox(),'invoke',mock):
            first=await self.call()
            self.assertEqual(first.status_code,200,first.text)
            second=await self.call()
        self.assertTrue(second.json()['reused'])
        mock.assert_awaited_once()
        record=workspace.store().result(self.key,first.json()['id'])
        file_id=record['payload']['files'][0]['id']
        path=f"/api/workspace/results/{record['id']}/files/{file_id}"
        downloaded=await self.client.get(path,headers={'X-Enzymind-Client':'a'*64})
        self.assertEqual(downloaded.content,b'<script>alert(1)</script>')
        self.assertEqual(downloaded.headers['x-content-type-options'],'nosniff')
        self.assertTrue(downloaded.headers['content-disposition'].startswith('attachment'))
        self.assertEqual((await self.client.get(path,headers={'X-Enzymind-Client':'b'*64})).status_code,404)
        self.assertEqual((await self.client.get(path.replace(record['id'],str(uuid4())),headers={'X-Enzymind-Client':'a'*64})).status_code,404)

    async def test_oversized_body_is_rejected_before_admission(self):
        response=await self.client.post('/api/workspace/tools/python',content=b'{"code":"'+b'x'*256000+b'"}',
                                       headers={'X-Enzymind-Turn':self.token})
        self.assertEqual(response.status_code,413)
        with workspace.store().db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM python_runs').fetchone()[0],0)

    async def test_transport_failure_is_saved_once_and_not_retried(self):
        mock=AsyncMock(side_effect=httpx.ReadError('private data must not leak'))
        with patch.object(workspace.python_sandbox(),'invoke',mock):
            response=await self.call()
            repeat=await self.call()
        self.assertEqual(response.json()['status'],'failed')
        self.assertEqual(repeat.json()['id'],response.json()['id'])
        self.assertNotIn('private data',response.text)
        mock.assert_awaited_once()

    async def test_cancel_turn_stops_inflight_submission(self):
        begun=asyncio.Event(); stopped=asyncio.Event()
        async def work(*args):
            begun.set()
            try: await asyncio.sleep(10)
            finally: stopped.set()
        with patch.object(workspace.python_sandbox(),'invoke',work):
            task=asyncio.create_task(self.call())
            await begun.wait()
            await self.client.post(f'/api/workspace/turns/{self.turn_id}/cancel',headers={'X-Enzymind-Client':'a'*64})
            response=await asyncio.wait_for(task,2)
        self.assertTrue(stopped.is_set())
        self.assertEqual(response.json()['data']['execution_status'],'cancelled')


if __name__=='__main__':
    unittest.main()
