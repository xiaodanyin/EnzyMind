"""Regression for the real CYP2A6 display-padding error in Agent/Python inputs."""
import copy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from gateway import main, workspace
from gateway.python_sandbox import PythonSandbox, json_bytes, normalize
from gateway.sequence_data import normalize_active_site_payload
from gateway.workspace_store import WorkspaceStore

REFERENCE = json.loads((Path(__file__).parent / 'fixtures/p11509_sequence.json').read_text())


def archived_payload():
    sequence = REFERENCE['sequence']
    rows = [[sequence[i:i+10].ljust(10, '&'), i+10 if i+10 <= len(sequence) else None,
             ['#000000']*10] for i in range(0, len(sequence), 10)]
    return {'data': {'uniprot_id': 'P11509', 'results': [{
        'multi_chain': False, 'enzyme_sequence_info': rows,
        'active_data': [[107, 'PHE', '#ff0000', 'Binding Site', .9995],
                        [297, 'ASN', '#ff0000', 'Binding Site', .9997],
                        [439, 'CYS', '#ff0000', 'Binding Site', .9999]],
        'structure_data': 'ORIGINAL COORDINATES',
        'record_compatibility': {'kind': 'legacy_prediction'},
    }]}}


def test_archived_record_agent_evidence_and_actual_sandbox_input_agree(tmp_path):
    store = WorkspaceStore(tmp_path/'test.sqlite')
    raw = archived_payload()
    assert len(''.join(row[0] for row in raw['data']['results'][0]['enzyme_sequence_info'])) == 500
    saved = store.save_result('owner', 'active-sites', {'uniprot_id':'P11509'}, raw)
    # Reopen storage: old evidence is fixed on read, not only on new tool calls.
    store = WorkspaceStore(store.path)
    record = store.result('owner', saved['id'])
    panel = record['payload']['data']['results'][0]
    assert panel['sequence'] == REFERENCE['sequence'] and panel['sequence_length'] == 494
    assert panel['enzyme_sequence_info'][-1] == ['FLPR', None, ['#000000']*4]
    assert panel['sequence_normalization']['display_padding_removed'] == 6
    assert panel['active_data'] == raw['data']['results'][0]['active_data']
    assert panel['structure_data'] == 'ORIGINAL COORDINATES'
    with store.db() as db:
        original = json.loads(db.execute('SELECT payload FROM results WHERE id=?', (record['id'],)).fetchone()[0])
    assert original == raw  # The archival response is not rewritten.
    evidence = workspace.result_evidence(record)['data']['data']['results'][0]
    assert evidence['sequence_length'] == 494 and evidence['sequence'] == REFERENCE['sequence']
    assert 'enzyme_sequence_info' not in evidence
    assert workspace.read_evidence(record, {'field':'data.results.0.sequence_length'})['data'] == 494
    inputs, _, sources = PythonSandbox(store).inputs('owner', normalize({'code':'pass', 'result_ids':[record['id']]}))
    copied = inputs['results'][record['id']]['data']['results'][0]
    # Replay the exact faulty calculation pattern from the production run.
    reconstructed = ''.join(chunk for chunk, end, colours in copied['enzyme_sequence_info'])
    assert len(reconstructed) == copied['sequence_length'] == 494
    assert reconstructed == copied['sequence'] == REFERENCE['sequence']
    assert [reconstructed[pos-1] for pos in (107,297,439)] == ['F','N','C']
    assert sources[0]['sha256'] == hashlib.sha256(json_bytes(record['payload'])).hexdigest()


def test_normalization_is_idempotent_and_keeps_records_separate():
    raw = archived_payload()
    raw['data']['results'].append({'enzyme_sequence_info': [['MUBZXJO&&&', None, ['#fff']*10]]})
    original = copy.deepcopy(raw)
    result = normalize_active_site_payload(raw)
    assert raw == original
    assert [p['sequence_length'] for p in result['data']['results']] == [494,7]
    assert normalize_active_site_payload(result) == result


@pytest.mark.parametrize('panel', [
    {'enzyme_sequence_info': [['AC&D', 4, []]]},
    {'enzyme_sequence_info': [['AC--D', 5, []]]},
    {'enzyme_sequence_info': [['AC*D', 4, []]]},
    {'enzyme_sequence_info': [['AC&&', 2, []], ['DE', 4, []]]},
    {'enzyme_sequence_info': [['&&&&', None, []]]},
    {'enzyme_sequence_info': [['ACD', 3, []], None]},
    {'multi_chain': True, 'enzyme_sequence_info': [['ACDE', 4, []]]},
    {'sequence':'ACDE', 'enzyme_sequence_info': [['ACDF&&', 4, []]]},
])
def test_ambiguous_sequences_are_flagged_without_guessing_or_renumbering(panel):
    result = normalize_active_site_payload(panel)
    assert result['sequence_normalization']['status'] == 'unavailable'
    assert result.get('sequence') == panel.get('sequence')
    assert result['enzyme_sequence_info'] == panel['enzyme_sequence_info']
    assert 'sequence_length' not in result


@pytest.mark.parametrize('path,method', [('/api/predict/active-sites','POST'),
                                         ('/api/predict/active-sites/results/test-job','GET')])
def test_public_proxy_normalizes_sync_and_async_responses(tmp_path, monkeypatch, path, method):
    monkeypatch.setattr(workspace, '_store', WorkspaceStore(tmp_path/'test.sqlite'))
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=archived_payload()))
    with patch.object(main.httpx, 'AsyncClient', side_effect=lambda **kw: real_client(transport=transport, **kw)):
        client = TestClient(main.app)
        response = client.request(method, path, json={'uniprot_id':'P11509'} if method=='POST' else None)
    assert response.status_code == 200
    panel = response.json()['data']['results'][0]
    assert panel['sequence_length'] == len(panel['sequence']) == 494
