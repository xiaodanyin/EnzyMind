"""Enzyme Full Info Service - Port: 18915"""

from fastapi import FastAPI, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uvicorn

from models.full_info_query import EnzymeFullInfoQuery
from models.reference_structure import reference_structure
from models.reference_sequence import reference_sequence

app = FastAPI(title="Enzyme Full Info Service", description="酶完整信息查询微服务", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

query = EnzymeFullInfoQuery()


class InfoRequest(BaseModel):
    uniprot_id: str = Field(..., description="UniProt accession ID")


class InfoResponse(BaseModel):
    success: bool
    protein_name: Optional[str] = None
    organism: Dict[str, Any] = Field(default_factory=dict)
    gene_names: List[str] = Field(default_factory=list)
    reviewed: Optional[bool] = None
    ec_numbers: List[str] = Field(default_factory=list)
    alphafold_id: Optional[str] = None
    function: Optional[str] = None
    cofactors: List[str] = Field(default_factory=list)
    structure_references: List[Dict[str, Any]] = Field(default_factory=list)
    sequence_features: List[Dict[str, Any]] = Field(default_factory=list)
    source: Optional[dict] = None
    partial: bool = False
    warnings: List[str] = Field(default_factory=list)
    unavailable_sections: List[str] = Field(default_factory=list)
    is_enzyme: Optional[bool] = None
    uniprot_id: Optional[str] = None
    sequence_info: Optional[Dict[str, Any]] = None
    catalytic_activities: Optional[List[Dict[str, Any]]] = None
    kinetic_parameters: Optional[Dict[str, Any]] = None
    functional_sites: Optional[List[Dict[str, Any]]] = None
    message: Optional[str] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="healthy", service="enzyme_full_info", version="1.0.0")


@app.get('/api/query/enzyme-full-info/{accession}/structure')
async def get_reference_structure(accession: str):
    """Retrieve a public reference model separately from the annotation query."""
    result = await run_in_threadpool(reference_structure.fetch, accession)
    if not result['success']:
        raise HTTPException(result.get('http_status', 502), result['error'])
    return result


@app.get('/api/query/enzyme-full-info/{accession}/sequence')
async def get_reference_sequence(accession: str):
    """Display context only: local-first lookup, no new analysis or saved run."""
    result = await run_in_threadpool(reference_sequence, accession)
    if not result['success']:
        raise HTTPException(result.get('http_status', 503), result['error'])
    return result


@app.post("/api/query/enzyme-full-info", response_model=InfoResponse)
async def query_enzyme_full_info(request: InfoRequest):
    if not request.uniprot_id or not request.uniprot_id.strip():
        raise HTTPException(status_code=400, detail="UniProt ID is required")
    
    result = await run_in_threadpool(query.get_full_info, request.uniprot_id.strip())
    return InfoResponse(**result)


@app.post("/api/query/enzyme-full-info/form", response_model=InfoResponse)
async def query_enzyme_full_info_form(uniprot_id: str = Form(...)):
    if not uniprot_id or not uniprot_id.strip():
        raise HTTPException(status_code=400, detail="UniProt ID is required")
    
    result = await run_in_threadpool(query.get_full_info, uniprot_id.strip())
    return InfoResponse(**result)


@app.post("/query/enzyme-full-info", response_model=InfoResponse, tags=["Legacy"])
async def query_enzyme_full_info_legacy(request: InfoRequest):
    return await query_enzyme_full_info(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=18915)
