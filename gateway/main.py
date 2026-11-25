"""
EnzyMind Gateway - API Proxy Server
Routes frontend requests to microservices
Port: 8080

Supports both /api and /enzymind/api prefixes for compatibility
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
import json
import time
from pathlib import Path

# Support both `uvicorn gateway.main:app` and the existing `cd gateway; uvicorn main:app`.
if not __package__:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gateway import workspace, structure_jobs
from gateway.result_catalog import tool_for_service
from gateway.service_policy import service_timeout
from gateway.structure_artifacts import read_generated_pdb, valid_pdb_name
from gateway.sequence_data import normalize_active_site_payload

app = FastAPI(
    title="EnzyMind API Gateway",
    description="API Gateway for EnzyMind Microservices",
    version="2.0.0",
    root_path="/enzymind"  # Support reverse proxy with /enzymind prefix
)

# CORS middleware - allow Vue frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify Vue frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service configuration
SERVICE_HOST = os.getenv("ENZYMIND_HOST", "localhost")

SERVICES = {
    "enzy_recognize": f"http://{SERVICE_HOST}:18901",
    "ecnumber_predict": f"http://{SERVICE_HOST}:18902",
    "substrate_predict": f"http://{SERVICE_HOST}:18903",
    "kcat_predict": f"http://{SERVICE_HOST}:18904",
    "km_predict": f"http://{SERVICE_HOST}:18905",
    "structure_predict": f"http://{SERVICE_HOST}:18906",
    "active_sites": f"http://{SERVICE_HOST}:18907",
    "enzyme_type": f"http://{SERVICE_HOST}:18908",
    "protparam": f"http://{SERVICE_HOST}:18909",
    "sequence_alignment": f"http://{SERVICE_HOST}:18910",
    "function_get": f"http://{SERVICE_HOST}:18911",
    "enzyme_subclass": f"http://{SERVICE_HOST}:18912",
    "ec_reaction_info": f"http://{SERVICE_HOST}:18913",
    "enzyme_check": f"http://{SERVICE_HOST}:18914",
    "enzyme_full_info": f"http://{SERVICE_HOST}:18915",
    "functional_site": f"http://{SERVICE_HOST}:18916",
    "kinetic_params": f"http://{SERVICE_HOST}:18917",
    "sequence_info": f"http://{SERVICE_HOST}:18918",
    "query_mechanism_mcsa": f"http://{SERVICE_HOST}:18919",
}

workspace.install(app, SERVICES)


async def proxy_request(service_name: str, path: str, request: Request, *, save=True, body=None):
    """Proxy request to microservice"""
    if service_name not in SERVICES:
        raise HTTPException(status_code=404, detail=f"Service {service_name} not found")
    
    base_url = SERVICES[service_name]
    url = f"{base_url}{path}"
    
    async with httpx.AsyncClient(timeout=httpx.Timeout(service_timeout(service_name), connect=15)) as client:
        if body is None:
            body = await request.body()
        if request.method == 'POST' and 'application/json' in request.headers.get('content-type', ''):
            from gateway.input_validation import normalize_inputs
            try:
                inputs = normalize_inputs(service_name, json.loads(body))
                body = json.dumps(inputs, ensure_ascii=False).encode()
            except (ValueError, UnicodeDecodeError):
                raise HTTPException(422, 'Send valid JSON.')
        started = time.monotonic()
        workspace_owner = workspace.owner(request) if request.headers.get('x-enzymind-client') else None
        forward_headers = {k: v for k, v in request.headers.items() 
                         if k.lower() not in ['host', 'content-length', 'x-enzymind-client', 'x-enzymind-turn']}
        if workspace_owner and service_name == 'active_sites':
            forward_headers['X-Easifa-Session'] = workspace_owner
        
        try:
            response = await client.request(
                method=request.method, url=url, content=body, headers=forward_headers,
            )
        except httpx.TimeoutException:
            response = httpx.Response(504, json={"success": False,
                "error": "The analysis exceeded its time limit. It may still be running; check your saved results before retrying."})
        except httpx.HTTPError as exc:
            response = httpx.Response(502, json={"success": False,
                "error": f"The analysis service is unavailable ({type(exc).__name__}). Check the service and try again."})
        
        content_type = response.headers.get('content-type', '')
        if response.is_error and not content_type.startswith('application/json'):
            response = httpx.Response(response.status_code, json={"success": False,
                "error": f"The analysis service returned HTTP {response.status_code}. Check the service log and try again."})
            content_type = 'application/json'
        if content_type.startswith('application/json'):
            payload = response.json()
            if service_name == 'active_sites':
                payload = normalize_active_site_payload(payload)
            if response.status_code == 422 and isinstance(payload, dict):
                payload.setdefault('error_code', 'invalid_input')
            if response.is_error and isinstance(payload, dict) and not payload.get('error'):
                payload = {**payload, 'success': False, 'error': str(payload.get('detail') or f'The service returned HTTP {response.status_code}.')}
            if save and workspace_owner and request.method == 'POST' and isinstance(payload, dict):
                payload = await workspace.preserve_structure(payload)
                try:
                    inputs = json.loads(body)
                except (ValueError, UnicodeDecodeError):
                    inputs = {"input_type": "uploaded file"}
                record = workspace.store().save_result(workspace_owner, tool_for_service(service_name), inputs,
                                                      payload, duration=time.monotonic() - started)
                payload = {**payload, 'workspace_result': {k: v for k, v in record.items() if k != 'payload'}}
            result = JSONResponse(
                content=payload,
                status_code=response.status_code
            )
        else:
            result = JSONResponse(
                content={"result": response.text},
                status_code=response.status_code
            )
        if workspace_owner or service_name == "active_sites":
            result.headers["Cache-Control"] = "private, no-store"
        if service_name == "active_sites":
            for cookie in response.headers.get_list("set-cookie"):
                if cookie.startswith("enzymind_easifa_session="):
                    result.headers.append("set-cookie", cookie)
        return result


async def proxy_form_request(service_name: str, path: str, request: Request):
    """Proxy form-data request to microservice"""
    if service_name not in SERVICES:
        raise HTTPException(status_code=404, detail=f"Service {service_name} not found")
    
    base_url = SERVICES[service_name]
    url = f"{base_url}{path}"
    
    async with httpx.AsyncClient(timeout=httpx.Timeout(service_timeout(service_name), connect=15)) as client:
        content_type = request.headers.get('content-type', '')
        
        if 'multipart/form-data' in content_type:
            form = await request.form()
            files = {}
            data = {}
            
            for key, value in form.items():
                if hasattr(value, 'file'):
                    file_content = await value.read()
                    files[key] = (value.filename, file_content, value.content_type or 'application/octet-stream')
                else:
                    data[key] = value
            
            response = await client.request(request.method, url, data=data, files=files if files else None)
        else:
            body = await request.body()
            forward_headers = {k: v for k, v in request.headers.items() 
                             if k.lower() not in ['host', 'content-length']}
            response = await client.request(request.method, url, content=body, headers=forward_headers)
        
        content_type = response.headers.get('content-type', '')
        if content_type.startswith('application/json'):
            return JSONResponse(content=response.json(), status_code=response.status_code)
        else:
            return JSONResponse(content={"result": response.text}, status_code=response.status_code)


# Legacy public chat had no workspace identity or accounting.
@app.post("/api/agent/chat")
async def proxy_agent_chat(request: Request):
    raise HTTPException(410, detail={
        "code": "workspace_required",
        "message": "Open the EnzyMind workspace to use the daily allowance or your own DeepSeek key.",
        "url": "/enzymind/agent",
    })


# ============ PDB File Proxy ============

@app.get("/api/pdb/{filename:path}")
async def get_pdb_file(filename: str):
    """Get PDB file content from structure_predict service's output directory."""
    if not valid_pdb_name(filename):
        raise HTTPException(status_code=400, detail='Invalid PDB filename')
    content = read_generated_pdb(filename, legacy=True)
    if content is not None:
        return Response(content=content, media_type="chemical/x-pdb", headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        })
    
    raise HTTPException(status_code=404, detail=f"PDB file not found: {filename}")


