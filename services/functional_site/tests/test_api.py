"""Test cases for Functional Site Service."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import app

client = TestClient(app)

MOCK_RESPONSE = {
    "features": [
        {"type": "Active site", "location": {"start": {"value": 10}, "end": {"value": 10}}, "description": "Active"},
        {"type": "Binding site", "location": {"start": {"value": 50}, "end": {"value": 55}}, "description": "Binding"}
    ]
}

class TestHealthEndpoint:
    def test_health_check(self):
        response = client.get("/health")
        assert response.status_code == 200

class TestFeaturesEndpoint:
    @patch("models.site_query.requests.get")
    def test_query_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_RESPONSE
        mock_get.return_value = mock_response
        
        response = client.post("/api/query/features", json={"query": "P12345"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 2

    @patch("models.site_query.requests.get")
    def test_not_found(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        response = client.post("/api/query/features", json={"query": "INVALID"})
        assert response.status_code == 200
        assert response.json()["success"] is False

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
