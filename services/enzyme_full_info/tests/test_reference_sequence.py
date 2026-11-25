import sys
from pathlib import Path
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from models.reference_sequence import reference_sequence, _slots
from shared.uniprot import UniProtSequence, UniProtDownloadError
from main import app


def test_local_sequence_preserves_requested_and_resolved_identity_without_internal_paths(monkeypatch):
    fetch=Mock(return_value=UniProtSequence('P00330','ACDX','https://www.uniprot.org/uniprotkb/P00330',1700000000,
        source={'name':'Local UniProt snapshot','method':'local_snapshot','snapshot_created_at':'2026-06-14','path':'private-path'}))
    monkeypatch.setattr('models.reference_sequence.uniprot_sequence_client.fetch',fetch)
    result=reference_sequence('p12345')
    assert result['requested_accession']=='P12345' and result['uniprot_id']=='P00330'
    assert result['sequence_info']=={'sequence':'ACDX','length':4}
    assert result['source']['method']=='local_snapshot' and 'path' not in result['source']
    fetch.assert_called_once_with('P12345',budget_seconds=15)


def test_invalid_accession_never_attempts_network():
    assert reference_sequence('../../etc/passwd')['http_status']==422


@pytest.mark.parametrize('code,status',[('uniprot_not_found',404),('uniprot_unavailable',503)])
def test_failure_is_explicit_and_releases_capacity(monkeypatch,code,status):
    monkeypatch.setattr('models.reference_sequence.uniprot_sequence_client.fetch',Mock(side_effect=UniProtDownloadError('Reference unavailable',code)))
    for _ in range(6):assert reference_sequence('P00330')['http_status']==status


def test_concurrency_is_bounded():
    for _ in range(4):assert _slots.acquire(blocking=False)
    try:assert reference_sequence('P00330')['http_status']==429
    finally:
        for _ in range(4):_slots.release()


def test_get_endpoint_returns_only_reference_context(monkeypatch):
    fetch=Mock(return_value=UniProtSequence('P00330','ACD','https://www.uniprot.org/uniprotkb/P00330',1700000000))
    monkeypatch.setattr('models.reference_sequence.uniprot_sequence_client.fetch',fetch)
    with TestClient(app) as client:
        result=client.get('/api/query/enzyme-full-info/P00330/sequence')
    assert result.status_code==200 and result.json()['sequence_info']['sequence']=='ACD'
    assert 'workspace_result' not in result.json()
