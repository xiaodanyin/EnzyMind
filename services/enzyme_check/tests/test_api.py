"""Test cases for Enzyme Check Service API."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app

client = TestClient(app)


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
    @patch("models.enzyme_checker.requests.get")
    def test_check_enzyme_true(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_ENZYME_RESPONSE
        mock_get.return_value = mock_response
        
        response = client.post("/api/check/enzyme", json={"query": "P12345"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["is_enzyme"] is True
        assert "1.1.1.1" in data["ec_numbers"]
    
    @patch("models.enzyme_checker.requests.get")
    def test_check_non_enzyme(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_NON_ENZYME_RESPONSE
        mock_get.return_value = mock_response
        
        response = client.post("/api/check/enzyme", json={"query": "P00000"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["is_enzyme"] is False
    
    @patch("models.enzyme_checker.requests.get")
    def test_check_not_found(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        response = client.post("/api/check/enzyme", json={"query": "INVALID"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["is_enzyme"] is None
    
    def test_check_empty_input(self):
        response = client.post("/api/check/enzyme", json={"query": ""})
        assert response.status_code == 400


class TestEnzymeCheckFormEndpoint:
    @patch("models.enzyme_checker.requests.get")
    def test_form_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_ENZYME_RESPONSE
        mock_get.return_value = mock_response
        
        response = client.post("/api/check/enzyme/form", data={"query": "P12345"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestBatchEndpoint:
    @patch("models.enzyme_checker.requests.get")
    def test_batch_mixed(self, mock_get):
        def mock_side_effect(url, timeout):
            mock_resp = MagicMock()
            if "P12345" in url:
                mock_resp.status_code = 200
                mock_resp.json.return_value = MOCK_ENZYME_RESPONSE
            else:
                mock_resp.status_code = 200
                mock_resp.json.return_value = MOCK_NON_ENZYME_RESPONSE
            return mock_resp
        
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
    @patch("models.enzyme_checker.requests.get")
    def test_legacy(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_ENZYME_RESPONSE
        mock_get.return_value = mock_response
        
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
