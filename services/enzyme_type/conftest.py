# enzyme_type/conftest.py
"""
Pytest configuration and fixtures for enzyme type service tests.
"""

import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add service directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def sample_reaction():
    """Sample reaction SMILES."""
    return "CC(=O)O>>CCO"


@pytest.fixture
def sample_reaction_complex():
    """Complex reaction SMILES."""
    return "CC(=O)OCC>>CC(=O)O.CCO"


@pytest.fixture
def invalid_reaction():
    """Invalid reaction string."""
    return "invalid-reaction-format"


@pytest.fixture
def empty_reaction():
    """Empty reaction string."""
    return ""


@pytest.fixture
def mock_api_response():
    """Mock response from RetroPlanner API."""
    return {
        "results": {
            "recommended enzyme type": [["1.1.1.1", "1.1.1.2", "1.1.1.3"]],
            "confidence": [[0.95, 0.88, 0.75]]
        }
    }


@pytest.fixture
def mock_empty_api_response():
    """Mock empty response from RetroPlanner API."""
    return {
        "results": {
            "recommended enzyme type": [[]],
            "confidence": [[]]
        }
    }
