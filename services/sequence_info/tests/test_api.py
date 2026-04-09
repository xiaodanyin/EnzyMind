"""Tests for Sequence Info Service"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app

client = TestClient(app)


# Mock UniProt response
MOCK_UNIPROT_RESPONSE = {
    "primaryAccession": "P12345",
    "sequence": {
        "length": 402,
        "molWeight": 44674,
        "value": "MSPFFFFFAGLLLPVPVQALPIGNDP..."
    }
}


class TestHealthEndpoint:
    """Tests for health check endpoint"""
    
    def test_health_check(self):
        """Test health check returns healthy status"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "sequence_info"


class TestSequenceInfoEndpoint:
    """Tests for sequence info query endpoint"""
    
    @patch("main.fetch_uniprot_data")
    def test_query_success(self, mock_fetch):
        """Test successful sequence info query"""
        mock_fetch.return_value = MOCK_UNIPROT_RESPONSE
        
        response = client.post(
            "/api/query/sequence-info",
            json={"uniprot_id": "P12345"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["length"] == 402
        assert data["molWeight"] == 44674
        assert "MSPFFFFFAGLLLPVPVQALPIGNDP" in data["value"]
    
    @patch("main.fetch_uniprot_data")
    def test_not_found(self, mock_fetch):
        """Test 404 for non-existent UniProt ID"""
        mock_fetch.return_value = None
        
        response = client.post(
            "/api/query/sequence-info",
            json={"uniprot_id": "INVALID123"}
        )
        
        assert response.status_code == 404
    
    @patch("main.fetch_uniprot_data")
    def test_empty_sequence(self, mock_fetch):
        """Test response when sequence block is missing"""
        mock_fetch.return_value = {"primaryAccession": "P12345", "sequence": {}}
        
        response = client.post(
            "/api/query/sequence-info",
            json={"uniprot_id": "P12345"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["length"] is None
        assert data["molWeight"] is None
        assert data["value"] is None


class TestDocumentation:
    """Tests for API documentation"""
    
    def test_openapi_schema(self):
        """Test OpenAPI schema is available"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert data["info"]["title"] == "Sequence Info Service"
