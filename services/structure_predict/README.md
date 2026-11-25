# Structure Prediction Service

Protein structure prediction microservice for EnzyMind platform. This service uses ESMFold running in a Docker container for predicting protein 3D structures from amino acid sequences.

## Features

- **Structure Prediction**: Predict 3D protein structures using ESMFold
- **Multiple Input Types**: Support for raw sequences, UniProt IDs, and FASTA files
- **Sequence Processing**: Validate and clean input sequences
- **Static PDB Serving**: Serve predicted PDB files
- **Docker Backend**: ESMFold runs in an isolated Docker container (no local PyTorch/ESM installation needed)
- **GPU Support**: Full NVIDIA GPU support via nvidia-docker

## Port

### Runtime behavior

`/health` uses the readiness result cached at startup; it does not launch containers.
`/api/config` explicitly refreshes the Docker/GPU diagnostic using the configured ESMFold image.
Inference runs outside the HTTP event loop, so health checks remain responsive.
One prediction runs at a time; concurrent submissions get a clear busy error.
Each request gets a unique output filename and directory to keep saved coordinates immutable.

CUDA's JIT cache is persisted in `files/esmfold_cuda_cache/` (override with
`ESMFOLD_CUDA_CACHE_DIR`). This matters on GPUs requiring runtime compilation of
the image's kernels. See [NVIDIA's JIT caching documentation](https://developer.nvidia.com/blog/cuda-pro-tip-understand-fat-binaries-jit-caching/).
The first run can take longer than five minutes. Gateway and frontend timeouts
cover the default `ESMFOLD_TIMEOUT=3600`; an external reverse proxy must do the same.

This service runs on port **18906**.

## Prerequisites

### Docker Installation

1. **Install Docker**:
   ```bash
   # Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install docker.io
   sudo systemctl start docker
   sudo systemctl enable docker
   
   # Add user to docker group (logout/login required)
   sudo usermod -aG docker $USER
   ```

2. **Install NVIDIA Container Toolkit** (for GPU support):
   ```bash
   # Add NVIDIA repository
   distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
   curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
   curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
       sudo tee /etc/apt/sources.list.d/nvidia-docker.list
   
   # Install nvidia-docker2
   sudo apt-get update
   sudo apt-get install nvidia-docker2
   sudo systemctl restart docker
   ```

3. **Pull ESMFold Docker Image**:
   ```bash
   docker pull biochunan/esmfold-image:nonroot-runtime
   ```

4. **Verify GPU Support**:
   ```bash
   docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
   ```

## Quick Start

### Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies (no PyTorch/ESM needed!)
pip install -r requirements.txt
```

### Configuration

Set the following environment variables (all optional):

```bash
# Docker configuration
export ESMFOLD_DOCKER_IMAGE="biochunan/esmfold-image:nonroot-runtime"
export ESMFOLD_MODEL_CACHE_DIR="$HOME/.cache/torch/hub/checkpoints"
export ESMFOLD_USE_GPU="true"        # Set to "false" for CPU-only mode
export ESMFOLD_TIMEOUT="3600"        # Prediction timeout in seconds (default: 1 hour)

# Output directories
export ESMFOLD_OUTPUT_DIR="/tmp/esmfold_output"
export ESMFOLD_FASTA_DIR="/tmp/esmfold_fasta"
export STATIC_PDB_DIR="/tmp/static/pdb"
export ESMFOLD_LOG_DIR=""            # Optional: directory for Docker logs
```

### Run Service

```bash
# Development
uvicorn main:app --reload --port 18906

# Production
uvicorn main:app --host 0.0.0.0 --port 18906

# Alternatively, supply explicit paths from the service directory.
python main.py \
    --docker-image biochunan/esmfold-image:nonroot-runtime \
    --model-cache-dir /path/to/esmfold_state \
    --static-pdb-dir /path/to/EnzyMind/files/pdb \
    --use-gpu true \
    --timeout 3600 \
    --host 0.0.0.0 \
    --port 18906
```

### Run Tests

```bash
pytest tests/ -v
```

## API Endpoints

### Health Check

```
GET /health
```

Returns service health status and Docker backend configuration status.

**Response Example:**
```json
{
  "status": "healthy",
  "service": "structure_predict",
  "docker_backend": true,
  "docker_image": "biochunan/esmfold-image:nonroot-runtime"
}
```

### Configuration Status

```
GET /api/config
```

Returns detailed Docker backend configuration information.

**Response Example:**
```json
{
  "configured": true,
  "issues": [],
  "output_dir": "/tmp/esmfold_output",
  "docker_image": "biochunan/esmfold-image:nonroot-runtime",
  "model_cache_dir": "/home/user/.cache/torch/hub/checkpoints",
  "use_gpu": true,
  "docker_available": true,
  "image_available": true,
  "gpu_available": true
}
```

### Predict Structure (JSON)

```
POST /api/predict/structure
Content-Type: application/json

{
  "query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR",
  "input_type": "auto",
  "output_name": "my_protein"
}
```

**Response Example:**
```json
{
  "success": true,
  "pdb_path": "/tmp/esmfold_output/my_protein.pdb",
  "static_path": "/static/pdb/my_protein.pdb",
  "sequence": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR",
  "sequence_length": 52,
  "error": null
}
```

**Error Response Example:**
```json
{
  "success": false,
  "pdb_path": null,
  "static_path": null,
  "sequence": null,
  "sequence_length": null,
  "error": "Docker prediction failed: Container exited with non-zero status"
}
```

### Predict Structure & Download (One-Click)

```
POST /api/predict/structure/download
Content-Type: application/json

{
  "query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR",
  "input_type": "auto",
  "output_name": "my_protein"
}
```

**Response:** Directly returns PDB file as downloadable attachment.

This endpoint combines prediction and download into a single request.

### Predict Structure (Form)

```
POST /api/predict/structure/form
Content-Type: application/x-www-form-urlencoded

query=MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR&input_type=auto&output_name=my_protein
```

**Response:** Same as JSON endpoint above.

### Predict Structure (File Upload)

```
POST /api/predict/structure/file
Content-Type: multipart/form-data

file=@protein.fasta
output_name=my_protein
```

**Response:** Same as JSON endpoint above.

### Process Sequence

```
POST /api/sequence/process
Content-Type: application/json

{
  "query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
}
```

Validates and cleans input sequence without running prediction.

**Response Example:**
```json
{
  "success": true,
  "sequence": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR",
  "sequence_length": 52,
  "is_valid": true
}
```

### Legacy Endpoint

```
POST /predict/structure
Content-Type: multipart/form-data

input_type=sequence
query=MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR
```

Backward compatible with the original structure-prediction API.

**Response Example (Success):**
```json
{
  "result": "/static/pdb/query.pdb"
}
```

**Response Example (Error):**
```json
{
  "result": "❌ Structure prediction failed: Docker container timeout"
}
```

## Input Types

- **auto**: Automatically detect input type
- **sequence**: Raw amino acid sequence
- **uniprot**: UniProt accession ID (e.g., P12345)
- **fasta**: FASTA format content

## Client Usage

```python
from client import StructurePredictClient

client = StructurePredictClient("http://localhost:18906")

# Check health
print(client.health_check())

# Predict from sequence
result = client.predict_from_sequence("MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR")
print(f"Success: {result['success']}")
print(f"PDB Path: {result.get('static_path')}")

# Predict from UniProt ID
result = client.predict_from_uniprot("P12345")

# Predict from FASTA file
result = client.predict_file("protein.fasta")

# Download PDB file
if result.get("success"):
    client.download_pdb(result["static_path"], "output.pdb")
```

## cURL Examples

### Basic requests

```bash
# Health check
curl -X GET "http://localhost:18906/health"
# Response: {"status":"healthy","service":"structure_predict","docker_backend":true,"docker_image":"biochunan/esmfold-image:nonroot-runtime"}

# Get configuration status
curl -X GET "http://localhost:18906/api/config"
# Response: {"configured":true,"issues":[],"output_dir":"/tmp/esmfold_output","docker_image":"biochunan/esmfold-image:nonroot-runtime",...}
```

### Structure prediction

```bash
# Predict a structure (JSON, automatic input detection)
curl -X POST "http://localhost:18906/api/predict/structure" \
    -H "Content-Type: application/json" \
    -d '{"query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR", "input_type": "auto", "output_name": "my_protein"}'
# Response: {"success":true,"pdb_path":"/tmp/esmfold_output/my_protein.pdb","static_path":"/static/pdb/my_protein.pdb","sequence":"MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR","sequence_length":52,"error":null}

# Predict and download the PDB file in one request
curl -X POST "http://localhost:18906/api/predict/structure/download" \
    -H "Content-Type: application/json" \
    -d '{"query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR", "input_type": "auto", "output_name": "my_protein"}' \
    -o my_protein.pdb
# Download the PDB directly to my_protein.pdb

# Predict a structure from an explicit sequence (JSON)
curl -X POST "http://localhost:18906/api/predict/structure" \
    -H "Content-Type: application/json" \
    -d '{"query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR", "input_type": "sequence"}'

# Predict a structure from a UniProt accession (JSON)
curl -X POST "http://localhost:18906/api/predict/structure" \
    -H "Content-Type: application/json" \
    -d '{"query": "P12345", "input_type": "uniprot"}'

# Predict a structure (form input)
curl -X POST "http://localhost:18906/api/predict/structure/form" \
    -F "query=MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR" \
    -F "input_type=auto" \
    -F "output_name=my_protein"

# Predict a structure (FASTA upload)
curl -X POST "http://localhost:18906/api/predict/structure/file" \
    -F "file=@protein.fasta" \
    -F "output_name=my_protein"
```

### Sequence processing

```bash
# Validate and normalize a sequence without predicting a structure
curl -X POST "http://localhost:18906/api/sequence/process" \
    -H "Content-Type: application/json" \
    -d '{"query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"}'
# Response: {"success":true,"sequence":"MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR","sequence_length":52,"is_valid":true}
```

### Legacy endpoint

```bash
# Legacy endpoint (form input)
curl -X POST "http://localhost:18906/predict/structure" \
    -F "input_type=sequence" \
    -F "query=MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
# Response: {"result":"/static/pdb/query.pdb"}
```

### Download results

```bash
# Download the predicted PDB file
curl -O "http://localhost:18906/static/pdb/my_protein.pdb"

# Or select a filename
curl -o output.pdb "http://localhost:18906/static/pdb/my_protein.pdb"
```

## Project Structure

```
structure_predict/
├── main.py                      # FastAPI application
├── client.py                    # Python client
├── conftest.py                  # Pytest configuration
├── requirements.txt             # Dependencies
├── README.md                    # This file
├── models/
│   ├── __init__.py
│   └── structure_predictor.py   # Core prediction logic (Docker backend)
└── tests/
    ├── __init__.py
    └── test_api.py              # API tests
```

## Docker Backend Details

This service uses the `biochunan/esmfold-image:nonroot-runtime` Docker image for ESMFold predictions.

### How It Works

1. User submits a sequence via API
2. Service saves sequence as a FASTA file
3. Service runs Docker container with mounted volumes:
   - Input FASTA file (read-only)
   - Output directory for PDB files
   - Model cache directory for weights
4. Docker container runs ESMFold prediction
5. Service retrieves and serves the resulting PDB file

### Docker Command (Internal)

The service automatically constructs and runs Docker commands like:

```bash
docker run --rm --gpus all \
    -v /path/to/input:/home/vscode/input:ro \
    -v /path/to/output:/home/vscode/output \
    -v ~/.cache/torch/hub/checkpoints:/home/vscode/.cache/torch/hub/checkpoints \
    biochunan/esmfold-image:nonroot-runtime \
    -i /home/vscode/input/query.fasta \
    -o /home/vscode/output
```

### Model Weights

ESMFold model weights (~2.5GB) are downloaded automatically on first prediction and cached in `ESMFOLD_MODEL_CACHE_DIR` (default: `~/.cache/torch/hub/checkpoints`).

### Troubleshooting

**Docker permission denied:**
```bash
sudo usermod -aG docker $USER
# Then logout and login again
```

**GPU not detected:**
```bash
# Check NVIDIA driver
nvidia-smi

# Check nvidia-docker
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

**Image not found:**
```bash
docker pull biochunan/esmfold-image:nonroot-runtime
```

## Notes

- Structure prediction can take several minutes for large sequences
- GPU is strongly recommended (10-100x faster than CPU)
- First prediction is slower due to model weight download
- Predicted PDB files are stored in the configured output directory

## License

Part of the EnzyMind platform.
