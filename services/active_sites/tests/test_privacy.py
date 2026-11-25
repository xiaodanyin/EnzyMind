"""Exercise Enzymind's public proxy boundary as well as EasIFA request identity."""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import secrets
import threading

import httpx
import pytest
import requests
from fastapi.testclient import TestClient

import main
from client import ActiveSitesClient
from models.active_sites_predictor import ActiveSitesPredictor
from models.easifa_access import load_owner_key, request_owner, SESSION_COOKIE


def response(status, data):
    result = requests.Response()
    result.status_code = status
    result.headers['Content-Type'] = 'application/json'
    result._content = json.dumps(data).encode()
    return result


@pytest.fixture
def upstream(monkeypatch):
    owners = {'legacy-job': None}
    calls = []
    def request(url, **kwargs):
        calls.append((url, kwargs))
        assert kwargs['allow_redirects'] is False
        owner = kwargs['headers']['X-Easifa-Session']
        if '/from_' in url:
            job = 'job-' + secrets.token_hex(8)
            owners[job] = owner
            return response(200, {'job_id': job, 'task_manager': 'celery'})
        job = url.rsplit('/', 1)[-1]
        if job not in owners or (owners[job] is not None and owners[job] != owner):
            return response(404, {'detail': 'Job not found'})
        return response(200, {'job_id': job, 'status': 'completed',
                              'active_data': [[1, 'MET', '#ff0000', 'Active Site', .95]]})
    monkeypatch.setattr(requests, 'post', request)
    monkeypatch.setattr(requests, 'get', request)
    return owners, calls


def submit(client, kind='uniprot'):
    if kind == 'uniprot':
        result = client.post('/api/predict/active-sites/submit/uniprot', json={'uniprot_id': 'F6KCZ5'})
    elif kind == 'sequence':
        result = client.post('/api/predict/active-sites/submit/sequence', json={'aa_sequence': 'ACDEFGHIKLMNPQRSTVWY'})
    elif kind == 'form':
        result = client.post('/api/predict/active-sites/submit/sequence/form', data={'aa_sequence': 'ACDEFGHIKLMNPQRSTVWY'})
    else:
        result = client.post('/api/predict/active-sites/submit/structure', files={'pdb_file': ('example.pdb', b'ATOM\n')})
    assert result.status_code == 200
    assert result.json()['success'] is True
    return result.json()['job_id']


def test_cookie_isolation_legacy_and_recovery(upstream, monkeypatch):
    # Even an operator's configured CLI key must never turn this proxy into a shared owner.
    service_key = secrets.token_urlsafe(32)
    monkeypatch.setenv('ENZYMIND_EASIFA_SESSION_KEY', service_key)
    with TestClient(main.app) as owner, TestClient(main.app) as other:
        job = submit(owner)
        key = owner.cookies[SESSION_COOKIE]
        assert key != service_key
        assert upstream[0][job] == key
        assert owner.get('/api/predict/active-sites/job/'+job).json()['success']
        assert owner.get('/api/predict/active-sites/results/'+job).json()['success']
        assert other.get('/api/predict/active-sites/results/'+job).json()['success'] is False
        assert other.get('/api/predict/active-sites/job/'+job).json()['success'] is False
        assert other.get('/api/predict/active-sites/results/legacy-job').json()['success']
        saved = owner.get('/api/predict/active-sites/session')
        assert saved.json()['session_token'] == key
        assert saved.headers['cache-control'] == 'private, no-store'
        owner.cookies.clear()
        assert not owner.get('/api/predict/active-sites/results/'+job).json()['success']
        restored = owner.get('/api/predict/active-sites/results/'+job, headers={'X-Easifa-Session': key})
        assert restored.json()['success']
        assert key not in restored.text and service_key not in restored.text
        assert owner.cookies[SESSION_COOKIE] == key
        assert request_owner.get() is None


