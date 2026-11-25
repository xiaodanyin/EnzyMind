import contextlib
import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import deploy
from build_workflow import build


class DeploymentTests(unittest.TestCase):
    def test_updates_only_target_reuses_easifa_binding_and_rolls_back_failure(self):
        for fail_update in (False,True):
            with self.subTest(fail_update=fail_update),tempfile.TemporaryDirectory() as directory:
                old=build();old.update(id='target',active=True);old['nodes'][0]['old_marker']=True
                old['settings']['unacceptedInternalSetting']=True
                source={'nodes':[{'name':'Research language model','type':'@n8n/n8n-nodes-langchain.lmChatDeepSeek','typeVersion':1,'parameters':{'options':{'maxRetries':0}},'credentials':{'deepSeekApi':{'id':'existing-free-credential','name':'DeepSeek'}}}]}
                calls=[];failed=False
                def api(request,timeout):
                    nonlocal failed
                    path=request.full_url.split('/api/v1')[1];body=json.loads(request.data) if request.data else None;method=request.method
                    calls.append((method,path,body))
                    if method=='GET':return io.BytesIO(json.dumps(source if path=='/workflows/easifa' else old).encode())
                    if path=='/credentials':
                        self.assertIn('model_relay_token',body['data']['apiKey']);self.assertTrue(body['data']['url'].endswith('/api/workspace/model'))
                        return io.BytesIO(b'{"id":"new-relay"}')
                    self.assertTrue(path.startswith('/workflows/target'))
                    if method=='PUT' and fail_update and not failed:
                        failed=True;raise HTTPError(request.full_url,500,'test failure',None,None)
                    return io.BytesIO(b'{"id":"target","name":"EnzyMind workspace","active":true}')
                args=['deploy.py','--model-workflow','easifa','--model-node','Research language model','--target','target','--backup-dir',directory]
                with patch.object(sys,'argv',args),patch.dict(os.environ,{'N8N_API_KEY':'management-test-only'}),patch.object(deploy,'urlopen',side_effect=api),contextlib.redirect_stdout(io.StringIO()):
                    if fail_update:
                        with self.assertRaises(RuntimeError):deploy.main()
                    else:deploy.main()
                writes=[body for method,path,body in calls if method=='PUT']
                model=next(n for n in writes[0]['nodes'] if n['name']=='Research language model')
                self.assertEqual(model['credentials'],source['nodes'][0]['credentials'])
                self.assertEqual(calls[-1][1],'/workflows/target/activate')
                if fail_update:
                    self.assertTrue(writes[-1]['nodes'][0]['old_marker'])
                    self.assertNotIn('unacceptedInternalSetting',writes[-1]['settings'])
                self.assertEqual(len(list(Path(directory).glob('workflow-*.json'))),1)

    def test_rejects_an_unrelated_target_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            source={'nodes':[{'name':'Research language model','type':'@n8n/n8n-nodes-langchain.lmChatDeepSeek','parameters':{}}]}
            def api(request,timeout):
                self.assertEqual(request.method,'GET')
                return io.BytesIO(json.dumps(source if request.full_url.endswith('/source') else {'name':'Another application'}).encode())
            with patch.object(sys,'argv',['deploy.py','--model-workflow','source','--target','unrelated','--backup-dir',directory]),patch.dict(os.environ,{'N8N_API_KEY':'test'}),patch.object(deploy,'urlopen',side_effect=api),contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):deploy.main()

    def test_reuses_deepseek_anthropic_binding_and_installs_personal_key_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            old=build();old.update(id='target',active=True)
            source_model={'name':'Research language model',
                'type':'@n8n/n8n-nodes-langchain.lmChatAnthropic','typeVersion':1.3,
                'parameters':{'model':{'__rl':True,'value':'deepseek-v4-flash','mode':'id'},
                              'options':{'maxTokensToSample':8192}},
                'credentials':{'anthropicApi':{'id':'existing-reference','name':'DeepSeek compatible'}}}
            writes=[]
            def api(request,timeout):
                path=request.full_url.split('/api/v1')[1]
                body=json.loads(request.data) if request.data else None
                if request.method=='GET':
                    return io.BytesIO(json.dumps({'nodes':[source_model]} if path.endswith('/source') else old).encode())
                if path=='/credentials':return io.BytesIO(b'{"id":"relay"}')
                if request.method=='PUT':writes.append(body)
                return io.BytesIO(b'{"id":"target","name":"EnzyMind workspace","active":true}')
            args=['deploy.py','--model-workflow','source','--model-node','Research language model',
                  '--target','target','--backup-dir',directory]
            with patch.object(sys,'argv',args),patch.dict(os.environ,{'N8N_API_KEY':'test'}),patch.object(deploy,'urlopen',side_effect=api),contextlib.redirect_stdout(io.StringIO()):
                deploy.main()
            model=next(n for n in writes[0]['nodes'] if n['name']=='Research language model')
            for field in ('type','typeVersion','parameters','credentials'):
                self.assertEqual(model[field],source_model[field])
            self.assertIn('Select billing model',writes[0]['connections'])
            relay=next(n for n in writes[0]['nodes'] if n['name']=='User DeepSeek relay')
            self.assertEqual(relay['credentials']['openAiApi']['id'],'relay')
