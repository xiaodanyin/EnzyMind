import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx

from services.python_sandbox import runner
from services.python_sandbox.engine import Engine


class RunnerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = runner.engine, runner.ready, runner.state_path
        runner.state_path=Path(self.temp.name)/'jobs.sqlite'
        runner.active.clear()
        with runner.db() as db:
            db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY, owner TEXT, created REAL, status TEXT)')
        runner.ready=True
        runner.engine=AsyncMock()
        runner.engine.execute.return_value={'success':True,'execution_status':'completed','duration':.1,'memory_bytes':100,'files':[]}
        self.env=patch.dict(os.environ,{'PYTHON_SANDBOX_TOKEN':'k'*48})
        self.env.start()
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=runner.app),base_url='http://127.0.0.1:8091',
                                     headers={'Authorization':'Bearer '+'k'*48})
        self.payload={'job_id':str(uuid4()),'owner':'a'*64,'code':'result=1',
                      'inputs':{'data':{},'results':{},'files':{}},'files':[]}

    async def asyncTearDown(self):
        await self.client.aclose()
        runner.engine,runner.ready,runner.state_path=self.old
        runner.active.clear()
        self.env.stop()
        self.temp.cleanup()

    async def test_token_preflight_and_request_allowlist(self):
        self.assertEqual((await self.client.get('/health',headers={'Authorization':'Bearer wrong'})).status_code,401)
        runner.ready=False
        self.assertEqual((await self.client.post('/jobs',json=self.payload)).status_code,503)
        runner.ready=True
        self.assertEqual((await self.client.post('/jobs',json={**self.payload,'network':'host'})).status_code,422)
        runner.engine.execute.assert_not_awaited()

    async def test_valid_service_token_cannot_be_used_remotely_or_through_a_browser_proxy(self):
        for peer in ['203.0.113.8','172.17.0.2','::ffff:203.0.113.8']:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=runner.app,client=(peer,2345)),
                                         base_url='http://127.0.0.1:8091',headers=self.client.headers) as client:
                self.assertEqual((await client.post('/jobs',json=self.payload)).status_code,403)
        for name in ['Origin','Forwarded','X-Forwarded-For','X-Real-IP','Sec-Fetch-Site']:
            self.assertEqual((await self.client.post('/jobs',json=self.payload,headers={name:'127.0.0.1'})).status_code,403)
        self.assertEqual((await self.client.get('/health',headers={'Host':'attacker.example'})).status_code,403)
        self.assertEqual((await self.client.get('/health',headers=[('Authorization','Bearer '+'k'*48),('Authorization','Bearer wrong')])).status_code,401)
        self.assertEqual((await self.client.get('/health',headers=[(b'Authorization',b'Bearer \xff')])).status_code,401)
        runner.engine.execute.assert_not_awaited()

    async def test_invalid_unicode_and_deep_json_never_reach_execution(self):
        self.assertEqual((await self.client.post('/jobs',content=json.dumps({**self.payload,'code':'\ud800'}),headers={'Content-Type':'application/json'})).status_code,422)
        self.assertEqual((await self.client.post('/jobs',content=b'['*2000+b']'*2000)).status_code,422)
        runner.engine.execute.assert_not_awaited()

    async def test_durable_tombstones_survive_memory_reset_and_early_cancel(self):
        self.assertEqual((await self.client.post('/jobs',json=self.payload)).status_code,200)
        runner.active.clear()
        self.assertEqual((await self.client.post('/jobs',json=self.payload)).status_code,409)
        runner.engine.execute.assert_awaited_once()
        self.payload['job_id']=str(uuid4())
        self.assertEqual((await self.client.delete('/jobs/'+self.payload['job_id'])).status_code,200)
        self.assertEqual((await self.client.post('/jobs',json=self.payload)).status_code,409)

    async def test_cancel_signals_the_whole_job_and_concurrency_rejects_without_queue(self):
        begun=asyncio.Event()
        async def execute(job_id,code,inputs,files,cancel):
            begun.set()
            await cancel.wait()
            return {'success':False,'execution_status':'cancelled','duration':.1,'memory_bytes':0,'files':[]}
        runner.engine.execute.side_effect=execute
        task=asyncio.create_task(self.client.post('/jobs',json=self.payload))
        await begun.wait()
        self.assertEqual((await self.client.post('/jobs',json={**self.payload,'job_id':str(uuid4())})).status_code,429)
        await self.client.delete('/jobs/'+self.payload['job_id'])
        self.assertEqual((await asyncio.wait_for(task,2)).json()['execution_status'],'cancelled')
        self.assertFalse(runner.active)

    async def test_cgroup_downgrade_is_never_accepted(self):
        engine=Engine('/tmp/not-used','sha256:'+'a'*64)
        engine.api=AsyncMock(return_value={'SecurityOptions':['name=rootless','name=seccomp'],
                                          'CgroupVersion':'1','CgroupDriver':'cgroupfs'})
        try:
            with self.assertRaisesRegex(RuntimeError,'cgroup v2'):
                await engine.preflight()
            engine.api.assert_awaited_once()
        finally:
            await engine.client.aclose()


if __name__=='__main__':
    unittest.main()
