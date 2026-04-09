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
    @patch("models.full_info_query.requests.get")
    def test_enzyme_found(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_ENZYME_RESPONSE
        mock_get.return_value = mock_response
        
        response = client.post("/api/query/enzyme-full-info", json={"uniprot_id": "P12345"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["is_enzyme"] is True
    
    @patch("models.full_info_query.requests.get")
    def test_non_enzyme(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_NON_ENZYME
        mock_get.return_value = mock_response
        
        response = client.post("/api/query/enzyme-full-info", json={"uniprot_id": "P00000"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["is_enzyme"] is False
    
    @patch("models.full_info_query.requests.get")
    def test_not_found(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        response = client.post("/api/query/enzyme-full-info", json={"uniprot_id": "INVALID"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False


class TestDocumentation:
    def test_docs(self):
        response = client.get("/docs")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
