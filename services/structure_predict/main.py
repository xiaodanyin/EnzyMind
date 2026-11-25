# structure_predict/main.py
"""
Structure Prediction Service - ESMFold Protein Structure Prediction via Docker

This microservice provides protein structure prediction using ESMFold
running in a Docker container (biochunan/esmfold-image:nonroot-runtime).

Supports multiple input types: raw sequence, UniProt ID, FASTA content/file.

Port: 18906
"""

import os
import logging
import argparse
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from models.structure_predictor import (
    StructurePredictor, 
    DockerESMFoldRunner,
    classify_input_v2,
    save_sequence_as_fasta,
    _clean_sequence
)


# ============== Argument Parser ==============

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Structure Prediction Service - ESMFold via Docker"
    )
    
    # Docker configuration
    parser.add_argument(
        "--docker-image",
        type=str,
        default=os.getenv("ESMFOLD_DOCKER_IMAGE", "biochunan/esmfold-image:nonroot-runtime"),
        help="Docker image for ESMFold (default: biochunan/esmfold-image:nonroot-runtime)"
    )
    parser.add_argument(
        "--model-cache-dir",
        type=str,
        default=os.getenv("ESMFOLD_MODEL_CACHE_DIR", os.path.expanduser("~/.cache/torch/hub/checkpoints")),
        help="Directory for model weights cache"
    )
    parser.add_argument(
        "--use-gpu",
        type=str,
        default=os.getenv("ESMFOLD_USE_GPU", "true"),
        help="Use GPU for prediction (true/false, default: true)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(os.getenv("ESMFOLD_TIMEOUT", "3600")),
        help="Prediction timeout in seconds (default: 3600)"
    )
    
    # Output directories
    parser.add_argument(
        "--output-dir",
        type=str,
        default=os.getenv("ESMFOLD_OUTPUT_DIR", "/tmp/esmfold_output"),
        help="Directory for PDB output files"
    )
    parser.add_argument(
        "--fasta-dir",
        type=str,
        default=os.getenv("ESMFOLD_FASTA_DIR", "/tmp/esmfold_fasta"),
        help="Directory for FASTA files"
    )
    parser.add_argument(
        "--static-pdb-dir",
        type=str,
        default=os.getenv("STATIC_PDB_DIR", "/tmp/static/pdb"),
        help="Directory for serving static PDB files"
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default=os.getenv("ESMFOLD_LOG_DIR", None),
        help="Directory for Docker logs (optional)"
    )
    
    # Server configuration
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=18906,
        help="Port to listen on (default: 18906)"
    )
    
    return parser.parse_args()


# Parse arguments (only when running as main script)
# When imported by uvicorn, use defaults
args = parse_args() if __name__ == "__main__" else None


# ============== Configuration ==============

# Docker configuration (use args if available, otherwise env/defaults)
DOCKER_IMAGE = getattr(args, 'docker_image', None) or os.getenv(
    "ESMFOLD_DOCKER_IMAGE",
    "biochunan/esmfold-image:nonroot-runtime"
)
MODEL_CACHE_DIR = getattr(args, 'model_cache_dir', None) or os.getenv(
    "ESMFOLD_MODEL_CACHE_DIR",
    os.path.expanduser("~/.cache/torch/hub/checkpoints")
)
_use_gpu_str = getattr(args, 'use_gpu', None) or os.getenv("ESMFOLD_USE_GPU", "true")
USE_GPU = _use_gpu_str.lower() == "true"
PREDICTION_TIMEOUT = getattr(args, 'timeout', None) or int(os.getenv("ESMFOLD_TIMEOUT", "3600"))

# Output directories
ESMFOLD_OUTPUT_DIR = getattr(args, 'output_dir', None) or os.getenv(
    "ESMFOLD_OUTPUT_DIR",
    "/tmp/esmfold_output"
)
ESMFOLD_FASTA_DIR = getattr(args, 'fasta_dir', None) or os.getenv(
    "ESMFOLD_FASTA_DIR", 
    "/tmp/esmfold_fasta"
)
STATIC_PDB_DIR = getattr(args, 'static_pdb_dir', None) or os.getenv(
    "STATIC_PDB_DIR",
    "/tmp/static/pdb"
)
LOG_DIR = getattr(args, 'log_dir', None) or os.getenv("ESMFOLD_LOG_DIR", None)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============== Predictor Instance ==============

