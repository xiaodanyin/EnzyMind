"""Test cases for Kinetic Params Service."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import app

client = TestClient(app)

MOCK_RESPONSE = {
    "comments": [{
        "commentType": "BIOPHYSICOCHEMICAL PROPERTIES",
        "kineticParameters": {
            "michaelisConstants": [{"constant": 0.5, "unit": "mM", "substrate": "ATP"}],
            "maximumVelocities": [{"velocity": 100, "unit": "umol/min/mg"}],
            "note": {"texts": [{"value": "kcat = 50 s-1"}]}
        }
    }]
}

class TestHealthEndpoint:
    def test_health_check(self):
        response = client.get("/health")
        assert response.status_code == 200

class TestKineticsEndpoint:
    @patch("models.kinetic_query.requests.get")
    def test_query_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_RESPONSE
        mock_get.return_value = mock_response
        
        response = client.post("/api/query/kinetics", json={"query": "P12345"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["km"]) == 1

    @patch("models.kinetic_query.requests.get")
    def test_not_found(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        response = client.post("/api/query/kinetics", json={"query": "INVALID"})
        assert response.status_code == 200
        assert response.json()["success"] is False

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
