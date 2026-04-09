# function_get/tests/test_api.py
"""Test cases for Function Get Service API."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app

client = TestClient(app)


# Mock UniProt response data
MOCK_UNIPROT_RESPONSE = {
    "primaryAccession": "P12345",
    "proteinDescription": {
        "recommendedName": {
            "fullName": {
                "value": "Aspartate aminotransferase, mitochondrial"
            }
        }
    },
    "organism": {
        "scientificName": "Homo sapiens"
    },
    "genes": [
        {
            "geneName": {
                "value": "GOT2"
            },
            "synonyms": [
                {"value": "FABP-1"},
                {"value": "KYAT4"}
            ]
        }
    ],
    "comments": [
        {
            "commentType": "FUNCTION",
            "texts": [
                {
                    "value": "Plays a key role in amino acid metabolism. Important for the interconversion of amino acids and oxoacids."
                }
            ]
        }
    ]
}

MOCK_NO_FUNCTION_RESPONSE = {
    "primaryAccession": "P00000",
    "proteinDescription": {
        "submissionNames": [
            {
                "fullName": {
                    "value": "Unknown protein"
                }
            }
        ]
    },
    "organism": {
        "scientificName": "Unknown organism"
    },
    "genes": [],
    "comments": []
}


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_check(self):
        """Test health endpoint returns correct status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "function_get"
        assert data["version"] == "1.0.0"


