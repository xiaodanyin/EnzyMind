"""
Enzymind Gateway - API Proxy Server
Routes frontend requests to microservices
Port: 8080

Supports both /api and /enzymind/api prefixes for compatibility
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os

app = FastAPI(
    title="Enzymind API Gateway",
    description="API Gateway for Enzymind Microservices",
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

# n8n webhook configuration
N8N_HOST = os.getenv("N8N_HOST", "localhost")
N8N_PORT = os.getenv("N8N_PORT", "5678")
N8N_WEBHOOK_ID = os.getenv("N8N_WEBHOOK_ID", "8e6add2a-15cd-4a13-be8f-937593f5680a")
N8N_WEBHOOK_URL = f"http://{N8N_HOST}:{N8N_PORT}/webhook/{N8N_WEBHOOK_ID}"

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
}


async def proxy_request(service_name: str, path: str, request: Request):
    """Proxy request to microservice"""
    if service_name not in SERVICES:
        raise HTTPException(status_code=404, detail=f"Service {service_name} not found")
    
    base_url = SERVICES[service_name]
    url = f"{base_url}{path}"
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        body = await request.body()
        forward_headers = {k: v for k, v in request.headers.items() 
                         if k.lower() not in ['host', 'content-length']}
        
        response = await client.request(
            method=request.method,
            url=url,
            content=body,
            headers=forward_headers,
        )
        
        content_type = response.headers.get('content-type', '')
        if content_type.startswith('application/json'):
            return JSONResponse(
                content=response.json(),
                status_code=response.status_code
            )
        else:
            return JSONResponse(
                content={"result": response.text},
                status_code=response.status_code
            )


async def proxy_form_request(service_name: str, path: str, request: Request):
    """Proxy form-data request to microservice"""
    if service_name not in SERVICES:
        raise HTTPException(status_code=404, detail=f"Service {service_name} not found")
    
    base_url = SERVICES[service_name]
    url = f"{base_url}{path}"
    
    async with httpx.AsyncClient(timeout=300.0) as client:
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
            
            response = await client.post(url, data=data, files=files if files else None)
        else:
            body = await request.body()
            forward_headers = {k: v for k, v in request.headers.items() 
                             if k.lower() not in ['host', 'content-length']}
            response = await client.post(url, content=body, headers=forward_headers)
        
        content_type = response.headers.get('content-type', '')
        if content_type.startswith('application/json'):
            return JSONResponse(content=response.json(), status_code=response.status_code)
        else:
            return JSONResponse(content={"result": response.text}, status_code=response.status_code)


# ============ n8n Agent Proxy ============

@app.post("/api/agent/chat")
async def proxy_agent_chat(request: Request):
    """Proxy chat request to n8n webhook for AI Agent
    
    Supports both JSON and multipart/form-data (file upload) requests.
    Streams response back to client for real-time output.
    """
    client = None
    response = None
    try:
        content_type = request.headers.get("content-type", "")
        
        body = await request.body()
        # Build headers - disable compression for proper streaming
        if "multipart/form-data" in content_type:
            headers = {"Content-Type": content_type, "Accept-Encoding": "identity"}
        else:
            headers = {"Content-Type": "application/json", "Accept-Encoding": "identity"}
        
        # Use longer connect timeout but no read timeout for streaming
        # 增加超时时间以支持长时间运行的工具调用
        timeout = httpx.Timeout(connect=60.0, read=600.0, write=60.0, pool=None)
        client = httpx.AsyncClient(timeout=timeout)
        req = client.build_request("POST", N8N_WEBHOOK_URL, content=body, headers=headers)
        response = await client.send(req, stream=True)

        async def iter_response():
            nonlocal client, response
            try:
                async for chunk in response.aiter_bytes():
                    if chunk:
                        yield chunk
            except httpx.ReadTimeout:
                # 读取超时时，发送一个错误消息给前端
                error_msg = '{"type":"item","content":"\\n\\n⚠️ 响应超时，请重试。"}\n'
                yield error_msg.encode('utf-8')
            except Exception as e:
                # 其他错误时，也发送错误消息
                error_msg = f'{{"type":"item","content":"\\n\\n⚠️ 连接错误: {str(e)}"}}\n'
                yield error_msg.encode('utf-8')
            finally:
                if response:
                    await response.aclose()
                if client:
                    await client.aclose()

        return StreamingResponse(
            iter_response(),
            status_code=response.status_code,
            media_type="text/plain; charset=utf-8",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            }
        )
    except httpx.TimeoutException as e:
        if client:
            await client.aclose()
        raise HTTPException(status_code=504, detail=f"Agent service timeout: {str(e)}")
    except httpx.ConnectError:
        if client:
            await client.aclose()
        raise HTTPException(status_code=503, detail="Cannot connect to Agent service (n8n)")
    except Exception as e:
        if client:
            await client.aclose()
        raise HTTPException(status_code=500, detail=f"Agent service error: {str(e)}")


# ============ PDB File Proxy ============

@app.get("/api/pdb/{filename:path}")
async def get_pdb_file(filename: str):
    """Get PDB file content from structure_predict service's output directory."""
    possible_paths = [
        f"/tmp/esmfold_output/{filename}",
        f"/tmp/static/pdb/{filename}",
    ]
    
    for pdb_path in possible_paths:
        if os.path.exists(pdb_path):
            try:
                with open(pdb_path, 'r') as f:
                    content = f.read()
                return Response(
                    content=content,
                    media_type="chemical/x-pdb",
                    headers={
                        "Content-Disposition": f"inline; filename={filename}",
                        "Access-Control-Allow-Origin": "*"
                    }
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to read PDB file: {str(e)}")
    
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
    return await proxy_request("structure_predict", "/api/predict/structure", request)

@app.api_route("/api/query/structure", methods=["POST"])
async def proxy_structure_query(request: Request):
    return await proxy_request("structure_predict", "/api/query/structure", request)

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
    return await proxy_form_request("active_sites", f"/api/predict/active-sites/{path}", request)


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
    return await proxy_request("sequence_alignment", "/api/query/blast", request)


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
    return await proxy_request("enzyme_type", "/api/recommend/enzyme", request)


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
    uvicorn.run(app, host="0.0.0.0", port=8080)
