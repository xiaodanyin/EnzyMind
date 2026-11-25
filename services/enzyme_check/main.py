"""Enzyme Check Service - Port: 18914"""

from fastapi import FastAPI, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, AliasChoices
from typing import Optional, List, Dict, Any
import uvicorn

from models.enzyme_checker import EnzymeChecker

app = FastAPI(
    title="Enzyme Check Service",
    description="酶检测微服务 - 检查蛋白质是否为酶",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

checker = EnzymeChecker()


class CheckRequest(BaseModel):
    query: str = Field(..., validation_alias=AliasChoices("query", "uniprot_id"), description="UniProt accession ID; uniprot_id is accepted for web-client compatibility")


class CheckResponse(BaseModel):
    source: Optional[dict] = None
    success: bool
    uniprot_id: str
    is_enzyme: Optional[bool] = None
    message: str
    ec_numbers: List[str] = Field(default_factory=list)
    result: Optional[str] = None
    error: Optional[str] = None


class BatchRequest(BaseModel):
    queries: List[str] = Field(..., description="List of UniProt accession IDs")


class BatchResponse(BaseModel):
    results: Dict[str, Dict[str, Any]]
    total: int
    enzymes: int
    non_enzymes: int


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    return HealthResponse(status="healthy", service="enzyme_check", version="1.0.0")


@app.post("/api/check/enzyme", response_model=CheckResponse, tags=["Enzyme Check"])
async def check_enzyme(request: CheckRequest):
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="UniProt ID is required")
    
    result = await run_in_threadpool(checker.check_enzyme, request.query.strip())
    
    return CheckResponse(
        success=result["success"],
        uniprot_id=result["uniprot_id"],
        is_enzyme=result.get("is_enzyme"),
        message=result["message"],
        ec_numbers=result.get("ec_numbers", []),
        result=result["message"],
        error=result.get("error"),
        source=result.get("source")
    )


@app.post("/api/check/enzyme/form", response_model=CheckResponse, tags=["Enzyme Check"])
async def check_enzyme_form(query: str = Form(...)):
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="UniProt ID is required")
    
    result = await run_in_threadpool(checker.check_enzyme, query.strip())
    
    return CheckResponse(
        success=result["success"],
        uniprot_id=result["uniprot_id"],
        is_enzyme=result.get("is_enzyme"),
        message=result["message"],
        ec_numbers=result.get("ec_numbers", []),
        result=result["message"],
        error=result.get("error"),
        source=result.get("source")
    )


@app.post("/api/check/enzyme/batch", response_model=BatchResponse, tags=["Enzyme Check"])
async def check_enzyme_batch(request: BatchRequest):
    if not request.queries:
        raise HTTPException(status_code=400, detail="At least one UniProt ID is required")
    
    clean_ids = list(set([q.strip() for q in request.queries if q and q.strip()]))
    
    if not clean_ids:
        raise HTTPException(status_code=400, detail="No valid UniProt IDs provided")
    
    results = await run_in_threadpool(checker.batch_check, clean_ids)
    
    enzymes = sum(1 for r in results.values() if r.get("is_enzyme") is True)
    non_enzymes = sum(1 for r in results.values() if r.get("is_enzyme") is False)
    
    return BatchResponse(
        results=results,
        total=len(clean_ids),
        enzymes=enzymes,
        non_enzymes=non_enzymes
    )


@app.post("/check/enzyme", response_model=CheckResponse, tags=["Legacy"])
async def check_enzyme_legacy(request: CheckRequest):
    return await check_enzyme(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=18914)
