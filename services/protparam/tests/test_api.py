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
        assert response.status_code == 422
        data = response.json()
        assert data["error_code"] == "invalid_input" and data["result"]


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

def test_structured_composition_and_legacy_json(client, mock_expasy_response):
    with patch('models.protparam_analyzer.send_expasy_param_request',return_value=mock_expasy_response):
        response=client.post('/query/protein-physchem',json={'query':'ACDA'})
    assert response.status_code == 200
    composition={r['residue']:r for r in response.json()['data']['amino_acid_composition']}
    assert composition['A']['count'] == 2
    assert composition['A']['percent'] == 50
    assert sum(r['count'] for r in composition.values()) == 4
    assert composition['W']['count'] == 0


def test_invalid_and_multiple_fasta_not_silently_cleaned():
    from models.protparam_analyzer import classify_input_v2
    for raw in ('ACD1*','>one\nACD\n>two\nEFG'):
        with pytest.raises(ValueError): classify_input_v2(raw)


def test_uniprot_input_uses_validated_shared_download(client, mock_expasy_response):
    from types import SimpleNamespace
    from models.protparam_analyzer import classify_input_v2
    with patch('models.protparam_analyzer.uniprot_client.fetch', return_value=SimpleNamespace(sequence='ACDEFGHIK')) as fetch:
        assert classify_input_v2('P00761') == 'ACDEFGHIK'
        fetch.assert_called_once_with('P00761')
        with patch('models.protparam_analyzer.send_expasy_param_request', return_value=mock_expasy_response):
            response = client.post('/query/protein-physchem', json={'query': 'P00761'})
    assert response.status_code == 200
    assert 'ProtParam' in response.json()['result']
    assert not response.json()['result'].startswith('[ERROR]')


def test_uniprot_outage_preserves_actionable_error_and_skips_expasy(client):
    from shared.uniprot import UniProtDownloadError
    with patch('models.protparam_analyzer.uniprot_client.fetch', side_effect=UniProtDownloadError('UniProt retrieval failed after bounded retries.')):
        with patch('models.protparam_analyzer.send_expasy_param_request') as expasy:
            response = client.post('/query/protein-physchem', json={'query': 'P00761'})
    assert response.json()['result'].startswith('[ERROR]')
    assert 'bounded retries' in response.json()['result']
    expasy.assert_not_called()


def test_expasy_outage_computes_published_biopython_example_and_declares_source(client):
    # Official Biopython 1.86 ProteinAnalysis worked example (independent values).
    sequence = ('MAEGEITTFTALTEKFNLPPGNYKKPKLLYCSNGGHFLRILPDGTVDGT'
                'RDRSDQHIQLQLSAESVGEVYIKSTETGQYLAMDTSGLLYGSQTPSEEC'
                'LFLERLEENHYNTYTSKKHAEKNWFVGLKKNGSCKRGPRTHYGQKAILF'
                'LPLPV')
    with patch('models.protparam_analyzer.send_expasy_param_request', return_value=None):
        result = client.post('/api/query/protein-physchem', json={'query': sequence}).json()
    assert result['success'] and result['sequence_length'] == 152
    assert result['parameters']['molecular_weight'] == 17103.16
    assert result['parameters']['theoretical_pi'] == 7.72
    assert result['parameters']['instability_index'] == 41.98
    assert result['source']['method'] == 'local_fallback'
    assert result['source']['version'] == '1.86'
    assert 'may differ slightly from ExPASy' in result['markdown']
    assert sum(row['count'] for row in result['amino_acid_composition']) == 152


def test_bad_expasy_html_and_wrong_sequence_length_are_not_saved_as_valid_remote_results(client, mock_expasy_response):
    for html in ('<html>Service unavailable</html>', mock_expasy_response):
        with patch('models.protparam_analyzer.send_expasy_param_request', return_value=html):
            result = client.post('/query/protein-physchem', json={'query': 'ACDE'}).json()
        assert result['data']['source']['method'] == 'local_fallback'
        assert result['data']['parameters']['num_amino_acids'] == 4
        assert result['data']['parameters']['molecular_weight'] == 436.44


def test_complete_expasy_output_retains_remote_values_and_source(client, mock_expasy_response):
    html = mock_expasy_response.replace('Number of amino acids: 52','Number of amino acids: 4').replace('Instability index (II)', 'The instability index (II)')
    with patch('models.protparam_analyzer.send_expasy_param_request', return_value=html):
        result = client.post('/api/query/protein-physchem', json={'query': 'ACDE'}).json()
    assert result['source']['name'] == 'ExPASy ProtParam'
    assert result['source']['method'] == 'remote'
    assert result['parameters']['molecular_weight'] == 5500.0
    assert result['parameters']['instability_index'] == 42.08
    assert result['fallback_reason'] is None
