# enzyme_subclass/main.py
"""
Enzyme Subclass Service - 酶亚类查询微服务

This service provides endpoints for querying enzyme subclass information
from a local enzyme database.

Port: 18912
"""

from fastapi import FastAPI, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uvicorn

from models.subclass_query import EnzymeSubclassQuery


# Initialize FastAPI app
app = FastAPI(
    title="Enzyme Subclass Service",
    description="酶亚类查询微服务 - Query enzyme subclass information from local database",
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

# Initialize query handler
subclass_query = EnzymeSubclassQuery()


# Request/Response Models
class SubclassQueryRequest(BaseModel):
    """Request model for subclass query."""
    query: str = Field(..., description="Enzyme class name (e.g., 'Oxidoreductases', 'hydrolase')")
    num_samples: Optional[int] = Field(5, ge=1, le=100, description="Number of samples to return")
    seed: Optional[int] = Field(42, description="Random seed for reproducibility")


class SubclassEntry(BaseModel):
    """Model for a single subclass entry."""
    ID: str = Field(..., description="EC number")
    DE: str = Field(..., description="Description")
    CA: List[str] = Field(default_factory=list, description="Catalytic activities")
    DR: List[str] = Field(default_factory=list, description="UniProt IDs")


class SubclassQueryResponse(BaseModel):
    """Response model for subclass query."""
    success: bool = Field(..., description="Whether the query was successful")
    enzyme_class: Optional[str] = Field(None, description="Normalized enzyme class name")
    ec_prefix: Optional[int] = Field(None, description="EC number prefix (1-7)")
    result: Optional[str] = Field(None, description="Markdown formatted result")
    subclasses: List[Dict[str, Any]] = Field(default_factory=list, description="Raw subclass data")
    total_available: Optional[int] = Field(None, description="Total number of subclasses available")
    sampled: Optional[int] = Field(None, description="Number of subclasses sampled")
    error: Optional[str] = Field(None, description="Error message if failed")
    valid_classes: Optional[List[str]] = Field(None, description="Valid class names if invalid input")


class EnzymeClassesResponse(BaseModel):
    """Response model for listing enzyme classes."""
    classes: Dict[str, int] = Field(..., description="Mapping of class names to EC numbers")


class StatisticsResponse(BaseModel):
    """Response model for database statistics."""
    success: bool
    total_entries: Optional[int] = None
    by_class: Optional[Dict[str, Dict[str, Any]]] = None
    error: Optional[str] = None


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
        service="enzyme_subclass",
        version="1.0.0"
    )


@app.post("/api/query/enzyme-subclass", response_model=SubclassQueryResponse, tags=["Subclass Query"])
async def query_enzyme_subclass(request: SubclassQueryRequest):
    """
    Query enzyme subclass information.
    
    - **query**: Enzyme class name (e.g., 'Oxidoreductases', 'Hydrolase', 'transferase')
    - **num_samples**: Number of random samples to return (default: 5)
    - **seed**: Random seed for reproducibility (default: 42)
    
    Returns randomly sampled subclasses with their EC numbers, descriptions,
    catalytic activities, and associated UniProt IDs.
    """
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Enzyme class name is required")
    
    result = subclass_query.get_subclasses(
        query=request.query.strip(),
        num_samples=request.num_samples,
        seed=request.seed
    )
    
    return SubclassQueryResponse(
        success=result.get("success", False),
        enzyme_class=result.get("enzyme_class"),
        ec_prefix=result.get("ec_prefix"),
        result=result.get("result"),
        subclasses=result.get("subclasses", []),
        total_available=result.get("total_available"),
        sampled=result.get("sampled"),
        error=result.get("error"),
        valid_classes=result.get("valid_classes")
    )


@app.post("/api/query/enzyme-subclass/form", response_model=SubclassQueryResponse, tags=["Subclass Query"])
async def query_enzyme_subclass_form(
    query: str = Form(..., description="Enzyme class name"),
    num_samples: int = Form(5, ge=1, le=100, description="Number of samples"),
    seed: int = Form(42, description="Random seed")
):
    """
    Query enzyme subclass via form submission.
    
    Same as /api/query/enzyme-subclass but accepts form data.
    """
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Enzyme class name is required")
    
    result = subclass_query.get_subclasses(
        query=query.strip(),
        num_samples=num_samples,
        seed=seed
    )
    
    return SubclassQueryResponse(
        success=result.get("success", False),
        enzyme_class=result.get("enzyme_class"),
        ec_prefix=result.get("ec_prefix"),
        result=result.get("result"),
        subclasses=result.get("subclasses", []),
        total_available=result.get("total_available"),
        sampled=result.get("sampled"),
        error=result.get("error"),
        valid_classes=result.get("valid_classes")
    )


@app.get("/api/enzyme-classes", response_model=EnzymeClassesResponse, tags=["Enzyme Classes"])
async def get_enzyme_classes():
    """
    Get all available enzyme classes.
    
    Returns a mapping of enzyme class names to their EC number prefixes.
    """
    return EnzymeClassesResponse(
        classes=subclass_query.get_all_classes()
    )


@app.get("/api/statistics", response_model=StatisticsResponse, tags=["Statistics"])
async def get_statistics():
    """
    Get database statistics.
    
    Returns statistics about the loaded enzyme database.
    """
    result = subclass_query.get_class_statistics()
    return StatisticsResponse(**result)


# Legacy endpoint for backward compatibility
@app.post("/query/enzyme-subclass", response_model=SubclassQueryResponse, tags=["Legacy"])
async def query_enzyme_subclass_legacy(request: SubclassQueryRequest):
    """
    Legacy endpoint for enzyme subclass query.
    
    Maintained for backward compatibility. Use /api/query/enzyme-subclass instead.
    """
    return await query_enzyme_subclass(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=18912)
