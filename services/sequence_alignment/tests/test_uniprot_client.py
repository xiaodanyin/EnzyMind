"""Fault injection for the download stage; no public network used by unit tests."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import ssl
import sys
import threading
from unittest.mock import Mock

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models import uniprot_client as module
from models.uniprot_client import UniProtClient, UniProtDownloadError, TLS12Adapter


def fasta(accession='P00698', sequence='ACDEFGHIKLMNPQRSTVWY'):
    return f'>sp|{accession}|TEST Test protein\n{sequence}\n'.encode()


class Response:
    def __init__(self, status=200, body=None, headers=None, broken=False):
        self.status_code = status
        self.body = fasta() if body is None else body
        self.headers = headers or {}
        self.broken, self.closed = broken, False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def iter_content(self, chunk_size):
        if self.broken:
            yield self.body[:10]
            raise requests.exceptions.ChunkedEncodingError('connection closed during body')
        yield self.body


@pytest.fixture
def transport(monkeypatch):
    client = UniProtClient()
    responses, calls, modes, sleeps = deque(), [], [], []

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url, **kwargs):
            calls.append((url, kwargs))
            assert kwargs.get('verify', True) is not False
            assert kwargs['allow_redirects'] is False
            answer = responses.popleft()
            if isinstance(answer, Exception):
                raise answer
            return answer

    def factory(mode):
        modes.append(mode)
        return Session()

    monkeypatch.setattr(client, '_session', factory)
    monkeypatch.setattr(module.time, 'sleep', sleeps.append)
    return client, responses, calls, modes, sleeps


def test_eof_then_connection_failure_recovers_with_bounded_tls_fallback(transport):
    client, responses, calls, modes, sleeps = transport
    responses.extend([requests.exceptions.SSLError('UNEXPECTED_EOF_WHILE_READING'), requests.ConnectionError('reset'), Response()])
    value = client.fetch('p00698')
    assert value.sequence == 'ACDEFGHIKLMNPQRSTVWY'
    assert not value.cache_hit
    assert modes == ['P256', 'TLS1.2', 'P256']
    assert sleeps == [1, 2]
    assert all(url == 'https://rest.uniprot.org/uniprotkb/P00698.fasta' for url, _ in calls)


def test_503_and_429_retry_after_are_respected(transport):
    client, responses, calls, modes, sleeps = transport
    responses.extend([Response(503), Response(429, headers={'Retry-After': '5'}), Response()])
    assert client.fetch('P00698').sequence
    assert sleeps == [1, 5]


def test_long_retry_after_does_not_block_or_retry_before_allowed(transport):
    client, responses, calls, modes, sleeps = transport
    responses.append(Response(429, headers={'Retry-After': '3600'}))
    with pytest.raises(UniProtDownloadError, match='analysis has not been submitted'):
        client.fetch('P00698')
    assert len(calls) == 1
    assert not sleeps


def test_outage_stops_after_four_attempts_with_actionable_error(transport):
    client, responses, calls, modes, sleeps = transport
    responses.extend(requests.ConnectTimeout('raw transport detail') for _ in range(4))
    with pytest.raises(UniProtDownloadError) as caught:
        client.fetch('P00698')
    assert len(calls) == 4 and sleeps == [1, 2, 4]
    assert caught.value.retryable
    assert 'upload a FASTA' in str(caught.value)
    assert 'raw transport detail' not in str(caught.value)


@pytest.mark.parametrize('status', [400, 401, 403, 404, 410])
def test_permanent_http_errors_are_not_retried_or_cached(transport, status):
    client, responses, calls, modes, sleeps = transport
    responses.extend([Response(status), Response()])
    with pytest.raises(UniProtDownloadError) as caught:
        client.fetch('P00698')
    assert not caught.value.retryable
    assert caught.value.code == ('uniprot_not_found' if status in (404, 410) else 'uniprot_http_error')
    assert len(calls) == 1 and not sleeps
    assert not client.fetch('P00698').cache_hit


def test_certificate_failures_never_fall_back_or_disable_verification(transport):
    client, responses, calls, modes, sleeps = transport
    responses.append(requests.exceptions.SSLError('[SSL: CERTIFICATE_VERIFY_FAILED] invalid certificate'))
    with pytest.raises(UniProtDownloadError) as caught:
        client.fetch('P00698')
    assert caught.value.code == 'uniprot_certificate_error'
    assert not caught.value.retryable
    assert len(calls) == 1 and not sleeps


@pytest.mark.parametrize('body', [b'', b'<html>Service unavailable</html>', fasta(sequence=''), fasta(sequence='AC12DE'), fasta(sequence='ACD*'), fasta('P00761'), fasta()+fasta()])
def test_bad_fasta_is_rejected_without_sequence_cleaning(body):
    with pytest.raises(UniProtDownloadError):
        module.parse_fasta(body.decode(), 'P00698')


def test_partial_body_and_invalid_200_response_retry_before_caching(transport):
    client, responses, calls, modes, sleeps = transport
    broken = Response(broken=True)
    responses.extend([broken, Response(body=b'<html>temporary error</html>'), Response()])
    value = client.fetch('P00698')
    assert broken.closed
    assert len(calls) == 3
    assert client.fetch('P00698').cache_hit
    assert client.fetch('P00698').sequence == value.sequence
    assert len(calls) == 3


def test_invalid_response_exhaustion_has_distinct_error_code(transport):
    client, responses, *_ = transport
    responses.extend(Response(body=b'<html>bad response</html>') for _ in range(4))
    with pytest.raises(UniProtDownloadError) as caught:
        client.fetch('P00698')
    assert caught.value.code == 'uniprot_invalid_response'


def test_response_size_limit_closes_connection(transport):
    client, responses, calls, modes, sleeps = transport
    client.RESPONSE_BYTES = 20
    response = Response()
    responses.append(response)
    with pytest.raises(UniProtDownloadError) as caught:
        client.fetch('P00698')
    assert caught.value.code == 'uniprot_response_too_large'
    assert response.closed and len(calls) == 1


def test_isoforms_and_ambiguous_residues_are_preserved(transport):
    client, responses, *_ = transport
    responses.append(Response(body=fasta('P05067-2', 'MAUXBZJO')))
    value = client.fetch('p05067-2')
    assert value.accession == 'P05067-2' and value.sequence == 'MAUXBZJO'


def test_secondary_accession_redirect_records_primary_provenance(transport):
    client, responses, calls, *_ = transport
    responses.extend([Response(303, headers={'Location': '/uniprotkb/P00698.fasta'}), Response()])
    value = client.fetch('P00761')
    assert value.accession == 'P00698'
    assert value.source_url.endswith('/P00698.fasta')
    assert calls[0][0].endswith('/P00761.fasta') and calls[1][0].endswith('/P00698.fasta')


@pytest.mark.parametrize('location', ['http://rest.uniprot.org/uniprotkb/P00761.fasta', 'https://example.org/P00761.fasta', '/uniprotkb/P00698.fasta', '/uniprotkb/P00761.fasta?token=not-allowed'])
def test_unsafe_or_looping_redirects_are_not_followed(transport, location):
    client, responses, calls, *_ = transport
    responses.append(Response(302, headers={'Location': location}))
    with pytest.raises(UniProtDownloadError):
        client.fetch('P00698')
    assert len(calls) == 1


def test_cache_expires_and_never_serves_stale_sequence_during_outage(transport, monkeypatch):
    client, responses, calls, *_ = transport
    now = [100.]
    monkeypatch.setattr(module.time, 'monotonic', lambda: now[0])
    responses.append(Response())
    first = client.fetch('P00698')
    assert client.fetch('P00698').retrieved_at == first.retrieved_at
    now[0] += client.CACHE_TTL + 1
    responses.extend(requests.ConnectTimeout() for _ in range(4))
    with pytest.raises(UniProtDownloadError):
        client.fetch('P00698')
    assert len(calls) == 5


def test_cache_enforces_entry_and_byte_limits(transport):
    client, responses, calls, *_ = transport
    client.CACHE_ENTRIES, client.CACHE_BYTES = 2, 8
    for accession in ('P00698', 'P00761', 'P05067'):
        responses.append(Response(body=fasta(accession, 'ACDE')))
        client.fetch(accession)
    assert client.fetch('P00761').cache_hit
    responses.append(Response(body=fasta('P00698', 'ACDEF')))
    assert not client.fetch('P00698').cache_hit
    assert client._cache_bytes <= 8 and len(client._cache) <= 2
    assert len(calls) == 4


def test_concurrent_identical_accessions_share_one_successful_download(monkeypatch):
    client = UniProtClient()
    entered, release = threading.Event(), threading.Event()
    def download(accession, deadline):
        entered.set()
        assert release.wait(5)
        return module.UniProtSequence(accession, 'ACDE', f'{module.BASE_URL}{accession}.fasta', 123.)
    get = Mock(side_effect=download)
    monkeypatch.setattr(client, '_download', get)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(client.fetch, 'P00698')
        assert entered.wait(5)
        second = pool.submit(client.fetch, 'P00698')
        release.set()
        a, b = first.result(), second.result()
    assert get.call_count == 1
    assert a.sequence == b.sequence and a.retrieved_at == b.retrieved_at
    assert a.cache_hit is False and b.cache_hit is True


def test_read_budget_stops_further_attempts(transport, monkeypatch):
    client, responses, calls, modes, sleeps = transport
    now = [0.]
    monkeypatch.setattr(module.time, 'monotonic', lambda: now[0])
    class SlowResponse(Response):
        def iter_content(self, chunk_size):
            now[0] = client.BUDGET_SECONDS + 1
            yield fasta()
    responses.append(SlowResponse())
    with pytest.raises(UniProtDownloadError):
        client.fetch('P00698')
    assert len(calls) == 1 and not sleeps


def test_tls_adapter_is_scoped_to_uniprot_and_verifies_certificates():
    with UniProtClient()._session('TLS1.2') as session:
        adapter = session.get_adapter('https://rest.uniprot.org/uniprotkb/P00698.fasta')
        assert isinstance(adapter, TLS12Adapter)
        context = adapter.tls_context
        assert context.minimum_version == context.maximum_version == ssl.TLSVersion.TLSv1_2
        assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
        assert session.verify is True
        assert not isinstance(session.get_adapter('https://blast.ncbi.nlm.nih.gov/Blast.cgi'), TLS12Adapter)
        proxy = adapter.proxy_manager_for('http://127.0.0.1:12345')
        assert proxy.connection_pool_kw['ssl_context'] is context


def test_retry_after_dates_and_invalid_headers():
    from datetime import datetime, timedelta, timezone
    from email.utils import format_datetime
    assert module.retry_after('3') == 3
    assert module.retry_after('-3') == 0
    assert module.retry_after('invalid') == 0
    assert module.retry_after(None) == 0
    future = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=30))
    assert 28 <= module.retry_after(future) <= 30


def test_download_failure_stops_before_ncbi_and_preserves_api_contract(transport, monkeypatch):
    from fastapi.testclient import TestClient
    from main import app, searcher
    from models import blast_searcher
    client, responses, *_ = transport
    responses.append(Response(404))
    monkeypatch.setattr(blast_searcher, 'uniprot_client', client)
    search = Mock()
    monkeypatch.setattr(searcher, 'search', search)
    with TestClient(app) as api:
        response = api.post('/api/query/blast', json={'query':'P00698'})
    data = response.json()
    assert response.status_code == 200 and data['success'] is False
    assert data['error_code'] == 'uniprot_not_found'
    assert data['error_stage'] == 'sequence_download' and data['retryable'] is False
    assert 'FASTA' in data['error']
    search.assert_not_called()


def test_api_recovers_and_returns_exact_sequence_provenance(transport, monkeypatch):
    import hashlib
    from fastapi.testclient import TestClient
    from main import app, searcher
    from models import blast_searcher
    client, responses, calls, *_ = transport
    responses.extend([requests.exceptions.SSLError('UNEXPECTED_EOF_WHILE_READING'), Response()])
    monkeypatch.setattr(blast_searcher, 'uniprot_client', client)
    search = Mock(return_value={'success':True,'query_length':20,'num_results':0,'alignments':[]})
    monkeypatch.setattr(searcher, 'search', search)
    with TestClient(app) as api:
        first = api.post('/api/query/blast', json={'query':'p00698','max_results':2}).json()
        second = api.post('/api/query/blast', json={'query':'P00698','max_results':2}).json()
    assert first['success'] and second['success']
    assert first['sequence'] == second['sequence'] == 'ACDEFGHIKLMNPQRSTVWY'
    assert first['sequence_source']['cache_hit'] is False and second['sequence_source']['cache_hit'] is True
    assert first['sequence_source']['sha256'] == hashlib.sha256(first['sequence'].encode()).hexdigest()
    assert first['sequence_source']['retrieved_at'] == second['sequence_source']['retrieved_at']
    assert len(calls) == 2
    assert all(call.args == (first['sequence'],2) for call in search.call_args_list)


@pytest.mark.parametrize('path,kind', [('/api/query/blast/form','form'),('/query/blast','form'),('/query/blast','json'),('/api/query/blast/html','json'),('/api/query/blast/markdown','json')])
def test_legacy_and_alternative_endpoints_use_hardened_download(transport, monkeypatch, path, kind):
    from fastapi.testclient import TestClient
    from main import app, searcher
    from models import blast_searcher
    client, responses, calls, *_ = transport
    responses.extend([requests.ConnectionError('interrupted'),Response()])
    monkeypatch.setattr(blast_searcher, 'uniprot_client', client)
    search = Mock(return_value={'success':True,'query_length':20,'num_results':0,'alignments':[]})
    monkeypatch.setattr(searcher, 'search', search)
    with TestClient(app) as api:
        response = api.post(path, **{('data' if kind=='form' else 'json'):{'query':'P00698','max_results':1}})
    assert response.status_code == 200
    assert len(calls) == 2
    search.assert_called_once_with('ACDEFGHIKLMNPQRSTVWY',1)


def test_raw_sequence_and_uploaded_fasta_never_require_uniprot(monkeypatch):
    from fastapi.testclient import TestClient
    from main import app, searcher
    from models import blast_searcher
    download = Mock(side_effect=AssertionError('UniProt must not be called'))
    monkeypatch.setattr(blast_searcher.uniprot_client,'fetch',download)
    monkeypatch.setattr(searcher,'search',Mock(return_value={'success':True,'query_length':4,'num_results':0,'alignments':[]}))
    assert blast_searcher.classify_input_v2('ac de') == 'ACDE'
    with TestClient(app) as api:
        assert api.post('/api/query/blast',json={'query':'ACDE'}).json()['success']
        assert api.post('/api/query/blast/file',files={'file':('protein.fasta',b'>test\nACDE\n','text/plain')}).json()['success']
    download.assert_not_called()


def test_tls12_adapter_negotiates_tls12_but_rejects_untrusted_certificate(tmp_path):
    """Real local TLS handshake: the adapter must not silently turn off checks."""
    import subprocess
    from http.server import BaseHTTPRequestHandler, HTTPServer
    certificate, key = tmp_path/'test.crt', tmp_path/'test.key'
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1',
                    '-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost',
                    '-keyout',str(key),'-out',str(certificate)],check=True,capture_output=True)
    negotiated=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            negotiated.append(self.connection.version())
            self.send_response(200)
            self.end_headers()
            self.wfile.write(fasta())
        def log_message(self,*args):
            pass
    server=HTTPServer(('127.0.0.1',0),Handler)
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certificate,key)
    server.socket=context.wrap_socket(server.socket,server_side=True)
    thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.05},daemon=True)
    thread.start()
    url=f'https://localhost:{server.server_port}/'
    try:
        with requests.Session() as session:
            session.trust_env=False
            session.mount('https://',TLS12Adapter())
            with pytest.raises(requests.exceptions.SSLError,match='CERTIFICATE_VERIFY_FAILED'):
                session.get(url,timeout=2)
            response=session.get(url,verify=str(certificate),timeout=2)
            assert response.content==fasta()
            assert negotiated==['TLSv1.2']
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
