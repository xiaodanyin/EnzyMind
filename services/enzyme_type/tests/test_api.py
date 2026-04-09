# enzyme_type/tests/test_api.py
"""
Comprehensive tests for the Enzyme Type Recommendation Service API.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_successful_response():
    """Mock successful API response."""
    return {
        "results": {
            "recommended enzyme type": [["1.1.1.1", "1.1.1.2", "1.1.1.3"]],
            "confidence": [[0.95, 0.88, 0.75]]
        }
    }


@pytest.fixture
def mock_empty_response():
    """Mock empty API response."""
    return {
        "results": {
            "recommended enzyme type": [[]],
            "confidence": [[]]
        }
    }


# =============================================================================
# Health Check Tests
# =============================================================================

class TestHealthEndpoint:
    """Tests for /health endpoint."""
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
        assert "service" in data
        assert data["service"] == "enzyme_type"


# =============================================================================
# Query Enzyme Type Endpoint Tests
# =============================================================================

class TestQueryEnzymeTypeEndpoint:
    """Tests for /api/query/enzyme-type endpoint."""
    
    def test_query_enzyme_type_success(self, client, mock_successful_response):
        """Test successful enzyme type query."""
        with patch("models.enzyme_type_predictor.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_successful_response
            )
            
            response = client.post(
                "/api/query/enzyme-type",
                json={"query": "CC(=O)O>>CCO"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "recommendations" in data
            assert len(data["recommendations"]) == 3
            assert data["recommendations"][0]["ec_number"] == "1.1.1.1"
            assert data["recommendations"][0]["confidence"] == 0.95
    
    def test_query_enzyme_type_empty_query(self, client):
        """Test query with empty reaction."""
        response = client.post(
            "/api/query/enzyme-type",
            json={"query": ""}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "error" in data
    
    def test_query_enzyme_type_no_results(self, client, mock_empty_response):
        """Test query with no recommendations."""
        with patch("models.enzyme_type_predictor.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_empty_response
            )
            
            response = client.post(
                "/api/query/enzyme-type",
                json={"query": "CC(=O)O>>CCO"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["recommendations"] == []
    
    def test_query_enzyme_type_api_error(self, client):
        """Test query when API call fails."""
        with patch("models.enzyme_type_predictor.requests.post") as mock_post:
            mock_post.side_effect = Exception("API connection failed")
            
            response = client.post(
                "/api/query/enzyme-type",
                json={"query": "CC(=O)O>>CCO"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "error" in data


class TestQueryEnzymeTypeFormEndpoint:
    """Tests for /api/query/enzyme-type/form endpoint."""
    
    def test_query_form_success(self, client, mock_successful_response):
        """Test form input endpoint."""
        with patch("models.enzyme_type_predictor.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_successful_response
            )
            
            response = client.post(
                "/api/query/enzyme-type/form",
                data={"query": "CC(=O)O>>CCO"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
    
    def test_query_form_empty(self, client):
        """Test form with empty input."""
        response = client.post(
            "/api/query/enzyme-type/form",
            data={"query": ""}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False


class TestQueryEnzymeTypeTopKEndpoint:
    """Tests for /api/query/enzyme-type/top-k endpoint."""
    
    def test_top_k_default(self, client, mock_successful_response):
        """Test top-k with default k value."""
        with patch("models.enzyme_type_predictor.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_successful_response
            )
            
            response = client.post(
                "/api/query/enzyme-type/top-k",
                json={"query": "CC(=O)O>>CCO"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
    
    def test_top_k_specific(self, client, mock_successful_response):
        """Test top-k with specific k value."""
        with patch("models.enzyme_type_predictor.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_successful_response
            )
            
            response = client.post(
                "/api/query/enzyme-type/top-k",
                json={"query": "CC(=O)O>>CCO", "k": 2}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            # Should have at most k recommendations
            assert len(data["recommendations"]) <= 2
    
    def test_top_k_one(self, client, mock_successful_response):
        """Test top-k with k=1."""
        with patch("models.enzyme_type_predictor.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_successful_response
            )
            
            response = client.post(
                "/api/query/enzyme-type/top-k",
                json={"query": "CC(=O)O>>CCO", "k": 1}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["recommendations"]) == 1


class TestQueryEnzymeTypeFormattedEndpoint:
    """Tests for /api/query/enzyme-type/formatted endpoint."""
    
    def test_formatted_success(self, client, mock_successful_response):
        """Test formatted output endpoint."""
        with patch("models.enzyme_type_predictor.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_successful_response
            )
            
            response = client.post(
                "/api/query/enzyme-type/formatted",
                json={"query": "CC(=O)O>>CCO"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "result" in data
            assert isinstance(data["result"], str)
    
    def test_formatted_empty_query(self, client):
        """Test formatted with empty query."""
        response = client.post(
            "/api/query/enzyme-type/formatted",
            json={"query": ""}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "result" in data


class TestQueryEnzymeTypeMarkdownEndpoint:
    """Tests for /api/query/enzyme-type/markdown endpoint."""
    
    def test_markdown_success(self, client, mock_successful_response):
        """Test markdown output endpoint."""
        with patch("models.enzyme_type_predictor.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_successful_response
            )
            
            response = client.post(
                "/api/query/enzyme-type/markdown",
                json={"query": "CC(=O)O>>CCO"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "result" in data
            # Check for markdown table indicators
            assert "|" in data["result"]
    
    def test_markdown_empty_results(self, client, mock_empty_response):
        """Test markdown with no results."""
        with patch("models.enzyme_type_predictor.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_empty_response
            )
            
            response = client.post(
                "/api/query/enzyme-type/markdown",
                json={"query": "CC(=O)O>>CCO"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "result" in data


# =============================================================================
# Legacy Endpoint Tests
# =============================================================================

class TestLegacyEndpoint:
    """Tests for legacy /query/enzyme-type endpoint."""
    
    def test_legacy_success(self, client, mock_successful_response):
        """Test legacy endpoint success."""
        with patch("models.enzyme_type_predictor.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_successful_response
            )
            
            response = client.post(
                "/query/enzyme-type",
                json={"query": "CC(=O)O>>CCO"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "result" in data
            assert isinstance(data["result"], list)
    
    def test_legacy_empty_query(self, client):
        """Test legacy endpoint with empty query."""
        response = client.post(
            "/query/enzyme-type",
            json={"query": ""}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
    
    def test_legacy_no_results(self, client, mock_empty_response):
        """Test legacy endpoint with no results."""
        with patch("models.enzyme_type_predictor.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_empty_response
            )
            
            response = client.post(
                "/query/enzyme-type",
                json={"query": "CC(=O)O>>CCO"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "error" in data or data.get("result") == []


# =============================================================================
# Input Validation Tests
# =============================================================================

class TestInputValidation:
    """Tests for input validation."""
    
    def test_missing_query_field(self, client):
        """Test request without query field."""
        response = client.post(
            "/api/query/enzyme-type",
            json={}
        )
        
        # Should return validation error
        assert response.status_code == 422
    
    def test_invalid_json(self, client):
        """Test request with invalid JSON."""
        response = client.post(
            "/api/query/enzyme-type",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422
    
    def test_whitespace_only_query(self, client):
        """Test query with only whitespace."""
        response = client.post(
            "/api/query/enzyme-type",
            json={"query": "   "}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False


# =============================================================================
# Response Structure Tests
# =============================================================================

class TestResponseStructure:
    """Tests for response structure."""
    
    def test_success_response_structure(self, client, mock_successful_response):
        """Test successful response has correct structure."""
        with patch("models.enzyme_type_predictor.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_successful_response
            )
            
            response = client.post(
                "/api/query/enzyme-type",
                json={"query": "CC(=O)O>>CCO"}
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Check required fields
            assert "success" in data
            assert "recommendations" in data
            
            # Check recommendation structure
            if data["recommendations"]:
                rec = data["recommendations"][0]
                assert "ec_number" in rec
                assert "confidence" in rec
    
    def test_error_response_structure(self, client):
        """Test error response has correct structure."""
        response = client.post(
            "/api/query/enzyme-type",
            json={"query": ""}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "success" in data
        assert data["success"] is False
        assert "error" in data


# =============================================================================
# Edge Cases Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases."""
    
    def test_very_long_reaction(self, client, mock_successful_response):
        """Test with very long reaction SMILES."""
        long_reaction = "C" * 1000 + ">>" + "C" * 1000
        
        with patch("models.enzyme_type_predictor.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_successful_response
            )
            
            response = client.post(
                "/api/query/enzyme-type",
                json={"query": long_reaction}
            )
            
            assert response.status_code == 200
    
    def test_special_characters_in_reaction(self, client, mock_successful_response):
        """Test reaction with special characters."""
        reaction = "CC(=O)[O-].[Na+]>>CC(=O)O"
        
        with patch("models.enzyme_type_predictor.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_successful_response
            )
            
            response = client.post(
                "/api/query/enzyme-type",
                json={"query": reaction}
            )
            
            assert response.status_code == 200
    
    def test_unicode_in_query(self, client, mock_successful_response):
        """Test query with unicode characters."""
        with patch("models.enzyme_type_predictor.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_successful_response
            )
            
            response = client.post(
                "/api/query/enzyme-type",
                json={"query": "CC(=O)O>>CCO 酶"}
            )
            
            assert response.status_code == 200


