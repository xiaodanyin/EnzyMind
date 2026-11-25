import time
from unittest.mock import patch

import pytest
import requests
from fastapi.testclient import TestClient
from main import app, searcher
from models.blast_searcher import BlastSearcher, BlastPending

XML2_EMPTY = '''<?xml version="1.0"?>
<BlastXML2><BlastOutput2><report><Report><program>blastp</program><version>BLASTP 2.17.0+</version><reference>NCBI</reference><search-target><Target><db>swissprot</db></Target></search-target><params><Parameters><expect>0.01</expect></Parameters></params><results><Results><search><Search><query-id>Query_1</query-id><query-title>test</query-title><query-len>5</query-len><hits></hits></Search></search></Results></results></Report></report></BlastOutput2></BlastXML2>'''

@pytest.fixture(autouse=True)
def empty_cache():
    BlastSearcher._poll_cache.clear()
    yield
    BlastSearcher._poll_cache.clear()


def test_submit_returns_rid_without_waiting_and_keeps_database():
    with patch.object(searcher, '_ncbi_request', return_value='RID = TEST123\nRTOE = 60') as request:
        with TestClient(app) as client:
            response = client.post('/api/query/blast', json={'query':'MAAAA','database':'swissprot','wait_for_result':False}).json()
    assert response['status'] == 'queued' and response['request_id'] == 'TEST123'
    assert response['database'] == 'swissprot'
    assert len(request.call_args_list) == 1
    assert request.call_args.args[1]['CMD'] == 'Put'
    assert request.call_args.args[1]['DATABASE'] == 'swissprot'


@pytest.mark.parametrize('upstream', ['Status=WAITING', 'Status=READY', '<html>Temporary maintenance</html>', requests.exceptions.SSLError('EOF')])
def test_retrieval_never_resubmits_or_reports_false_no_hits(upstream):
    with patch.object(searcher, '_ncbi_request', side_effect=[upstream] if not isinstance(upstream, Exception) else upstream) as request:
        a = searcher.poll('TEST123')
        b = searcher.poll('TEST123')
    assert a['status'] == b['status'] == 'queued'
    assert a['success'] and 'alignments' not in a
    assert len(request.call_args_list) == 1
    assert request.call_args.args[1]['CMD'] == 'Get'
    assert 'queued' in searcher.format_as_html(a)
    assert 'No significant' not in searcher.format_as_markdown(a)


def test_xml2_complete_with_no_hits_is_completed():
    with patch.object(searcher, '_ncbi_request', return_value=XML2_EMPTY):
        result = searcher.poll('TEST123', database='swissprot')
    assert result['status'] == 'completed'
    assert result['query_length'] == 5
    assert result['num_results'] == 0 and result['alignments'] == []


@pytest.mark.parametrize('state', ['FAILED', 'UNKNOWN'])
def test_ncbi_terminal_status_is_distinct_from_queue(state):
    with patch.object(searcher, '_ncbi_request', return_value='Status=' + state):
        result = searcher.poll('TEST123')
    assert result['status'] == 'failed' and result['success'] is False
    assert result['error_code'] == 'ncbi_' + state.lower()


def test_sync_timeout_preserves_legacy_contract_and_rid():
    with patch.object(searcher, '_query_ncbi', side_effect=BlastPending('TEST123','Still queued')):
        result = searcher.search('MAAAA')
    assert result['status'] == 'queued' and result['request_id'] == 'TEST123'
    assert result['success'] is True


def test_poll_cache_expires_after_minute():
    with patch('models.blast_searcher.time.time', return_value=1000), patch.object(searcher, '_ncbi_request', return_value='Status=WAITING') as request:
        searcher.poll('TEST123')
        searcher.poll('TEST123')
        assert request.call_count == 1
        with patch('models.blast_searcher.time.time', return_value=1061):
            searcher.poll('TEST123')
        assert request.call_count == 2


def test_invalid_poll_parameters_never_reach_ncbi():
    with patch.object(searcher, '_ncbi_request', side_effect=AssertionError('unexpected network')):
        with TestClient(app) as client:
            assert client.get('/api/query/blast/results/bad').status_code == 422
            assert client.get('/api/query/blast/results/TEST123?max_results=51').status_code == 422
            assert client.post('/api/query/blast', json={'query':'MAAAA','database':'invalid'}).status_code == 422


def test_shared_transport_enforces_per_rid_cooldown_even_without_cache():
    from unittest.mock import Mock
    session = Mock()
    session.post.return_value.text = 'Status=WAITING'
    BlastSearcher._last_request = 995
    BlastSearcher._last_poll['TEST123'] = 990
    try:
        with patch('models.blast_searcher.time.monotonic', return_value=1000), patch('models.blast_searcher.time.sleep') as sleep:
            searcher._ncbi_request(session, {'CMD':'Get','RID':'TEST123'})
        sleep.assert_called_once_with(50)
        assert session.post.call_count == 1
    finally:
        BlastSearcher._last_request = 0
        BlastSearcher._last_poll.clear()


def test_truncated_xml_remains_retrievable_not_a_false_failure():
    with patch.object(searcher, '_ncbi_request', return_value='<?xml version="1.0"?><BlastXML2><BlastOutput2>'):
        result = searcher.poll('TEST123')
    assert result['status'] == 'queued' and result['request_id'] == 'TEST123'
    assert result['last_poll_error']
