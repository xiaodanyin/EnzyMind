"""Kinetic Params Service - Port: 18917"""
from fastapi import FastAPI, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uvicorn
from models.kinetic_query import KineticParamsQuery

app = FastAPI(title="Kinetic Params Service", description="动力学参数查询微服务", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
query = KineticParamsQuery()

class KineticRequest(BaseModel):
    query: str = Field(..., description="UniProt accession ID")

class KineticResponse(BaseModel):
    success: bool
    source: Optional[dict] = None
    uniprot_id: Optional[str] = None
    km: List[Dict[str, Any]] = Field(default_factory=list)
    vmax: List[Dict[str, Any]] = Field(default_factory=list)
    kcat_note: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str

@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="healthy", service="kinetic_params", version="1.0.0")

@app.post("/api/query/kinetics", response_model=KineticResponse)
async def query_kinetics(request: KineticRequest):
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="UniProt ID is required")
    result = await run_in_threadpool(query.get_kinetics, request.query.strip())
    return KineticResponse(**result)

@app.post("/api/query/kinetics/form", response_model=KineticResponse)
async def query_kinetics_form(query_id: str = Form(..., alias="query")):
    if not query_id or not query_id.strip():
        raise HTTPException(status_code=400, detail="UniProt ID is required")
    result = await run_in_threadpool(query.get_kinetics, query_id.strip())
    return KineticResponse(**result)

@app.post("/query/kinetics", response_model=KineticResponse, tags=["Legacy"])
async def query_kinetics_legacy(request: KineticRequest):
    return await query_kinetics(request)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=18917)
