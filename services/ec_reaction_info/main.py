# ec_reaction_info/main.py
"""EC Reaction Info Service - Port: 18913"""

from fastapi import FastAPI, HTTPException, Form, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uvicorn

from models.catalytic_activity_query import CatalyticActivityQuery

app = FastAPI(
    title="EC Reaction Info Service",
    description="催化活性查询微服务",
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

activity_query = CatalyticActivityQuery()


class ActivityQueryRequest(BaseModel):
    query: str = Field(..., description="UniProt accession ID")


class ActivityQueryResponse(BaseModel):
    success: bool
    uniprot_id: str
    activities: List[Dict[str, Any]] = Field(default_factory=list)
    count: Optional[int] = None
    markdown: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None


class BatchQueryRequest(BaseModel):
    queries: List[str] = Field(..., description="List of UniProt accession IDs")


class BatchQueryResponse(BaseModel):
    results: Dict[str, Dict[str, Any]]
    total: int
    successful: int


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    return HealthResponse(status="healthy", service="ec_reaction_info", version="1.0.0")


@app.post("/api/query/catalytic-activity", response_model=ActivityQueryResponse, tags=["Catalytic Activity"])
async def query_catalytic_activity(request: ActivityQueryRequest):
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="UniProt ID is required")
    
    result = activity_query.get_catalytic_activities(request.query.strip())
    
    return ActivityQueryResponse(
        success=result["success"],
        uniprot_id=result["uniprot_id"],
        activities=result.get("activities", []),
        count=result.get("count"),
        markdown=result.get("markdown"),
        result=result.get("markdown"),
        error=result.get("error")
    )


@app.post("/api/query/catalytic-activity/form", response_model=ActivityQueryResponse, tags=["Catalytic Activity"])
async def query_catalytic_activity_form(query: str = Form(...)):
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="UniProt ID is required")
    
    result = activity_query.get_catalytic_activities(query.strip())
    
    return ActivityQueryResponse(
        success=result["success"],
        uniprot_id=result["uniprot_id"],
        activities=result.get("activities", []),
        count=result.get("count"),
        markdown=result.get("markdown"),
        result=result.get("markdown"),
        error=result.get("error")
    )


@app.post("/api/query/catalytic-activity/batch", response_model=BatchQueryResponse, tags=["Catalytic Activity"])
async def query_catalytic_activity_batch(request: BatchQueryRequest):
    if not request.queries:
        raise HTTPException(status_code=400, detail="At least one UniProt ID is required")
    
    clean_ids = list(set([q.strip() for q in request.queries if q and q.strip()]))
    
    if not clean_ids:
        raise HTTPException(status_code=400, detail="No valid UniProt IDs provided")
    
    results = activity_query.batch_get_activities(clean_ids)
    successful = sum(1 for r in results.values() if r["success"])
    
    return BatchQueryResponse(results=results, total=len(clean_ids), successful=successful)


@app.post("/api/query/catalytic-activity/file", response_model=BatchQueryResponse, tags=["Catalytic Activity"])
async def query_catalytic_activity_file(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    try:
        content = await file.read()
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded text")
    
    lines = text.strip().split("\n")
    uniprot_ids = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
    
    if not uniprot_ids:
        raise HTTPException(status_code=400, detail="No valid UniProt IDs found in file")
    
    uniprot_ids = list(set(uniprot_ids))
    results = activity_query.batch_get_activities(uniprot_ids)
    successful = sum(1 for r in results.values() if r["success"])
    
    return BatchQueryResponse(results=results, total=len(uniprot_ids), successful=successful)


@app.post("/query/catalytic_activity", response_model=ActivityQueryResponse, tags=["Legacy"])
async def query_catalytic_activity_legacy(request: ActivityQueryRequest):
    return await query_catalytic_activity(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=18913)