predictor: Optional[StructurePredictor] = None
backend_config: Dict[str, Any] = {"configured": False, "issues": ["Predictor not initialized"]}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global predictor, backend_config
    
    # Initialize predictor on startup
    try:
        predictor = StructurePredictor(
            output_dir=ESMFOLD_OUTPUT_DIR,
            fasta_dir=ESMFOLD_FASTA_DIR,
            static_pdb_dir=STATIC_PDB_DIR,
            docker_image=DOCKER_IMAGE,
            model_cache_dir=MODEL_CACHE_DIR,
            use_gpu=USE_GPU,
            timeout=PREDICTION_TIMEOUT,
            log_dir=LOG_DIR
        )
        logger.info("Structure predictor initialized successfully")
        
        # Check configuration
        config = await run_in_threadpool(predictor.check_config)
        backend_config = config
        if not config["configured"]:
            logger.warning(f"Docker backend configuration issues: {config['issues']}")
        else:
            logger.info(f"Docker image: {DOCKER_IMAGE}")
            logger.info(f"GPU enabled: {USE_GPU}")
    except Exception as e:
        logger.error(f"Failed to initialize predictor: {e}")
        predictor = None
    
    yield
    
    # Cleanup on shutdown
    logger.info("Shutting down structure prediction service")


# ============== FastAPI App ==============

app = FastAPI(
    title="Structure Prediction Service",
    description="Protein structure prediction using ESMFold",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for PDB serving
os.makedirs(STATIC_PDB_DIR, exist_ok=True)


# ============== Request/Response Models ==============

class StructureRequest(BaseModel):
    """Request model for structure prediction."""
    query: str = Field(..., description="Protein sequence, UniProt ID, or FASTA content")
    input_type: str = Field(
        default="auto", 
        description="Input type: auto, sequence, uniprot, fasta"
    )
    output_name: str = Field(
        default="query",
        description="Name for output files"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR",
                "input_type": "auto",
                "output_name": "my_protein"
            }
        }
    }


class StructureResponse(BaseModel):
    """Response model for structure prediction."""
    success: bool
    pdb_path: Optional[str] = None
    static_path: Optional[str] = None
    sequence: Optional[str] = None
    sequence_length: Optional[int] = None
    prediction_time: Optional[float] = None
    error: Optional[str] = None


def prediction_response(result):
    if result.get("success"):
        return StructureResponse(**result)
    code = result.get("error_code", "structure_worker_failed")
    status = {"invalid_input": 422, "uniprot_invalid_accession": 422,
              "uniprot_not_found": 404, "structure_busy": 503,
              "structure_memory_exhausted": 503, "structure_unavailable": 503,
              "structure_timeout": 504}.get(code, 502)
    return JSONResponse({**result, "error_code": code}, status_code=status)


class ConfigResponse(BaseModel):
    """Response model for configuration check."""
    configured: bool
    issues: List[str]
    output_dir: str
    docker_image: str
    model_cache_dir: Optional[str] = None
    use_gpu: bool
    docker_available: Optional[bool] = None
    image_available: Optional[bool] = None
    gpu_available: Optional[bool] = None


# ============== API Endpoints ==============

@app.get("/health")
async def health_check():
    """Cheap readiness check; never launch a GPU container for a probe."""
    ready = predictor is not None and backend_config["configured"]
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=200 if ready else 503, content={
        "status": "healthy" if ready else "unavailable",
        "service": "structure_predict",
        "docker_backend": ready,
        "docker_image": DOCKER_IMAGE,
        "issues": backend_config.get("issues", []),
    })


@app.get("/api/config", response_model=ConfigResponse)
async def get_config():
    """Get Docker backend configuration status."""
    global backend_config
    if not predictor:
        return ConfigResponse(
            configured=False,
            issues=["Predictor not initialized"],
            output_dir=ESMFOLD_OUTPUT_DIR,
            docker_image=DOCKER_IMAGE,
            model_cache_dir=MODEL_CACHE_DIR,
            use_gpu=USE_GPU
        )
    
    config = await run_in_threadpool(predictor.check_config)
    backend_config = config
    return ConfigResponse(**config)


@app.post("/api/predict/structure", response_model=StructureResponse)
async def predict_structure(request: StructureRequest):
    """
    Predict protein structure from sequence/UniProt ID/FASTA.
    
    Args:
        request: Structure prediction request
        
    Returns:
        Prediction result with PDB path
    """
    if not request.query or not request.query.strip():
        return prediction_response({"success": False, "error_code": "invalid_input", "error": "Query cannot be empty"})

    if not predictor:
        return prediction_response({"success": False, "error_code": "structure_unavailable", "error": "Predictor not initialized"})
    
    result = await run_in_threadpool(predictor.predict_from_input,
        input_data=request.query,
        input_type=request.input_type,
        output_name=request.output_name
    )
    
    return prediction_response(result)


