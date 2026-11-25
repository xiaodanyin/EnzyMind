"""Test cases for Enzyme Check Service API."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from shared.uniprot import UniProtDownloadError

client = TestClient(app)


def test_health_remains_responsive_during_slow_annotation():
    import threading
    from concurrent.futures import ThreadPoolExecutor
    entered, release = threading.Event(), threading.Event()
    def slow_lookup(_accession, **_options):
        entered.set()
        assert release.wait(5)
        return MOCK_ENZYME_RESPONSE
    with TestClient(app) as active, ThreadPoolExecutor(max_workers=2) as pool:
        with patch('models.enzyme_checker.uniprot_json_client.fetch_json', side_effect=slow_lookup):
            query = pool.submit(active.post, '/api/check/enzyme', json={'query': 'P00698'})
            try:
                assert entered.wait(2)
                assert pool.submit(active.get, '/health').result(timeout=2).status_code == 200
            finally:
                release.set()
            assert query.result(timeout=2).json()['success'] is True


MOCK_ENZYME_RESPONSE = {
    "primaryAccession": "P12345",
    "comments": [
        {
            "commentType": "CATALYTIC ACTIVITY",
            "reaction": {"ecNumber": "1.1.1.1", "name": "Test reaction"}
        }
    ]
}

MOCK_NON_ENZYME_RESPONSE = {
    "primaryAccession": "P00000",
    "comments": []
}


class TestHealthEndpoint:
    def test_health_check(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "enzyme_check"


class TestEnzymeCheckEndpoint:
    @pytest.mark.parametrize("field", ["query", "uniprot_id"])
    @patch("models.enzyme_checker.uniprot_json_client.fetch_json")
    def test_platform_and_agent_input_names(self, mock_get, field):
        mock_get.return_value = MOCK_ENZYME_RESPONSE
        response = client.post("/api/check/enzyme", json={field: "P12345"})
        assert response.status_code == 200
        assert response.json()["is_enzyme"] is True

    @patch("models.enzyme_checker.uniprot_json_client.fetch_json")
    def test_check_enzyme_true(self, mock_get):
        mock_get.return_value = MOCK_ENZYME_RESPONSE
        
        response = client.post("/api/check/enzyme", json={"query": "P12345"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["is_enzyme"] is True
        assert "1.1.1.1" in data["ec_numbers"]
    
    @patch("models.enzyme_checker.uniprot_json_client.fetch_json")
    def test_check_non_enzyme(self, mock_get):
        mock_get.return_value = MOCK_NON_ENZYME_RESPONSE
        
        response = client.post("/api/check/enzyme", json={"query": "P00000"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["is_enzyme"] is False
    
    @patch("models.enzyme_checker.uniprot_json_client.fetch_json")
    def test_check_not_found(self, mock_get):
        mock_get.side_effect = UniProtDownloadError("UniProt accession not found", "uniprot_not_found", False)
        
        response = client.post("/api/check/enzyme", json={"query": "INVALID"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["is_enzyme"] is None
    
    def test_check_empty_input(self):
        response = client.post("/api/check/enzyme", json={"query": ""})
        assert response.status_code == 400


class TestEnzymeCheckFormEndpoint:
    @patch("models.enzyme_checker.uniprot_json_client.fetch_json")
    def test_form_success(self, mock_get):
        mock_get.return_value = MOCK_ENZYME_RESPONSE
        
        response = client.post("/api/check/enzyme/form", data={"query": "P12345"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestBatchEndpoint:
    @patch("models.enzyme_checker.uniprot_json_client.fetch_json")
    def test_batch_mixed(self, mock_get):
        def mock_side_effect(accession, **_options):
            return MOCK_ENZYME_RESPONSE if accession == 'P12345' else MOCK_NON_ENZYME_RESPONSE
        
        mock_get.side_effect = mock_side_effect
        
        response = client.post("/api/check/enzyme/batch", json={"queries": ["P12345", "P00000"]})
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["enzymes"] == 1
        assert data["non_enzymes"] == 1
    
    def test_batch_empty(self):
        response = client.post("/api/check/enzyme/batch", json={"queries": []})
        assert response.status_code == 400


class TestLegacyEndpoint:
    @patch("models.enzyme_checker.uniprot_json_client.fetch_json")
    def test_legacy(self, mock_get):
        mock_get.return_value = MOCK_ENZYME_RESPONSE
        
        response = client.post("/check/enzyme", json={"query": "P12345"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestDocumentation:
    def test_openapi_docs(self):
        response = client.get("/docs")
        assert response.status_code == 200
    
    def test_openapi_schema(self):
        response = client.get("/openapi.json")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
