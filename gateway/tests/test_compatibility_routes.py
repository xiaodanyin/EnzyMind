"""Compatibility URLs must use working services and retain saved results."""
import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from gateway import main, workspace
from gateway.workspace_store import WorkspaceStore, digest
from gateway.structure_artifacts import read_generated_pdb

PDB = 'ATOM      1  CA  ALA A   1      10.000  10.000  10.000  1.00 90.00           C\nEND\n'
HEADERS = {'X-Enzymind-Client': 'c' * 64}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, '_store', WorkspaceStore(tmp_path / 'workspace.sqlite'))
    # No lifespan/background cleanup is needed for these isolated route tests.
    return TestClient(main.app)


@pytest.mark.parametrize('url,body,upstream,tool,payload', [
    ('/query/structure', {'query': 'ACDEFGHIK', 'input_type': 'sequence'}, '/api/predict/structure', 'structure', {'success': True, 'structure_data': PDB}),
    ('/recommend/enzyme', {'query': 'CCO>>CC=O'}, '/api/query/enzyme-type', 'enzyme-type', {'success': True, 'recommendations': [{'ec_number': '1.1.1.1', 'confidence': .9}]}),
    ('/recommend/enzyme', {'query': 'CCO>>CC=O', 'k': 3}, '/api/query/enzyme-type/top-k', 'enzyme-type', {'success': True, 'recommendations': [{'ec_number': '1.1.1.1', 'confidence': .9}]}),
    ('/query/ec-info', {'query': '3.2.1.17'}, '/api/query/ec-info', 'reaction', {'success': True, 'ec_number': '3.2.1.17', 'name': 'lysozyme'}),
])
def test_legacy_routes_return_real_payload_and_save_inputs(client, url, body, upstream, tool, payload):
    requests = []
    def handler(request):
        requests.append(request)
        assert request.url.path == upstream
        assert json.loads(request.content) == body
        assert 'x-enzymind-client' not in request.headers
        return httpx.Response(200, json=payload)
    real_client = httpx.AsyncClient
    with patch.object(main.httpx, 'AsyncClient', side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs)):
        response = client.post('/api' + url, json=body, headers=HEADERS)
    assert response.status_code == 200
    assert len(requests) == 1
    result = response.json()
    assert {k: v for k, v in result.items() if k != 'workspace_result'} == payload
    saved = workspace.store().result(digest('c' * 64), result['workspace_result']['id'])
    assert saved['tool'] == tool and saved['inputs'] == body
    assert saved['status'] == 'completed' and saved['payload'] == payload


def test_invalid_recommendation_json(client):
    response = client.post('/api/recommend/enzyme', content='{', headers={'Content-Type': 'application/json'})
    assert response.status_code == 422


@pytest.mark.parametrize('kind', ['structure', 'sequence'])
def test_reference_model_get_does_not_create_an_analysis_record(client, kind):
    real_client = httpx.AsyncClient
    def handler(request):
        assert request.method == 'GET'
        assert request.url.path == f'/api/query/enzyme-full-info/P00176/{kind}'
        return httpx.Response(200, json={'success':True, 'structure_data':PDB})
    with patch.object(main.httpx, 'AsyncClient', side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs)), \
            patch.object(workspace.store(), 'save_result', side_effect=AssertionError('A reference GET is not an analysis run')):
        response = client.get(f'/api/query/enzyme-full-info/p00176/{kind}', headers=HEADERS)
    assert response.status_code == 200 and 'workspace_result' not in response.json()
    assert client.get(f'/api/query/enzyme-full-info/INVALID/{kind}').status_code == 422


def test_alias_does_not_hide_upstream_failures(client):
    real_client = httpx.AsyncClient
    with patch.object(main.httpx, 'AsyncClient', side_effect=lambda **kwargs: real_client(
            transport=httpx.MockTransport(lambda _: httpx.Response(503, json={'detail': 'Model unavailable'})), **kwargs)):
        response = client.post('/api/recommend/enzyme', json={'query': 'CCO>>CC=O'}, headers=HEADERS)
    assert response.status_code == 503
    assert response.json()['error'] == 'Model unavailable'
    assert response.json()['workspace_result']['status'] == 'failed'


@pytest.fixture
def pdb_roots(tmp_path, monkeypatch):
    output, static = tmp_path / 'output', tmp_path / 'static'
    output.mkdir()
    static.mkdir()
    monkeypatch.setenv('ESMFOLD_OUTPUT_DIR', str(output))
    monkeypatch.setenv('STATIC_PDB_DIR', str(static))
    return output, static


@pytest.mark.parametrize('layout', ['static', 'flat', 'job'])
def test_pdb_download_and_result_snapshot_share_configured_roots(client, pdb_roots, layout):
    output, static = pdb_roots
    directory = static if layout == 'static' else output if layout == 'flat' else output / 'compat_job'
    directory.mkdir(exist_ok=True)
    (directory / 'compat_job.pdb').write_text(PDB)
    response = client.get('/api/pdb/compat_job.pdb')
    assert response.status_code == 200 and response.text == PDB
    assert response.headers['content-type'].startswith('chemical/x-pdb')
    assert response.headers['cache-control'] == 'private, no-store'
    assert asyncio.run(workspace.preserve_structure({'static_path': '/static/pdb/compat_job.pdb'}))['structure_data'] == PDB


def test_pdb_rejects_escaping_files_directories_and_large_files(client, pdb_roots, tmp_path):
    output, static = pdb_roots
    outside = tmp_path / 'secret.pdb'
    outside.write_text(PDB)
    (static / 'compat_escape.pdb').symlink_to(outside)
    (output / 'compat_job').symlink_to(tmp_path, target_is_directory=True)
    (tmp_path / 'compat_job.pdb').write_text(PDB)
    (static / 'compat_directory.pdb').mkdir()
    (static / 'compat_binary.pdb').write_bytes(b'\xff')
    with (static / 'compat_large.pdb').open('wb') as stream:
        stream.truncate(20_000_001)
    for filename in ('compat_escape.pdb', 'compat_job.pdb', 'compat_directory.pdb', 'compat_binary.pdb', 'compat_large.pdb', 'missing_5a2efbf8.pdb'):
        assert client.get('/api/pdb/' + filename).status_code == 404
        assert read_generated_pdb(filename) is None
    for filename in ('..%2Fsecret.pdb', '%2Ftmp%2Fsecret.pdb', 'secret%5Cfile.pdb', 'secret.txt', 'bad%22.pdb'):
        assert client.get('/api/pdb/' + filename).status_code == 400
    # Starlette rejects a newline-containing path before the route is called.
    assert client.get('/api/pdb/bad%0A.pdb').status_code in (400, 404)
    assert read_generated_pdb('bad\n.pdb') is None
