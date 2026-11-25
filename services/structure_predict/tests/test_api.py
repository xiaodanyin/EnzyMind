# structure_predict/tests/test_api.py
"""
Comprehensive tests for the Structure Prediction Service API.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app


@pytest.fixture
def client():
    """Exercise successful route wiring without requiring actual GPU weights."""
    with patch("main.predictor") as worker:
        worker.check_config.return_value = dict(configured=True, issues=[], output_dir="/tmp/test", docker_image="test", use_gpu=False)
        worker.predict_from_input.return_value = {"success": True, "pdb_path": "/tmp/test.pdb"}
        worker.predict_from_file.return_value = worker.predict_from_input.return_value
        yield TestClient(app)


@pytest.fixture
def sample_sequence():
    """Sample amino acid sequence."""
    return "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"


@pytest.fixture
def sample_fasta():
    """Sample FASTA content."""
    return """>test_protein
MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"""


# =============================================================================
# Health Check Tests
# =============================================================================

class TestHealthEndpoint:
    """Tests for /health endpoint."""
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        with patch("main.predictor") as predictor, patch("main.backend_config", {"configured": True}):
            response = client.get("/health")
            predictor.check_config.assert_not_called()
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
        assert "service" in data
        assert data["service"] == "structure_predict"
    
    def test_health_check_includes_config_status(self, client):
        """Test health check includes ESMFold config status."""
        response = client.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert data["docker_backend"] is False
        assert data["status"] == "unavailable"


# =============================================================================
# Configuration Endpoint Tests
# =============================================================================

class TestConfigEndpoint:
    """Tests for /api/config endpoint."""
    
    def test_get_config(self, client):
        """Test configuration endpoint."""
        response = client.get("/api/config")
        assert response.status_code == 200
        data = response.json()
        assert "configured" in data
        assert "issues" in data
        assert "docker_image" in data
        assert "model_cache_dir" in data
        assert "output_dir" in data
        assert "use_gpu" in data


# =============================================================================
# Structure Prediction Endpoint Tests
# =============================================================================

class TestPredictStructureEndpoint:
    """Tests for /api/predict/structure endpoint."""
    
    def test_predict_structure_empty_query(self, client):
        """Test prediction with empty query."""
        response = client.post(
            "/api/predict/structure",
            json={"query": ""}
        )
        
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert "error" in data
    
    def test_predict_structure_missing_query(self, client):
        """Test prediction without query field."""
        response = client.post(
            "/api/predict/structure",
            json={}
        )
        
        # Should return validation error
        assert response.status_code == 422
    
    def test_predict_structure_whitespace_query(self, client):
        """Test prediction with whitespace-only query."""
        response = client.post(
            "/api/predict/structure",
            json={"query": "   "}
        )
        
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
    
    def test_predict_structure_with_mock(self, client, sample_sequence):
        """Test prediction with mocked predictor."""
        mock_result = {
            "success": True,
            "pdb_path": "/tmp/test.pdb",
            "static_path": "/static/pdb/query.pdb",
            "sequence": sample_sequence,
            "sequence_length": len(sample_sequence)
        }
        
        with patch("main.predictor") as mock_predictor:
            mock_predictor.predict_from_input.return_value = mock_result
            
            response = client.post(
                "/api/predict/structure",
                json={"query": sample_sequence}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "pdb_path" in data
    
    def test_predict_structure_input_types(self, client, sample_sequence):
        """Test different input types."""
        input_types = ["auto", "sequence", "uniprot", "fasta"]
        
        for input_type in input_types:
            response = client.post(
                "/api/predict/structure",
                json={
                    "query": sample_sequence,
                    "input_type": input_type
                }
            )
            
            assert response.status_code == 200
    
    def test_predict_structure_custom_output_name(self, client, sample_sequence):
        """Test prediction with custom output name."""
        response = client.post(
            "/api/predict/structure",
            json={
                "query": sample_sequence,
                "output_name": "my_custom_protein"
            }
        )
        
        assert response.status_code == 200


class TestPredictStructureFormEndpoint:
    """Tests for /api/predict/structure/form endpoint."""
    
    def test_predict_form_success(self, client, sample_sequence):
        """Test form input endpoint."""
        response = client.post(
            "/api/predict/structure/form",
            data={"query": sample_sequence}
        )
        
        assert response.status_code == 200
    
    def test_predict_form_empty(self, client):
        """Test form with empty input."""
        response = client.post(
            "/api/predict/structure/form",
            data={"query": ""}
        )
        
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
    
    def test_predict_form_with_input_type(self, client, sample_sequence):
        """Test form with input type."""
        response = client.post(
            "/api/predict/structure/form",
            data={
                "query": sample_sequence,
                "input_type": "sequence"
            }
        )
        
        assert response.status_code == 200
    
    def test_predict_form_with_output_name(self, client, sample_sequence):
        """Test form with output name."""
        response = client.post(
            "/api/predict/structure/form",
            data={
                "query": sample_sequence,
                "output_name": "test_protein"
            }
        )
        
        assert response.status_code == 200


class TestPredictStructureFileEndpoint:
    """Tests for /api/predict/structure/file endpoint."""
    
    def test_predict_file_success(self, client, sample_fasta):
        """Test file upload endpoint."""
        response = client.post(
            "/api/predict/structure/file",
            files={"file": ("test.fasta", sample_fasta.encode(), "text/plain")}
        )
        
        assert response.status_code == 200
    
    def test_predict_file_with_output_name(self, client, sample_fasta):
        """Test file upload with output name."""
        response = client.post(
            "/api/predict/structure/file",
            files={"file": ("test.fasta", sample_fasta.encode(), "text/plain")},
            data={"output_name": "uploaded_protein"}
        )
        
        assert response.status_code == 200
    
    def test_predict_file_missing(self, client):
        """Test file endpoint without file."""
        response = client.post(
            "/api/predict/structure/file",
            data={"output_name": "test"}
        )
        
        # Should return validation error
        assert response.status_code == 422


# =============================================================================
# Legacy Endpoint Tests
# =============================================================================

class TestLegacyEndpoint:
    """Tests for legacy /predict/structure endpoint."""
    
    def test_legacy_sequence_input(self, client, sample_sequence):
        """Test legacy endpoint with sequence input."""
        response = client.post(
            "/predict/structure",
            data={
                "input_type": "sequence",
                "query": sample_sequence
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
    
    def test_legacy_fasta_input(self, client, sample_fasta):
        """Test legacy endpoint with FASTA file."""
        response = client.post(
            "/predict/structure",
            data={"input_type": "fasta"},
            files={"file": ("test.fasta", sample_fasta.encode(), "text/plain")}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
    
    def test_legacy_missing_query(self, client):
        """Test legacy endpoint without query."""
        response = client.post(
            "/predict/structure",
            data={"input_type": "sequence"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "❌" in data["result"]


# =============================================================================
# Sequence Processing Tests
# =============================================================================

class TestSequenceProcessEndpoint:
    """Tests for /api/sequence/process endpoint."""
    
    def test_process_sequence(self, client, sample_sequence):
        """Test sequence processing."""
        response = client.post(
            "/api/sequence/process",
            json={"query": sample_sequence}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "sequence" in data
        assert "sequence_length" in data
    
    def test_process_fasta_content(self, client, sample_fasta):
        """Test processing FASTA content."""
        response = client.post(
            "/api/sequence/process",
            json={"query": sample_fasta}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Should strip the header
        assert not data["sequence"].startswith(">")
    
    def test_process_invalid_sequence(self, client):
        """Test processing invalid sequence."""
        response = client.post(
            "/api/sequence/process",
            json={"query": "123456"}
        )
        
        assert response.status_code == 200
        data = response.json()
        # Numbers should be stripped, result may be empty
        assert "sequence" in data or "error" in data


# =============================================================================
# Input Validation Tests
# =============================================================================

class TestInputValidation:
    """Tests for input validation."""
    
    def test_invalid_json(self, client):
        """Test request with invalid JSON."""
        response = client.post(
            "/api/predict/structure",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422
    
    def test_very_long_sequence(self, client):
        """Test with very long sequence."""
        long_seq = "M" + "A" * 5000 + "K"
        
        response = client.post(
            "/api/predict/structure",
            json={"query": long_seq}
        )
        
        assert response.status_code == 200
    
    def test_special_characters_stripped(self, client):
        """Test that special characters are stripped from sequence."""
        dirty_seq = "MK-FLI LLF\nNIL"
        
        response = client.post(
            "/api/sequence/process",
            json={"query": dirty_seq}
        )
        
        assert response.status_code == 200
        data = response.json()
        if data.get("success"):
            # Should have no special chars
            assert "-" not in data["sequence"]
            assert " " not in data["sequence"]
            assert "\n" not in data["sequence"]


# =============================================================================
# Response Structure Tests
# =============================================================================

class TestResponseStructure:
    """Tests for response structure."""
    
    def test_success_response_structure(self, client, sample_sequence):
        """Test successful response structure."""
        mock_result = {
            "success": True,
            "pdb_path": "/tmp/test.pdb",
            "static_path": "/static/pdb/query.pdb",
            "sequence": sample_sequence,
            "sequence_length": len(sample_sequence)
        }
        
        with patch("main.predictor") as mock_predictor:
            mock_predictor.predict_from_input.return_value = mock_result
            
            response = client.post(
                "/api/predict/structure",
                json={"query": sample_sequence}
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Check response model fields
            assert "success" in data
            assert "pdb_path" in data
            assert "static_path" in data
            assert "sequence" in data
            assert "sequence_length" in data
            assert "error" in data
    
    def test_error_response_structure(self, client):
        """Test error response structure."""
        response = client.post(
            "/api/predict/structure",
            json={"query": ""}
        )
        
        assert response.status_code == 422
        data = response.json()
        
        assert "success" in data
        assert data["success"] is False
        assert "error" in data


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


# =============================================================================
# Predictor Unit Tests
# =============================================================================

class TestStructurePredictorUnit:
    """Unit tests for StructurePredictor class."""
    
    def test_classify_input_sequence(self):
        """Test classify_input_v2 with raw sequence."""
        from models.structure_predictor import classify_input_v2
        
        seq = "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
        result = classify_input_v2(seq)
        
        assert result == seq
    
    def test_classify_input_fasta(self):
        """Test classify_input_v2 with FASTA content."""
        from models.structure_predictor import classify_input_v2
        
        fasta = """>test
MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"""
        result = classify_input_v2(fasta)
        
        assert result == "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
    
    def test_clean_sequence(self):
        """Test _clean_sequence function."""
        from models.structure_predictor import _clean_sequence
        
        dirty = "MK-FLI LLF\nNIL123"
        clean = _clean_sequence(dirty)
        
        assert clean == "MKFLILLFNIL"
    
    def test_save_sequence_as_fasta(self):
        """Test save_sequence_as_fasta function."""
        from models.structure_predictor import save_sequence_as_fasta
        import tempfile
        
        seq = "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.fasta")
            result = save_sequence_as_fasta(seq, path, "test_header")
            
            assert os.path.exists(result)
            with open(result) as f:
                content = f.read()
            
            assert ">test_header" in content
            assert seq in content


def test_health_remains_responsive_during_prediction():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    started, release = Event(), Event()
    def predict(**kwargs):
        started.set()
        assert release.wait(5)
        return {"success": False, "error": "test finished"}
    with patch("main.predictor") as predictor, patch("main.backend_config", {"configured": True}):
        predictor.predict_from_input.side_effect = predict
        with ThreadPoolExecutor() as pool:
            http = TestClient(app)
            with patch("main.predictor.predict_from_input", side_effect=predict):
                pending = pool.submit(http.post, "/api/predict/structure", json={"query": "MAAAA"})
                try:
                    assert started.wait(2)
                    health = pool.submit(http.get, "/health").result(timeout=2)
                    assert health.status_code == 200
                finally:
                    release.set()
                assert pending.result(timeout=2).status_code == 502


def test_same_output_names_never_share_structure_artifacts(tmp_path):
    from models.structure_predictor import StructurePredictor
    predictor = StructurePredictor(output_dir=str(tmp_path / "out"), fasta_dir=str(tmp_path / "in"),
                                  static_pdb_dir=str(tmp_path / "static"), log_dir=str(tmp_path / "logs"))
    def fake_run(input_fasta_path, output_dir, output_name):
        from pathlib import Path
        output = Path(output_dir) / (output_name + ".pdb")
        output.parent.mkdir(parents=True)
        sequence = Path(input_fasta_path).read_text().splitlines()[1]
        atoms = [f"ATOM  {i:5d}  CA  ALA A{i:4d}    {1.:8.3f}{2.:8.3f}{3.:8.3f}" for i in range(1,len(sequence)+1)]
        output.write_text("HEADER " + sequence + "\n" + "\n".join(atoms))
        return {"success": True, "pdb_path": str(output)}
    predictor._runner = MagicMock()
    predictor._runner.predict_structure.side_effect = fake_run
    first = predictor.predict_from_sequence("MAAAA", "query")
    second = predictor.predict_from_sequence("MGGGG", "query")
    assert first["success"] and second["success"]
    assert first["static_path"] != second["static_path"]
    from pathlib import Path
    assert "MAAAA" in Path(first["pdb_path"]).read_text()
    assert "MGGGG" not in Path(first["pdb_path"]).read_text()


def test_requested_gpu_failure_is_not_reported_ready(tmp_path):
    from models.structure_predictor import StructurePredictor
    predictor = StructurePredictor(output_dir=str(tmp_path / "out"), fasta_dir=str(tmp_path / "in"),
                                  static_pdb_dir=str(tmp_path / "static"), log_dir=str(tmp_path / "logs"),
                                  docker_image="configured-esmfold-image", use_gpu=True)
    predictor._runner = MagicMock()
    predictor._runner.check_docker_available.return_value = True
    predictor._runner.check_image_available.return_value = True
    with patch("models.structure_predictor.subprocess.run", return_value=MagicMock(returncode=1)) as check:
        config = predictor.check_config()
    assert config["configured"] is False
    assert config["gpu_available"] is False
    assert "configured-esmfold-image" in check.call_args.args[0]


@pytest.mark.parametrize("exit_code,log,expected", [(1, "RuntimeError: CUDA out of memory", "structure_memory_exhausted"),
                                                  (0, "Failed (CUDA out of memory)", "structure_memory_exhausted"),
                                                  (125, "daemon unavailable", "structure_worker_failed")])
def test_worker_diagnostics_survive_file_redirection(tmp_path, exit_code, log, expected):
    from models.structure_predictor import DockerESMFoldRunner
    from subprocess import CompletedProcess
    runner = DockerESMFoldRunner(model_cache_dir=str(tmp_path), log_dir=str(tmp_path))
    def run(cmd, **kwargs):
        kwargs["stderr"].write(log)
        return CompletedProcess(cmd, exit_code)
    with patch("models.structure_predictor.subprocess.run", side_effect=run):
        result = runner.predict_structure(str(tmp_path/"job.fasta"), str(tmp_path/"out"), "job")
    assert result["error_code"] == expected
