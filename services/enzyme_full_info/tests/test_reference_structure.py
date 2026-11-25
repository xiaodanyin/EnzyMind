import json
import sys
import time
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from models.reference_structure import ReferenceStructure, StructureCache, model_url, validate_model

PDB = 'ATOM      1  CA  ALA A   1      11.000  12.000  13.000  1.00 90.00           C\nEND\n'
META = {'uniprotAccession':'P00176','entryId':'AF-P00176-F1','pdbUrl':'https://alphafold.ebi.ac.uk/files/AF-P00176-F1-model_v6.pdb','latestVersion':6,'uniprotStart':1,'uniprotEnd':1}


@pytest.fixture
def provider(tmp_path, monkeypatch):
    monkeypatch.setenv('ENZYMIND_REFERENCE_STRUCTURE_CACHE_PATH', str(tmp_path / 'models.sqlite'))
    service = ReferenceStructure()
    service._read = Mock(side_effect=[json.dumps([META]), PDB])
    return service


def test_model_metadata_version_and_cache_survive_new_provider(provider):
    result = provider.fetch('p00176')
    assert result['success'] and result['source']['version'] == 6
    assert result['source']['kind'] == 'predicted'
    assert result['structure_data'] == PDB
    restarted = ReferenceStructure()
    restarted._read = Mock(side_effect=AssertionError('Fresh cache must avoid downloads'))
    assert restarted.fetch('P00176')['source']['cache_hit'] is True


@pytest.mark.parametrize('url', ['http://127.0.0.1/data', 'https://alphafold.ebi.ac.uk@evil.test/model.pdb',
    'https://alphafold.ebi.ac.uk/files/AF-P00330-F1-model_v6.pdb',
    'https://alphafold.ebi.ac.uk/files/AF-P00176-F1-model_v6.pdb?next=http://localhost'])
def test_reject_untrusted_or_wrong_identity_model_url(url):
    with pytest.raises(ValueError):
        model_url({**META, 'pdbUrl':url}, 'P00176')


def test_invalid_accession_never_downloads(provider):
    assert provider.fetch('../../etc/passwd')['http_status'] == 422
    provider._read.assert_not_called()


def test_wrong_accession_or_complex_is_not_mapped(provider):
    provider._read = Mock(return_value=json.dumps([{**META, 'uniprotAccession':'P00330'}]))
    assert provider.fetch('P00176')['http_status'] == 404
    assert provider._read.call_count == 1


def test_outage_uses_only_explicitly_stale_cached_model(provider):
    result = provider.fetch('P00176')
    provider.cache.put('P00176', json.dumps(result), time.time() - 8*86400)
    provider._read = Mock(side_effect=requests.Timeout())
    assert provider.fetch('P00176')['source']['stale'] is True
    assert provider._read.call_count == 2


def test_not_found_does_not_resurrect_a_stale_model(provider):
    from models.reference_structure import ModelUnavailable
    result = provider.fetch('P00176')
    provider.cache.put('P00176', json.dumps(result), time.time() - 8*86400)
    provider._read = Mock(side_effect=ModelUnavailable())
    assert provider.fetch('P00176')['http_status'] == 404


def test_busy_and_failure_release_capacity(provider):
    provider.active = {'P00176'}
    assert provider.fetch('P00176')['http_status'] == 429
    provider.active = set()
    provider._read = Mock(side_effect=requests.Timeout())
    assert provider.fetch('P00176')['http_status'] == 502
    assert not provider.active


@pytest.mark.parametrize('text', ['<html>Not a protein</html>', PDB.replace('11.000','   nan')])
def test_reject_invalid_coordinates(text):
    with pytest.raises(ValueError):
        validate_model(text)


def test_size_and_redirect_limits(provider):
    # Use a real context-manager mock to exercise streamed size checks.
    from unittest.mock import MagicMock
    session = MagicMock()
    response = session.get.return_value.__enter__.return_value
    response.status_code = 200
    response.iter_content.return_value = [b'a'*20, b'b'*20]
    with pytest.raises(ValueError):
        ReferenceStructure._read(session, META['pdbUrl'], 30, time.monotonic()+10)
    assert session.get.call_args.kwargs['allow_redirects'] is False
    assert session.get.call_args.kwargs.get('verify', True) is True
    response.status_code = 302
    with pytest.raises(ValueError):
        ReferenceStructure._read(session, META['pdbUrl'], 30, time.monotonic()+10)


def test_cache_refuses_shared_annotation_or_reference_database(tmp_path, monkeypatch):
    path = tmp_path / 'reference.sqlite'
    path.write_bytes(b'original')
    monkeypatch.setenv('ENZYMIND_REFERENCE_STRUCTURE_CACHE_PATH', str(path))
    for key in ['ENZYMIND_UNIPROT_LOCAL_DB_PATH', 'ENZYMIND_UNIPROT_CACHE_PATH']:
        with monkeypatch.context() as context:
            context.setenv(key, str(path))
            cache = StructureCache()
            cache.put('P00176', '{}', time.time())
            assert cache.get('P00176') is None
            assert path.read_bytes() == b'original'
