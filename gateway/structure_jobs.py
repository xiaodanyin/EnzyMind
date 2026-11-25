"""Owner-scoped folding results that outlive a public proxy's idle timeout."""
import asyncio
import json
import logging
import secrets
import time

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from . import workspace
from .input_validation import normalize_inputs
from .workspace_store import digest

_tasks = set()
SYNC_WAIT = 75


def response(record, token=None, *, polling=False):
    payload = dict(record["payload"])
    code = payload.pop("_http_status", 200)
    headers = {"Cache-Control": "private, no-store"}
    if polling:
        payload["status"] = record["status"]
    if record["status"] == "running":
        code = 202
        path = f"/predict/structure/jobs/{record['id']}"
        headers.update({"Retry-After": "5", "Location": "/enzymind/api" + path})
        payload.update(job_id=record["id"], poll_path=path)
        if token:
            payload["poll_token"] = token
    payload["workspace_result"] = {k: v for k, v in record.items() if k != "payload"}
    return JSONResponse(payload, status_code=code, headers=headers)


async def finish(store, owner, job_id, predict):
    start = time.monotonic()
    try:
        result = await predict()
        code, data = result.status_code, json.loads(result.body)
        if data.get("success") and code == 200:
            data = await workspace.preserve_structure(data)
            status = "completed"
        else:
            status = "failed"
            if code < 400:
                code = 502
            data["success"] = False
    except Exception:
        logging.getLogger(__name__).exception("Folding response unavailable for job %s", job_id)
        code, status = 502, "failed"
        data = {"success": False, "error_code": "structure_service_error", "error": "The structure worker response could not be read."}
    if status == "failed":
        data.update(status=status, _http_status=code)
    with store.db() as db:
        db.execute("UPDATE results SET payload=?,status=?,duration=? WHERE owner=? AND id=? AND status='running'",
                   (json.dumps(data), status, time.monotonic() - start, owner, job_id))


async def submit(request, predict):
    raw = await workspace.body_json(request)
    inputs = normalize_inputs("structure_predict", raw)
    if not inputs.get("query"):
        return JSONResponse({"success": False, "error_code": "invalid_input", "error": "A protein query is required.",
                             "detail": [{"loc": ["body", "query"], "msg": "Field required", "type": "missing"}]}, status_code=422)
    token = None if request.headers.get("x-enzymind-client") else secrets.token_hex(32)
    owner = digest(token) if token else workspace.owner(request)
    store = workspace.store()
    # A single Gateway worker registers the row before yielding to the event loop.
    with store.db() as db:
        active = db.execute("SELECT id,inputs FROM results WHERE owner=? AND tool='structure' AND status='running'",
                            (owner,)).fetchall()
    for previous in active:
        if json.loads(previous["inputs"]) == inputs:
            return response(store.result(owner, previous["id"]), token)
    record = store.save_result(owner, "structure", inputs, {"status": "running"})
    task = asyncio.create_task(finish(store, owner, record["id"], lambda: predict(inputs)))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    await asyncio.wait({task}, timeout=1 if "respond-async" in request.headers.get("prefer", "").lower() else SYNC_WAIT)
    return response(store.result(owner, record["id"]), token)


def get(request, job_id):
    record = workspace.store().result(workspace.owner(request), workspace.validate_uuid(job_id))
    if record["tool"] != "structure":
        raise HTTPException(404, "Folding job not found.")
    return response(record, polling=True)


def recover():
    data = {"status": "failed", "success": False, "error_code": "structure_interrupted", "_http_status": 503,
            "error": "The gateway restarted before receiving the structure result."}
    with workspace.store().db() as db:
        db.execute("UPDATE results SET status='failed', payload=? WHERE tool='structure' AND status='running'",
                   (json.dumps(data),))
