"""Test cases for Enzyme Full Info Service API."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import app

client = TestClient(app)


MOCK_ENZYME_RESPONSE = {
    "primaryAccession": "P12345",
    "sequence": {"length": 100, "molWeight": 11000, "value": "MSEQ..."},
    "comments": [
        {"commentType": "CATALYTIC ACTIVITY", "reaction": {"ecNumber": "1.1.1.1", "name": "Test reaction"}}
    ],
    "features": [{"type": "Active site", "location": {"start": {"value": 10}, "end": {"value": 10}}, "description": "Active"}]
}

MOCK_NON_ENZYME = {"primaryAccession": "P00000", "comments": [], "features": [], "sequence": {}}


class TestHealthEndpoint:
    def test_health_check(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestFullInfoEndpoint:
    @patch("models.full_info_query.uniprot_json_client.fetch_json")
    def test_enzyme_found(self, mock_get):
        mock_get.return_value = MOCK_ENZYME_RESPONSE
        
        response = client.post("/api/query/enzyme-full-info", json={"uniprot_id": "P12345"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["is_enzyme"] is True
    
    @patch("models.full_info_query.uniprot_json_client.fetch_json")
    def test_non_enzyme(self, mock_get):
        mock_get.return_value = MOCK_NON_ENZYME
        
        response = client.post("/api/query/enzyme-full-info", json={"uniprot_id": "P00000"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["is_enzyme"] is False
    
    @patch("models.full_info_query.uniprot_json_client.fetch_json")
    def test_not_found(self, mock_get):
        from shared.uniprot import UniProtDownloadError
        mock_get.side_effect = UniProtDownloadError('UniProt accession P12345 was not found.', 'uniprot_not_found', False)
        
        response = client.post("/api/query/enzyme-full-info", json={"uniprot_id": "INVALID"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert 'not found' in data['error']

    @patch('models.full_info_query.uniprot_json_client.fetch_json')
    def test_connection_outage_is_not_reported_as_missing_enzyme(self, fetch):
        from shared.uniprot import UniProtDownloadError
        fetch.side_effect = UniProtDownloadError('Could not retrieve annotations after bounded retries.')
        result = client.post('/api/query/enzyme-full-info', json={'uniprot_id': 'P00761'}).json()
        assert result['success'] is False and result['is_enzyme'] is None
        assert 'bounded retries' in result['error']

    @patch('models.full_info_query.uniprot_json_client.fetch_json')
    def test_resolved_primary_accession_and_annotations_are_preserved(self, fetch):
        fetch.return_value = MOCK_ENZYME_RESPONSE
        result = client.post('/api/query/enzyme-full-info', json={'uniprot_id': 'P00761'}).json()
        assert result['uniprot_id'] == 'P12345'
        assert result['sequence_info']['length'] == 100
        assert result['catalytic_activities'][0]['ec_number'] == '1.1.1.1'
        assert result['functional_sites'][0]['start'] == 10

    @patch('models.full_info_query.uniprot_json_client.fetch_json')
    def test_partial_annotations_remain_useful_without_claiming_missing_kinetics(self, fetch):
        fetch.return_value = {**MOCK_ENZYME_RESPONSE, 'enzymindSource': {'method':'local_snapshot','partial':True}}
        result = client.post('/api/query/enzyme-full-info', json={'uniprot_id':'P12345'}).json()
        assert result['success'] and result['partial'] and result['warnings']
        assert result['kinetic_parameters'] is None
        assert result['sequence_info']['length'] == 100 and result['functional_sites']
        assert result['source']['method'] == 'local_snapshot'

    @patch('models.full_info_query.uniprot_json_client.fetch_json')
    def test_partial_missing_catalysis_is_not_reported_as_non_enzyme(self, fetch):
        fetch.return_value = {**MOCK_NON_ENZYME, 'enzymindSource': {'method':'local_snapshot','partial':True}}
        result = client.post('/api/query/enzyme-full-info', json={'uniprot_id':'P00000'}).json()
        assert result['success'] and result['partial'] and result['is_enzyme'] is None

    @patch('models.full_info_query.uniprot_json_client.fetch_json')
    def test_slow_upstream_does_not_block_health_checks(self, fetch):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        entered, release = Event(), Event()
        def slow(*args, **kwargs):
            entered.set()
            assert release.wait(5)
            return MOCK_ENZYME_RESPONSE
        fetch.side_effect = slow
        with TestClient(app) as running, ThreadPoolExecutor(max_workers=2) as pool:
            pending = pool.submit(running.post, '/api/query/enzyme-full-info', json={'uniprot_id':'P12345'})
            try:
                assert entered.wait(2)
                assert pool.submit(running.get, '/health').result(timeout=1).status_code == 200
            finally:
                release.set()
            assert pending.result(timeout=2).json()['success']


class TestDocumentation:
    def test_docs(self):
        response = client.get("/docs")
        assert response.status_code == 200


@patch('models.full_info_query.uniprot_json_client.fetch_json')
def test_visualization_metadata_survives_even_without_catalytic_annotation(fetch):
    fetch.return_value = {**MOCK_NON_ENZYME, 'entryType':'UniProtKB reviewed (Swiss-Prot)',
        'proteinDescription':{'recommendedName':{'fullName':{'value':'Example protein'}}},
        'organism':{'scientificName':'Example species'},'genes':[{'geneName':{'value':'gene1'}}],
        'sequence':{'value':'ACDE','length':4},
        'uniProtKBCrossReferences':[{'database':'PDB','id':'1abc','properties':[{'key':'Method','value':'X-ray'},{'key':'Resolution','value':'2.0 A'}]}],
        'comments':[{'commentType':'FUNCTION','texts':[{'value':'Reported function.'}]}],
        'features':[{'type':'Binding site','location':{'start':{'value':2,'modifier':'UNSURE'},'end':{'value':2}},'ligand':{'name':'zinc'}}]}
    result = client.post('/api/query/enzyme-full-info',json={'uniprot_id':'P00000'}).json()
    assert result['sequence_info']['sequence'] == 'ACDE'
    assert result['protein_name'] == 'Example protein' and result['reviewed'] is True
    assert result['gene_names'] == ['gene1'] and result['function'] == 'Reported function.'
    assert result['structure_references'][0]['id'] == '1ABC'
    assert result['functional_sites'][0]['position_exact'] is False
    assert result['functional_sites'][0]['ligand'] == 'zinc'


@patch('main.reference_structure.fetch')
def test_structure_outage_has_its_own_response(fetch):
    fetch.return_value = {'success':False,'http_status':502,'error':'Reference unavailable.'}
    response = client.get('/api/query/enzyme-full-info/P00176/structure')
    assert response.status_code == 502 and response.json()['detail'] == 'Reference unavailable.'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
