# active_sites/main.py
"""
Active Sites Prediction Service - FastAPI Application
Port: 18907

This service predicts enzyme active sites using the EasIFA API.

Supported input types:
1. UniProt ID - uses /from_uniprot endpoint
2. Amino Acid Sequence - uses /from_sequence endpoint  
3. PDB Structure File - uses /from_structure endpoint

EasIFA API async workflow:
1. Submit task -> get job_id
2. Poll /job/{job_id} for status
3. Get results from /results/{job_id} when completed
"""

from fastapi import FastAPI, Form, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uvicorn
import tempfile
import os
import secrets

from models.active_sites_predictor import ActiveSitesPredictor
from models.utils import classify_input, is_uniprot_id, is_amino_acid_sequence
from models.easifa_access import (SESSION_HEADER, SESSION_COOKIE, request_owner,
                                 valid_token, cookie_secure)

app = FastAPI(
    title="Active Sites Prediction Service",
    description="Enzyme active sites prediction using EasIFA API",
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

@app.middleware("http")
async def easifa_identity(request: Request, call_next):
    """Carry one caller identity through submit, polling and retrieval, including sync tools."""
    if not (request.url.path.startswith("/api/predict/active-sites")
            or request.url.path == "/api/query/active-sites"):
        return await call_next(request)
    key = request.headers.get(SESSION_HEADER)
    if key is not None and not valid_token(key):
        return JSONResponse({"detail": "Invalid X-Easifa-Session"}, status_code=400,
                            headers={"Cache-Control": "private, no-store"})
    # Existing wildcard CORS must not expose a browser's cookie-owned jobs or
    # recovery key to a different origin. Same-origin proxies preserve Fetch Metadata;
    # cross-origin API callers can explicitly supply their own capability header.
    if (key is None and request.cookies.get(SESSION_COOKIE) and request.headers.get("origin")
            and request.headers.get("sec-fetch-site") != "same-origin"):
        return JSONResponse({"detail": "Cross-origin access requires X-Easifa-Session"}, status_code=403,
                            headers={"Cache-Control": "private, no-store"})
    key = key or request.cookies.get(SESSION_COOKIE)
    if not valid_token(key):
        key = secrets.token_urlsafe(32)
    context = request_owner.set(key)
    try:
        response = await call_next(request)
        response.set_cookie(SESSION_COOKIE, key, httponly=True, secure=cookie_secure(),
                            samesite="lax", path="/", max_age=31536000)
        response.headers["Cache-Control"] = "private, no-store"
        return response
    finally:
        request_owner.reset(context)


@app.get("/api/predict/active-sites/session")
def easifa_session():
    """Explicit recovery/initialization; never include this credential in job responses."""
    return {"session_token": request_owner.get()}


# Global predictor instance (identity is request-scoped, never stored on this instance).
predictor: Optional[ActiveSitesPredictor] = None


def get_predictor() -> ActiveSitesPredictor:
    """Get or initialize the predictor instance."""
    global predictor
    if predictor is None:
        predictor = ActiveSitesPredictor()
    return predictor


# ============== Request/Response Models ==============

class UniProtSubmitRequest(BaseModel):
    """Request model for UniProt-based submission."""
    uniprot_id: str
    use_celery: bool = True


class SequenceSubmitRequest(BaseModel):
    """Request model for sequence-based submission."""
    aa_sequence: str
    rxn_smiles: Optional[str] = None
    use_celery: bool = True


class ActiveSitesSyncRequest(BaseModel):
    """Request model for synchronous prediction (supports both UniProt ID and sequence)."""
    uniprot_id: Optional[str] = None
    aa_sequence: Optional[str] = None
    rxn_smiles: Optional[str] = None
    use_celery: bool = True
    timeout: int = 600


class ActiveSitesPredictRequest(BaseModel):
    """Request model for active sites prediction (legacy)."""
    uniprot_id: str


class ActiveSitesPredictResponse(BaseModel):
    """Response model for active sites prediction (sync)."""
    result: str
    # Preserve machine-readable structures/sites for the shared result workspace.
    data: Optional[Dict[str, Any]] = None
    job_id: Optional[str] = None


class ActiveSitesSubmitResponse(BaseModel):
    """Response model for async task submission."""
    success: bool
    job_id: Optional[str] = None
    task_manager: Optional[str] = None
    input_type: Optional[str] = None
    error: Optional[str] = None


class ActiveSitesJobStatusResponse(BaseModel):
    """Response model for job status."""
    success: bool
    status: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ActiveSitesResultsResponse(BaseModel):
    """Response model for job results."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    markdown: Optional[str] = None
    error: Optional[str] = None


# ============== Health Check ==============

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "active_sites"}


# ============== UniProt Submission Endpoints ==============

@app.post("/api/predict/active-sites/submit/uniprot", response_model=ActiveSitesSubmitResponse)
def submit_uniprot_task(request: UniProtSubmitRequest):
    """
    Submit an active sites prediction task using UniProt ID.
    
    Args:
        request: JSON request containing uniprot_id and use_celery flag
        
    Returns:
        Job submission result with job_id
    """
    pred = get_predictor()
    
    # Validate UniProt ID format
    if not is_uniprot_id(request.uniprot_id):
        return ActiveSitesSubmitResponse(
            success=False,
            error=f"Invalid UniProt ID format: {request.uniprot_id}"
        )
    
    result = pred.submit_uniprot(request.uniprot_id, use_celery=request.use_celery)
    
    if result.get("success"):
        return ActiveSitesSubmitResponse(
            success=True,
            job_id=result.get("job_id"),
            task_manager=result.get("task_manager"),
            input_type="uniprot"
        )
    else:
        return ActiveSitesSubmitResponse(
            success=False,
            error=result.get("error")
        )


# ============== Sequence Submission Endpoints ==============

@app.post("/api/predict/active-sites/submit/sequence", response_model=ActiveSitesSubmitResponse)
def submit_sequence_task(request: SequenceSubmitRequest):
    """
    Submit an active sites prediction task using amino acid sequence (JSON).
    
    Args:
        request: JSON request containing aa_sequence, optional rxn_smiles, and use_celery flag
        
    Returns:
        Job submission result with job_id
    """
    pred = get_predictor()
    
    # Validate sequence
    if not is_amino_acid_sequence(request.aa_sequence):
        return ActiveSitesSubmitResponse(
            success=False,
            error=f"Invalid amino acid sequence format"
        )
    
    result = pred.submit_sequence(
        request.aa_sequence, 
        rxn_smiles=request.rxn_smiles,
        use_celery=request.use_celery
    )
    
    if result.get("success"):
        return ActiveSitesSubmitResponse(
            success=True,
            job_id=result.get("job_id"),
            task_manager=result.get("task_manager"),
            input_type="sequence"
        )
    else:
        return ActiveSitesSubmitResponse(
            success=False,
            error=result.get("error")
        )


@app.post("/api/predict/active-sites/submit/sequence/form", response_model=ActiveSitesSubmitResponse)
def submit_sequence_task_form(
    aa_sequence: str = Form(...),
    rxn_smiles: Optional[str] = Form(None),
    use_celery: bool = Form(True)
):
    """
    Submit an active sites prediction task using amino acid sequence (Form).
    
    Args:
        aa_sequence: Amino acid sequence
        rxn_smiles: Optional reaction SMILES
        use_celery: Whether to use celery for async processing
        
    Returns:
        Job submission result with job_id
    """
    pred = get_predictor()
    
    # Validate sequence
    if not is_amino_acid_sequence(aa_sequence):
        return ActiveSitesSubmitResponse(
            success=False,
            error=f"Invalid amino acid sequence format"
        )
    
    result = pred.submit_sequence(
        aa_sequence, 
        rxn_smiles=rxn_smiles,
        use_celery=use_celery
    )
    
    if result.get("success"):
        return ActiveSitesSubmitResponse(
            success=True,
            job_id=result.get("job_id"),
            task_manager=result.get("task_manager"),
            input_type="sequence"
        )
    else:
        return ActiveSitesSubmitResponse(
            success=False,
            error=result.get("error")
        )


# ============== Structure Submission Endpoints ==============

@app.post("/api/predict/active-sites/submit/structure", response_model=ActiveSitesSubmitResponse)
async def submit_structure_task(
    pdb_file: UploadFile = File(...),
    rxn_smiles: Optional[str] = Form(None),
    use_celery: bool = Form(True)
):
    """
    Submit an active sites prediction task using PDB structure file.
    
    Args:
        pdb_file: PDB structure file
        rxn_smiles: Optional reaction SMILES
        use_celery: Whether to use celery for async processing
        
    Returns:
        Job submission result with job_id
    """
    pred = get_predictor()
    
    # Save uploaded file temporarily
    try:
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdb', delete=False) as tmp_file:
            content = await pdb_file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        result = pred.submit_structure(
            tmp_path,
            rxn_smiles=rxn_smiles,
            use_celery=use_celery
        )
        
        # Clean up temp file
        os.unlink(tmp_path)
        
        if result.get("success"):
            return ActiveSitesSubmitResponse(
                success=True,
                job_id=result.get("job_id"),
                task_manager=result.get("task_manager"),
                input_type="structure"
            )
        else:
            return ActiveSitesSubmitResponse(
                success=False,
                error=result.get("error")
            )
    except Exception as e:
        return ActiveSitesSubmitResponse(
            success=False,
            error=f"Error processing structure file: {str(e)}"
        )


# ============== Job Status and Results Endpoints ==============

@app.get("/api/predict/active-sites/job/{job_id}", response_model=ActiveSitesJobStatusResponse)
def get_job_status(job_id: str):
    """
    Get the status of a submitted prediction job.
    
    Args:
        job_id: Job ID returned from submit endpoint
        
    Returns:
        Job status information
    """
    pred = get_predictor()
    result = pred.get_job_status(job_id)
    
    if result.get("success"):
        return ActiveSitesJobStatusResponse(
            success=True,
            status=result.get("status"),
            data=result.get("data")
        )
    else:
        return ActiveSitesJobStatusResponse(
            success=False,
            error=result.get("error")
        )


@app.get("/api/predict/active-sites/results/{job_id}", response_model=ActiveSitesResultsResponse)
def get_job_results(job_id: str):
    """
    Get the results of a completed prediction job.
    
    Args:
        job_id: Job ID returned from submit endpoint
        
    Returns:
        Job results if completed
    """
    pred = get_predictor()
    result = pred.get_job_results(job_id)
    
    if result.get("success"):
        data = result.get("data", {})
        # Also return formatted markdown
        markdown = pred.format_results_to_markdown(data)
        return ActiveSitesResultsResponse(
            success=True,
            data=data,
            markdown=markdown
        )
    else:
        return ActiveSitesResultsResponse(
            success=False,
            error=result.get("error")
        )


def invalid_protein(fields, message):
    return JSONResponse({"success": False, "error_code": "invalid_input", "error": message,
                         "result": "[ERROR] " + message,
                         "detail": [{"loc": ["body", field], "msg": message, "type": "value_error"}
                                    for field in fields]}, status_code=422)


# ============== Synchronous Prediction Endpoints ==============

@app.post("/api/predict/active-sites", response_model=ActiveSitesPredictResponse)
def predict_active_sites_sync(request: ActiveSitesSyncRequest):
    """
    Predict enzyme active sites from UniProt ID or amino acid sequence (synchronous).
    
    Submits task, waits for completion, and returns formatted results.
    May take several minutes for new predictions.
    
    Args:
        request: JSON request containing either uniprot_id or aa_sequence
            - uniprot_id: UniProt ID (e.g., "P12345")
            - aa_sequence: Amino acid sequence
            - rxn_smiles: Optional reaction SMILES (for sequence input)
            - use_celery: Whether to use celery (default: True)
            - timeout: Maximum wait time in seconds (default: 600)
        
    Returns:
        Active sites prediction results as markdown table
    """
    fields = ["uniprot_id", "aa_sequence"]
    if bool(request.uniprot_id) == bool(request.aa_sequence):
        return invalid_protein(fields, "Provide exactly one of uniprot_id or aa_sequence.")
    if request.uniprot_id:
        if not is_uniprot_id(request.uniprot_id):
            return invalid_protein(["uniprot_id"], "Enter a valid UniProt accession.")
        pred = get_predictor()
        submit_result = pred.submit_uniprot(request.uniprot_id, use_celery=request.use_celery)
    else:
        if not is_amino_acid_sequence(request.aa_sequence):
            return invalid_protein(["aa_sequence"], "Enter a valid amino acid sequence.")
        pred = get_predictor()
        submit_result = pred.submit_sequence(request.aa_sequence, rxn_smiles=request.rxn_smiles,
                                            use_celery=request.use_celery)

    if not submit_result.get("success"):
        return ActiveSitesPredictResponse(
            result=f"[ERROR] Failed to submit task: {submit_result.get('error')}"
        )
    
    job_id = submit_result.get("job_id")
    
    # Wait for completion
    wait_result = pred.wait_for_completion(job_id, timeout=request.timeout, poll_interval=5)
    
    if not wait_result.get("success"):
        return ActiveSitesPredictResponse(
            result=f"[ERROR] Task failed or timed out: {wait_result.get('error')}"
        )
    
    # Get results
    results_data = wait_result.get("data", {})
    markdown = pred.format_results_to_markdown(results_data)
    
    return ActiveSitesPredictResponse(result=markdown, data=results_data, job_id=job_id)


@app.post("/api/predict/active-sites/sequence", response_model=ActiveSitesPredictResponse)
def predict_active_sites_sequence_sync(
    aa_sequence: str = Form(...),
    rxn_smiles: Optional[str] = Form(None),
    use_celery: bool = Form(True),
    timeout: int = Form(600)
):
    """
    Predict enzyme active sites from amino acid sequence (synchronous).
    
    Args:
        aa_sequence: Amino acid sequence
        rxn_smiles: Optional reaction SMILES
        use_celery: Whether to use celery
        timeout: Maximum wait time in seconds
        
    Returns:
        Active sites prediction results as markdown table
    """
    pred = get_predictor()
    
    if not is_amino_acid_sequence(aa_sequence):
        return ActiveSitesPredictResponse(
            result=f"[ERROR] Invalid amino acid sequence"
        )
    
    # Submit
    submit_result = pred.submit_sequence(aa_sequence, rxn_smiles=rxn_smiles, use_celery=use_celery)
    
    if not submit_result.get("success"):
        return ActiveSitesPredictResponse(
            result=f"[ERROR] Failed to submit task: {submit_result.get('error')}"
        )
    
    job_id = submit_result.get("job_id")
    
    # Wait for completion
    wait_result = pred.wait_for_completion(job_id, timeout=timeout, poll_interval=5)
    
    if not wait_result.get("success"):
        return ActiveSitesPredictResponse(
            result=f"[ERROR] Task failed or timed out: {wait_result.get('error')}"
        )
    
    # Format results
    results_data = wait_result.get("data", {})
    markdown = pred.format_results_to_markdown(results_data)
    
    return ActiveSitesPredictResponse(result=markdown, data=results_data, job_id=job_id)


@app.post("/api/predict/active-sites/structure", response_model=ActiveSitesPredictResponse)
async def predict_active_sites_structure_sync(
    pdb_file: UploadFile = File(...),
    rxn_smiles: Optional[str] = Form(None),
    use_celery: bool = Form(True),
    timeout: int = Form(600)
):
    """
    Predict enzyme active sites from PDB structure file (synchronous).
    
    Args:
        pdb_file: PDB structure file
        rxn_smiles: Optional reaction SMILES
        use_celery: Whether to use celery
        timeout: Maximum wait time in seconds
        
    Returns:
        Active sites prediction results as markdown table
    """
    pred = get_predictor()
    
    # Save uploaded file temporarily
    try:
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdb', delete=False) as tmp_file:
            content = await pdb_file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        # Submit
        submit_result = pred.submit_structure(tmp_path, rxn_smiles=rxn_smiles, use_celery=use_celery)
        
        # Clean up temp file
        os.unlink(tmp_path)
        
        if not submit_result.get("success"):
            return ActiveSitesPredictResponse(
                result=f"[ERROR] Failed to submit task: {submit_result.get('error')}"
            )
        
        job_id = submit_result.get("job_id")
        
        # Wait for completion
        wait_result = pred.wait_for_completion(job_id, timeout=timeout, poll_interval=5)
        
        if not wait_result.get("success"):
            return ActiveSitesPredictResponse(
                result=f"[ERROR] Task failed or timed out: {wait_result.get('error')}"
            )
        
        # Format results
        results_data = wait_result.get("data", {})
        markdown = pred.format_results_to_markdown(results_data)
        
        return ActiveSitesPredictResponse(result=markdown, data=results_data, job_id=job_id)
        
    except Exception as e:
        return ActiveSitesPredictResponse(
            result=f"[ERROR] Error processing structure file: {str(e)}"
        )


# ============== Auto-detect Input Type Endpoint ==============

@app.post("/api/predict/active-sites/auto", response_model=ActiveSitesSubmitResponse)
def submit_auto_detect(
    input_data: str = Form(...),
    rxn_smiles: Optional[str] = Form(None),
    use_celery: bool = Form(True)
):
    """
    Auto-detect input type and submit prediction task.
    
    Supports UniProt ID or amino acid sequence.
    For PDB files, use the /submit/structure endpoint.
    
    Args:
        input_data: Input data (UniProt ID or sequence)
        rxn_smiles: Optional reaction SMILES (for sequence input)
        use_celery: Whether to use celery
        
    Returns:
        Job submission result with job_id
    """
    pred = get_predictor()
    
    # Classify input
    input_type, cleaned_input = classify_input(input_data)
    
    if input_type == "uniprot_id":
        result = pred.submit_uniprot(cleaned_input, use_celery=use_celery)
        detected_type = "uniprot"
    elif input_type in ("sequence", "fasta"):
        result = pred.submit_sequence(cleaned_input, rxn_smiles=rxn_smiles, use_celery=use_celery)
        detected_type = "sequence"
    else:
        return ActiveSitesSubmitResponse(
            success=False,
            error=f"Could not determine input type. Detected: {input_type}. Please provide a valid UniProt ID or amino acid sequence."
        )
    
    if result.get("success"):
        return ActiveSitesSubmitResponse(
            success=True,
            job_id=result.get("job_id"),
            task_manager=result.get("task_manager"),
            input_type=detected_type
        )
    else:
        return ActiveSitesSubmitResponse(
            success=False,
            error=result.get("error")
        )


# ============== Legacy Endpoints ==============

@app.post("/api/query/active-sites", response_model=ActiveSitesPredictResponse)
def predict_active_sites_legacy(request: ActiveSitesPredictRequest):
    """
    Legacy endpoint for active sites prediction.
    Kept for backward compatibility.
    """
    # Convert to new request format
    new_request = ActiveSitesSyncRequest(uniprot_id=request.uniprot_id, use_celery=True)
    return predict_active_sites_sync(new_request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=18907)
