"""The shared JSON transport has the same bounded, verified behavior as FASTA."""
from collections import deque
import json
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from shared import uniprot as module
from shared.uniprot import UniProtJSONClient, UniProtDownloadError
from .test_uniprot_client import Response


def response(accession='P00698', **fields):
    return Response(body=json.dumps({'primaryAccession': accession, 'comments': [], 'features': [], **fields}).encode())


@pytest.fixture
def transport(monkeypatch):
    client, replies, sleeps, modes = UniProtJSONClient(), deque(), [], []
    session = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    def get(url, **kwargs):
        assert url.startswith('https://rest.uniprot.org/uniprotkb/') and url.endswith('.json')
        assert kwargs.get('verify', True) is True and kwargs['allow_redirects'] is False
        reply = replies.popleft()
        if isinstance(reply, Exception): raise reply
        return reply
    session.get.side_effect = get
    def factory(mode):
        modes.append(mode)
        return session
    monkeypatch.setattr(client, '_session', factory)
    monkeypatch.setattr(module.time, 'sleep', sleeps.append)
    return client, replies, session.get, sleeps, modes


def test_json_eof_and_partial_response_recover_then_cache_without_shared_mutation(transport):
    client, replies, get, sleeps, modes = transport
    replies.extend([requests.exceptions.SSLError('UNEXPECTED_EOF_WHILE_READING'), Response(broken=True), response(sequence={'value': 'ACDE'})])
    data = client.fetch_json('p00698')
    data['sequence']['value'] = 'CHANGED'
    assert client.fetch_json('P00698')['sequence']['value'] == 'ACDE'
    assert get.call_count == 3 and sleeps == [1, 2]
    assert modes == ['P256', 'TLS1.2', 'P256']


@pytest.mark.parametrize('body', [b'<html>Outage</html>', b'{}', b'[]', b'{', b'{"primaryAccession":"P00761"}', b'{"primaryAccession":"P00698","comments":{}}'])
def test_json_invalid_record_is_retried_but_never_cached(transport, body):
    client, replies, get, *_ = transport
    replies.extend([Response(body=body), response()])
    assert client.fetch_json('P00698')['primaryAccession'] == 'P00698'
    assert get.call_count == 2


def test_json_rejects_certificate_errors_without_disabling_verification(transport):
    client, replies, get, sleeps, _ = transport
    replies.append(requests.exceptions.SSLError('CERTIFICATE_VERIFY_FAILED'))
    with pytest.raises(UniProtDownloadError) as exc:
        client.fetch_json('P00698')
    assert exc.value.code == 'uniprot_certificate_error'
    assert get.call_count == 1 and not sleeps


@pytest.mark.parametrize('status', [404, 410])
def test_json_unknown_id_does_not_retry_or_cache(transport, status):
    client, replies, get, sleeps, _ = transport
    replies.extend([Response(status), response()])
    with pytest.raises(UniProtDownloadError) as exc: client.fetch_json('P00698')
    assert exc.value.code == 'uniprot_not_found' and not exc.value.retryable
    assert get.call_count == 1 and not sleeps
    assert client.fetch_json('P00698')['primaryAccession'] == 'P00698'


def test_json_retry_after_and_outage_budget(transport):
    client, replies, get, sleeps, _ = transport
    replies.extend([Response(503), Response(429, headers={'Retry-After': '3'}), response()])
    assert client.fetch_json('P00698')['primaryAccession'] == 'P00698'
    assert sleeps == [1, 3]
    replies.append(Response(429, headers={'Retry-After': '3600'}))
    with pytest.raises(UniProtDownloadError, match='annotations.*bounded retries'):
        client.fetch_json('P00761')
    assert get.call_count == 4


def test_json_redirect_and_secondary_accession_preserve_primary(transport):
    client, replies, get, *_ = transport
    replies.extend([Response(303, headers={'Location': '/uniprotkb/P00761.json'}), response('P00761')])
    assert client.fetch_json('P00698')['primaryAccession'] == 'P00761'
    replies.append(response('P00761', secondaryAccessions=['P12345']))
    assert client.fetch_json('P12345')['primaryAccession'] == 'P00761'


def test_json_size_limits_and_cache_expiry(transport, monkeypatch):
    client, replies, get, *_ = transport
    client.CACHE_ENTRIES = 1
    now = [100.]
    monkeypatch.setattr(module.time, 'monotonic', lambda: now[0])
    replies.extend([response(), response('P00761')])
    client.fetch_json('P00698')
    client.fetch_json('P00761')
    assert list(client._cache) == ['P00761']
    now[0] += client.CACHE_TTL + 1
    replies.append(response('P00761'))
    assert client.fetch('P00761').cache_hit is False
    client.RESPONSE_BYTES = 10
    replies.append(response())
    with pytest.raises(UniProtDownloadError) as exc: client.fetch_json('P00698')
    assert exc.value.code == 'uniprot_response_too_large'
