# structure_predict/models/structure_predictor.py
"""
Structure Prediction using ESMFold via Docker.

This module provides classes for protein structure prediction using ESMFold model
running in a Docker container.
"""

import os
import re
import glob
import shutil
import logging
import subprocess
import requests
import tempfile
import time
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
from timeit import default_timer as timer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def classify_input_v2(raw: str) -> str:
    """
    Process user input:
    - If UniProt ID, fetch sequence from UniProt API
    - If FASTA format, strip header
    - If raw sequence, return cleaned version
    
    Args:
        raw: Raw input string
        
    Returns:
        Cleaned protein sequence
    """
    raw = raw.strip()

    # Check if UniProt ID
    if re.match(r"^[OPQ][0-9][A-Z0-9]{3}[0-9]$", raw) or re.match(r"^[A-NR-Z][0-9][A-Z0-9]{3}[0-9]$", raw):
        logger.info("[DEBUG] Detected UniProt ID")
        url = f"https://rest.uniprot.org/uniprotkb/{raw}.fasta"
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            raise ValueError("Failed to fetch sequence from UniProt.")
        fasta_content = response.text
        return _extract_sequence_from_fasta(fasta_content)

    # Check if FASTA format
    if raw.startswith(">") or "\n>" in raw:
        logger.info("[DEBUG] Detected FASTA content")
        return _extract_sequence_from_fasta(raw)

    # Assume raw sequence
    logger.info("[DEBUG] Detected raw amino acid sequence")
    return _clean_sequence(raw)


def _extract_sequence_from_fasta(fasta_text: str) -> str:
    """Extract sequence from FASTA text."""
    lines = fasta_text.strip().splitlines()
    seq_lines = [line.strip() for line in lines if not line.startswith(">")]
    return _clean_sequence("".join(seq_lines))


def _clean_sequence(seq: str) -> str:
    """Remove non-amino acid characters."""
    return re.sub(r"[^A-Z]", "", seq.upper())


