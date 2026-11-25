import json
import unittest
from unittest.mock import patch
from uuid import uuid4
import httpx
from gateway import workspace
import test_workspace


class PredictionReuseTests(unittest.TestCase):
    setUp = test_workspace.APITests.setUp
    tearDown = test_workspace.APITests.tearDown

    def prepare_turn(self):
        session=workspace.store().create_session(self.key)
        turn,token=workspace.store().begin(self.key,session['id'],str(uuid4()),'Compare candidates',[])
        workspace.store().status(self.key,turn['id'],'running')
        return turn,{'X-Enzymind-Turn':token}

    def test_same_input_reuses_result_but_different_substrates_can_run(self):
        turn,headers=self.prepare_turn();calls=[];real_client=httpx.AsyncClient
        def handler(request):
            calls.append(json.loads(request.content))
            return httpx.Response(200,json={'kcat':10,'unit':'s^-1'})
        with patch.object(workspace.httpx,'AsyncClient',side_effect=lambda **kw:real_client(transport=httpx.MockTransport(handler),**kw)):
            a=self.client.post('/api/workspace/tools/kcat',headers=headers,json={'enzyme_query':'P00330','smiles':'CCO'}).json()
            b=self.client.post('/api/workspace/tools/kcat',headers=headers,json={'enzyme_query':'P00330','smiles':'CCO','timeout':999}).json()
            c=self.client.post('/api/workspace/tools/kcat',headers=headers,json={'enzyme_query':'P00330','smiles':'CCCO'}).json()
        self.assertEqual(len(calls),2)
        self.assertEqual(a['id'],b['id']);self.assertTrue(b['reused'])
        self.assertNotEqual(a['id'],c['id'])

    def test_failure_blocks_more_predictions_in_this_turn(self):
        turn,headers=self.prepare_turn();calls=[];real_client=httpx.AsyncClient
        def handler(request):
            calls.append(1);return httpx.Response(200,json={'success':False,'error':'Simulated upstream timeout'})
        with patch.object(workspace.httpx,'AsyncClient',side_effect=lambda **kw:real_client(transport=httpx.MockTransport(handler),**kw)):
            a=self.client.post('/api/workspace/tools/active-sites',headers=headers,json={'uniprot_id':'P00698'}).json()
            b=self.client.post('/api/workspace/tools/active-sites',headers=headers,json={'uniprot_id':'P00698','use_celery':False}).json()
            c=self.client.post('/api/workspace/tools/active-sites',headers=headers,json={'aa_sequence':'ACDEFG'}).json()
            _,other_headers=self.prepare_turn()
            self.client.post('/api/workspace/tools/active-sites',headers=other_headers,json={'uniprot_id':'P00698'})
        self.assertEqual(len(calls),2)  # Only the original attempt and the new turn.
        self.assertEqual(a['id'],b['id']);self.assertEqual(a['id'],c['id'])
        self.assertEqual(c['reuse_reason'],'predictor_failed')

    def test_duplicate_inflight_call_does_not_start_another_job(self):
        turn,headers=self.prepare_turn();inputs={'enzyme_query':'P00330','smiles':'CCO'}
        workspace.store().event(turn['id'],'tool_start',{'tool':'kcat','fingerprint':workspace.prediction_fingerprint('kcat',inputs)})
        with patch.object(workspace.httpx,'AsyncClient',side_effect=AssertionError('Duplicate computation was started')):
            response=self.client.post('/api/workspace/tools/kcat',headers=headers,json=inputs)
        self.assertEqual(response.json()['status'],'pending')
        self.assertEqual(response.json()['reuse_reason'],'already_running')
