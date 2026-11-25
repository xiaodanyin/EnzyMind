"""Tests for Sequence Info Service"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app, fetch_uniprot_data
from shared.uniprot import UniProtDownloadError

client = TestClient(app)


def test_lookup_uses_verified_shared_downloader():
    with patch('main.uniprot_json_client.fetch_json', return_value={'sequence': {'length': 20}}) as fetch:
        assert fetch_uniprot_data("P00761")["sequence"]["length"] == 20
        fetch.assert_called_once_with('P00761', capability='sequence')


def test_lookup_does_not_nest_a_second_retry_loop():
    with patch('main.uniprot_json_client.fetch_json', side_effect=UniProtDownloadError('Unavailable after bounded retries.')) as fetch:
        with pytest.raises(UniProtDownloadError):
            fetch_uniprot_data("P00761")
        assert fetch.call_count == 1


def test_lookup_does_not_retry_missing_accession():
    with patch('main.uniprot_json_client.fetch_json', side_effect=UniProtDownloadError('Not found', 'uniprot_not_found', False)) as fetch:
        assert fetch_uniprot_data("P00761") is None
        assert fetch.call_count == 1


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

    @pytest.mark.parametrize('code,status', [('uniprot_unavailable', 502), ('uniprot_invalid_accession', 422), ('uniprot_not_found', 404)])
    def test_shared_downloader_errors_preserve_http_contract(self, code, status):
        with patch('main.uniprot_json_client.fetch_json', side_effect=UniProtDownloadError('UniProt lookup unavailable.', code, False)):
            response = client.post('/api/query/sequence-info', json={'uniprot_id': 'P00698'})
        assert response.status_code == status
        assert 'UniProt' in response.json()['detail']

    @pytest.mark.parametrize("failure,status", [(httpx.ReadTimeout("timeout"), 504), (httpx.ConnectError("offline"), 502)])
    def test_remote_failures_are_actionable(self, failure, status):
        with patch("main.fetch_uniprot_data", side_effect=failure):
            response = client.post("/api/query/sequence-info", json={"uniprot_id": "P00761"})
        assert response.status_code == status
        assert "UniProt" in response.json()["detail"]

    def test_current_proxy_scheme_is_supported(self, monkeypatch):
        monkeypatch.setenv("ALL_PROXY", "socks5h://127.0.0.1:7891")
        with httpx.Client():
            pass  # The previous dependency raised ValueError before any request.
    
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


@pytest.mark.parametrize("sequence,mass", [("ACD", 307), ("AX", None)])
def test_snapshot_mass_provenance(sequence, mass):
    with patch("main.fetch_uniprot_data", return_value={"sequence": {"value": sequence}}):
        data = client.post("/api/query/sequence-info", json={"uniprot_id": "P12345"}).json()
    assert data["molWeight"] == mass
    assert data["molWeight_note"] if mass is None else "Calculated" in data["molWeight_source"]
