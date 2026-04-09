# sequence_alignment/tests/test_api.py
"""
Tests for the Sequence Alignment Service API.
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
def mock_blast_result():
    """Mock BLAST search result."""
    return {
        "success": True,
        "query_length": 52,
        "num_results": 2,
        "alignments": [
            {
                "title": "sp|P12345|TEST_HUMAN Test protein",
                "length": 500,
                "e_value": 1e-50,
                "score": 200,
                "bits": 150,
                "query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR",
                "match": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR",
                "subject": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
            },
            {
                "title": "sp|Q67890|TEST2_MOUSE Test protein 2",
                "length": 450,
                "e_value": 1e-30,
                "score": 150,
                "bits": 100,
                "query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITF",
                "match": "MKFLILLFNIL LFPVLAADNHGVGPQGASGVDPITF",
                "subject": "MKFLILLFNILSLFPVLAADNHGVGPQGASGVDPITF"
            }
        ]
    }


# =============================================================================
# Health Check Tests
# =============================================================================

class TestHealthEndpoint:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "sequence_alignment"


# =============================================================================
# API Endpoint Tests
# =============================================================================

class TestBlastEndpoint:
    def test_blast_empty_query(self, client):
        response = client.post(
            "/api/query/blast",
            json={"query": ""}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
    
    def test_blast_missing_query(self, client):
        response = client.post(
            "/api/query/blast",
            json={}
        )
        assert response.status_code == 422
    
    def test_blast_with_mock(self, client, sample_sequence, mock_blast_result):
        with patch("models.blast_searcher.BlastSearcher.search") as mock_search:
            mock_search.return_value = mock_blast_result
            
            response = client.post(
                "/api/query/blast",
                json={"query": sample_sequence, "max_results": 3}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "alignments" in data
    
    def test_blast_with_max_results(self, client, sample_sequence, mock_blast_result):
        with patch("models.blast_searcher.BlastSearcher.search") as mock_search:
            mock_search.return_value = mock_blast_result
            
            response = client.post(
                "/api/query/blast",
                json={"query": sample_sequence, "max_results": 5}
            )
            
            assert response.status_code == 200


class TestBlastFormEndpoint:
    def test_form_empty_query(self, client):
        response = client.post(
            "/api/query/blast/form",
            data={"query": ""}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
    
    def test_form_with_sequence(self, client, sample_sequence, mock_blast_result):
        with patch("models.blast_searcher.BlastSearcher.search") as mock_search:
            mock_search.return_value = mock_blast_result
            
            response = client.post(
                "/api/query/blast/form",
                data={"query": sample_sequence}
            )
            
            assert response.status_code == 200


class TestBlastFileEndpoint:
    def test_file_upload(self, client, mock_blast_result):
        fasta_content = ">test\nMKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
        
        with patch("models.blast_searcher.BlastSearcher.search") as mock_search:
            mock_search.return_value = mock_blast_result
            
            response = client.post(
                "/api/query/blast/file",
                files={"file": ("test.fasta", fasta_content.encode(), "text/plain")}
            )
            
            assert response.status_code == 200


class TestBlastHtmlEndpoint:
    def test_html_format(self, client, sample_sequence, mock_blast_result):
        with patch("models.blast_searcher.BlastSearcher.search") as mock_search:
            mock_search.return_value = mock_blast_result
            
            response = client.post(
                "/api/query/blast/html",
                json={"query": sample_sequence}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "result" in data
            assert "<div" in data["result"]


class TestBlastMarkdownEndpoint:
    def test_markdown_format(self, client, sample_sequence, mock_blast_result):
        with patch("models.blast_searcher.BlastSearcher.search") as mock_search:
            mock_search.return_value = mock_blast_result
            
            response = client.post(
                "/api/query/blast/markdown",
                json={"query": sample_sequence}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "result" in data
            assert "##" in data["result"]


class TestLegacyEndpoint:
    def test_legacy_sequence(self, client, sample_sequence, mock_blast_result):
        with patch("models.blast_searcher.BlastSearcher.search") as mock_search:
            mock_search.return_value = mock_blast_result
            
            response = client.post(
                "/query/blast",
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
            "/query/blast",
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
