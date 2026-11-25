"""Offline integration tests: no models, GPUs, n8n or public services required."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient
from gateway import workspace
from gateway.main import app
from gateway.workspace_store import WorkspaceStore, digest
from gateway.result_catalog import compact


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = WorkspaceStore(Path(self.tmp.name) / 'research.sqlite')
        self.owner = digest('a' * 64)
        self.session = self.store.create_session(self.owner)

    def tearDown(self):
        self.tmp.cleanup()

    def test_durable_memory_and_owner_isolation(self):
        result = self.store.save_result(self.owner, 'kcat', {'query':'P00761'}, {'success':True,'kcat':0,'unit':'s^-1'})
        reopened = WorkspaceStore(self.store.path)
        self.assertEqual(reopened.result(self.owner, result['id'])['payload']['kcat'], 0)
        with self.assertRaises(HTTPException) as error:
            reopened.result(digest('b' * 64), result['id'])
        self.assertEqual(error.exception.status_code, 404)
        with self.assertRaises(HTTPException):
            reopened.session(digest('b' * 64), self.session['id'])

    def test_idempotency_and_one_active_turn(self):
        rid = str(uuid4())
        first, token = self.store.begin(self.owner, self.session['id'], rid, 'question', [])
        repeated, repeated_token = self.store.begin(self.owner, self.session['id'], rid, 'question', [])
        self.assertEqual(first['id'], repeated['id'])
        self.assertIsNone(repeated_token)
        with self.assertRaises(HTTPException):
            self.store.begin(self.owner, self.session['id'], rid, 'different question', [])
        with self.assertRaises(HTTPException):
            self.store.begin(self.owner, self.session['id'], str(uuid4()), 'parallel question', [])
        self.store.status(self.owner, first['id'], 'running')
        self.assertEqual(self.store.authorize_turn(token)['id'], first['id'])
        self.store.status(self.owner, first['id'], 'cancelled')
        with self.assertRaises(HTTPException): self.store.authorize_turn(token)
        self.store.status(self.owner, first['id'], 'completed', output='late response')
        self.assertEqual(self.store.turn(self.owner,first['id'])['status'], 'cancelled')

    def test_restart_does_not_resubmit(self):
        first,_ = self.store.begin(self.owner,self.session['id'],str(uuid4()),'question',[])
        self.store.recover()
        self.assertEqual(self.store.turn(self.owner,first['id'])['status'], 'queued')
        with self.store.db() as db: db.execute('UPDATE turns SET lease_expires=0 WHERE id=?',(first['id'],))
        self.store.recover()
        self.assertEqual(self.store.turn(self.owner,first['id'])['status'], 'interrupted')

    def test_atomic_memory_commit_and_stale_revision(self):
        sid = self.session['id']
        old,_ = self.store.begin(self.owner,sid,str(uuid4()),'old question',[])
        self.store.status(self.owner,old['id'],'completed',output='old answer')
        turn,token = self.store.begin(self.owner,sid,str(uuid4()),'new question',[])
        self.store.status(self.owner,turn['id'],'running')
        self.assertTrue(self.store.renew(self.owner,turn['id']))
        with self.assertRaises(ValueError):
            self.store.complete(self.owner,turn['id'],99,'answer','memory',2,[],1,7000)
        self.assertEqual(self.store.session(self.owner,sid)['summary'],'')
        self.assertEqual(self.store.turn(self.owner,turn['id'])['status'],'running')
        with self.assertRaises(ValueError):
            self.store.complete(self.owner,turn['id'],0,'answer','记忆'*1000,2,[],1,7000)
        self.store.complete(self.owner,turn['id'],0,'answer','memory with exact result references',2,[],1,7000)
        reopened=WorkspaceStore(self.store.path)
        self.assertEqual(reopened.session(self.owner,sid)['summarized_count'],2)
        self.assertEqual(reopened.session(self.owner,sid)['compression_count'],1)
        self.assertEqual(reopened.turn(self.owner,turn['id'])['output'],'answer')
        with self.assertRaises(ValueError):
            reopened.complete(self.owner,turn['id'],0,'late answer','other memory',2,[],1,7000)
        self.assertEqual(reopened.session(self.owner,sid)['summary'],'memory with exact result references')

    def test_additive_migration_keeps_legacy_summary(self):
        import sqlite3
        path=Path(self.tmp.name)/'old.sqlite'
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL, summary TEXT NOT NULL DEFAULT '', summarized_count INTEGER NOT NULL DEFAULT 0)")
            db.execute("INSERT INTO sessions VALUES(?,?,?,?,?,?,?)",('old',self.owner,'Legacy study',1,1,'Legacy summary',4))
        reopened=WorkspaceStore(path)
        self.assertEqual(reopened.session(self.owner,'old')['summary'],'Legacy summary')
        self.assertEqual(reopened.session(self.owner,'old')['summarized_count'],4)
        self.assertEqual(reopened.session(self.owner,'old')['memory_revision'],0)

    def test_expired_or_cancelled_worker_cannot_commit(self):
        turn,_=self.store.begin(self.owner,self.session['id'],str(uuid4()),'question',[])
        self.store.status(self.owner,turn['id'],'running')
        with self.store.db() as db: db.execute('UPDATE turns SET lease_expires=0 WHERE id=?',(turn['id'],))
        self.assertFalse(self.store.renew(self.owner,turn['id']))
        with self.assertRaises(ValueError): self.store.complete(self.owner,turn['id'],0,'answer','',0,[])
        self.assertEqual(self.store.session(self.owner,self.session['id'])['memory_revision'],0)

    def test_failure_and_compact_evidence(self):
        r = self.store.save_result(self.owner, 'active-sites', {}, {'result':'[ERROR] unavailable'})
        self.assertEqual(r['status'], 'failed')
        evidence = compact({'structure_data':'ATOM'*10000,'active_data':[[1,'ALA',1]],'sequence':'A'*10000})
        self.assertNotIn('structure_data', evidence)
        self.assertEqual(evidence['active_data'][0][0],1)
        self.assertLess(len(evidence['sequence']),3100)
        sites = compact({'active_data':[[48,'HIS','#green','Catalytic Site',0.9999]],'scores':[[0.999949,0,0,0]],'residue_labels':[0,0,0]})
        self.assertNotIn('scores',sites)
        self.assertEqual(sites['active_data'][0][-1],0.9999)
        for payload in ({'result':{'error':'model unavailable'}}, {'data':{'success':False}}, {'result':'❌ Invalid sequence'}):
            result = self.store.save_result(self.owner, 'ec', {}, payload)
            self.assertEqual(result['status'], 'failed')


class APITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        workspace._store = WorkspaceStore(Path(self.tmp.name) / 'workspace.sqlite')
        # Tests must never prune production structure files in /tmp.
        self.retention_env = patch.dict('os.environ', {'ENZYMIND_RETENTION_ARTIFACT_ROOTS': '[]'})
        self.retention_env.start()
        self.addCleanup(self.retention_env.stop)
        self.client = TestClient(app)
        self.client.__enter__()
        self.headers = {'X-Enzymind-Client': 'a'*64}
        self.key = digest('a'*64)

    def tearDown(self):
        self.client.__exit__(None,None,None)
        workspace._store = None
        self.tmp.cleanup()

    def test_context_warning_is_advisory_and_requires_a_live_turn(self):
        session = workspace.store().create_session(self.key)
        turn, token = workspace.store().begin(self.key, session['id'], str(uuid4()), 'long question', [])
        workspace.store().status(self.key, turn['id'], 'running')
        headers = {'X-Enzymind-Turn': token}
        endpoint = '/api/workspace/memory-progress'
        body = {'state': 'ready', 'context_tokens': 48000, 'warning': True}
        self.assertEqual(self.client.post(endpoint, json=body).status_code, 403)
        self.assertEqual(self.client.post(endpoint, headers=headers, json={**body, 'warning': 'arbitrary text'}).status_code, 422)
        self.assertEqual(self.client.post(endpoint, headers=headers, json=body).status_code, 200)
        record = workspace.store().turn(self.key, turn['id'])
        self.assertEqual(record['status'], 'running')
        self.assertIn('Analysis is continuing', record['events'][-1]['data']['warning'])
        workspace.store().complete(self.key, turn['id'], 0, 'Answer', '', 0, [], 0, 48000)
        self.assertEqual(workspace.store().session(self.key, session['id'])['context_tokens'], 48000)
        self.assertEqual(self.client.post(endpoint, headers=headers, json=body).status_code, 403)

    def test_access_and_validation(self):
        self.assertEqual(self.client.get('/api/workspace/sessions').status_code,401)
        r = self.client.post('/api/workspace/sessions',headers=self.headers)
        self.assertEqual(r.status_code,200)
        self.assertNotIn('owner',r.json())
        self.assertIn('no-store',r.headers['cache-control'])
        sid = r.json()['id']
        for body in [{'message':'x','request_id':'invalid'}, {'message':'','request_id':str(uuid4())}, {'message':'x','request_id':str(uuid4()),'references':[str(uuid4())]*5}]:
            response = self.client.post(f'/api/workspace/sessions/{sid}/turns',json=body,headers=self.headers)
            self.assertEqual(response.status_code,422)
        response = self.client.get(f'/api/workspace/sessions/{sid}',headers={'X-Enzymind-Client':'b'*64})
        self.assertEqual(response.status_code,404)

    def test_large_questions_reach_context_evaluation_without_the_old_transport_limits(self):
        async def no_model(*args):
            pass

        session = workspace.store().create_session(self.key)
        endpoint = f"/api/workspace/sessions/{session['id']}/turns"
        with patch.object(workspace, 'run_turn', side_effect=no_model) as dispatch:
            # Cover the full ASCII allowance and escaped Unicode JSON > 256 KB.
            for message in ['A' * 300000, '研' * 49000]:
                body = json.dumps({'message': message, 'request_id': str(uuid4()), 'references': []})
                self.assertGreater(len(body), 256000)
                response = self.client.post(endpoint, headers={**self.headers, 'Content-Type': 'application/json'}, content=body)
                self.assertEqual(response.status_code, 200, response.text[:200])
                turn = response.json()
                self.assertEqual(turn['message'], message)
                self.assertEqual(workspace.store().turn(self.key, turn['id'])['message'], message)
                workspace.store().status(self.key, turn['id'], 'cancelled')
            self.assertEqual(dispatch.call_count, 2)
            response = self.client.post(endpoint, headers=self.headers, json={'message': 'x' * 300001, 'request_id': str(uuid4())})
            self.assertEqual(response.status_code, 422)
            response = self.client.post(endpoint, headers=self.headers, json={'message': 'x', 'padding': 'x' * 2000000, 'request_id': str(uuid4())})
            self.assertEqual(response.status_code, 413)
            self.assertEqual(dispatch.call_count, 2)

        # The larger transport allowance is restricted to question submissions.
        turn, token = workspace.store().begin(self.key, session['id'], str(uuid4()), 'question', [])
        workspace.store().status(self.key, turn['id'], 'running')
        response = self.client.post('/api/workspace/memory-progress', headers={'X-Enzymind-Turn': token},
                                    json={'state': 'ready', 'padding': 'x' * 256000})
        self.assertEqual(response.status_code, 413)

    def test_reference_authorization_and_private_structure(self):
        record = workspace.store().save_result(self.key,'structure',{}, {'structure_data':'ATOM      1  CA  ALA A   1      10.000  10.000  10.000  1.00 90.00           C\n'})
        r = self.client.get(f"/api/workspace/results/{record['id']}/structure", headers=self.headers)
        self.assertEqual(r.status_code,200)
        self.assertIn('ATOM',r.text)
        self.assertEqual(self.client.get(f"/api/workspace/results/{record['id']}",headers={'X-Enzymind-Client':'b'*64}).status_code,404)
        self.assertEqual(self.client.post('/api/workspace/tools/kcat',json={}).status_code,403)
        self.assertTrue(workspace.result_evidence(record)['artifacts']['structure_available'])
        self.assertNotIn('structure_data',workspace.result_evidence(record)['data'])

    def test_structure_snapshot_uses_project_directories_and_rejects_symlinks(self):
        root = Path(self.tmp.name)
        output = root / 'project-output'
        static = root / 'project-pdb'
        output.mkdir()
        static.mkdir()
        pdb = 'ATOM      1  CA  ALA A   1      10.000  10.000  10.000  1.00 90.00           C\n'
        (static / 'query.pdb').write_text(pdb)
        (root / 'outside.pdb').write_text(pdb)
        (output / 'outside.pdb').symlink_to(root / 'outside.pdb')
        with patch.dict('os.environ', {'ESMFOLD_OUTPUT_DIR': str(output), 'STATIC_PDB_DIR': str(static)}):
            payload = asyncio.run(workspace.preserve_structure({'static_path': '/static/pdb/query.pdb'}))
            self.assertEqual(payload['structure_data'], pdb)
            record = workspace.store().save_result(self.key, 'structure', {}, payload)
            (static / 'query.pdb').unlink()
            response = self.client.get(f"/api/workspace/results/{record['id']}/structure", headers=self.headers)
            self.assertEqual(response.text, pdb)
            outside = {'pdb_path': str(output / 'outside.pdb')}
            self.assertEqual(asyncio.run(workspace.preserve_structure(outside)), outside)

    def test_individual_tool_capture_and_upstream_failure(self):
        real_client = httpx.AsyncClient
        def handler(request):
            self.assertNotIn('x-enzymind-client', request.headers)
            return httpx.Response(200,json={'result':{'kcat':10,'unit':'s^-1'}})
        with patch.object(workspace.httpx,'AsyncClient',side_effect=lambda **kwargs:real_client(transport=httpx.MockTransport(handler),**kwargs)):
            response = self.client.post('/api/predict/kcat',headers=self.headers,json={'enzyme_query':'P00761','smiles':'CCO'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['result']['kcat'],10)
        record = response.json()['workspace_result']
        self.assertEqual(record['tool'],'kcat')
        self.assertNotIn('owner',record)
        self.assertIn('no-store', response.headers['cache-control'])
        restored = self.client.get('/api/workspace/results/'+record['id'],headers=self.headers).json()
        self.assertEqual(restored['payload']['result']['kcat'],10)
        with patch.object(workspace.httpx,'AsyncClient',side_effect=lambda **kwargs:real_client(transport=httpx.MockTransport(lambda r:httpx.Response(503,json={'detail':'Service unavailable'})),**kwargs)):
            response = self.client.post('/api/predict/kcat',headers=self.headers,json={})
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json()['workspace_result']['status'],'failed')

    def test_non_json_failure_is_saved_as_failure(self):
        real_client = httpx.AsyncClient
        with patch.object(workspace.httpx, 'AsyncClient', side_effect=lambda **kw: real_client(
                transport=httpx.MockTransport(lambda r: httpx.Response(500, text='Internal Server Error')), **kw)):
            response = self.client.post('/api/predict/ec', headers=self.headers, json={})
        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.json()['success'])
        self.assertEqual(response.json()['workspace_result']['status'], 'failed')

    def test_saved_result_pagination_and_tool_budget(self):
        session = workspace.store().create_session(self.key)
        turn,token = workspace.store().begin(self.key,session['id'],str(uuid4()),'read saved evidence',[])
        workspace.store().status(self.key,turn['id'],'running')
        record = workspace.store().save_result(self.key,'active-sites',{}, {'data':{'active_data':list(range(80))}})
        body = {'result_id':record['id'],'field':'data.active_data','offset':30,'limit':10}
        response = self.client.post('/api/workspace/tools/read-result',json=body,headers={'X-Enzymind-Turn':token})
        self.assertEqual(response.json()['data'],list(range(30,40)))
        self.assertEqual(response.json()['selection']['next_offset'],40)
        foreign = workspace.store().save_result(digest('b'*64),'active-sites',{}, {'secret':'foreign workspace'})
        response = self.client.post('/api/workspace/tools/read-result',json={'result_id':foreign['id']},headers={'X-Enzymind-Turn':token})
        self.assertEqual(response.json()['status'],'failed')
        self.assertNotIn('secret',response.text)
        for i in range(10):
            workspace.store().event(turn['id'],'tool_start',{'tool':'read-result'})
        response = self.client.post('/api/workspace/tools/read-result',json=body,headers={'X-Enzymind-Turn':token})
        self.assertEqual(response.status_code,429)

    def test_completed_history_is_rehydrated_with_saved_summary(self):
        session = workspace.store().create_session(self.key)
        for question, answer in [('older question','older answer'),('recent question','recent answer')]:
            prior,_ = workspace.store().begin(self.key,session['id'],str(uuid4()),question,[])
            workspace.store().status(self.key,prior['id'],'completed',output=answer)
        workspace.store().memory(self.key,session['id'],'Preserved research objective',2)
        real_client = httpx.AsyncClient
        seen=[]
        def handler(request):
            seen.append(json.loads(request.content))
            return httpx.Response(200,json={'output':'Context retained','summary':'Preserved research objective','summarized_count':2})
        with patch.object(workspace.httpx,'AsyncClient',side_effect=lambda **kwargs:real_client(transport=httpx.MockTransport(handler),**kwargs)):
            self.client.post(f"/api/workspace/sessions/{session['id']}/turns",headers=self.headers,json={'message':'follow up','request_id':str(uuid4())})
            self.client.portal.call(asyncio.sleep,0.05)
        self.assertEqual(seen[0]['summary'],'Preserved research objective')
        self.assertEqual(seen[0]['history'],[{'role':'user','content':'recent question'},{'role':'assistant','content':'recent answer'}])

    def test_tool_records_and_error_handling(self):
        session = workspace.store().create_session(self.key)
        turn,token = workspace.store().begin(self.key,session['id'],str(uuid4()),'predict',[])
        workspace.store().status(self.key,turn['id'],'running')
        real_client = httpx.AsyncClient
        def handler(request):
            self.assertEqual(request.headers['X-Easifa-Session'],self.key)
            return httpx.Response(200,json={'success':True,'kcat':23.5,'unit':'s^-1'})
        with patch.object(workspace.httpx, 'AsyncClient', side_effect=lambda **kwargs:real_client(transport=httpx.MockTransport(handler),**kwargs)):
            response=self.client.post('/api/workspace/tools/kcat',json={'smiles':'CCO','enzyme_query':'P00761'},headers={'X-Enzymind-Turn':token})
        self.assertEqual(response.status_code,200,response.text)
        data=response.json()
        self.assertEqual(data['data']['kcat'],23.5)
        self.assertIn('/enzymind/results/',data['url'])
        events=workspace.store().turn(self.key,turn['id'])['events']
        self.assertEqual([e['kind'] for e in events],['tool_start','tool_end'])
        self.assertEqual(events[-1]['data']['status'],'completed')
        with patch.object(workspace.httpx, 'AsyncClient', side_effect=lambda **kwargs:real_client(transport=httpx.MockTransport(lambda r:httpx.Response(503)),**kwargs)):
            response=self.client.post('/api/workspace/tools/ec',json={'query':'P00761'},headers={'X-Enzymind-Turn':token})
        self.assertEqual(response.json()['status'],'failed')
        self.assertEqual(len(workspace.store().results(self.key,session['id'])),2)

    def test_completed_turn_and_replay(self):
        session=workspace.store().create_session(self.key)
        record=workspace.store().save_result(self.key,'kcat',{}, {'kcat':10,'unit':'s^-1'})
        real_client=httpx.AsyncClient
        calls=[]
        def handler(request):
            data=json.loads(request.content)
            calls.append(data)
            self.assertEqual(data['evidence'][0]['id'],record['id'])
            self.assertNotIn('x-enzymind-client',request.headers)
            return httpx.Response(200,json={'output':f"See [kinetics]({record['url']}).",'summary':'','summarized_count':0})
        body={'message':'Interpret this result','request_id':str(uuid4()),'references':[record['id']]}
        with patch.object(workspace.httpx,'AsyncClient',side_effect=lambda **kwargs:real_client(transport=httpx.MockTransport(handler),**kwargs)):
            created=self.client.post(f"/api/workspace/sessions/{session['id']}/turns",headers=self.headers,json=body)
            self.assertEqual(created.status_code,200,created.text)
            turn_id=created.json()['id']
            # Barrier through the same portal lets the queued worker finish without a timing sleep.
            self.client.portal.call(asyncio.sleep,0.05)
            replay=self.client.post(f"/api/workspace/sessions/{session['id']}/turns",headers=self.headers,json=body)
            self.assertEqual(replay.json()['id'],turn_id)
            turn=self.client.get(f'/api/workspace/turns/{turn_id}',headers=self.headers).json()
        self.assertEqual(turn['status'],'completed',turn)
        self.assertEqual(len(calls),1)
        self.assertEqual(turn['events'][-1]['data']['results'][0]['id'],record['id'])
        session_data = self.client.get(f"/api/workspace/sessions/{session['id']}",headers=self.headers).json()
        self.assertEqual(session_data['results'][0]['id'],record['id'])
        self.assertNotIn('payload',session_data['results'][0])
        self.assertIsNone(session_data['results'][0]['session_id'])  # Provenance stays with the original tool.

    def test_model_citation_repair_preserves_owner_isolation(self):
        session=workspace.store().create_session(self.key)
        own=workspace.store().save_result(self.key,'kcat',{}, {'kcat':10,'unit':'s^-1'})
        foreign=workspace.store().save_result(digest('b'*64),'kcat',{}, {'kcat':99,'unit':'s^-1'})
        real_client=httpx.AsyncClient
        output=f"[Our result](https://enzymind.results/{own['id']}) [Unknown]({foreign['id']})"
        with patch.object(workspace.httpx,'AsyncClient',side_effect=lambda **kw:real_client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'output':output})),**kw)):
            created=self.client.post(f"/api/workspace/sessions/{session['id']}/turns",headers=self.headers,json={'message':'Read evidence','request_id':str(uuid4())})
            self.client.portal.call(asyncio.sleep,0.05)
            turn=self.client.get('/api/workspace/turns/'+created.json()['id'],headers=self.headers).json()
        self.assertEqual(turn['status'],'completed',turn)
        self.assertIn(f"[Our result]({own['url']})",turn['output'])
        self.assertIn(f"[Unknown]({foreign['id']})",turn['output'])
        self.assertEqual([r['id'] for r in turn['events'][-1]['data']['results']],[own['id']])

    def test_old_answers_get_working_links_without_rewriting_raw_history(self):
        session=workspace.store().create_session(self.key)
        record=workspace.store().save_result(self.key,'kcat',{}, {'kcat':10},session_id=session['id'])
        prior,_=workspace.store().begin(self.key,session['id'],str(uuid4()),'Read result',[])
        original=f"[Evidence](https://enzymind.results/{record['id']})"
        workspace.store().status(self.key,prior['id'],'completed',output=original)
        displayed=self.client.get('/api/workspace/sessions/'+session['id'],headers=self.headers).json()
        self.assertEqual(displayed['turns'][0]['output'],f"[Evidence]({record['url']})")
        self.assertEqual(workspace.store().turn(self.key,prior['id'])['output'],original)

    def test_invalid_citations_are_removed_from_answer_and_memory_but_raw_history_is_preserved(self):
        session = workspace.store().create_session(self.key)
        question = 'Explain [this URL](https://example.invalid/)'
        original = 'See [annotation](https://example.invalid/).'
        prior, _ = workspace.store().begin(self.key, session['id'], str(uuid4()), question, [])
        workspace.store().status(self.key, prior['id'], 'completed', output=original)
        workspace.store().memory(self.key, session['id'], original, 0)
        seen = []
        real_client = httpx.AsyncClient
        def handler(request):
            seen.append(json.loads(request.content))
            return httpx.Response(200, json={'output': original, 'summary': original, 'summarized_count': 0})
        with patch.object(workspace.httpx, 'AsyncClient', side_effect=lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)):
            created = self.client.post(f"/api/workspace/sessions/{session['id']}/turns", headers=self.headers, json={'message': 'Follow up', 'request_id': str(uuid4())})
            self.client.portal.call(asyncio.sleep, 0.05)
        turn = workspace.store().turn(self.key, created.json()['id'])
        self.assertEqual(turn['status'], 'completed', turn)
        self.assertEqual(turn['output'], 'See annotation.')
        self.assertEqual(seen[0]['summary'], 'See annotation.')
        self.assertEqual(seen[0]['history'], [{'role': 'user', 'content': question}, {'role': 'assistant', 'content': 'See annotation.'}])
        self.assertEqual(workspace.store().session(self.key, session['id'])['summary'], original)
        self.assertEqual(workspace.store().turn(self.key, prior['id'])['output'], original)
        displayed = self.client.get('/api/workspace/sessions/' + session['id'], headers=self.headers).json()
        self.assertEqual(displayed['turns'][0]['output'], 'See annotation.')

    def test_new_compressed_memory_saves_clean_citations(self):
        session = workspace.store().create_session(self.key)
        prior, _ = workspace.store().begin(self.key, session['id'], str(uuid4()), 'Annotation', [])
        workspace.store().status(self.key, prior['id'], 'completed', output='Previous answer')
        real_client = httpx.AsyncClient
        result = {'output': 'New answer', 'summary': 'See [annotation](https://example.invalid/).', 'summarized_count': 2, 'compression_count': 1}
        with patch.object(workspace.httpx, 'AsyncClient', side_effect=lambda **kw: real_client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=result)), **kw)):
            created = self.client.post(f"/api/workspace/sessions/{session['id']}/turns", headers=self.headers, json={'message': 'Follow up', 'request_id': str(uuid4())})
            self.client.portal.call(asyncio.sleep, 0.05)
        self.assertEqual(workspace.store().turn(self.key, created.json()['id'])['status'], 'completed')
        self.assertEqual(workspace.store().session(self.key, session['id'])['summary'], 'See annotation.')


if __name__ == '__main__': unittest.main()