def save_sequence_as_fasta(sequence: str, output_path: str, header: str = "query") -> str:
    """
    Save a sequence as a FASTA file.
    
    Args:
        sequence: Amino acid sequence
        output_path: Path to save the FASTA file
        header: FASTA header (default: "query")
        
    Returns:
        Path to saved file
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as file:
        file.write(f">{header}\n{sequence}")
    return output_path


class DockerESMFoldRunner:
    """
    ESMFold runner using Docker container.
    
    This class runs ESMFold predictions using a Docker container
    (biochunan/esmfold-image:nonroot-runtime).
    """
    
    DEFAULT_DOCKER_IMAGE = "biochunan/esmfold-image:nonroot-runtime"
    
    def __init__(
        self,
        docker_image: Optional[str] = None,
        model_cache_dir: Optional[str] = None,
        use_gpu: bool = True,
        timeout: int = 3600,
        log_dir: Optional[str] = None
    ):
        """
        Initialize Docker ESMFold runner.
        
        Args:
            docker_image: Docker image name (default: biochunan/esmfold-image:nonroot-runtime)
            model_cache_dir: Directory for model weights cache
            use_gpu: Whether to use GPU (--gpus all)
            timeout: Timeout in seconds for Docker command
            log_dir: Directory for log files (optional)
        """
        self.docker_image = docker_image or self.DEFAULT_DOCKER_IMAGE
        self.model_cache_dir = model_cache_dir or os.path.expanduser("~/.cache/torch/hub/checkpoints")
        self.use_gpu = use_gpu
        self.timeout = timeout
        self.log_dir = log_dir
        
        self.logger = logging.getLogger("DockerESMFoldRunner")
        self.logger.setLevel(logging.INFO)
        
        # Ensure model cache directory exists
        os.makedirs(self.model_cache_dir, exist_ok=True)
        if self.log_dir:
            os.makedirs(self.log_dir, exist_ok=True)
    
    def check_docker_available(self) -> bool:
        """Check if Docker is available."""
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception as e:
            self.logger.error(f"Docker check failed: {e}")
            return False
    
    def check_image_available(self) -> bool:
        """Check if the Docker image is available locally."""
        try:
            result = subprocess.run(
                ["docker", "images", "-q", self.docker_image],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0 and result.stdout.strip() != ""
        except Exception as e:
            self.logger.error(f"Image check failed: {e}")
            return False
    
    def pull_image(self) -> bool:
        """Pull the Docker image if not available."""
        if self.check_image_available():
            self.logger.info(f"Docker image {self.docker_image} already available")
            return True
        
        self.logger.info(f"Pulling Docker image {self.docker_image}...")
        try:
            result = subprocess.run(
                ["docker", "pull", self.docker_image],
                capture_output=True,
                text=True,
                timeout=1800  # 30 minutes for large image
            )
            if result.returncode == 0:
                self.logger.info("Docker image pulled successfully")
                return True
            else:
                self.logger.error(f"Failed to pull image: {result.stderr}")
                return False
        except Exception as e:
            self.logger.error(f"Failed to pull image: {e}")
            return False
    
    def predict_structure(
        self,
        input_fasta_path: str,
        output_dir: str,
        output_name: str = "query"
    ) -> Dict[str, Any]:
        """
        Predict protein structure using Docker.
        
        Args:
            input_fasta_path: Path to input FASTA file
            output_dir: Directory for output PDB files
            output_name: Name for output files
            
        Returns:
            Dictionary with prediction results
        """
        # Ensure directories exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Get absolute paths
        input_dir = os.path.dirname(os.path.abspath(input_fasta_path))
        input_filename = os.path.basename(input_fasta_path)
        output_dir = os.path.abspath(output_dir)
        
        self.logger.info(f"Running ESMFold prediction via Docker")
        self.logger.info(f"  Input: {input_fasta_path}")
        self.logger.info(f"  Output dir: {output_dir}")
        
        # Build Docker command
        cmd = ["docker", "run", "--rm"]
        
        # Add GPU support if enabled
        if self.use_gpu:
            cmd.extend(["--gpus", "all"])
        
        # Mount volumes
        cmd.extend([
            "-v", f"{input_dir}:/home/vscode/input:ro",
            "-v", f"{output_dir}:/home/vscode/output",
            "-v", f"{self.model_cache_dir}:/home/vscode/.cache/torch/hub/checkpoints"
        ])
        
        # Add image and arguments
        cmd.extend([
            self.docker_image,
            "-i", f"/home/vscode/input/{input_filename}",
            "-o", "/home/vscode/output"
        ])
        
        self.logger.info(f"Docker command: {' '.join(cmd)}")
        
        start = timer()
        start_timestamp = time.time()  # Unix timestamp for file mtime comparison
        
        try:
            # Prepare log files if log_dir is specified
            stdout_file = None
            stderr_file = None
            if self.log_dir:
                stdout_file = open(os.path.join(self.log_dir, f"{output_name}.log"), "w")
                stderr_file = open(os.path.join(self.log_dir, f"{output_name}.err"), "w")
            
            # Run Docker command
            result = subprocess.run(
                cmd,
                capture_output=True if not self.log_dir else False,
                stdout=stdout_file if stdout_file else subprocess.PIPE,
                stderr=stderr_file if stderr_file else subprocess.PIPE,
                text=True,
                timeout=self.timeout
            )
            
            # Close log files
            if stdout_file:
                stdout_file.close()
            if stderr_file:
                stderr_file.close()
            
            pred_time = timer() - start
            
            if result.returncode != 0:
                error_msg = result.stderr if hasattr(result, 'stderr') and result.stderr else "Unknown error"
                self.logger.error(f"Docker prediction failed: {error_msg}")
                return {
                    "success": False,
                    "error": f"Docker prediction failed: {error_msg}",
                    "prediction_time": pred_time
                }
            
            # Find output PDB file
            # ESMFold Docker outputs files with FASTA header as filename
            # The expected output file should match the header in the FASTA file
            
            # First, read the FASTA header to get expected output filename
            expected_pdb_name = None
            try:
                with open(input_fasta_path, 'r') as f:
                    header_line = f.readline().strip()
                    if header_line.startswith('>'):
                        expected_pdb_name = header_line[1:].split()[0]  # Get first word after '>'
            except Exception as e:
                self.logger.warning(f"Could not read FASTA header: {e}")
            
            # Check for the expected output file from Docker
            expected_docker_output = None
            if expected_pdb_name:
                expected_docker_output = os.path.join(output_dir, f"{expected_pdb_name}.pdb")
                self.logger.info(f"Looking for expected Docker output: {expected_docker_output}")
            
            # Also check log file for errors (CUDA OOM, etc.)
            if self.log_dir:
                log_file = os.path.join(self.log_dir, f"{output_name}.log")
                if os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        log_content = f.read()
                        if "Failed" in log_content or "CUDA out of memory" in log_content or "Error" in log_content:
                            # Extract error message from log
                            error_lines = [line for line in log_content.split('\n') if 'Failed' in line or 'Error' in line]
                            error_msg = error_lines[-1] if error_lines else "Prediction failed (see logs)"
                            self.logger.error(f"Docker prediction failed: {error_msg}")
                            return {
                                "success": False,
                                "error": error_msg,
                                "prediction_time": pred_time
                            }
            
            # Check if the expected Docker output file exists and was created after we started
            pdb_path = None
            if expected_docker_output and os.path.exists(expected_docker_output):
                # Verify the file was created after we started the prediction
                file_mtime = os.path.getmtime(expected_docker_output)
                if file_mtime >= start_timestamp:
                    pdb_path = expected_docker_output
                    self.logger.info(f"Found expected Docker output: {expected_docker_output}")
            
            if not pdb_path:
                # Fallback: look for any new PDB files created after we started
                pdb_files = glob.glob(os.path.join(output_dir, "*.pdb"))
                new_pdb_files = [f for f in pdb_files if os.path.getmtime(f) >= start_timestamp]
                
                if not new_pdb_files:
                    self.logger.error("No new PDB file generated")
                    return {
                        "success": False,
                        "error": "No PDB file generated by Docker container. The sequence may be too long for available GPU memory.",
                        "prediction_time": pred_time
                    }
                
                # Get the most recently modified PDB file among new files
                pdb_path = max(new_pdb_files, key=os.path.getmtime)
                self.logger.info(f"Found new PDB file: {pdb_path}")
            
            # Copy/rename to desired output name if different
            final_pdb_path = os.path.join(output_dir, f"{output_name}.pdb")
            if pdb_path != final_pdb_path:
                shutil.copy(pdb_path, final_pdb_path)
            
            self.logger.info(f"Structure prediction completed in {pred_time:.1f}s")
            self.logger.info(f"Output PDB: {final_pdb_path}")
            
            return {
                "success": True,
                "pdb_path": final_pdb_path,
                "prediction_time": pred_time
            }
            
        except subprocess.TimeoutExpired:
            self.logger.error(f"Docker prediction timed out after {self.timeout}s")
            return {
                "success": False,
                "error": f"Prediction timed out after {self.timeout} seconds"
            }
        except Exception as e:
            self.logger.error(f"Prediction failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }


class StructurePredictor:
    """
    High-level structure predictor class.
    
    This class provides a convenient interface for protein structure prediction
    using ESMFold via Docker container.
    """
    
    DEFAULT_OUTPUT_DIR = "/tmp/esmfold_output"
    DEFAULT_FASTA_DIR = "/tmp/esmfold_fasta"
    DEFAULT_STATIC_PDB_DIR = "/tmp/static/pdb"
    DEFAULT_LOG_DIR = "/tmp/esmfold_output/logs"
    
    def __init__(
        self,
        output_dir: Optional[str] = None,
        fasta_dir: Optional[str] = None,
        static_pdb_dir: Optional[str] = None,
        docker_image: Optional[str] = None,
        model_cache_dir: Optional[str] = None,
        use_gpu: bool = True,
        timeout: int = 3600,
        log_dir: Optional[str] = None
    ):
        """
        Initialize structure predictor.
        
        Args:
            output_dir: Directory for PDB output
            fasta_dir: Directory for FASTA files
            static_pdb_dir: Directory for serving static PDB files
            docker_image: Docker image for ESMFold
            model_cache_dir: Directory for model weights cache
            use_gpu: Whether to use GPU
            timeout: Timeout in seconds for prediction
            log_dir: Directory for log files
        """
        self.output_dir = output_dir or self.DEFAULT_OUTPUT_DIR
        self.fasta_dir = fasta_dir or self.DEFAULT_FASTA_DIR
        self.static_pdb_dir = static_pdb_dir or self.DEFAULT_STATIC_PDB_DIR
        self.docker_image = docker_image or DockerESMFoldRunner.DEFAULT_DOCKER_IMAGE
        self.model_cache_dir = model_cache_dir
        self.use_gpu = use_gpu
        self.timeout = timeout
        self.log_dir = log_dir or self.DEFAULT_LOG_DIR
        
        # Create directories
        os.makedirs(self.fasta_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.static_pdb_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Docker runner
        self._runner: Optional[DockerESMFoldRunner] = None
        
        self.logger = logging.getLogger("StructurePredictor")
    
    @property
    def runner(self) -> DockerESMFoldRunner:
        """Lazy load the Docker runner."""
        if self._runner is None:
            self._runner = DockerESMFoldRunner(
                docker_image=self.docker_image,
                model_cache_dir=self.model_cache_dir,
                use_gpu=self.use_gpu,
                timeout=self.timeout,
                log_dir=self.log_dir
            )
        return self._runner
    
    def predict_from_sequence(
        self, 
        sequence: str, 
        output_name: str = "query"
    ) -> Dict[str, Any]:
        """
        Predict structure from amino acid sequence.
        
        Args:
            sequence: Amino acid sequence
            output_name: Name for output files
            
        Returns:
            Dictionary with prediction results
        """
        # Clean sequence
        clean_seq = _clean_sequence(sequence)
        
        if not clean_seq:
            return {
                "success": False,
                "error": "Empty or invalid sequence"
            }
        
        # Save as FASTA
        fasta_path = os.path.join(self.fasta_dir, f"{output_name}.fasta")
        save_sequence_as_fasta(clean_seq, fasta_path, output_name)
        
        try:
            # Run prediction via Docker
            result = self.runner.predict_structure(
                input_fasta_path=fasta_path,
                output_dir=self.output_dir,
                output_name=output_name
            )
            
            if not result["success"]:
                return result
            
            # Copy to static directory
            pdb_path = result["pdb_path"]
            static_pdb_path = os.path.join(self.static_pdb_dir, f"{output_name}.pdb")
            shutil.copy(pdb_path, static_pdb_path)
            
            return {
                "success": True,
                "pdb_path": pdb_path,
                "static_path": f"/static/pdb/{output_name}.pdb",
                "sequence": clean_seq,
                "sequence_length": len(clean_seq),
                "prediction_time": result.get("prediction_time")
            }
        except Exception as e:
            self.logger.error(f"Structure prediction failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def predict_from_input(
        self,
        input_data: str,
        input_type: str = "auto",
        output_name: str = "query"
    ) -> Dict[str, Any]:
        """
        Predict structure from various input types.
        
        Args:
            input_data: Input data (sequence, UniProt ID, or FASTA content)
            input_type: Type of input ("sequence", "uniprot", "fasta", "auto")
            output_name: Name for output files
            
        Returns:
            Dictionary with prediction results
        """
        try:
            # Process input to get sequence
            if input_type == "auto":
                sequence = classify_input_v2(input_data)
            elif input_type == "uniprot":
                url = f"https://rest.uniprot.org/uniprotkb/{input_data.strip()}.fasta"
                response = requests.get(url, timeout=30)
                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to fetch sequence for UniProt ID: {input_data}"
                    }
                sequence = _extract_sequence_from_fasta(response.text)
            elif input_type == "fasta":
                sequence = _extract_sequence_from_fasta(input_data)
            else:  # sequence
                sequence = _clean_sequence(input_data)
            
            return self.predict_from_sequence(sequence, output_name)
            
        except Exception as e:
            self.logger.error(f"Failed to process input: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def predict_from_file(
        self,
        file_content: bytes,
        output_name: str = "query"
    ) -> Dict[str, Any]:
        """
        Predict structure from uploaded FASTA file.
        
        Args:
            file_content: FASTA file content as bytes
            output_name: Name for output files
            
        Returns:
            Dictionary with prediction results
        """
        try:
            fasta_content = file_content.decode("utf-8")
            sequence = _extract_sequence_from_fasta(fasta_content)
            return self.predict_from_sequence(sequence, output_name)
        except Exception as e:
            self.logger.error(f"Failed to process file: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def check_config(self) -> Dict[str, Any]:
        """
        Check if Docker backend is properly configured.
        
        Returns:
            Dictionary with configuration status
        """
        issues = []
        
        # Check Docker availability
        docker_available = self.runner.check_docker_available()
        if not docker_available:
            issues.append("Docker is not available or not running")
        
        # Check Docker image
        image_available = self.runner.check_image_available()
        if not image_available:
            issues.append(f"Docker image {self.docker_image} not found. Run: docker pull {self.docker_image}")
        
        # Check GPU support (nvidia-docker)
        gpu_available = False
        if self.use_gpu:
            try:
                result = subprocess.run(
                    ["docker", "run", "--rm", "--gpus", "all", "nvidia/cuda:11.0-base", "nvidia-smi"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                gpu_available = result.returncode == 0
                if not gpu_available:
                    issues.append("GPU support not available in Docker. Will fall back to CPU.")
            except Exception:
                issues.append("Could not verify GPU support in Docker")
        
        return {
            "configured": docker_available and image_available,
            "issues": issues,
            "output_dir": self.output_dir,
            "docker_image": self.docker_image,
            "model_cache_dir": self.model_cache_dir,
            "use_gpu": self.use_gpu,
            "docker_available": docker_available,
            "image_available": image_available,
            "gpu_available": gpu_available
        }


# Factory function
def create_predictor(
    output_dir: Optional[str] = None,
    docker_image: Optional[str] = None,
    use_gpu: bool = True,
    model_cache_dir: Optional[str] = None
) -> StructurePredictor:
    """
    Create a structure predictor instance.
    
    Args:
        output_dir: Directory for output files
        docker_image: Docker image for ESMFold
        use_gpu: Whether to use GPU
        model_cache_dir: Directory for model weights cache
        
    Returns:
        StructurePredictor instance
    """
    return StructurePredictor(
        output_dir=output_dir,
        docker_image=docker_image,
        use_gpu=use_gpu,
        model_cache_dir=model_cache_dir
    )
