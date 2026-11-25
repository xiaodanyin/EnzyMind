import json
import os
import sqlite3
import time
from unittest.mock import Mock

import pytest
import requests

from shared.uniprot import UniProtJSONClient, UniProtDownloadError
from shared.uniprot_cache import UniProtJSONCache
from shared.tests.test_uniprot_local import snapshot


@pytest.fixture
def cache(tmp_path, monkeypatch):
    path = tmp_path / 'cache' / 'annotations.sqlite'
    monkeypatch.setenv('ENZYMIND_UNIPROT_CACHE_PATH', str(path))
    monkeypatch.setattr('shared.uniprot.time.sleep', lambda _: None)
    return path


def document(accession='P12345'):
    return json.dumps({'primaryAccession': accession, 'sequence': {'value': 'ACDEFGHIK'},
                       'comments': [{'commentType': 'FUNCTION', 'texts': [{'value': 'Recorded function'}]}]})


def put(age=0, text=None):
    UniProtJSONCache().put('P12345', text or document(), time.time() - age)


def offline(monkeypatch, client):
    get = Mock(side_effect=requests.ConnectTimeout('simulated network interruption'))
    monkeypatch.setattr(client, '_get', get)
    return get


def test_success_survives_client_restart_with_timestamp_and_no_network(cache, monkeypatch):
    client = UniProtJSONClient()
    record = client._parse_record(document(), 'P12345', '')
    monkeypatch.setattr(client, '_get', Mock(return_value=(record, 0)))
    assert client.fetch_json('P12345')['comments']
    restarted = UniProtJSONClient()
    get = offline(monkeypatch, restarted)
    result = restarted.fetch_json('P12345')
    assert result['enzymindSource']['method'] == 'uniprot_cache'
    assert result['enzymindSource']['retrieved_at']
    assert result['enzymindSource']['stale'] is False and not get.called
    assert cache.stat().st_mode & 0o777 == 0o600


def test_local_stays_first_but_full_annotations_can_use_complete_cache(cache, snapshot, monkeypatch):
    put()
    client = UniProtJSONClient()
    get = offline(monkeypatch, client)
    assert client.fetch_json('P12345', capability='sequence')['enzymindSource']['method'] == 'local_snapshot'
    assert client.fetch_json('P12345')['enzymindSource']['method'] == 'uniprot_cache'
    assert not get.called


def test_network_outage_uses_dated_stale_data_and_short_cooldown(cache, monkeypatch):
    put(age=7 * 3600)
    client = UniProtJSONClient()
    get = offline(monkeypatch, client)
    result = client.fetch_json('P12345')
    assert result['enzymindSource']['stale'] is True and get.call_count == 4
    assert client.fetch_json('P12345') == result and get.call_count == 4
    with sqlite3.connect(cache) as db:
        assert time.time() - db.execute('SELECT fetched_at FROM entries').fetchone()[0] >= 7 * 3600


@pytest.mark.parametrize('mutation', [
    "UPDATE entries SET checksum='corrupted'",
    "UPDATE entries SET fetched_at=0",
    "UPDATE entries SET fetched_at=99999999999",
])
def test_bad_or_expired_cache_never_satisfies_lookup(cache, monkeypatch, mutation):
    put()
    with sqlite3.connect(cache) as db: db.execute(mutation)
    client = UniProtJSONClient()
    offline(monkeypatch, client)
    with pytest.raises(UniProtDownloadError): client.fetch_json('P12345')


@pytest.mark.parametrize('payload', [document('Q12345'), json.dumps({'primaryAccession':'P12345','enzymindSource':{}}), json.dumps({'primaryAccession':'P12345','easifaLocal':{}})])
def test_valid_checksum_cannot_bypass_record_or_scope_validation(cache, monkeypatch, payload):
    put(text=payload)
    client = UniProtJSONClient()
    offline(monkeypatch, client)
    with pytest.raises(UniProtDownloadError): client.fetch_json('P12345')


def test_online_not_found_does_not_return_stale_annotation(cache, monkeypatch):
    put(age=7 * 3600)
    client = UniProtJSONClient()
    monkeypatch.setattr(client, '_get', Mock(side_effect=UniProtDownloadError('Missing', 'uniprot_not_found', False)))
    with pytest.raises(UniProtDownloadError) as exc: client.fetch_json('P12345')
    assert exc.value.code == 'uniprot_not_found'


def test_cache_is_bounded_and_expired_entries_are_pruned(cache, monkeypatch):
    monkeypatch.setattr(UniProtJSONCache, 'MAX_ENTRIES', 2)
    provider = UniProtJSONCache()
    for i, accession in enumerate(['P12345', 'Q12345', 'O12345']):
        provider.put(accession, document(accession), time.time() - 10 + i)
    assert provider.get('P12345') is None
    assert provider.get('Q12345') and provider.get('O12345')
    with sqlite3.connect(cache) as db: assert db.execute('SELECT count(*) FROM entries').fetchone()[0] == 2


def test_cache_never_writes_snapshot_even_via_hardlink(cache, snapshot, monkeypatch, tmp_path):
    original = snapshot.read_bytes()
    alias = tmp_path / 'alias.sqlite'
    os.link(snapshot, alias)
    for path in [snapshot, alias]:
        monkeypatch.setenv('ENZYMIND_UNIPROT_CACHE_PATH', str(path))
        put()
        assert snapshot.read_bytes() == original


def test_cache_failure_does_not_fail_live_response(cache, monkeypatch):
    cache.parent.mkdir()
    cache.mkdir()
    client = UniProtJSONClient()
    record = client._parse_record(document(), 'P12345', '')
    monkeypatch.setattr(client, '_get', Mock(return_value=(record, 0)))
    assert client.fetch_json('P12345')['primaryAccession'] == 'P12345'


def test_overview_partial_is_explicit_cooled_down_and_does_not_poison_full_queries(snapshot, monkeypatch):
    client = UniProtJSONClient()
    get = offline(monkeypatch, client)
    data = client.fetch_json('P12345', allow_partial=True)
    assert data['enzymindSource']['partial'] is True
    count = get.call_count
    assert client.fetch_json('P12345', allow_partial=True) == data and get.call_count == count
    with pytest.raises(UniProtDownloadError): client.fetch_json('P12345')
    assert get.call_count > count


def test_overview_budget_bounds_first_wait_when_local_data_exists(snapshot, monkeypatch):
    client = UniProtJSONClient()
    now = [100.]
    monkeypatch.setattr('shared.uniprot.time.monotonic', lambda: now[0])
    def interrupted(*args):
        now[0] += 7
        raise requests.ConnectTimeout()
    get = Mock(side_effect=interrupted)
    monkeypatch.setattr(client, '_get', get)
    assert client.fetch_json('P12345', allow_partial=True)['enzymindSource']['partial']
    assert get.call_count == 2


def test_overview_does_not_turn_authoritative_api_absence_into_partial_success(snapshot, monkeypatch):
    client = UniProtJSONClient()
    monkeypatch.setattr(client, '_get', Mock(side_effect=UniProtDownloadError('Missing', 'uniprot_not_found', False)))
    with pytest.raises(UniProtDownloadError) as exc: client.fetch_json('P12345', allow_partial=True)
    assert exc.value.code == 'uniprot_not_found'