# ============ API Proxy Routes ============

# 8001 - Enzyme Recognition Service
@app.api_route("/api/recognize/{path:path}", methods=["GET", "POST"])
async def proxy_recognize(path: str, request: Request):
    return await proxy_request("enzy_recognize", f"/api/recognize/{path}", request)


# 8002 - EC Number Prediction Service
@app.api_route("/api/predict/ec", methods=["POST"])
async def proxy_ec_predict(request: Request):
    return await proxy_request("ecnumber_predict", "/api/predict/ec", request)


# 8003 - Substrate Prediction Service
@app.api_route("/api/predict/substrate", methods=["POST"])
async def proxy_substrate_predict(request: Request):
    return await proxy_request("substrate_predict", "/api/predict/substrate", request)


# 8004 - Kcat Prediction Service
@app.api_route("/api/predict/kcat", methods=["POST"])
async def proxy_kcat_predict(request: Request):
    return await proxy_request("kcat_predict", "/api/predict/kcat", request)


# 8005 - Km Prediction Service
@app.api_route("/api/predict/km", methods=["POST"])
async def proxy_km_predict(request: Request):
    return await proxy_request("km_predict", "/api/predict/km", request)


# 8006 - Structure Prediction Service
@app.api_route("/api/predict/structure", methods=["POST"])
async def proxy_structure_predict(request: Request):
    return await structure_jobs.submit(request, lambda inputs: proxy_request("structure_predict", "/api/predict/structure", request, save=False, body=json.dumps(inputs).encode()))

