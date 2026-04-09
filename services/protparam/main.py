# protparam/main.py
"""
ProtParam Service - Protein Physicochemical Properties Analysis

This microservice provides protein physicochemical properties analysis
using the ExPASy ProtParam service.

Port: 18909
"""

import logging
from typing import Optional

from fastapi import FastAPI
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
async def analyze_protein_physchem(request: ProtParamRequest):
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


@app.post("/query/protein-physchem")
async def analyze_protein_legacy(request: ProtParamRequest):
    """
    Legacy endpoint for backward compatibility (JSON格式).
    """
    try:
        if not request.query or not request.query.strip():
            return {"result": "❌ Please enter a valid protein sequence, UniProt ID, or FASTA content."}
        
        protein = request.query.strip()

        try:
            sequence = classify_input_v2(protein)
        except Exception:
            return {"result": "❌ Please enter a valid protein sequence, UniProt ID, or FASTA content."}

        result = analyzer.analyze(sequence)
        
        if result["success"]:
            return {"result": result["markdown"]}
        else:
            return {"result": f"[ERROR] {result['error']}"}

    except Exception as e:
        return {"result": f"[ERROR] Failed to compute parameters: {str(e)}"}


# ============== Main Entry ==============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18909)
