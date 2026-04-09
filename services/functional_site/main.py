"""Functional Site Service - Port: 18916"""
from fastapi import FastAPI, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uvicorn
from models.site_query import FunctionalSiteQuery

app = FastAPI(title="Functional Site Service", description="功能位点查询微服务", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
query = FunctionalSiteQuery()

class SiteRequest(BaseModel):
    query: str = Field(..., description="UniProt accession ID")

class SiteResponse(BaseModel):
    success: bool
    uniprot_id: Optional[str] = None
    sites: List[Dict[str, Any]] = Field(default_factory=list)
    count: Optional[int] = None
    result: Optional[str] = None
    error: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str

@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="healthy", service="functional_site", version="1.0.0")

@app.post("/api/query/features", response_model=SiteResponse)
async def query_features(request: SiteRequest):
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="UniProt ID is required")
    result = query.get_sites(request.query.strip())
    return SiteResponse(**result)

@app.post("/api/query/features/form", response_model=SiteResponse)
async def query_features_form(query_id: str = Form(..., alias="query")):
    if not query_id or not query_id.strip():
        raise HTTPException(status_code=400, detail="UniProt ID is required")
    result = query.get_sites(query_id.strip())
    return SiteResponse(**result)

@app.post("/query/features", response_model=SiteResponse, tags=["Legacy"])
async def query_features_legacy(request: SiteRequest):
    return await query_features(request)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=18916)