@app.get("/api/predict/structure/jobs/{job_id}")
async def read_fold_job(job_id: str, request: Request):
    return structure_jobs.get(request, job_id)

app.router.add_event_handler("startup", structure_jobs.recover)

@app.api_route("/api/query/structure", methods=["POST"])
async def proxy_structure_query(request: Request):
    return await proxy_structure_predict(request)

@app.api_route("/api/predict/structure/download", methods=["POST"])
async def proxy_structure_download(request: Request):
    if "structure_predict" not in SERVICES:
        raise HTTPException(status_code=404, detail="Service structure_predict not found")
    
    base_url = SERVICES["structure_predict"]
    url = f"{base_url}/api/predict/structure/download"
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        body = await request.body()
        forward_headers = {k: v for k, v in request.headers.items() 
                         if k.lower() not in ['host', 'content-length']}
        
        response = await client.post(url, content=body, headers=forward_headers)
        
        return Response(
            content=response.content,
            status_code=response.status_code,
            media_type=response.headers.get('content-type', 'chemical/x-pdb'),
            headers={
                "Content-Disposition": response.headers.get('content-disposition', 'attachment; filename=structure.pdb')
            }
        )


# 8007 - Active Sites Prediction Service
@app.api_route("/api/query/active-sites", methods=["POST"])
async def proxy_active_sites(request: Request):
    return await proxy_request("active_sites", "/api/query/active-sites", request)

@app.api_route("/api/predict/active-sites", methods=["POST"])
async def proxy_active_sites_sync(request: Request):
    """Proxy for synchronous active sites prediction (supports uniprot_id or aa_sequence)."""
    return await proxy_request("active_sites", "/api/predict/active-sites", request)

@app.api_route("/api/predict/active-sites/{path:path}", methods=["GET", "POST"])
async def proxy_active_sites_predict(path: str, request: Request):
    # Preserve GET, multipart boundaries, Cookie and X-Easifa-Session verbatim.
    return await proxy_request("active_sites", f"/api/predict/active-sites/{path}", request)


# 8008 - Enzyme Type Recommendation Service
@app.api_route("/api/query/enzyme-type", methods=["POST"])
async def proxy_enzyme_type(request: Request):
    return await proxy_request("enzyme_type", "/api/query/enzyme-type", request)

@app.api_route("/api/query/enzyme-type/{path:path}", methods=["POST"])
async def proxy_enzyme_type_extra(path: str, request: Request):
    return await proxy_request("enzyme_type", f"/api/query/enzyme-type/{path}", request)


# 8009 - ProtParam Service
@app.api_route("/api/query/protein-physchem", methods=["POST"])
async def proxy_protparam(request: Request):
    return await proxy_request("protparam", "/query/protein-physchem", request)

@app.api_route("/api/query/protein-params", methods=["POST"])
async def proxy_protparam_params(request: Request):
    return await proxy_request("protparam", "/query/protein-physchem", request)


# 8010 - Sequence Alignment (BLAST) Service
@app.api_route("/api/query/blast", methods=["POST"])
async def proxy_blast(request: Request):
    if request.headers.get('x-enzymind-client'):
        from gateway.input_validation import normalize_inputs
        inputs = normalize_inputs('sequence_alignment', await workspace.body_json(request))
        record = await workspace.blast_jobs().submit(workspace.owner(request), inputs)
        return {**record['payload'], 'workspace_result': {k: v for k, v in record.items() if k != 'payload'}}
    return await proxy_request("sequence_alignment", "/api/query/blast", request)

@app.get("/api/query/blast/config")
async def blast_config():
    return {"local_available": bool(os.getenv("ENZYMIND_BLAST_DB"))}


@app.get("/api/query/blast/results/{request_id}")
async def retrieve_blast(request_id: str, request: Request):
    import re
    if not re.fullmatch(r"[A-Z0-9-]{5,40}", request_id):
        raise HTTPException(422, "Invalid NCBI request ID.")
    # Explicit public RID retrieval supports legacy clients without a workspace.
    try:
        async with httpx.AsyncClient(timeout=210) as client:
            response = await client.get(SERVICES['sequence_alignment'] + f'/api/query/blast/results/{request_id}', params=dict(request.query_params))
        return JSONResponse(response.json(), status_code=response.status_code)
    except (httpx.HTTPError, ValueError):
        return JSONResponse({'success': True, 'status': 'queued', 'request_id': request_id,
            'last_poll_error': 'Retrieval is temporarily unavailable. Check this same request again in at least one minute; no new search was submitted.'})