class TestFunctionQueryEndpoint:
    """Test /api/query/function endpoint."""
    
    @patch("models.function_query.requests.get")
    def test_query_function_success(self, mock_get):
        """Test successful function query."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_UNIPROT_RESPONSE
        mock_get.return_value = mock_response
        
        response = client.post(
            "/api/query/function",
            json={"query": "P12345"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["uniprot_id"] == "P12345"
        assert "amino acid metabolism" in data["function"]
        assert data["protein_name"] == "Aspartate aminotransferase, mitochondrial"
        assert data["organism"] == "Homo sapiens"
        assert "GOT2" in data["gene_names"]
    
    @patch("models.function_query.requests.get")
    def test_query_function_not_found(self, mock_get):
        """Test function query with non-existent UniProt ID."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        response = client.post(
            "/api/query/function",
            json={"query": "INVALID123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not found" in data["error"]
    
    @patch("models.function_query.requests.get")
    def test_query_function_no_function_text(self, mock_get):
        """Test query when protein has no function annotation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_NO_FUNCTION_RESPONSE
        mock_get.return_value = mock_response
        
        response = client.post(
            "/api/query/function",
            json={"query": "P00000"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["function"] is None
        assert data["protein_name"] == "Unknown protein"
    
    def test_query_function_empty_input(self):
        """Test function query with empty input."""
        response = client.post(
            "/api/query/function",
            json={"query": ""}
        )
        
        assert response.status_code == 400
    
    def test_query_function_whitespace_input(self):
        """Test function query with whitespace-only input."""
        response = client.post(
            "/api/query/function",
            json={"query": "   "}
        )
        
        assert response.status_code == 400


class TestFunctionQueryFormEndpoint:
    """Test /api/query/function/form endpoint."""
    
    @patch("models.function_query.requests.get")
    def test_query_function_form_success(self, mock_get):
        """Test successful form-based function query."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_UNIPROT_RESPONSE
        mock_get.return_value = mock_response
        
        response = client.post(
            "/api/query/function/form",
            data={"query": "P12345"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["uniprot_id"] == "P12345"
    
    def test_query_function_form_empty(self):
        """Test form query with empty input."""
        response = client.post(
            "/api/query/function/form",
            data={"query": ""}
        )
        
        assert response.status_code == 400


class TestBatchQueryEndpoint:
    """Test /api/query/function/batch endpoint."""
    
    @patch("models.function_query.requests.get")
    def test_batch_query_success(self, mock_get):
        """Test successful batch query."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_UNIPROT_RESPONSE
        mock_get.return_value = mock_response
        
        response = client.post(
            "/api/query/function/batch",
            json={"queries": ["P12345", "P67890"]}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["successful"] == 2
        assert "P12345" in data["results"]
        assert "P67890" in data["results"]
    
    @patch("models.function_query.requests.get")
    def test_batch_query_partial_success(self, mock_get):
        """Test batch query with some failures."""
        def mock_get_side_effect(url, timeout):
            mock_resp = MagicMock()
            if "INVALID" in url:
                mock_resp.status_code = 404
            else:
                mock_resp.status_code = 200
                mock_resp.json.return_value = MOCK_UNIPROT_RESPONSE
            return mock_resp
        
        mock_get.side_effect = mock_get_side_effect
        
        response = client.post(
            "/api/query/function/batch",
            json={"queries": ["P12345", "INVALID123"]}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["successful"] == 1
    
    def test_batch_query_empty_list(self):
        """Test batch query with empty list."""
        response = client.post(
            "/api/query/function/batch",
            json={"queries": []}
        )
        
        assert response.status_code == 400
    
    @patch("models.function_query.requests.get")
    def test_batch_query_deduplication(self, mock_get):
        """Test that duplicate IDs are deduplicated."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_UNIPROT_RESPONSE
        mock_get.return_value = mock_response
        
        response = client.post(
            "/api/query/function/batch",
            json={"queries": ["P12345", "P12345", "P12345"]}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1  # Duplicates removed
        assert mock_get.call_count == 1


class TestFileUploadEndpoint:
    """Test /api/query/function/file endpoint."""
    
    @patch("models.function_query.requests.get")
    def test_file_upload_success(self, mock_get):
        """Test successful file upload query."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_UNIPROT_RESPONSE
        mock_get.return_value = mock_response
        
        file_content = b"P12345\nP67890\n"
        
        response = client.post(
            "/api/query/function/file",
            files={"file": ("ids.txt", file_content, "text/plain")}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
    
    @patch("models.function_query.requests.get")
    def test_file_upload_with_comments(self, mock_get):
        """Test file upload with comment lines."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_UNIPROT_RESPONSE
        mock_get.return_value = mock_response
        
        file_content = b"# This is a comment\nP12345\n# Another comment\nP67890\n"
        
        response = client.post(
            "/api/query/function/file",
            files={"file": ("ids.txt", file_content, "text/plain")}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
    
    def test_file_upload_empty_file(self):
        """Test file upload with empty file."""
        file_content = b""
        
        response = client.post(
            "/api/query/function/file",
            files={"file": ("empty.txt", file_content, "text/plain")}
        )
        
        assert response.status_code == 400


class TestLegacyEndpoint:
    """Test legacy /query/function endpoint."""
    
    @patch("models.function_query.requests.get")
    def test_legacy_endpoint(self, mock_get):
        """Test legacy endpoint for backward compatibility."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_UNIPROT_RESPONSE
        mock_get.return_value = mock_response
        
        response = client.post(
            "/query/function",
            json={"query": "P12345"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestErrorHandling:
    """Test error handling scenarios."""
    
    @patch("models.function_query.requests.get")
    def test_timeout_error(self, mock_get):
        """Test timeout handling."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")
        
        response = client.post(
            "/api/query/function",
            json={"query": "P12345"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "timeout" in data["error"].lower()
    
    @patch("models.function_query.requests.get")
    def test_connection_error(self, mock_get):
        """Test connection error handling."""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        response = client.post(
            "/api/query/function",
            json={"query": "P12345"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "failed" in data["error"].lower()


class TestDocumentation:
    """Test API documentation endpoints."""
    
    def test_openapi_docs(self):
        """Test OpenAPI documentation is available."""
        response = client.get("/docs")
        assert response.status_code == 200
    
    def test_redoc(self):
        """Test ReDoc documentation is available."""
        response = client.get("/redoc")
        assert response.status_code == 200
    
    def test_openapi_schema(self):
        """Test OpenAPI schema is valid."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "paths" in data
        assert "/api/query/function" in data["paths"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