@pytest.mark.parametrize('kind', ['uniprot', 'sequence', 'form', 'structure'])
def test_all_submit_types_keep_header_through_poll_and_result(upstream, kind):
    key = secrets.token_urlsafe(32)
    with TestClient(main.app, headers={'X-Easifa-Session': key}) as caller:
        job = submit(caller, kind)
        assert caller.get('/api/predict/active-sites/job/'+job).json()['success']
        result = caller.get('/api/predict/active-sites/results/'+job)
        assert 'Residue Index' in result.json()['markdown']
    assert {kwargs['headers']['X-Easifa-Session'] for _, kwargs in upstream[1]} == {key}
    # The existing JSON/form contract stays private by default; no forced-public escape.
    assert all('visibility' not in kwargs.get('json', {}) and 'visibility' not in kwargs.get('data', {})
               for _, kwargs in upstream[1])


@pytest.mark.parametrize('endpoint,body', [('/api/query/active-sites', {'uniprot_id':'F6KCZ5'}),
    ('/api/predict/active-sites', {'uniprot_id':'F6KCZ5'}),
    ('/api/predict/active-sites', {'aa_sequence':'ACDEFGHIKLMNPQRSTVWY'})])
def test_stateless_sync_agent_call_still_submits_polls_and_formats(upstream, endpoint, body):
    with TestClient(main.app) as caller:
        result = caller.post(endpoint, json=body)
        assert result.status_code == 200
        assert 'Residue Index' in result.json()['result']
        keys = {kwargs['headers']['X-Easifa-Session'] for _, kwargs in upstream[1]}
        assert len(keys) == 1
        assert next(iter(keys)) not in result.text


def test_bad_header_rejected_before_network(upstream):
    with TestClient(main.app) as caller:
        result = caller.get('/api/predict/active-sites/results/legacy-job',headers={'X-Easifa-Session':'bad'})
        assert result.status_code == 400
    assert not upstream[1]


def test_secure_cookie_default_and_http_override(upstream, monkeypatch):
    monkeypatch.delenv('ENZYMIND_EASIFA_COOKIE_SECURE')
    with TestClient(main.app, base_url='https://testserver') as caller:
        result = caller.get('/api/predict/active-sites/session')
        assert '; Secure' in result.headers['set-cookie']
        assert 'HttpOnly' in result.headers['set-cookie']
        assert 'SameSite=lax' in result.headers['set-cookie']


def test_concurrent_http_requests_do_not_share_identity(monkeypatch):
    barrier = threading.Barrier(2)
    def fake_predict(self, uniprot_id, use_celery=True):
        key = request_owner.get()
        barrier.wait(timeout=5)
        assert request_owner.get() == key
        return {'success':True, 'job_id': uniprot_id}
    monkeypatch.setattr(ActiveSitesPredictor, 'submit_uniprot', fake_predict)
    keys = [secrets.token_urlsafe(32), secrets.token_urlsafe(32)]
    def run(key):
        with TestClient(main.app,headers={'X-Easifa-Session':key}) as caller:
            assert submit(caller) == 'F6KCZ5'
            return caller.cookies[SESSION_COOKIE]
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(run,keys)) == keys
    assert request_owner.get() is None


def test_predictor_restarts_fallback_and_original_credential(upstream, monkeypatch, tmp_path):
    file = tmp_path/'recovery.json'
    predictor = ActiveSitesPredictor(session_file=file)
    post = requests.post
    count = 0
    def fail_primary(url, **kwargs):
        nonlocal count
        count += 1
        if count == 1:
            raise requests.ConnectionError('primary unavailable')
        return post(url, **kwargs)
    monkeypatch.setattr(requests, 'post', fail_primary)
    job = predictor.submit_uniprot('F6KCZ5')['job_id']
    assert count == 2
    key = json.loads(file.read_text())['token']
    restarted = ActiveSitesPredictor(session_file=file)
    assert restarted.wait_for_completion(job)['success']
    assert set(upstream[0].values()) == {None, key}
    assert file.stat().st_mode & 0o777 == 0o600
    foreign = ActiveSitesPredictor(session_key=secrets.token_urlsafe(32))
    assert not foreign.get_job_results(job)['success']


