# enzyme_type/main.py
"""
Enzyme Type Recommendation Service - FastAPI Application
Port: 18908

This service recommends enzyme types (EC numbers) for chemical reactions
using the RetroPlanner API.

API Endpoints:
- POST /api/query/enzyme-type - Recommend enzyme types for a reaction (JSON)
- POST /api/query/enzyme-type/form - Recommend enzyme types (Form input)
- POST /api/query/enzyme-type/top-k - Get top K recommendations
- GET /api/query/enzyme-type/markdown - Get results as markdown table
- GET /health - Health check
"""

from fastapi import FastAPI, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uvicorn

import os
from models.enzyme_type_predictor import EnzymeTypePredictor

app = FastAPI(
    title="Enzyme Type Recommendation Service",
    description="Recommend enzyme types (EC numbers) for chemical reactions using RetroPlanner",
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

# Global predictor instance
predictor: Optional[EnzymeTypePredictor] = None


def get_predictor() -> EnzymeTypePredictor:
    """Get or initialize the predictor instance."""
    global predictor
    if predictor is None:
        predictor = EnzymeTypePredictor(api_url=os.environ.get("RETRO_ENZYME_API_URL") or None)
    return predictor


# ============== Request/Response Models ==============

class EnzymeTypeRequest(BaseModel):
    """Request model for enzyme type recommendation."""
    query: str = Field(..., description="Reaction SMILES (format: reactants>>products)")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "CC(=O)O>>CCO"
            }
        }
    }


class EnzymeTypeTopKRequest(BaseModel):
    """Request model for top-K enzyme type recommendation."""
    query: str = Field(..., description="Reaction SMILES (format: reactants>>products)")
    k: int = Field(default=5, ge=1, le=100, description="Number of top recommendations")


class EnzymeRecommendation(BaseModel):
    """Single enzyme recommendation."""
    ec_number: str
    confidence: float


class EnzymeTypeResponse(BaseModel):
    """Response model for enzyme type recommendation."""
    success: bool
    recommendations: Optional[List[EnzymeRecommendation]] = None
    formatted: Optional[List[str]] = None
    total_count: Optional[int] = None
    message: Optional[str] = None
    error: Optional[str] = None


class EnzymeTypeFormattedResponse(BaseModel):
    """Response model for formatted string result."""
    result: str


class EnzymeTypeMarkdownResponse(BaseModel):
    """Response model for markdown result."""
    result: str
    reaction: str


# ============== Backward Compatible Response ==============

class LegacyResponse(BaseModel):
    """Legacy response format for backward compatibility."""
    result: Optional[List[str]] = None
    error: Optional[str] = None


# ============== Health Check ==============

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "enzyme_type"}


# ============== Main Prediction Endpoints ==============

@app.post("/api/query/enzyme-type", response_model=EnzymeTypeResponse)
def recommend_enzyme_type(request: EnzymeTypeRequest):
    """
    Recommend enzyme types for a chemical reaction.
    
    Takes a reaction SMILES string and returns recommended EC numbers
    with confidence scores.
    
    Args:
        request: JSON request containing reaction SMILES
        
    Returns:
        Enzyme type recommendations with confidence scores
    """
    pred = get_predictor()
    result = pred.predict(request.query, output_topk=1)
    
    if result.get("success"):
        return EnzymeTypeResponse(
            success=True,
            recommendations=[
                EnzymeRecommendation(**rec) 
                for rec in result.get("recommendations", [])
            ],
            formatted=result.get("formatted"),
            total_count=result.get("total_count"),
            message=result.get("message")
        )
    else:
        return EnzymeTypeResponse(
            success=False,
            error=result.get("error")
        )


@app.post("/api/query/enzyme-type/form", response_model=EnzymeTypeResponse)
def recommend_enzyme_type_form(
    query: str = Form(..., description="Reaction SMILES (format: reactants>>products)")
):
    """
    Recommend enzyme types for a chemical reaction (Form input).
    
    Args:
        query: Reaction SMILES from form
        
    Returns:
        Enzyme type recommendations with confidence scores
    """
    pred = get_predictor()
    result = pred.predict(query)
    
    if result.get("success"):
        return EnzymeTypeResponse(
            success=True,
            recommendations=[
                EnzymeRecommendation(**rec) 
                for rec in result.get("recommendations", [])
            ],
            formatted=result.get("formatted"),
            total_count=result.get("total_count"),
            message=result.get("message")
        )
    else:
        return EnzymeTypeResponse(
            success=False,
            error=result.get("error")
        )


@app.post("/api/query/enzyme-type/top-k", response_model=EnzymeTypeResponse)
def recommend_enzyme_type_top_k(request: EnzymeTypeTopKRequest):
    """
    Get top K enzyme type recommendations for a chemical reaction.
    
    Args:
        request: JSON request containing reaction SMILES and k value
        
    Returns:
        Top K enzyme type recommendations
    """
    pred = get_predictor()
    result = pred.predict_top_k(request.query, k=request.k)
    
    if result.get("success"):
        return EnzymeTypeResponse(
            success=True,
            recommendations=[
                EnzymeRecommendation(**rec) 
                for rec in result.get("recommendations", [])
            ],
            formatted=result.get("formatted"),
            total_count=result.get("total_count")
        )
    else:
        return EnzymeTypeResponse(
            success=False,
            error=result.get("error")
        )


@app.post("/api/query/enzyme-type/formatted", response_model=EnzymeTypeFormattedResponse)
def recommend_enzyme_type_formatted(request: EnzymeTypeRequest):
    """
    Get enzyme type recommendations as formatted string.
    
    Args:
        request: JSON request containing reaction SMILES
        
    Returns:
        Formatted string with recommendations
    """
    pred = get_predictor()
    result = pred.predict_formatted(request.query)
    return EnzymeTypeFormattedResponse(result=result)


@app.post("/api/query/enzyme-type/markdown", response_model=EnzymeTypeMarkdownResponse)
def recommend_enzyme_type_markdown(request: EnzymeTypeRequest):
    """
    Get enzyme type recommendations as markdown table.
    
    Args:
        request: JSON request containing reaction SMILES
        
    Returns:
        Markdown formatted table with recommendations
    """
    pred = get_predictor()
    result = pred.predict_to_markdown(request.query)
    return EnzymeTypeMarkdownResponse(result=result, reaction=request.query)


# ============== Legacy Endpoint (Backward Compatibility) ==============

@app.post("/query/enzyme-type", response_model=LegacyResponse)
def recommend_enzyme_type_legacy(request: EnzymeTypeRequest):
    """
    Legacy endpoint for enzyme type recommendation.
    Kept for backward compatibility with the original API.
    
    Args:
        request: JSON request containing reaction SMILES
        
    Returns:
        List of formatted recommendations or error
    """
    pred = get_predictor()
    result = pred.predict(request.query)
    
    if result.get("success"):
        formatted = result.get("formatted", [])
        if not formatted:
            return LegacyResponse(error="No enzyme recommendations found.")
        return LegacyResponse(result=formatted)
    else:
        return LegacyResponse(error=result.get("error"))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=18908)