# 8011 - Function Get Service
@app.api_route("/api/query/function", methods=["POST"])
async def proxy_function(request: Request):
    return await proxy_request("function_get", "/api/query/function", request)

@app.api_route("/api/query/function/{path:path}", methods=["POST"])
async def proxy_function_extra(path: str, request: Request):
    return await proxy_request("function_get", f"/api/query/function/{path}", request)


# 8012 - Enzyme Subclass Service
@app.api_route("/api/query/enzyme-subclass", methods=["POST"])
async def proxy_subclass(request: Request):
    return await proxy_request("enzyme_subclass", "/api/query/enzyme-subclass", request)

@app.api_route("/api/enzyme-classes", methods=["GET"])
async def proxy_enzyme_classes(request: Request):
    return await proxy_request("enzyme_subclass", "/api/enzyme-classes", request)


# 8013 - EC Reaction Info (Catalytic Activity) Service
@app.api_route("/api/query/catalytic_activity", methods=["POST"])
async def proxy_catalytic_underscore(request: Request):
    return await proxy_request("ec_reaction_info", "/api/query/catalytic-activity", request)

@app.api_route("/api/query/catalytic-activity", methods=["POST"])
async def proxy_catalytic_hyphen(request: Request):
    return await proxy_request("ec_reaction_info", "/api/query/catalytic-activity", request)


# 8014 - Enzyme Check Service
@app.api_route("/api/check/enzyme", methods=["POST"])
async def proxy_enzyme_check(request: Request):
    return await proxy_request("enzyme_check", "/api/check/enzyme", request)


# 8015 - Enzyme Full Info Service
@app.get('/api/query/enzyme-full-info/{accession}/sequence')
async def proxy_reference_sequence(accession: str, request: Request):
    from gateway.input_validation import ACCESSION
    if not ACCESSION.fullmatch(accession.upper()):
        raise HTTPException(422, 'Enter a valid UniProt accession.')
    return await proxy_request('enzyme_full_info', f'/api/query/enzyme-full-info/{accession.upper()}/sequence', request)


@app.get('/api/query/enzyme-full-info/{accession}/structure')
async def proxy_reference_structure(accession: str, request: Request):
    from gateway.input_validation import ACCESSION
    if not ACCESSION.fullmatch(accession.upper()):
        raise HTTPException(422, 'Enter a valid UniProt accession.')
    return await proxy_request('enzyme_full_info', f'/api/query/enzyme-full-info/{accession.upper()}/structure', request)


@app.api_route("/api/query/enzyme-full-info", methods=["POST"])
async def proxy_full_info(request: Request):
    return await proxy_request("enzyme_full_info", "/api/query/enzyme-full-info", request)

@app.api_route("/api/query/enzyme-info", methods=["POST"])
async def proxy_enzyme_info(request: Request):
    return await proxy_request("enzyme_full_info", "/api/query/enzyme-full-info", request)

@app.api_route("/api/query/ec-info", methods=["POST"])
async def proxy_ec_info(request: Request):
    return await proxy_request("ec_reaction_info", "/api/query/ec-info", request)

@app.api_route("/api/recommend/enzyme", methods=["POST"])
async def proxy_recommend_enzyme(request: Request):
    # Keep the ordinary recommendation response, and honor top-K requests from
    # older clients instead of silently ignoring their k parameter.
    try:
        inputs = await request.json()
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(422, 'Send valid JSON.')
    path = "/api/query/enzyme-type/top-k" if isinstance(inputs, dict) and "k" in inputs else "/api/query/enzyme-type"
    return await proxy_request("enzyme_type", path, request)


# 8016 - Functional Site Service
@app.api_route("/api/query/features", methods=["POST"])
async def proxy_features(request: Request):
    return await proxy_request("functional_site", "/api/query/features", request)


# 8017 - Kinetic Params Service
@app.api_route("/api/query/kinetics", methods=["POST"])
async def proxy_kinetics(request: Request):
    return await proxy_request("kinetic_params", "/api/query/kinetics", request)


# 8018 - Sequence Info Service
@app.api_route("/api/query/sequence-info", methods=["POST"])
async def proxy_sequence_info(request: Request):
    return await proxy_request("sequence_info", "/api/query/sequence-info", request)


# Health check
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "api-gateway"}

@app.get("/api/health")
async def api_health():
    return {"status": "healthy", "service": "api-gateway"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080, workers=1, proxy_headers=False)
