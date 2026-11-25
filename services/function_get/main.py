# function_get/main.py
"""
Function Get Service - 蛋白质功能查询微服务

This service provides endpoints for querying protein function information
from the UniProt database.

Port: 18911
"""

from fastapi import FastAPI, HTTPException, Form, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from typing import Optional, List
import uvicorn

from models.function_query import FunctionQuery


# Initialize FastAPI app
app = FastAPI(
    title="Function Get Service",
    description="蛋白质功能查询微服务 - Query protein function information from UniProt",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize function query handler
function_query = FunctionQuery()


# Request/Response Models
class FunctionQueryRequest(BaseModel):
    """Request model for function query."""
    query: str = Field(..., description="UniProt accession ID (e.g., P12345, Q9Y6K9)")


class FunctionQueryResponse(BaseModel):
    """Response model for function query."""
    source: Optional[dict] = None
    success: bool = Field(..., description="Whether the query was successful")
    uniprot_id: str = Field(..., description="UniProt accession ID")
    function: Optional[str] = Field(None, description="Protein function description")
    protein_name: Optional[str] = Field(None, description="Protein name")
    organism: Optional[str] = Field(None, description="Source organism")
    gene_names: Optional[List[str]] = Field(None, description="Gene names")
    error: Optional[str] = Field(None, description="Error message if query failed")


class BatchQueryRequest(BaseModel):
    """Request model for batch function query."""
    queries: List[str] = Field(..., description="List of UniProt accession IDs")


class BatchQueryResponse(BaseModel):
    """Response model for batch function query."""
    results: dict = Field(..., description="Dictionary mapping UniProt IDs to results")
    total: int = Field(..., description="Total number of queries")
    successful: int = Field(..., description="Number of successful queries")


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    service: str
    version: str


# Endpoints
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        service="function_get",
        version="1.0.0"
    )


@app.post("/api/query/function", response_model=FunctionQueryResponse, tags=["Function Query"])
async def query_function(request: FunctionQueryRequest):
    """
    Query protein function from UniProt database.
    
    - **query**: UniProt accession ID (e.g., P12345, Q9Y6K9)
    
    Returns protein function description along with additional metadata.
    """
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="UniProt ID is required")
    
    result = await run_in_threadpool(function_query.get_function, request.query.strip())
    
    return FunctionQueryResponse(
        success=result["success"],
        uniprot_id=result["uniprot_id"],
        function=result.get("function"),
        protein_name=result.get("protein_name"),
        organism=result.get("organism"),
        gene_names=result.get("gene_names"),
        error=result.get("error"),
        source=result.get('source')
    )


@app.post("/api/query/function/form", response_model=FunctionQueryResponse, tags=["Function Query"])
async def query_function_form(
    query: str = Form(..., description="UniProt accession ID")
):
    """
    Query protein function via form submission.
    
    Same as /api/query/function but accepts form data.
    """
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="UniProt ID is required")
    
    result = await run_in_threadpool(function_query.get_function, query.strip())
    
    return FunctionQueryResponse(
        success=result["success"],
        uniprot_id=result["uniprot_id"],
        function=result.get("function"),
        protein_name=result.get("protein_name"),
        organism=result.get("organism"),
        gene_names=result.get("gene_names"),
        error=result.get("error"),
        source=result.get('source')
    )


@app.post("/api/query/function/batch", response_model=BatchQueryResponse, tags=["Function Query"])
async def query_function_batch(request: BatchQueryRequest):
    """
    Query functions for multiple UniProt IDs.
    
    - **queries**: List of UniProt accession IDs
    
    Returns results for all queries.
    """
    if not request.queries:
        raise HTTPException(status_code=400, detail="At least one UniProt ID is required")
    
    # Clean and deduplicate IDs
    clean_ids = list(set([q.strip() for q in request.queries if q and q.strip()]))
    
    if not clean_ids:
        raise HTTPException(status_code=400, detail="No valid UniProt IDs provided")
    
    results = await run_in_threadpool(function_query.batch_get_functions, clean_ids)
    
    successful = sum(1 for r in results.values() if r["success"])
    
    return BatchQueryResponse(
        results=results,
        total=len(clean_ids),
        successful=successful
    )


@app.post("/api/query/function/file", response_model=BatchQueryResponse, tags=["Function Query"])
async def query_function_file(
    file: UploadFile = File(..., description="Text file with UniProt IDs (one per line)")
):
    """
    Query functions for UniProt IDs from uploaded file.
    
    File should contain one UniProt ID per line.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    try:
        content = await file.read()
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded text")
    
    # Parse IDs from file
    lines = text.strip().split("\n")
    uniprot_ids = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
    
    if not uniprot_ids:
        raise HTTPException(status_code=400, detail="No valid UniProt IDs found in file")
    
    # Deduplicate
    uniprot_ids = list(set(uniprot_ids))
    
    results = await run_in_threadpool(function_query.batch_get_functions, uniprot_ids)
    
    successful = sum(1 for r in results.values() if r["success"])
    
    return BatchQueryResponse(
        results=results,
        total=len(uniprot_ids),
        successful=successful
    )


# Legacy endpoint for backward compatibility
@app.post("/query/function", response_model=FunctionQueryResponse, tags=["Legacy"])
async def query_function_legacy(request: FunctionQueryRequest):
    """
    Legacy endpoint for function query.
    
    Maintained for backward compatibility. Use /api/query/function instead.
    """
    return await query_function(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=18911)