@app.post("/api/predict/structure/download")
async def predict_structure_download(request: StructureRequest):
    """
    Predict protein structure and directly download PDB file.
    
    One-click prediction + download workflow.
    
    Args:
        request: Structure prediction request
        
    Returns:
        PDB file as downloadable attachment
    """
    if not predictor:
        raise HTTPException(status_code=500, detail="Predictor not initialized")
    
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    result = await run_in_threadpool(predictor.predict_from_input,
        input_data=request.query,
        input_type=request.input_type,
        output_name=request.output_name
    )
    
    if not result["success"]:
        return prediction_response(result)
    
    pdb_path = result["pdb_path"]
    
    if not os.path.exists(pdb_path):
        raise HTTPException(status_code=404, detail="PDB file not found")
    
    return FileResponse(
        path=pdb_path,
        filename=f"{request.output_name}.pdb",
        media_type="chemical/x-pdb",
        headers={
            "Content-Disposition": f"attachment; filename={request.output_name}.pdb"
        }
    )


@app.post("/api/predict/structure/form", response_model=StructureResponse)
async def predict_structure_form(
    query: str = Form(...),
    input_type: str = Form(default="auto"),
    output_name: str = Form(default="query")
):
    """
    Predict protein structure using form input.
    
    Args:
        query: Protein sequence, UniProt ID, or FASTA content
        input_type: Type of input
        output_name: Name for output files
        
    Returns:
        Prediction result with PDB path
    """
    if not query or not query.strip():
        return prediction_response({"success": False, "error_code": "invalid_input", "error": "Query cannot be empty"})

    if not predictor:
        return prediction_response({"success": False, "error_code": "structure_unavailable", "error": "Predictor not initialized"})
    
    result = await run_in_threadpool(predictor.predict_from_input,
        input_data=query,
        input_type=input_type,
        output_name=output_name
    )
    
    return prediction_response(result)


@app.post("/api/predict/structure/file", response_model=StructureResponse)
async def predict_structure_file(
    file: UploadFile = File(...),
    output_name: str = Form(default="query")
):
    """
    Predict protein structure from uploaded FASTA file.
    
    Args:
        file: Uploaded FASTA file
        output_name: Name for output files
        
    Returns:
        Prediction result with PDB path
    """
    if not file:
        return prediction_response({"success": False, "error_code": "invalid_input", "error": "No file uploaded"})

    if not predictor:
        return prediction_response({"success": False, "error_code": "structure_unavailable", "error": "Predictor not initialized"})
    
    content = await file.read()
    result = await run_in_threadpool(predictor.predict_from_file, content, output_name)
    
    return prediction_response(result)


@app.post("/predict/structure")
async def predict_structure_legacy(
    input_type: str = Form(...),
    query: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    """
    Legacy endpoint for backward compatibility.
    
    This endpoint matches the original enzyme_agent API signature.
    """
    if not predictor:
        return {"result": "❌ Predictor not initialized"}
    
    try:
        # Handle file upload
        if input_type == "fasta" and file is not None:
            fasta_content = (await file.read()).decode("utf-8")
            protein = fasta_content
        else:
            if query is None:
                return {"result": "❌ Query is required"}
            protein = query.strip()
        
        # Process input
        sequence = await run_in_threadpool(classify_input_v2, protein)
        
        # Predict
        result = await run_in_threadpool(predictor.predict_from_sequence, sequence)
        
        if result["success"]:
            return {"result": result["static_path"]}
        else:
            return {"result": f"❌ Structure prediction failed: {result['error']}"}
            
    except Exception as e:
        return {"result": f"❌ Failed to classify input: {e}"}


@app.post("/api/sequence/process")
async def process_sequence(request: StructureRequest):
    """
    Process and validate input sequence without running prediction.
    
    Useful for validating input before expensive prediction.
    """
    try:
        sequence = await run_in_threadpool(classify_input_v2, request.query)
        return {
            "success": True,
            "sequence": sequence,
            "sequence_length": len(sequence),
            "is_valid": len(sequence) > 0
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# ============== Main Entry ==============

if __name__ == "__main__":
    import uvicorn
    
    host = getattr(args, 'host', '0.0.0.0') or '0.0.0.0'
    port = getattr(args, 'port', 18906) or 18906
    
    print(f"Starting Structure Prediction Service...")
    print(f"  Docker Image: {DOCKER_IMAGE}")
    print(f"  Model Cache: {MODEL_CACHE_DIR}")
    print(f"  Use GPU: {USE_GPU}")
    print(f"  Output Dir: {ESMFOLD_OUTPUT_DIR}")
    print(f"  Static PDB Dir: {STATIC_PDB_DIR}")
    print(f"  Host: {host}, Port: {port}")
    
    uvicorn.run(app, host=host, port=port)
