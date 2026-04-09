# structure_predict/conftest.py
"""
Pytest configuration and fixtures for structure prediction service tests.
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
def sample_sequence():
    """Sample amino acid sequence."""
    return "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"


@pytest.fixture
def sample_uniprot_id():
    """Sample UniProt ID."""
    return "P12345"


@pytest.fixture
def sample_fasta():
    """Sample FASTA content."""
    return """>test_protein
MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"""


@pytest.fixture
def invalid_sequence():
    """Invalid sequence with non-amino acid characters."""
    return "INVALID123SEQUENCE!!!@@##"


@pytest.fixture
def empty_sequence():
    """Empty sequence."""
    return ""
