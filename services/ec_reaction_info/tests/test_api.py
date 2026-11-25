"""Test cases for EC Reaction Info Service API."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from shared.uniprot import UniProtDownloadError

client = TestClient(app)


MOCK_UNIPROT_RESPONSE = {
    "primaryAccession": "P12345",
    "comments": [
        {
            "commentType": "CATALYTIC ACTIVITY",
            "reaction": {
                "name": "ATP + L-aspartate + L-glutamine = AMP + diphosphate + L-asparagine",
                "ecNumber": "6.3.5.4",
                "reactionCrossReferences": [
                    {"database": "Rhea", "id": "RHEA:11844"}
                ]
            },
            "evidences": [{"evidenceCode": "ECO:0000269"}]
        }
    ]
}

MOCK_NO_ACTIVITY_RESPONSE = {
    "primaryAccession": "P00000",
    "comments": []
}


class TestHealthEndpoint:
    def test_health_check(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "ec_reaction_info"


class TestECInfoEndpoint:
    @pytest.mark.parametrize('field,value', [('query', '3.2.1.17'), ('ec_number', 'EC: 3.2.1.17')])
    def test_ec_number_has_official_name_reaction_and_hierarchy(self, field, value):
        with patch('models.catalytic_activity_query.uniprot_json_client.fetch_json', side_effect=AssertionError('EC lookup must be offline')):
            response = client.post('/api/query/ec-info', json={field: value})
        assert response.status_code == 200
        result = response.json()
        assert result['success'] and result['name'] == 'lysozyme'
        assert result['status'] == 'active'
        assert [row['name'] for row in result['hierarchy']] == ['Hydrolases', 'Glycosylases', 'Glycosidases, i.e. enzymes hydrolyzing O- and S-glycosyl compounds', 'lysozyme']
        assert 'peptidoglycan' in result['activities'][0]['reaction_name']
        assert result['source']['license'] == 'CC BY 4.0'
        assert result['source']['release'] == '04-Nov-2026'

    def test_partial_ec_does_not_invent_an_enzyme_or_reaction(self):
        result = client.post('/api/query/ec-info', json={'query': '3.2.-.-'}).json()
        assert result['success'] and result['name'] == 'Glycosylases'
        assert result['status'] == 'class' and result['activities'] == []
        assert result['hierarchy'][2]['name'] is None

    def test_transferred_deleted_and_unknown_entries(self):
        from models.ec_info_query import reference
        for prefix, status in [('Transferred entry:', 'transferred'), ('Deleted entry', 'deleted')]:
            code = next(key for key, name in reference()['names'].items() if name.startswith(prefix))
            result = client.post('/api/query/ec-info', json={'query': code}).json()
            assert result['status'] == status
            assert result['activities'] == []
        response = client.post('/api/query/ec-info', json={'query': '3.999.999.999'})
        assert response.status_code == 200
        assert response.json()['success'] is False
        assert response.json()['code'] == 'ec_not_in_reference'

    @pytest.mark.parametrize('query', ['', '3.-.1.17', '8.1.1.1', 'not-an-id', '../etc/passwd'])
    def test_invalid_query_is_validation_error(self, query):
        assert client.post('/api/query/ec-info', json={'query': query}).status_code == 422

    @patch('models.catalytic_activity_query.uniprot_json_client.fetch_json')
    def test_uniprot_compatibility(self, mock_get):
        mock_get.return_value = MOCK_UNIPROT_RESPONSE
        result = client.post('/api/query/ec-info', json={'uniprot_id': 'p12345'}).json()
        assert result['success'] and result['uniprot_id'] == 'P12345'
        assert result['activities'][0]['ec_number'] == '6.3.5.4'
        assert result['result'] == result['markdown']

    def test_offline_reference_matches_frontend_names_and_source_hashes(self):
        import json
        from pathlib import Path
        from models.ec_info_query import reference
        frontend = json.loads((Path(__file__).resolve().parents[3] / 'frontend/src/data/ec-reference.json').read_text())
        assert {k: v for k, v in reference().items() if k != 'activities'} == frontend


class TestCatalyticActivityEndpoint:
    @patch("models.catalytic_activity_query.uniprot_json_client.fetch_json")
    def test_query_success(self, mock_get):
        mock_get.return_value = MOCK_UNIPROT_RESPONSE
        
        response = client.post("/api/query/catalytic-activity", json={"query": "P12345"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 1
        assert data["activities"][0]["ec_number"] == "6.3.5.4"
        assert data["activities"][0]["rhea_id"] == "11844"
    
    @patch("models.catalytic_activity_query.uniprot_json_client.fetch_json")
    def test_query_not_found(self, mock_get):
        mock_get.side_effect = UniProtDownloadError("UniProt accession not found", "uniprot_not_found", False)
        
        response = client.post("/api/query/catalytic-activity", json={"query": "INVALID"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not found" in data["error"]
    
    @patch("models.catalytic_activity_query.uniprot_json_client.fetch_json")
    def test_query_no_activities(self, mock_get):
        mock_get.return_value = MOCK_NO_ACTIVITY_RESPONSE
        
        response = client.post("/api/query/catalytic-activity", json={"query": "P00000"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 0
    
    def test_query_empty_input(self):
        response = client.post("/api/query/catalytic-activity", json={"query": ""})
        assert response.status_code == 400


class TestCatalyticActivityFormEndpoint:
    @patch("models.catalytic_activity_query.uniprot_json_client.fetch_json")
    def test_form_success(self, mock_get):
        mock_get.return_value = MOCK_UNIPROT_RESPONSE
        
        response = client.post("/api/query/catalytic-activity/form", data={"query": "P12345"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestBatchEndpoint:
    @patch("models.catalytic_activity_query.uniprot_json_client.fetch_json")
    def test_batch_success(self, mock_get):
        mock_get.return_value = MOCK_UNIPROT_RESPONSE
        
        response = client.post("/api/query/catalytic-activity/batch", json={"queries": ["P12345", "P67890"]})
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["successful"] == 2
    
    def test_batch_empty(self):
        response = client.post("/api/query/catalytic-activity/batch", json={"queries": []})
        assert response.status_code == 400


class TestFileEndpoint:
    @patch("models.catalytic_activity_query.uniprot_json_client.fetch_json")
    def test_file_upload(self, mock_get):
        mock_get.return_value = MOCK_UNIPROT_RESPONSE
        
        file_content = b"P12345\nP67890\n"
        response = client.post("/api/query/catalytic-activity/file", files={"file": ("ids.txt", file_content, "text/plain")})
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2


class TestLegacyEndpoint:
    @patch("models.catalytic_activity_query.uniprot_json_client.fetch_json")
    def test_legacy(self, mock_get):
        mock_get.return_value = MOCK_UNIPROT_RESPONSE
        
        response = client.post("/query/catalytic_activity", json={"query": "P12345"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestErrorHandling:
    @patch("models.catalytic_activity_query.uniprot_json_client.fetch_json")
    def test_timeout(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()
        
        response = client.post("/api/query/catalytic-activity", json={"query": "P12345"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "timeout" in data["error"].lower()


class TestDocumentation:
    def test_openapi_docs(self):
        response = client.get("/docs")
        assert response.status_code == 200
    
    def test_openapi_schema(self):
        response = client.get("/openapi.json")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
