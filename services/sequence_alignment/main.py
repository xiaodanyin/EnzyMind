# sequence_alignment/main.py
"""
Sequence Alignment Service - NCBI BLAST Search

This microservice provides protein sequence alignment using NCBI BLAST.

Port: 18910
"""

import logging
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from models.blast_searcher import BlastSearcher, classify_input_v2


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============== FastAPI App ==============

app = FastAPI(
    title="Sequence Alignment Service",
    description="Protein sequence alignment using NCBI BLAST",
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

# Initialize searcher
searcher = BlastSearcher()


# ============== Request/Response Models ==============

class BlastRequest(BaseModel):
    """Request model for BLAST search."""
    query: str = Field(..., description="Protein sequence, UniProt ID, or FASTA content")
    max_results: int = Field(default=3, ge=1, le=50, description="Maximum number of results")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR",
                "max_results": 3
            }
        }
    }


class AlignmentResult(BaseModel):
    """Model for individual alignment result."""
    title: str
    length: int
    e_value: float
    score: Optional[float] = None
    bits: Optional[float] = None
    query: str
    match: str
    subject: str


class BlastResponse(BaseModel):
    """Response model for BLAST search."""
    success: bool
    query_length: Optional[int] = None
    num_results: Optional[int] = None
    alignments: Optional[list] = None
    error: Optional[str] = None


# ============== API Endpoints ==============

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "sequence_alignment"
    }


@app.post("/api/query/blast", response_model=BlastResponse)
async def perform_blast_search(request: BlastRequest):
    """
    Perform NCBI BLAST search.
    
    Args:
        request: BLAST search request
        
    Returns:
        Search results with alignments
    """
    if not request.query or not request.query.strip():
        return BlastResponse(
            success=False,
            error="Query cannot be empty"
        )
    
    result = searcher.search_from_input(request.query, request.max_results)
    return BlastResponse(**result)


@app.post("/api/query/blast/html")
async def perform_blast_search_html(request: BlastRequest):
    """
    Perform BLAST search and return HTML formatted results.
    """
    if not request.query or not request.query.strip():
        return {"result": "<div class='pred-class error'>❌ Query cannot be empty</div>"}
    
    result = searcher.search_from_input(request.query, request.max_results)
    html = searcher.format_as_html(result)
    return {"result": html}


@app.post("/api/query/blast/markdown")
async def perform_blast_search_markdown(request: BlastRequest):
    """
    Perform BLAST search and return Markdown formatted results.
    """
    if not request.query or not request.query.strip():
        return {"result": "❌ Query cannot be empty"}
    
    result = searcher.search_from_input(request.query, request.max_results)
    markdown = searcher.format_as_markdown(result)
    return {"result": markdown}


@app.post("/query/blast")
async def perform_blast_search_legacy(request: BlastRequest):
    """
    Legacy endpoint for backward compatibility (JSON格式).
    """
    try:
        if not request.query or not request.query.strip():
            return {"result": "<div class='pred-class error'>❌ Query is required</div>"}
        
        sequence = classify_input_v2(request.query.strip())
        result = searcher.search(sequence, request.max_results)
        html = searcher.format_as_html(result)
        return {"result": html}

    except Exception as e:
        return {"result": f"<div class='pred-class error'>[ERROR] BLAST query failed: {str(e)}</div>"}


# ============== Main Entry ==============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18910)
