"""Test cases for EC Reaction Info Service API."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app

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


class TestCatalyticActivityEndpoint:
    @patch("models.catalytic_activity_query.requests.get")
    def test_query_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_UNIPROT_RESPONSE
        mock_get.return_value = mock_response
        
        response = client.post("/api/query/catalytic-activity", json={"query": "P12345"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 1
        assert data["activities"][0]["ec_number"] == "6.3.5.4"
        assert data["activities"][0]["rhea_id"] == "11844"
    
    @patch("models.catalytic_activity_query.requests.get")
    def test_query_not_found(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        response = client.post("/api/query/catalytic-activity", json={"query": "INVALID"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not found" in data["error"]
    
    @patch("models.catalytic_activity_query.requests.get")
    def test_query_no_activities(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_NO_ACTIVITY_RESPONSE
        mock_get.return_value = mock_response
        
        response = client.post("/api/query/catalytic-activity", json={"query": "P00000"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 0
    
    def test_query_empty_input(self):
        response = client.post("/api/query/catalytic-activity", json={"query": ""})
        assert response.status_code == 400


class TestCatalyticActivityFormEndpoint:
    @patch("models.catalytic_activity_query.requests.get")
    def test_form_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_UNIPROT_RESPONSE
        mock_get.return_value = mock_response
        
        response = client.post("/api/query/catalytic-activity/form", data={"query": "P12345"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestBatchEndpoint:
    @patch("models.catalytic_activity_query.requests.get")
    def test_batch_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_UNIPROT_RESPONSE
        mock_get.return_value = mock_response
        
        response = client.post("/api/query/catalytic-activity/batch", json={"queries": ["P12345", "P67890"]})
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["successful"] == 2
    
    def test_batch_empty(self):
        response = client.post("/api/query/catalytic-activity/batch", json={"queries": []})
        assert response.status_code == 400


class TestFileEndpoint:
    @patch("models.catalytic_activity_query.requests.get")
    def test_file_upload(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_UNIPROT_RESPONSE
        mock_get.return_value = mock_response
        
        file_content = b"P12345\nP67890\n"
        response = client.post("/api/query/catalytic-activity/file", files={"file": ("ids.txt", file_content, "text/plain")})
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2


class TestLegacyEndpoint:
    @patch("models.catalytic_activity_query.requests.get")
    def test_legacy(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_UNIPROT_RESPONSE
        mock_get.return_value = mock_response
        
        response = client.post("/query/catalytic_activity", json={"query": "P12345"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestErrorHandling:
    @patch("models.catalytic_activity_query.requests.get")
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
