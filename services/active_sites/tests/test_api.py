# active_sites/tests/test_api.py
"""
Tests for Active Sites Prediction Service
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from starlette.testclient import TestClient
import io

# Import the FastAPI app
from main import app, get_predictor

# Import models for testing
from models.utils import (
    is_amino_acid_sequence,
    is_uniprot_id,
    is_fasta_content,
    clean_sequence,
    extract_sequence_from_fasta_content,
    classify_input,
)
from models.active_sites_predictor import ActiveSitesPredictor

# Create test client
client = TestClient(app)


# ============== Utility Function Tests ==============

class TestUtilityFunctions:
    """Tests for utility functions in models/utils.py"""
    
    def test_is_uniprot_id_valid_6char(self):
        """Test valid 6-character UniProt IDs."""
        assert is_uniprot_id("P42327") is True
        assert is_uniprot_id("Q9Y6K9") is True
        assert is_uniprot_id("F6KCZ5") is True
        assert is_uniprot_id("O00487") is True
    
    def test_is_uniprot_id_valid_10char(self):
        """Test valid 10-character UniProt IDs."""
        assert is_uniprot_id("A0A024R1R8") is True
        assert is_uniprot_id("A0A0A0MRZ7") is True
    
    def test_is_uniprot_id_invalid(self):
        """Test invalid UniProt IDs."""
        assert is_uniprot_id("") is False
        assert is_uniprot_id("ABC") is False
        assert is_uniprot_id("12345") is False
        assert is_uniprot_id("MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAV") is False
        assert is_uniprot_id("P4232") is False  # Too short
        assert is_uniprot_id("P423271111") is False  # Invalid format
    
    def test_is_amino_acid_sequence_valid(self):
        """Test valid amino acid sequences."""
        assert is_amino_acid_sequence("MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAV") is True
        assert is_amino_acid_sequence("ACDEFGHIKLMNPQRSTVWY") is True
        assert is_amino_acid_sequence("mktayiakqrqisfvk") is True  # lowercase
    
    def test_is_amino_acid_sequence_invalid(self):
        """Test invalid amino acid sequences."""
        assert is_amino_acid_sequence("") is False
        assert is_amino_acid_sequence("ABC") is False  # Too short
        assert is_amino_acid_sequence("P42327") is False  # Too short
        assert is_amino_acid_sequence("MKTAY1AK2RQ") is False  # Contains numbers
        assert is_amino_acid_sequence("MKTAY!AK@RQ") is False  # Contains special chars
    
    def test_is_fasta_content_valid(self):
        """Test valid FASTA content."""
        fasta = ">sp|P42327|Test\nMKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAV"
        assert is_fasta_content(fasta) is True
        
        fasta_multiline = ">sp|P42327|Test\nMKTAYIAKQRQISFVKSHFS\nRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAV"
        assert is_fasta_content(fasta_multiline) is True
    
    def test_is_fasta_content_invalid(self):
        """Test invalid FASTA content."""
        assert is_fasta_content("") is False
        assert is_fasta_content("MKTAYIAK") is False  # No header
        assert is_fasta_content(">header only") is False  # No sequence
        assert is_fasta_content("Not FASTA") is False
    
    def test_clean_sequence(self):
        """Test sequence cleaning."""
        assert clean_sequence("MKTAY IAK\nQRQ") == "MKTAYIAKQRQ"
        assert clean_sequence("mktayiak") == "MKTAYIAK"
        assert clean_sequence("") == ""
        assert clean_sequence("  MKTAY  ") == "MKTAY"
    
    def test_extract_sequence_from_fasta_content(self):
        """Test FASTA sequence extraction."""
        fasta = ">sp|P42327|Test\nMKTAYIAKQRQISFVKSHFS\nRQLEERLGLIEV"
        assert extract_sequence_from_fasta_content(fasta) == "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEV"
        assert extract_sequence_from_fasta_content("") == ""
    
    def test_classify_input_uniprot_id(self):
        """Test input classification for UniProt ID."""
        input_type, cleaned = classify_input("P42327")
        assert input_type == "uniprot_id"
        assert cleaned == "P42327"
        
        input_type, cleaned = classify_input("f6kcz5")  # lowercase
        assert input_type == "uniprot_id"
        assert cleaned == "F6KCZ5"
    
    def test_classify_input_sequence(self):
        """Test input classification for amino acid sequence."""
        seq = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAV"
        input_type, cleaned = classify_input(seq)
        assert input_type == "sequence"
        assert cleaned == seq
    
    def test_classify_input_fasta(self):
        """Test input classification for FASTA content."""
        fasta = ">test\nMKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAV"
        input_type, cleaned = classify_input(fasta)
        assert input_type == "fasta"
    
    def test_classify_input_unknown(self):
        """Test input classification for unknown content."""
        input_type, cleaned = classify_input("invalid123!@#")
        assert input_type == "unknown"


# ============== API Endpoint Tests ==============

class TestHealthEndpoint:
    """Tests for health check endpoint."""
    
    def test_health_check(self):
        """Test health check returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "active_sites"


