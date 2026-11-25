# structure_predict/models/structure_predictor.py
"""
Structure Prediction using ESMFold via Docker.

This module provides classes for protein structure prediction using ESMFold model
running in a Docker container.
"""

import os
import re
import math
import shutil
import logging
import subprocess
import sys
import threading
from uuid import uuid4
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
from timeit import default_timer as timer

root = str(Path(__file__).resolve().parents[3])
if root not in sys.path:
    sys.path.insert(0, root)
from shared.uniprot import ACCESSION, UniProtDownloadError, uniprot_sequence_client

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
    if re.fullmatch(r"(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})(?:-[1-9][0-9]*)?", raw, re.I):
        logger.info("[DEBUG] Detected UniProt ID")
        return uniprot_sequence_client.fetch(raw).sequence

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
        self.cuda_cache_dir = os.getenv("ESMFOLD_CUDA_CACHE_DIR", str(
            Path(__file__).resolve().parents[3] / "files" / "esmfold_cuda_cache"))
        
        self.logger = logging.getLogger("DockerESMFoldRunner")
        self.logger.setLevel(logging.INFO)
        
        # Ensure model cache directory exists
        os.makedirs(self.model_cache_dir, exist_ok=True)
        os.makedirs(self.cuda_cache_dir, exist_ok=True)
        if self.log_dir:
            os.makedirs(self.log_dir, exist_ok=True)
    
    def check_docker_available(self) -> bool:
        """Check if Docker is available."""
        try:
            result = subprocess.run(
                ["docker", "info", "--format", "{{.ServerVersion}}"],
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
        container_name = f"enzymind-esmfold-{uuid4().hex}"
        cmd = ["docker", "run", "--rm", "--network", "none", "--name", container_name]
        
        # Add GPU support if enabled
        if self.use_gpu:
            cmd.extend(["--gpus", "all"])
        
        else:
            threads = int(os.getenv("ESMFOLD_CPU_THREADS", "6"))
            memory = os.getenv("ESMFOLD_CPU_MEMORY", "28g")
            cmd.extend(["--cpus", str(threads), "--memory", memory, "--memory-swap", memory,
                        "-e", f"OMP_NUM_THREADS={threads}", "-e", f"MKL_NUM_THREADS={threads}"])

        # Mount volumes
        cmd.extend([
            "-v", f"{input_dir}:/home/vscode/input:ro",
            "-v", f"{output_dir}:/home/vscode/output",
            "-v", f"{self.model_cache_dir}:/home/vscode/.cache/torch/hub/checkpoints:ro",
            "-v", f"{self.cuda_cache_dir}:/home/vscode/.cache/cuda",
            "-e", "CUDA_CACHE_PATH=/home/vscode/.cache/cuda",
            "-e", "CUDA_CACHE_MAXSIZE=4294967296",
        ])
        
        # Add image and arguments
        cmd.extend([
            self.docker_image,
            "-i", f"/home/vscode/input/{input_filename}",
            "-o", "/home/vscode/output"
        ])
        
        # The target host has no NVIDIA GPU; pass the ESMFold CPU option.
        if not self.use_gpu:
            cmd.extend(["--cpu-only", "--chunk-size", "32"])

        self.logger.info(f"Docker command: {' '.join(cmd)}")
        
        start = timer()
        stdout_file = stderr_file = None
        try:
            if self.log_dir:
                stdout_file = open(Path(self.log_dir) / f"{output_name}.log", "w+")
                stderr_file = open(Path(self.log_dir) / f"{output_name}.err", "w+")
            result = subprocess.run(cmd, stdout=stdout_file or subprocess.PIPE,
                                    stderr=stderr_file or subprocess.PIPE, text=True,
                                    timeout=self.timeout)
            pred_time = timer() - start
            diagnostics = [result.stdout or "", result.stderr or ""]
            for stream in (stdout_file, stderr_file):
                if stream:
                    # Capture the end of the job log even when the CLI wrote to disk.
                    stream.seek(0, os.SEEK_END)
                    stream.seek(max(0, stream.tell() - 16384))
                    diagnostics.append(stream.read())
            diagnostic = "\n".join(diagnostics).lower()
            if "out of memory" in diagnostic or result.returncode == 137:
                return {"success": False, "error_code": "structure_memory_exhausted",
                        "error": "ESMFold exceeded available GPU or host memory.", "prediction_time": pred_time}
            if result.returncode:
                self.logger.error("ESMFold job %s exited with status %s", output_name, result.returncode)
                return {"success": False, "error_code": "structure_worker_failed",
                        "error": f"ESMFold worker exited with status {result.returncode}.", "prediction_time": pred_time}

            # Each invocation owns its output directory and FASTA header.
            pdb_path = os.path.join(output_dir, f"{output_name}.pdb")
            if not os.path.isfile(pdb_path):
                return {"success": False, "error_code": "structure_invalid_output",
                        "error": "ESMFold completed without producing coordinates."}
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
            # Killing docker's CLI alone leaves its GPU container running.
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, timeout=30)
            self.logger.error(f"Docker prediction timed out after {self.timeout}s")
            return {
                "success": False,
                "error_code": "structure_timeout",
                "error": f"Prediction timed out after {self.timeout} seconds"
            }
        except Exception as e:
            self.logger.error(f"Prediction failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            for stream in (stdout_file, stderr_file):
                if stream:
                    stream.close()


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
        self._prediction_lock = threading.Lock()
        
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
        clean_seq = "".join(sequence.split()).upper()
        
        if not re.fullmatch(r"[ACDEFGHIKLMNPQRSTVWYBXZUO]+", clean_seq):
            return {
                "success": False,
                "error_code": "invalid_input", "error": "Empty or invalid sequence"
            }
        
        if not self._prediction_lock.acquire(blocking=False):
            return {"success": False, "error_code": "structure_busy", "error": "A structure prediction is already running. Wait for it to finish before submitting another."}
        # Each output is immutable and isolated from other requests, even when
        # users keep the default name. Never return another job's coordinates.
        label = re.sub(r"[^A-Za-z0-9_-]", "_", output_name)[:64] or "query"
        output_name = f"{label}_{uuid4().hex[:12]}"
        fasta_path = os.path.join(self.fasta_dir, f"{output_name}.fasta")
        
        try:
            save_sequence_as_fasta(clean_seq, fasta_path, output_name)
            # Run prediction via Docker
            result = self.runner.predict_structure(
                input_fasta_path=fasta_path,
                output_dir=os.path.join(self.output_dir, output_name),
                output_name=output_name
            )
            
            if not result["success"]:
                return result
            
            # Copy to static directory
            pdb_path = result["pdb_path"]
            residues = set()
            try:
                with open(pdb_path, encoding="ascii") as coordinates:
                    for line in coordinates:
                        if line.startswith("ATOM  ") and line[12:16].strip() == "CA":
                            if not all(math.isfinite(float(line[i:i+8])) for i in (30, 38, 46)):
                                raise ValueError("Non-finite coordinates")
                            residues.add(line[21:27])
                if len(residues) != len(clean_seq):
                    raise ValueError("Incomplete backbone")
            except (OSError, ValueError):
                return {"success": False, "error_code": "structure_invalid_output",
                        "error": "The predicted backbone does not cover the submitted sequence."}
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
        finally:
            self._prediction_lock.release()
    
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
            raw = input_data.strip()
            if input_type == "uniprot" or (input_type == "auto" and re.fullmatch(ACCESSION, raw, re.I)):
                sequence = uniprot_sequence_client.fetch(raw).sequence
            elif input_type == "fasta" or (input_type == "auto" and raw.startswith(">")):
                lines = raw.splitlines()
                if not lines or not lines[0].startswith(">") or any(line.startswith(">") for line in lines[1:]):
                    return {"success": False, "error_code": "invalid_input", "error": "Submit one FASTA record."}
                sequence = "".join(lines[1:])
            elif input_type in ("auto", "sequence"):
                sequence = raw
            else:
                return {"success": False, "error_code": "invalid_input", "error": "Unknown protein input type."}
            return self.predict_from_sequence(sequence, output_name)
            
        except UniProtDownloadError as exc:
            return {"success": False, "error_code": exc.code, "error": str(exc)}
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
            return self.predict_from_input(fasta_content, "auto", output_name)
        except UnicodeDecodeError:
            return {"success": False, "error_code": "invalid_input", "error": "Submit a UTF-8 FASTA file."}
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
                    ["docker", "run", "--rm", "--gpus", "all", "--entrypoint", "nvidia-smi", self.docker_image, "-L"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                gpu_available = result.returncode == 0
                if not gpu_available:
                    issues.append("GPU access failed in the configured Docker image. Set ESMFOLD_USE_GPU=false to use CPU explicitly.")
            except Exception:
                issues.append("Could not verify GPU support in Docker")
        
        for filename in ("esmfold_3B_v1.pt", "esm2_t36_3B_UR50D.pt", "esm2_t36_3B_UR50D-contact-regression.pt"):
            weight = Path(self.runner.model_cache_dir) / filename
            if not weight.is_file() or not os.access(weight, os.R_OK):
                issues.append(f"Missing or unreadable ESMFold checkpoint: {filename}")
        return {
            "configured": not issues,
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
