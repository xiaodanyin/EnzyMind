# sequence_alignment/main.py
"""
Sequence Alignment Service - NCBI BLAST Search

This microservice provides protein sequence alignment using NCBI BLAST.

Port: 18910
"""

import logging
import re
from typing import Optional, Literal

from fastapi import FastAPI, Form, File, UploadFile, Request, Query, HTTPException
from starlette.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from models.local_blast import default_database
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
    database: Literal["nr", "swissprot", "local_uniprot"] = Field(default_factory=default_database)
    wait_for_result: bool = True
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
    status: Optional[str] = None
    message: Optional[str] = None
    ncbi_url: Optional[str] = None
    submitted_at: Optional[float] = None
    next_poll_at: Optional[float] = None
    last_checked_at: Optional[float] = None
    last_poll_error: Optional[str] = None
    query_length: Optional[int] = None
    num_results: Optional[int] = None
    alignments: Optional[list] = None
    error: Optional[str] = None
    request_id: Optional[str] = None
    database: Optional[str] = None
    source: Optional[str] = None
    sequence: Optional[str] = None
    sequence_source: Optional[dict] = None
    database_release: Optional[str] = None
    database_size: Optional[int] = None
    annotation_status: Optional[str] = None
    error_code: Optional[str] = None
    error_stage: Optional[str] = None
    retryable: Optional[bool] = None


# ============== API Endpoints ==============

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "sequence_alignment"
    }


@app.post("/api/query/blast", response_model=BlastResponse)
def perform_blast_search(request: BlastRequest):
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
    
    result = searcher.search_from_input(request.query, request.max_results, database=request.database, wait_for_result=request.wait_for_result)
    if request.database == "local_uniprot" and not result.get("success"):
        status = {"blast_busy": 429, "blast_timeout": 504, "invalid_input": 422, "uniprot_not_found": 404}.get(result.get("error_code"), 503)
        return JSONResponse(result, status_code=status)
    return BlastResponse(**result)


@app.get("/api/query/blast/results/{request_id}", response_model=BlastResponse)
def retrieve_blast(request_id: str, max_results: int = Query(3, ge=1, le=50), database: Literal["nr", "swissprot"] = "nr"):
    if not re.fullmatch(r"[A-Z0-9-]{5,40}", request_id):
        raise HTTPException(422, "Invalid NCBI request ID.")
    return searcher.poll(request_id, max_results, database)


@app.post("/api/query/blast/form", response_model=BlastResponse)
def perform_blast_search_form(query: str = Form(""), max_results: int = Form(3, ge=1, le=50)):
    return perform_blast_search(BlastRequest(query=query, max_results=max_results))


@app.post("/api/query/blast/file", response_model=BlastResponse)
def perform_blast_search_file(file: UploadFile = File(...), max_results: int = Form(3, ge=1, le=50)):
    try:
        content = file.file.read().decode("utf-8")
    except UnicodeDecodeError:
        return BlastResponse(success=False, error="Upload a UTF-8 FASTA file.")
    return perform_blast_search(BlastRequest(query=content, max_results=max_results))


@app.post("/api/query/blast/html")
def perform_blast_search_html(request: BlastRequest):
    """
    Perform BLAST search and return HTML formatted results.
    """
    if not request.query or not request.query.strip():
        return {"result": "<div class='pred-class error'>❌ Query cannot be empty</div>"}
    
    result = searcher.search_from_input(request.query, request.max_results, database=request.database, wait_for_result=request.wait_for_result)
    html = searcher.format_as_html(result)
    return {"result": html}


@app.post("/api/query/blast/markdown")
def perform_blast_search_markdown(request: BlastRequest):
    """
    Perform BLAST search and return Markdown formatted results.
    """
    if not request.query or not request.query.strip():
        return {"result": "❌ Query cannot be empty"}
    
    result = searcher.search_from_input(request.query, request.max_results, database=request.database, wait_for_result=request.wait_for_result)
    markdown = searcher.format_as_markdown(result)
    return {"result": markdown}


@app.post("/query/blast")
async def perform_blast_search_legacy(request: Request):
    """
    Legacy endpoint for backward compatibility (JSON格式).
    """
    try:
        data = await request.json() if "application/json" in request.headers.get("content-type", "") else await request.form()
        query = str(data.get("query") or "")
        if not query.strip():
            return {"result": "<div class='pred-class error'>❌ Query is required</div>"}
        parsed = BlastRequest(query=query, max_results=data.get("max_results", 3))
        result = await run_in_threadpool(searcher.search_from_input, parsed.query, parsed.max_results, parsed.database)
        html = searcher.format_as_html(result)
        return {"result": html}

    except Exception as e:
        return {"result": f"<div class='pred-class error'>[ERROR] BLAST query failed: {str(e)}</div>"}


# ============== Main Entry ==============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18910)
