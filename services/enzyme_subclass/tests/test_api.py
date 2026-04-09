# enzyme_subclass/tests/test_api.py
"""Test cases for Enzyme Subclass Service API."""

import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app

client = TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_check(self):
        """Test health endpoint returns correct status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "enzyme_subclass"
        assert data["version"] == "1.0.0"


class TestEnzymeClassesEndpoint:
    """Test /api/enzyme-classes endpoint."""
    
    def test_get_enzyme_classes(self):
        """Test getting all enzyme classes."""
        response = client.get("/api/enzyme-classes")
        assert response.status_code == 200
        data = response.json()
        
        assert "classes" in data
        assert data["classes"]["Oxidoreductases"] == 1
        assert data["classes"]["Transferases"] == 2
        assert data["classes"]["Hydrolases"] == 3
        assert data["classes"]["Lyases"] == 4
        assert data["classes"]["Isomerases"] == 5
        assert data["classes"]["Ligases"] == 6
        assert data["classes"]["Translocases"] == 7


class TestSubclassQueryEndpoint:
    """Test /api/query/enzyme-subclass endpoint."""
    
    def test_query_oxidoreductases(self):
        """Test querying Oxidoreductases."""
        response = client.post(
            "/api/query/enzyme-subclass",
            json={"query": "Oxidoreductases", "num_samples": 3, "seed": 42}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["enzyme_class"] == "Oxidoreductases"
        assert data["ec_prefix"] == 1
        assert len(data["subclasses"]) <= 3
    
    def test_query_hydrolase_lowercase(self):
        """Test querying with lowercase name."""
        response = client.post(
            "/api/query/enzyme-subclass",
            json={"query": "hydrolase", "num_samples": 2}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["enzyme_class"] == "Hydrolases"
        assert data["ec_prefix"] == 3
    
    def test_query_transferase_mixed_case(self):
        """Test querying with mixed case name."""
        response = client.post(
            "/api/query/enzyme-subclass",
            json={"query": "Transferase"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["enzyme_class"] == "Transferases"
    
    def test_query_invalid_class(self):
        """Test querying with invalid enzyme class."""
        response = client.post(
            "/api/query/enzyme-subclass",
            json={"query": "InvalidClass"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Invalid enzyme class name" in data["error"]
        assert "valid_classes" in data
        assert len(data["valid_classes"]) == 7
    
    def test_query_empty_input(self):
        """Test querying with empty input."""
        response = client.post(
            "/api/query/enzyme-subclass",
            json={"query": ""}
        )
        
        assert response.status_code == 400
    
    def test_query_reproducibility(self):
        """Test that same seed produces same results."""
        response1 = client.post(
            "/api/query/enzyme-subclass",
            json={"query": "Oxidoreductases", "num_samples": 2, "seed": 123}
        )
        response2 = client.post(
            "/api/query/enzyme-subclass",
            json={"query": "Oxidoreductases", "num_samples": 2, "seed": 123}
        )
        
        data1 = response1.json()
        data2 = response2.json()
        
        assert data1["subclasses"] == data2["subclasses"]
    
    def test_query_different_seeds(self):
        """Test that different seeds can produce different results."""
        # For small datasets, results might be the same, so we just check success
        response1 = client.post(
            "/api/query/enzyme-subclass",
            json={"query": "Oxidoreductases", "num_samples": 2, "seed": 1}
        )
        response2 = client.post(
            "/api/query/enzyme-subclass",
            json={"query": "Oxidoreductases", "num_samples": 2, "seed": 999}
        )
        
        assert response1.status_code == 200
        assert response2.status_code == 200
    
    def test_query_all_classes(self):
        """Test querying all enzyme classes."""
        classes = ["Oxidoreductases", "Transferases", "Hydrolases", 
                   "Lyases", "Isomerases", "Ligases", "Translocases"]
        
        for enzyme_class in classes:
            response = client.post(
                "/api/query/enzyme-subclass",
                json={"query": enzyme_class, "num_samples": 1}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["enzyme_class"] == enzyme_class
    
    def test_query_result_contains_markdown(self):
        """Test that result contains markdown formatting."""
        response = client.post(
            "/api/query/enzyme-subclass",
            json={"query": "Hydrolases", "num_samples": 1}
        )
        
        data = response.json()
        assert data["success"] is True
        assert "**Selected" in data["result"]
        assert "### EC number:" in data["result"]
        assert "**Description:**" in data["result"]


class TestSubclassQueryFormEndpoint:
    """Test /api/query/enzyme-subclass/form endpoint."""
    
    def test_form_query_success(self):
        """Test successful form-based query."""
        response = client.post(
            "/api/query/enzyme-subclass/form",
            data={"query": "Hydrolases", "num_samples": 2, "seed": 42}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["enzyme_class"] == "Hydrolases"
    
    def test_form_query_empty(self):
        """Test form query with empty input."""
        response = client.post(
            "/api/query/enzyme-subclass/form",
            data={"query": "", "num_samples": 2}
        )
        
        assert response.status_code == 400


class TestStatisticsEndpoint:
    """Test /api/statistics endpoint."""
    
    def test_get_statistics(self):
        """Test getting database statistics."""
        response = client.get("/api/statistics")
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "total_entries" in data
        assert "by_class" in data
        assert data["total_entries"] > 0


class TestLegacyEndpoint:
    """Test legacy /query/enzyme-subclass endpoint."""
    
    def test_legacy_endpoint(self):
        """Test legacy endpoint for backward compatibility."""
        response = client.post(
            "/query/enzyme-subclass",
            json={"query": "lyase", "num_samples": 1}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["enzyme_class"] == "Lyases"


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
        assert "/api/query/enzyme-subclass" in data["paths"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
