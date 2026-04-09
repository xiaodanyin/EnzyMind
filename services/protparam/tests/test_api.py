# protparam/tests/test_api.py
"""
Tests for the ProtParam Service API.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def sample_sequence():
    """Sample amino acid sequence."""
    return "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"


@pytest.fixture
def mock_expasy_response():
    """Mock ExPASy response HTML."""
    return """
    <html>
    <pre>Some header</pre>
    <pre>
Number of amino acids: 52
Molecular weight: 5500.0
Theoretical pI: 5.5
Instability index (II) is computed to be 42.08
Grand average of hydropathicity (GRAVY): -0.5
    </pre>
    </html>
    """


# =============================================================================
# Health Check Tests
# =============================================================================

class TestHealthEndpoint:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "protparam"


# =============================================================================
# API Endpoint Tests
# =============================================================================

class TestProtParamEndpoint:
    def test_analyze_empty_query(self, client):
        response = client.post(
            "/api/query/protein-physchem",
            json={"query": ""}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
    
    def test_analyze_missing_query(self, client):
        response = client.post(
            "/api/query/protein-physchem",
            json={}
        )
        assert response.status_code == 422
    
    def test_analyze_with_mock(self, client, sample_sequence, mock_expasy_response):
        with patch("models.protparam_analyzer.send_expasy_param_request") as mock_request:
            mock_request.return_value = mock_expasy_response
            
            response = client.post(
                "/api/query/protein-physchem",
                json={"query": sample_sequence}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "markdown" in data


class TestProtParamFormEndpoint:
    def test_form_empty_query(self, client):
        response = client.post(
            "/api/query/protein-physchem/form",
            data={"query": ""}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
    
    def test_form_with_sequence(self, client, sample_sequence, mock_expasy_response):
        with patch("models.protparam_analyzer.send_expasy_param_request") as mock_request:
            mock_request.return_value = mock_expasy_response
            
            response = client.post(
                "/api/query/protein-physchem/form",
                data={"query": sample_sequence}
            )
            
            assert response.status_code == 200


class TestProtParamFileEndpoint:
    def test_file_upload(self, client, mock_expasy_response):
        fasta_content = ">test\nMKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
        
        with patch("models.protparam_analyzer.send_expasy_param_request") as mock_request:
            mock_request.return_value = mock_expasy_response
            
            response = client.post(
                "/api/query/protein-physchem/file",
                files={"file": ("test.fasta", fasta_content.encode(), "text/plain")}
            )
            
            assert response.status_code == 200


class TestLegacyEndpoint:
    def test_legacy_sequence(self, client, sample_sequence, mock_expasy_response):
        with patch("models.protparam_analyzer.send_expasy_param_request") as mock_request:
            mock_request.return_value = mock_expasy_response
            
            response = client.post(
                "/query/protein-physchem",
                data={
                    "input_type": "sequence",
                    "query": sample_sequence
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "result" in data
    
    def test_legacy_missing_query(self, client):
        response = client.post(
            "/query/protein-physchem",
            data={"input_type": "sequence"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "❌" in data["result"]


# =============================================================================
# Documentation Tests
# =============================================================================

class TestDocumentation:
    def test_docs_endpoint(self, client):
        response = client.get("/docs")
        assert response.status_code == 200
    
    def test_openapi_json(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200