def test_python_client_saves_identity_and_keeps_original_request_calls(monkeypatch, tmp_path):
    observed = []
    def capture(url, **kwargs):
        observed.append(kwargs)
        return response(200, {'success':True, 'job_id':'job-1'})
    monkeypatch.setattr(requests, 'post', capture)
    monkeypatch.setattr(requests, 'get', capture)
    file = tmp_path/'client.json'
    ActiveSitesClient(session_file=file).submit_uniprot('F6KCZ5')
    ActiveSitesClient(session_file=file).get_job_results('job-1')
    assert len({call['headers']['X-Easifa-Session'] for call in observed}) == 1
    assert all(call['allow_redirects'] is False for call in observed)


def test_identity_concurrent_creation_and_no_silent_rotation(tmp_path):
    file = tmp_path/'saved.json'
    def load(_):
        return load_owner_key(('https://easifa.example/api',), session_file=file)
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert len(set(pool.map(load,range(16)))) == 1
    file.write_text('corrupted; preserve original')
    with pytest.raises(RuntimeError, match='Preserve'):
        load(0)
    assert file.read_text() == 'corrupted; preserve original'


def test_explicit_key_precedence_and_invalid_key_never_echoed(tmp_path):
    file = tmp_path/'bad.json';file.write_text('keep')
    key = secrets.token_urlsafe(32)
    assert load_owner_key(('test',),session_key=key,session_file=file)==key
    with pytest.raises(ValueError) as error:
        load_owner_key(('test',),session_key='invalid-private-value',session_file=file)
    assert 'invalid-private-value' not in str(error.value)
    assert file.read_text()=='keep'


@pytest.fixture
def gateway(monkeypatch):
    path = Path(__file__).resolve().parents[3]/'gateway'/'main.py'
    spec = importlib.util.spec_from_file_location('enzymind_gateway_privacy_test', path)
    gateway = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gateway)
    original = httpx.AsyncClient
    def client(*args, **kwargs):
        return original(*args, transport=httpx.ASGITransport(app=main.app), trust_env=False, **kwargs)
    monkeypatch.setattr(gateway.httpx, 'AsyncClient', client)
    return gateway.app


@pytest.mark.parametrize('kind', ['uniprot','sequence','form','structure'])
def test_gateway_keeps_http_method_upload_headers_and_response_cookie(upstream, gateway, kind):
    with TestClient(gateway) as owner, TestClient(gateway) as stranger:
        job = submit(owner, kind)
        assert SESSION_COOKIE in owner.cookies
        assert owner.get('/api/predict/active-sites/job/'+job).json()['success']
        result = owner.get('/api/predict/active-sites/results/'+job)
        assert result.status_code==200 and 'MET' in result.json()['markdown']
        assert result.headers['cache-control']=='private, no-store'
        assert not stranger.get('/api/predict/active-sites/results/'+job).json()['success']
        key = owner.get('/api/predict/active-sites/session').json()['session_token']
        assert key == upstream[0][job]
        recovered = stranger.get('/api/predict/active-sites/results/'+job,headers={'X-Easifa-Session':key})
        assert recovered.json()['success']


def test_gateway_json_and_multipart_forward_explicit_identity(upstream, gateway):
    key=secrets.token_urlsafe(32)
    with TestClient(gateway, headers={'X-Easifa-Session':key}) as caller:
        for kind in ('uniprot','structure'):
            job=submit(caller,kind)
            assert upstream[0][job]==key
            assert caller.get('/api/predict/active-sites/results/'+job).json()['success']


def test_gateway_cross_origin_cannot_read_cookie_identity(upstream, gateway):
    with TestClient(gateway) as caller:
        job = submit(caller)
        key = caller.cookies[SESSION_COOKIE]
        foreign = {'Origin':'https://another-origin.example','Sec-Fetch-Site':'same-site'}
        for path in ('session','results/'+job):
            denied = caller.get('/api/predict/active-sites/'+path,headers=foreign)
            assert denied.status_code == 403
            assert key not in denied.text
        # A same-origin frontend proxy continues to use its HttpOnly cookie.
        same_origin = {**foreign,'Sec-Fetch-Site':'same-origin'}
        assert caller.get('/api/predict/active-sites/results/'+job,headers=same_origin).json()['success']
        # Explicit credentials still permit intentional cross-origin API use.
        explicit = {**foreign,'X-Easifa-Session':key}
        assert caller.get('/api/predict/active-sites/results/'+job,headers=explicit).json()['success']