class TestUniProtSubmitEndpoint:
    """Tests for UniProt submission endpoint."""
    
    @patch.object(ActiveSitesPredictor, 'submit_uniprot')
    def test_submit_uniprot_success(self, mock_submit):
        """Test successful UniProt submission."""
        mock_submit.return_value = {
            "success": True,
            "job_id": "test-job-123",
            "task_manager": "celery"
        }
        
        response = client.post(
            "/api/predict/active-sites/submit/uniprot",
            json={"uniprot_id": "F6KCZ5", "use_celery": True}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["job_id"] == "test-job-123"
        assert data["input_type"] == "uniprot"
    
    def test_submit_uniprot_invalid_id(self):
        """Test UniProt submission with invalid ID."""
        response = client.post(
            "/api/predict/active-sites/submit/uniprot",
            json={"uniprot_id": "invalid", "use_celery": True}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Invalid UniProt ID format" in data["error"]


class TestSequenceSubmitEndpoint:
    """Tests for sequence submission endpoint."""
    
    @patch.object(ActiveSitesPredictor, 'submit_sequence')
    def test_submit_sequence_json_success(self, mock_submit):
        """Test successful sequence submission with JSON."""
        mock_submit.return_value = {
            "success": True,
            "job_id": "seq-job-123",
            "task_manager": "celery"
        }
        
        response = client.post(
            "/api/predict/active-sites/submit/sequence",
            json={
                "aa_sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAV",
                "rxn_smiles": "CC(=O)O>>CC(=O)OC",
                "use_celery": True
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["job_id"] == "seq-job-123"
        assert data["input_type"] == "sequence"
    
    def test_submit_sequence_invalid(self):
        """Test sequence submission with invalid sequence."""
        response = client.post(
            "/api/predict/active-sites/submit/sequence",
            json={"aa_sequence": "123456", "use_celery": True}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Invalid amino acid sequence" in data["error"]
    
    @patch.object(ActiveSitesPredictor, 'submit_sequence')
    def test_submit_sequence_form_success(self, mock_submit):
        """Test successful sequence submission with form."""
        mock_submit.return_value = {
            "success": True,
            "job_id": "seq-form-job-123",
            "task_manager": "celery"
        }
        
        response = client.post(
            "/api/predict/active-sites/submit/sequence/form",
            data={
                "aa_sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAV",
                "rxn_smiles": "CC(=O)O>>CC(=O)OC",
                "use_celery": "true"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["input_type"] == "sequence"


class TestStructureSubmitEndpoint:
    """Tests for structure submission endpoint."""
    
    @patch.object(ActiveSitesPredictor, 'submit_structure')
    def test_submit_structure_success(self, mock_submit):
        """Test successful structure submission."""
        mock_submit.return_value = {
            "success": True,
            "job_id": "struct-job-123",
            "task_manager": "celery"
        }
        
        # Create a mock PDB file
        pdb_content = b"ATOM      1  N   MET A   1       0.000   0.000   0.000  1.00  0.00           N\n"
        
        response = client.post(
            "/api/predict/active-sites/submit/structure",
            files={"pdb_file": ("test.pdb", pdb_content, "application/octet-stream")},
            data={"rxn_smiles": "CC(=O)O>>CC(=O)OC", "use_celery": "true"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["job_id"] == "struct-job-123"
        assert data["input_type"] == "structure"


class TestJobStatusEndpoint:
    """Tests for job status endpoint."""
    
    @patch.object(ActiveSitesPredictor, 'get_job_status')
    def test_get_job_status_pending(self, mock_get_status):
        """Test getting job status when pending."""
        mock_get_status.return_value = {
            "success": True,
            "status": "pending",
            "data": {"status": "pending", "progress": 0}
        }
        
        response = client.get("/api/predict/active-sites/job/test-job-123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "pending"
    
    @patch.object(ActiveSitesPredictor, 'get_job_status')
    def test_get_job_status_completed(self, mock_get_status):
        """Test getting job status when completed."""
        mock_get_status.return_value = {
            "success": True,
            "status": "completed",
            "data": {"status": "completed"}
        }
        
        response = client.get("/api/predict/active-sites/job/test-job-123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "completed"
    
    @patch.object(ActiveSitesPredictor, 'get_job_status')
    def test_get_job_status_error(self, mock_get_status):
        """Test getting job status with error."""
        mock_get_status.return_value = {
            "success": False,
            "error": "Job not found"
        }
        
        response = client.get("/api/predict/active-sites/job/nonexistent-job")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not found" in data["error"]


class TestJobResultsEndpoint:
    """Tests for job results endpoint."""
    
    @patch.object(ActiveSitesPredictor, 'get_job_results')
    @patch.object(ActiveSitesPredictor, 'format_results_to_markdown')
    def test_get_job_results_success(self, mock_format, mock_get_results):
        """Test getting job results."""
        mock_get_results.return_value = {
            "success": True,
            "data": {
                "results": [
                    [0, "rxn_smiles", [[1, "M", "#FF0000", "Active Site", 0.95]]]
                ]
            }
        }
        mock_format.return_value = "| Residue Index | Residue Name | Active Type | Confidence |\n|---|---|---|---|"
        
        response = client.get("/api/predict/active-sites/results/test-job-123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "results" in data["data"]
        assert "markdown" in data
    
    @patch.object(ActiveSitesPredictor, 'get_job_results')
    def test_get_job_results_error(self, mock_get_results):
        """Test getting job results with error."""
        mock_get_results.return_value = {
            "success": False,
            "error": "Job not completed yet"
        }
        
        response = client.get("/api/predict/active-sites/results/incomplete-job")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False


class TestSyncPredictEndpoints:
    """Tests for synchronous prediction endpoints."""
    
    @patch.object(ActiveSitesPredictor, 'submit_uniprot')
    @patch.object(ActiveSitesPredictor, 'wait_for_completion')
    @patch.object(ActiveSitesPredictor, 'format_results_to_markdown')
    def test_predict_sync_success(self, mock_format, mock_wait, mock_submit):
        """Test synchronous prediction success."""
        mock_submit.return_value = {"success": True, "job_id": "job-123"}
        mock_wait.return_value = {
            "success": True,
            "data": {"results": [[1, "M", "#FF0000", "Active Site", 0.95]]}
        }
        mock_format.return_value = "| Residue Index | Residue Name | Active Type | Confidence |\n|---|---|---|---|"
        
        response = client.post(
            "/api/predict/active-sites",
            json={"uniprot_id": "F6KCZ5", "use_celery": True}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "Residue Index" in data["result"]
    
    def test_predict_sync_invalid_uniprot(self):
        """Test synchronous prediction with invalid UniProt ID."""
        response = client.post(
            "/api/predict/active-sites",
            json={"uniprot_id": "invalid", "use_celery": True}
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "[ERROR]" in data["result"]
    
    @patch.object(ActiveSitesPredictor, 'submit_sequence')
    @patch.object(ActiveSitesPredictor, 'wait_for_completion')
    @patch.object(ActiveSitesPredictor, 'format_results_to_markdown')
    def test_predict_sequence_sync_success(self, mock_format, mock_wait, mock_submit):
        """Test synchronous sequence prediction success."""
        mock_submit.return_value = {"success": True, "job_id": "job-456"}
        mock_wait.return_value = {"success": True, "data": {"results": []}}
        mock_format.return_value = "No active sites predicted."
        
        response = client.post(
            "/api/predict/active-sites/sequence",
            data={
                "aa_sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAV",
                "use_celery": "true"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "result" in data


class TestAutoDetectEndpoint:
    """Tests for auto-detect input type endpoint."""
    
    @patch.object(ActiveSitesPredictor, 'submit_uniprot')
    def test_auto_detect_uniprot(self, mock_submit):
        """Test auto-detect with UniProt ID."""
        mock_submit.return_value = {
            "success": True,
            "job_id": "auto-job-123",
            "task_manager": "celery"
        }
        
        response = client.post(
            "/api/predict/active-sites/auto",
            data={"input_data": "F6KCZ5", "use_celery": "true"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["input_type"] == "uniprot"
    
    @patch.object(ActiveSitesPredictor, 'submit_sequence')
    def test_auto_detect_sequence(self, mock_submit):
        """Test auto-detect with sequence."""
        mock_submit.return_value = {
            "success": True,
            "job_id": "auto-seq-job-123",
            "task_manager": "celery"
        }
        
        response = client.post(
            "/api/predict/active-sites/auto",
            data={
                "input_data": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAV",
                "use_celery": "true"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["input_type"] == "sequence"
    
    def test_auto_detect_invalid(self):
        """Test auto-detect with invalid input."""
        response = client.post(
            "/api/predict/active-sites/auto",
            data={"input_data": "12345!@#$%", "use_celery": "true"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Could not determine input type" in data["error"]


class TestLegacyEndpoint:
    """Tests for legacy backward-compatible endpoint."""
    
    @patch.object(ActiveSitesPredictor, 'submit_uniprot')
    @patch.object(ActiveSitesPredictor, 'wait_for_completion')
    @patch.object(ActiveSitesPredictor, 'format_results_to_markdown')
    def test_legacy_endpoint(self, mock_format, mock_wait, mock_submit):
        """Test legacy endpoint works correctly."""
        mock_submit.return_value = {"success": True, "job_id": "legacy-job-123"}
        mock_wait.return_value = {"success": True, "data": {"results": []}}
        mock_format.return_value = "No active sites predicted."
        
        response = client.post(
            "/api/query/active-sites",
            json={"uniprot_id": "F6KCZ5"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "result" in data


# ============== Predictor Model Tests ==============

class TestActiveSitesPredictor:
    """Tests for ActiveSitesPredictor class."""
    
    def test_predictor_initialization(self):
        """Test predictor initialization with default values."""
        predictor = ActiveSitesPredictor()
        assert predictor.api_base == "https://cadd.drugflow.com/easifa/api"
        assert predictor.api_bases == (
            "https://cadd.drugflow.com/easifa/api",
            "https://cadd.zju.edu.cn/easifa/api",
            "https://cadd.iddd.group/easifa/api",
        )
        assert predictor.timeout == 30
    
    def test_predictor_custom_initialization(self):
        """Test predictor initialization with custom values."""
        predictor = ActiveSitesPredictor(
            api_base="http://custom.api",
            timeout=60
        )
        assert predictor.api_base == "http://custom.api"
        assert predictor.timeout == 60
    
    @patch('requests.post')
    def test_submit_uniprot_success(self, mock_post):
        """Test UniProt submission success."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "job_id": "uniprot-job-123",
            "task_manager": "celery"
        }
        mock_post.return_value = mock_response
        
        predictor = ActiveSitesPredictor()
        result = predictor.submit_uniprot("F6KCZ5")
        
        assert result["success"] is True
        assert result["job_id"] == "uniprot-job-123"
        
        # Verify correct API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "from_uniprot" in call_args[0][0]
        assert call_args[1]["json"]["uniprot_id"] == "F6KCZ5"

    @patch('requests.post')
    def test_submit_uniprot_falls_back_in_order(self, mock_post):
        """Test fallback from the primary through both backup endpoints."""
        unavailable_response = Mock()
        unavailable_response.status_code = 503
        unavailable_response.headers = {}
        unavailable_response.text = "temporarily unavailable"

        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "job_id": "backup-job-123",
            "task_manager": "celery"
        }

        mock_post.side_effect = [
            Exception("primary unavailable"),
            unavailable_response,
            success_response,
        ]

        predictor = ActiveSitesPredictor()
        result = predictor.submit_uniprot("F6KCZ5")

        assert result["success"] is True
        assert result["job_id"] == "backup-job-123"
        assert [call.args[0] for call in mock_post.call_args_list] == [
            "https://cadd.drugflow.com/easifa/api/from_uniprot",
            "https://cadd.zju.edu.cn/easifa/api/from_uniprot",
            "https://cadd.iddd.group/easifa/api/from_uniprot",
        ]
        assert predictor.api_base == "https://cadd.iddd.group/easifa/api"

    @patch('requests.get')
    def test_job_status_prefers_last_successful_endpoint(self, mock_get):
        """Test polling stays on the endpoint that accepted the async job."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "completed"}
        mock_get.return_value = mock_response

        predictor = ActiveSitesPredictor()
        predictor.api_base = "https://cadd.zju.edu.cn/easifa/api"
        result = predictor.get_job_status("backup-job-123")

        assert result["success"] is True
        assert mock_get.call_args.args[0] == (
            "https://cadd.zju.edu.cn/easifa/api/job/backup-job-123"
        )
    
    @patch('requests.post')
    def test_submit_sequence_success(self, mock_post):
        """Test sequence submission success."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "job_id": "seq-job-123",
            "task_manager": "celery"
        }
        mock_post.return_value = mock_response
        
        predictor = ActiveSitesPredictor()
        result = predictor.submit_sequence(
            "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAV",
            rxn_smiles="CC(=O)O>>CC(=O)OC"
        )
        
        assert result["success"] is True
        assert result["job_id"] == "seq-job-123"
        
        # Verify correct API call (form data)
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "from_sequence" in call_args[0][0]

    @patch('requests.post')
    def test_submit_uniprot_non_json_response(self, mock_post):
        """Test UniProt submission reports a readable error for non-JSON responses."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = "<html>temporary upstream error</html>"
        mock_response.url = "https://cadd.drugflow.com/easifa/api/from_uniprot"
        mock_response.json.side_effect = ValueError("Expecting value: line 1 column 1")
        mock_post.return_value = mock_response

        predictor = ActiveSitesPredictor()
        result = predictor.submit_uniprot("F6KCZ5")

        assert result["success"] is False
        assert "Expected JSON from EasIFA" in result["error"]
        assert "text/html" in result["error"]
    
    @patch('requests.post')
    def test_submit_structure_success(self, mock_post):
        """Test structure submission success."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "job_id": "struct-job-123",
            "task_manager": "celery"
        }
        mock_post.return_value = mock_response
        
        predictor = ActiveSitesPredictor()
        
        # Create a temporary file for testing
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pdb', delete=False) as f:
            f.write("ATOM      1  N   MET A   1       0.000   0.000   0.000  1.00  0.00           N\n")
            temp_path = f.name
        
        try:
            result = predictor.submit_structure(temp_path)
            assert result["success"] is True
            assert result["job_id"] == "struct-job-123"
        finally:
            import os
            os.unlink(temp_path)
    
    @patch('requests.get')
    def test_get_job_status(self, mock_get):
        """Test job status retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "completed"}
        mock_get.return_value = mock_response
        
        predictor = ActiveSitesPredictor()
        result = predictor.get_job_status("test-job-123")
        
        assert result["success"] is True
        assert result["status"] == "completed"
        
        # Verify correct API call
        mock_get.assert_called_once()
        assert "job/test-job-123" in mock_get.call_args[0][0]
    
    @patch('requests.get')
    def test_get_job_results(self, mock_get):
        """Test job results retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [[1, "M", "#FF0000", "Active Site", 0.95]]
        }
        mock_get.return_value = mock_response
        
        predictor = ActiveSitesPredictor()
        result = predictor.get_job_results("test-job-123")
        
        assert result["success"] is True
        assert "results" in result["data"]
        
        # Verify correct API call
        mock_get.assert_called_once()
        assert "results/test-job-123" in mock_get.call_args[0][0]
    
    @patch.object(ActiveSitesPredictor, 'get_job_status')
    @patch.object(ActiveSitesPredictor, 'get_job_results')
    def test_wait_for_completion_success(self, mock_results, mock_status):
        """Test wait for completion success."""
        mock_status.return_value = {"success": True, "status": "completed"}
        mock_results.return_value = {
            "success": True,
            "data": {"results": [[1, "M", "#FF0000", "Active Site", 0.95]]}
        }
        
        predictor = ActiveSitesPredictor()
        result = predictor.wait_for_completion("test-job-123", timeout=10, poll_interval=0.1)
        
        assert result["success"] is True
        assert "results" in result["data"]
    
    @patch.object(ActiveSitesPredictor, 'get_job_status')
    def test_wait_for_completion_timeout(self, mock_status):
        """Test wait for completion timeout."""
        mock_status.return_value = {"success": True, "status": "pending"}
        
        predictor = ActiveSitesPredictor()
        result = predictor.wait_for_completion("test-job-123", timeout=0.5, poll_interval=0.1)
        
        assert result["success"] is False
        assert "timed out" in result["error"].lower()
    
    @patch.object(ActiveSitesPredictor, 'get_job_status')
    def test_wait_for_completion_failed(self, mock_status):
        """Test wait for completion when job fails."""
        mock_status.return_value = {"success": True, "status": "failed"}
        
        predictor = ActiveSitesPredictor()
        result = predictor.wait_for_completion("test-job-123", timeout=10, poll_interval=0.1)
        
        assert result["success"] is False
        assert "failed" in result["error"].lower()
    
    def test_format_results_to_markdown_empty(self):
        """Test markdown formatting with empty results."""
        predictor = ActiveSitesPredictor()
        result = predictor.format_results_to_markdown({})
        assert "No active sites" in result or result == "No active sites predicted."
    
    def test_format_results_to_markdown_with_data(self):
        """Test markdown formatting with actual data."""
        predictor = ActiveSitesPredictor()
        data = {
            "results": [
                [0, "CC(=O)O>>CC(=O)OC", [
                    [1, "M", "#FF0000", "Active Site", 0.95],
                    [5, "K", "#00FF00", "Binding Site", 0.88]
                ]]
            ]
        }
        result = predictor.format_results_to_markdown(data)
        
        assert "Residue Index" in result
        assert "Residue Name" in result
        assert "Active Type" in result
        assert "Confidence" in result


# ============== Client Tests ==============

class TestActiveSitesClient:
    """Tests for ActiveSitesClient class."""
    
    def test_client_initialization(self):
        """Test client initialization."""
        from client import ActiveSitesClient
        
        client = ActiveSitesClient()
        assert client.base_url == "http://localhost:18907"
        
        client = ActiveSitesClient("http://custom:8000/")
        assert client.base_url == "http://custom:8000"
    
    @patch('requests.get')
    def test_client_health_check(self, mock_get):
        """Test client health check."""
        from client import ActiveSitesClient
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy", "service": "active_sites"}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        client = ActiveSitesClient()
        result = client.health_check()
        
        assert result["status"] == "healthy"
    
    @patch('requests.post')
    def test_client_submit_uniprot(self, mock_post):
        """Test client UniProt submission."""
        from client import ActiveSitesClient
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "job_id": "test-job-123",
            "input_type": "uniprot"
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        client = ActiveSitesClient()
        result = client.submit_uniprot("F6KCZ5")
        
        assert result["success"] is True
        assert result["job_id"] == "test-job-123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
