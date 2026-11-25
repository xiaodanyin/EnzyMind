# protparam/main.py
"""
ProtParam Service - Protein Physicochemical Properties Analysis

This microservice provides protein physicochemical properties analysis
using the ExPASy ProtParam service.

Port: 18909
"""

import logging
from typing import Optional

from fastapi import FastAPI, Request, UploadFile, File, Form
from starlette.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from models.protparam_analyzer import ProtParamAnalyzer, classify_input_v2


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============== FastAPI App ==============

app = FastAPI(
    title="ProtParam Service",
    description="Protein physicochemical properties analysis using ExPASy ProtParam",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize analyzer
analyzer = ProtParamAnalyzer()


# ============== Request/Response Models ==============

class ProtParamRequest(BaseModel):
    """Request model for ProtParam analysis."""
    query: str = Field(..., description="Protein sequence, UniProt ID, or FASTA content")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
            }
        }
    }


class ProtParamResponse(BaseModel):
    """Response model for ProtParam analysis."""
    success: bool
    sequence_length: Optional[int] = None
    markdown: Optional[str] = None
    raw_text: Optional[str] = None
    parameters: Optional[dict] = None
    amino_acid_composition: Optional[list] = None
    source: Optional[dict] = None
    fallback_reason: Optional[str] = None
    error: Optional[str] = None


# ============== API Endpoints ==============

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "protparam"
    }


@app.post("/api/query/protein-physchem", response_model=ProtParamResponse)
def analyze_protein_physchem(request: ProtParamRequest):
    """
    Analyze protein physicochemical properties.
    
    Args:
        request: Analysis request with protein sequence/UniProt ID/FASTA
        
    Returns:
        Analysis results with parameters
    """
    if not request.query or not request.query.strip():
        return ProtParamResponse(
            success=False,
            error="Query cannot be empty"
        )
    
    result = analyzer.analyze_from_input(request.query)
    return ProtParamResponse(**result)


@app.post("/api/query/protein-physchem/form", response_model=ProtParamResponse)
def analyze_protein_form(query: str = Form("")):
    return analyze_protein_physchem(ProtParamRequest(query=query))


@app.post("/api/query/protein-physchem/file", response_model=ProtParamResponse)
async def analyze_protein_file(file: UploadFile = File(...)):
    content = await file.read(1_048_577)
    if len(content) > 1_048_576:
        return ProtParamResponse(success=False, error="Choose a FASTA text file smaller than 1 MB.")
    try:
        query = content.decode("utf-8")
    except UnicodeDecodeError:
        return ProtParamResponse(success=False, error="Upload a UTF-8 FASTA text file.")
    return await run_in_threadpool(analyze_protein_physchem, ProtParamRequest(query=query))


@app.post("/query/protein-physchem")
async def analyze_protein_legacy(request: Request):
    """Preserve both JSON and historical form clients, including the result field."""
    try:
        body = await request.json() if 'application/json' in request.headers.get('content-type', '') else dict(await request.form())
        query = body.get('query', '') if isinstance(body, dict) else ''
        if not isinstance(query, str) or not query.strip():
            message = "Enter a protein sequence, UniProt accession, or FASTA record."
            return JSONResponse({"success": False, "error_code": "invalid_input", "error": message,
                                 "result": "[ERROR] " + message,
                                 "detail": [{"loc": ["body", "query"], "msg": message, "type": "missing"}]},
                                status_code=422)
        result = await run_in_threadpool(analyzer.analyze_from_input, query)
        if result["success"]:
            return {"result": result["markdown"], "data": {k: v for k, v in result.items() if k != "markdown"}}
        return {"result": f"[ERROR] {result['error']}"}
    except Exception as e:
        return {"result": f"[ERROR] Failed to compute parameters: {str(e)}"}


# ============== Main Entry ==============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18909)