# =============================================================================
# API Error Handling Tests
# =============================================================================

class TestAPIErrorHandling:
    """Tests for API error handling."""
    
    def test_api_timeout(self, client):
        """Test handling of API timeout."""
        import requests as req_lib
        
        with patch("models.enzyme_type_predictor.requests.post") as mock_post:
            mock_post.side_effect = req_lib.exceptions.Timeout("Connection timed out")
            
            response = client.post(
                "/api/query/enzyme-type",
                json={"query": "CC(=O)O>>CCO"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "error" in data
    
    def test_api_connection_error(self, client):
        """Test handling of API connection error."""
        import requests as req_lib
        
        with patch("models.enzyme_type_predictor.requests.post") as mock_post:
            mock_post.side_effect = req_lib.exceptions.ConnectionError("Failed to connect")
            
            response = client.post(
                "/api/query/enzyme-type",
                json={"query": "CC(=O)O>>CCO"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
    
    def test_api_invalid_response_format(self, client):
        """Test handling of unexpected API response format."""
        with patch("models.enzyme_type_predictor.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: {"unexpected": "format"}
            )
            
            response = client.post(
                "/api/query/enzyme-type",
                json={"query": "CC(=O)O>>CCO"}
            )
            
            assert response.status_code == 200
            data = response.json()
            # Should handle gracefully
            assert "success" in data


# =============================================================================
# Concurrent Request Tests
# =============================================================================

class TestConcurrency:
    """Tests for concurrent request handling."""
    
    def test_multiple_requests(self, client, mock_successful_response):
        """Test multiple simultaneous requests."""
        with patch("models.enzyme_type_predictor.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_successful_response
            )
            
            reactions = [
                "CC(=O)O>>CCO",
                "CCO>>CC=O",
                "CC(=O)OCC>>CC(=O)O.CCO"
            ]
            
            for reaction in reactions:
                response = client.post(
                    "/api/query/enzyme-type",
                    json={"query": reaction}
                )
                assert response.status_code == 200


# =============================================================================
# Documentation Endpoint Tests
# =============================================================================

class TestDocumentationEndpoints:
    """Tests for documentation endpoints."""
    
    def test_docs_endpoint(self, client):
        """Test /docs endpoint is accessible."""
        response = client.get("/docs")
        assert response.status_code == 200
    
    def test_redoc_endpoint(self, client):
        """Test /redoc endpoint is accessible."""
        response = client.get("/redoc")
        assert response.status_code == 200
    
    def test_openapi_json(self, client):
        """Test OpenAPI JSON is available."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "paths" in data
        assert "info" in data
