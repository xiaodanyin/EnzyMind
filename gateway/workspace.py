"""Research workspace API. n8n orchestrates reasoning; the gateway owns records."""
import asyncio
from contextlib import suppress
import json
import logging
import os
from gateway.service_policy import service_timeout
import re
import time
from pathlib import Path
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from .result_catalog import TOOLS, cited_results, compact, payload_error, RESULT_UUID, normalize_result_links
from .workspace_store import WorkspaceStore, digest
from .input_validation import normalize_inputs
from .workspace_stream import read_workflow_response
from .retention import run_cleanup
from .retention_policy import RETENTION_DAYS, CLEANUP_INTERVAL_SECONDS, EXPIRY_WARNING_DAYS
from .model_relay import relay, validate_key
from .python_sandbox import PythonSandbox, source_ip, require_agent_transport

router = APIRouter(prefix="/api/workspace")
_store = None
_tasks = {}
_services = {}
_retention_task = None
_blast_jobs = None
_python_sandbox = None
PREDICTION_TOOLS = {'recognize', 'ec', 'substrate', 'kcat', 'km', 'structure', 'active-sites', 'enzyme-type', 'blast'}


def prediction_fingerprint(tool, inputs):
    """Operational timeouts / queue settings do not make a new scientific input."""
    fields = ('enzyme_query', 'smiles') if tool in {'substrate', 'kcat', 'km'} else (
        ('uniprot_id', 'aa_sequence', 'rxn_smiles') if tool == 'active-sites' else ('query',))
    values = {field: inputs[field] for field in fields if inputs.get(field) not in (None, '')}
    if tool == 'blast':
        values['max_results'] = inputs.get('max_results', 3)
        values['database'] = inputs.get('database', 'nr')
    return digest(json.dumps(values, sort_keys=True, ensure_ascii=False))


def store():
    global _store
    if _store is None:
        _store = WorkspaceStore()
    return _store


def blast_jobs():
    global _blast_jobs
    from .blast_jobs import BlastJobs
    if _blast_jobs is None or _blast_jobs.store is not store():
        _blast_jobs = BlastJobs(store(), _services['sequence_alignment'])
    return _blast_jobs


def python_sandbox():
    global _python_sandbox
    if _python_sandbox is None or _python_sandbox.store is not store():
        _python_sandbox = PythonSandbox(store())
    return _python_sandbox


def owner(request):
    key = request.headers.get("x-enzymind-client", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", key):
        raise HTTPException(401, "A workspace access key is required. Reopen the workspace to initialize it.")
    return digest(key)


def validate_uuid(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(422, "A valid UUID is required.")


async def body_json(request, *, max_bytes=256_000):
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > max_bytes:
            raise HTTPException(413, f"Input is too large. Limit each request to {max_bytes // 1000:,} KB.")
    try:
        body = json.loads(raw)
    except (ValueError, RecursionError):
        raise HTTPException(422, "Send valid JSON.")
    if not isinstance(body, dict):
        raise HTTPException(422, "Send a JSON object.")
    return body


def result_evidence(record):
    payload = compact(record["payload"])
    encoded = json.dumps(payload, ensure_ascii=False)
    return {"id": record["id"], "url": record["url"], "title": record["title"],
            "status": record["status"], "evidence_type": record["evidence_type"],
            "artifacts": {"structure_available": bool(pdb_text(record["payload"])),
                          "note": "Structure contents are omitted from model context, but available in the linked result when structure_available is true."},
            "inputs": compact(record["inputs"]),
            "data": payload if len(encoded) <= 12000 else {"excerpt": encoded[:12000], "truncated": True}}


def read_evidence(record, inputs):
    """Let the model inspect a precise portion of a large saved result."""
    evidence = result_evidence(record)
    if not any(k in inputs for k in ("field", "offset", "limit")):
        return evidence
    field = inputs.get("field", "")
    if not isinstance(field, str) or len(field) > 300:
        raise HTTPException(422, "field must be a dotted path inside the saved payload.")
    selected = record["payload"]
    parts = field.split(".") if field else []
    try:
        for part in parts:
            if part in {"structure_data", "pdb", "pdb_content", "pdb_text", "html", "structure_html"}:
                raise HTTPException(422, "Coordinate and HTML blobs are available in the result viewer, not model context.")
            selected = selected[int(part)] if isinstance(selected, list) and part.isdigit() else selected[part]
    except (KeyError, IndexError, TypeError):
        raise HTTPException(422, "This field path does not exist in the saved payload.")
    offset, limit = inputs.get("offset", 0), inputs.get("limit", 30)
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 30:
        raise HTTPException(422, "Use an integer offset >= 0 and limit between 1 and 30.")
    page = {"field": field}
    if isinstance(selected, list):
        total = len(selected)
        selected = selected[offset:offset + limit]
        page.update(offset=offset, returned=len(selected), total=total,
                    next_offset=offset + len(selected) if offset + len(selected) < total else None)
    elif offset:
        raise HTTPException(422, "Array pagination requires an array field.")
    compacted = compact(selected)
    encoded = json.dumps(compacted, ensure_ascii=False)
    evidence.update(selection=page, data=compacted if len(encoded) <= 12000 else
                    {"excerpt": encoded[:12000], "truncated": True, "hint": "Select a narrower field or smaller page."})
    return evidence


@router.get("/sessions")
def sessions(request: Request):
    return {"sessions": store().sessions(owner(request))}


@router.get('/retention')
def retention_policy():
    return {'retention_days': RETENTION_DAYS, 'warning_days': EXPIRY_WARNING_DAYS,
            'cleanup_interval_seconds': CLEANUP_INTERVAL_SECONDS,
            'basis': 'Each result and conversation turn expires 90 days after creation.'}


@router.get('/usage')
def usage(request: Request):
    return store().usage(owner(request))


@router.post('/model/chat/completions')
async def model_completion(request: Request):
    authorization = request.headers.get('authorization', '')
    if not authorization.startswith('Bearer '):
        raise HTTPException(401, 'A temporary model capability is required.')
    return await relay.forward(authorization[7:], await body_json(request), store())


@router.post("/sessions")
async def create_session(request: Request):
    session = store().create_session(owner(request))
    session.pop("owner")
    return session


@router.get("/sessions/{session_id}")
def get_session(session_id: str, request: Request):
    store().recover()
    key = owner(request)
    session = store().session(key, session_id)
    session.pop("owner")
    turns = store().turns(key, session_id)
    records = session_results(key, session_id, turns)
    known = {record['id']: record for record in records}
    for turn in turns:
        turn['output'] = normalize_result_links(turn['output'], known)
    return {**session, "turns": turns, "results": records}


def session_results(key, session_id, turns=None):
    records = {r['id']: r for r in store().results(key, session_id)}
    refs = set()
    for turn in turns if turns is not None else store().turns(key, session_id):
        refs.update(turn['references'])
        for event in turn['events']:
            if event['kind'] == 'references':
                refs.update(r['id'] for r in event['data']['results'])
            elif event['kind'] == 'tool_end' and event['data'].get('result_id'):
                refs.add(event['data']['result_id'])
    for result_id in refs - records.keys():
        try:
            records[result_id] = store().result(key, result_id, full=False)
        except HTTPException:
            continue
    return sorted(records.values(), key=lambda r: r['created'], reverse=True)


@router.post("/sessions/{session_id}/turns")
async def create_turn(session_id: str, request: Request):
    # Admit a 100k-token ASCII question (up to 300k characters), including JSON
    # escaping and attached FASTA. Other workspace endpoints retain their cap.
    key, body = owner(request), await body_json(request, max_bytes=2_000_000)
    provider_key = request.headers.get('x-deepseek-api-key', '')
    if provider_key:
        validate_key(provider_key)
    message = body.get("message")
    if not isinstance(message, str) or not message.strip() or len(message) > 300000:
        raise HTTPException(422, "Enter a message between 1 and 300,000 characters.")
    refs = body.get("references", [])
    if not isinstance(refs, list) or len(refs) > 4:
        raise HTTPException(422, "Attach up to four saved results.")
    refs = list(dict.fromkeys(validate_uuid(r) for r in refs))
    # Explicit result links in a question are treated like attached evidence.
    refs = list(dict.fromkeys(refs + cited_results(message)))
    if len(refs) > 4:
        raise HTTPException(422, "Reference up to four results per message.")
    turn, token = store().begin(key, session_id, validate_uuid(body.get("request_id")), message.strip(), refs,
                                billing_mode='byok' if provider_key else 'free', source_ip_hash=source_ip(request))
    if token:
        task = asyncio.create_task(run_turn(key, turn, token, provider_key))
        _tasks[turn["id"]] = task
        task.add_done_callback(lambda _: _tasks.pop(turn["id"], None))
    return turn


@router.get("/turns/{turn_id}")
def get_turn(turn_id: str, request: Request):
    store().recover()
    return store().turn(owner(request), turn_id)


@router.get("/turns/{turn_id}/stream")
async def stream_turn(turn_id: str, request: Request):
    key = owner(request)
    store().recover()
    store().turn(key, turn_id)  # Authorize before sending any response headers.

    async def frames():
        previous = None
        heartbeat_at = time.monotonic()
        def frame(kind, data):
            return f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        while not await request.is_disconnected():
            store().recover()
            current = store().turn(key, turn_id)
            if previous is None:
                yield frame('snapshot', {'turn': current, 'results': session_results(key, current['session_id'])})
            else:
                text, old = current['partial_output'], previous['partial_output']
                if text != old and current['status'] in ('queued', 'running'):
                    if text.startswith(old):
                        yield frame('delta', {'text': text[len(old):]})
                    else:
                        yield frame('snapshot', {'turn': current})
                if (current['status'], current['error'], current['events']) != (previous['status'], previous['error'], previous['events']):
                    yield frame('progress', {k: current[k] for k in ('status', 'error', 'events')})
                    if current['events'] != previous['events']:
                        yield frame('results', {'results': session_results(key, current['session_id'])})
            if current['status'] not in ('queued', 'running'):
                yield frame('done', {'turn': current})
                return
            if time.monotonic() - heartbeat_at >= 15:
                yield ': keepalive\n\n'
                heartbeat_at = time.monotonic()
            previous = current
            await asyncio.sleep(.1)

    return StreamingResponse(frames(), media_type='text/event-stream', headers={
        'Cache-Control': 'private, no-cache, no-store, no-transform',
        'X-Accel-Buffering': 'no',
    })


@router.post("/memory-progress")
async def memory_progress(request: Request):
    turn = store().authorize_turn(request.headers.get("x-enzymind-turn", ""))
    body = await body_json(request)
    state = body.get("state")
    if state not in ("compressing", "ready"):
        raise HTTPException(422, "Unknown memory state.")
    tokens = body.get("context_tokens", 0)
    if type(tokens) is not int or not 0 <= tokens <= 2_000_000:
        raise HTTPException(422, "Invalid context estimate.")
    warning = body.get("warning", False)
    if type(warning) is not bool:
        raise HTTPException(422, "Invalid context warning.")
    warning_text = ("Long context. Analysis is continuing with your full question and attached evidence. "
                    "Processing may take longer.") if warning else ""
    store().event(turn['id'], 'memory', {"state": state, "context_tokens": tokens,
        "warning": warning_text,
        "label": "Compressing older conversation; original turns remain saved" if state == 'compressing' else "Memory ready for analysis"})
    return {"ok": True}


@router.post("/turns/{turn_id}/cancel")
async def cancel_turn(turn_id: str, request: Request):
    key = owner(request)
    store().turn(key, turn_id)
    store().status(key, turn_id, "cancelled", error="Stopped by you. A computation already submitted may still finish; saved results remain available in the result library.")
    if turn_id in _tasks:
        _tasks[turn_id].cancel()
    return store().turn(key, turn_id)


@router.get("/results")
def list_results(request: Request):
    return {"results": store().results(owner(request))}


@router.get("/results/{result_id}")
def get_result(result_id: str, request: Request):
    return store().result(owner(request), result_id)


@router.get('/results/{result_id}/files/{file_id}')
def result_file(result_id: str, file_id: str, request: Request):
    item = python_sandbox().file(owner(request), validate_uuid(file_id), validate_uuid(result_id))
    return Response(item['content'], media_type=item['mime'], headers={
        'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
        'Content-Security-Policy': "default-src 'none'; sandbox",
        'Content-Disposition': f'attachment; filename="{item["name"]}"',
    })


@router.post("/results/{result_id}/refresh")
def refresh_blast_result(result_id: str, request: Request):
    return blast_jobs().refresh(owner(request), result_id)


def pdb_text(payload):
    if not isinstance(payload, dict):
        return None
    for field in ("structure_data", "pdb_content", "pdb_text"):
        text = payload.get(field)
        if isinstance(text, str) and re.search(r"^(?:ATOM  |HETATM)", text, re.M):
            return text
    for value in payload.values():
        candidates = value if isinstance(value, list) else [value]
        for item in candidates:
            if isinstance(item, dict):
                text = pdb_text(item)
                if text:
                    return text
    return None


@router.get("/results/{result_id}/structure")
def result_structure(result_id: str, request: Request):
    record = store().result(owner(request), result_id)
    text = pdb_text(record["payload"])
    if not text:
        raise HTTPException(404, "No PDB structure is stored in this result.")
    return Response(text, media_type="chemical/x-pdb", headers={"Cache-Control": "private, no-store"})


async def run_turn(key, turn, token, provider_key=''):
    turn_id, session_id = turn["id"], turn["session_id"]
    model_token = relay.register(provider_key, key, turn_id) if provider_key else ''
    provider_key = ''
    worker = asyncio.current_task()
    async def heartbeat():
        while True:
            await asyncio.sleep(30)
            if not store().renew(key, turn_id):
                store().recover()
                worker.cancel()
                return
    lease_task = asyncio.create_task(heartbeat())
    pending_text, last_flush = '', 0
    def flush_text(text='', force=False):
        nonlocal pending_text, last_flush
        pending_text += text
        if pending_text and (force or time.monotonic() - last_flush >= .05 or len(pending_text) >= 512):
            if not store().append_partial(key, turn_id, pending_text):
                raise ValueError('This answer can no longer accept streamed text. Saved results are preserved.')
            pending_text, last_flush = '', time.monotonic()
    try:
        if not store().renew(key, turn_id):
            store().recover()
            return
        store().status(key, turn_id, "running")
        store().event(turn_id, "status", {"label": "Reading conversation and attached results"})
        session = store().session(key, session_id)
        completed = [t for t in store().turns(key, session_id) if t["status"] == "completed"]
        records = session_results(key, session_id)
        known = {r['id']: r for r in records}
        history = [{"role": role, "content": normalize_result_links(t[field], known) if role == 'assistant' else t[field]} for t in completed
                   for role, field in (("user", "message"), ("assistant", "output"))]
        evidence = [result_evidence(store().result(key, r)) for r in turn["references"]]
        recent = records[:20]
        payload = {"session_id": session_id, "request_id": turn["request_id"], "turn_id": turn_id,
                   "message": turn["message"], "summary": normalize_result_links(session["summary"], known),
                   "summarized_count": session["summarized_count"],
                   "memory_revision": session["memory_revision"],
                   "history": history[session["summarized_count"]:], "evidence": evidence,
                   "billing_mode": turn.get('billing_mode', 'free'), "model_relay_token": model_token,
                   "result_index": [{k: r[k] for k in ("id", "title", "status", "url", "tool")} for r in recent]}
        url = os.getenv("N8N_WORKSPACE_WEBHOOK_URL", "http://localhost:5678/webhook/enzymind-workspace-v2")
        store().event(turn_id, "memory", {"state": "evaluating", "label": "Checking the conversation context budget"})
        async with httpx.AsyncClient(timeout=httpx.Timeout(7200, connect=15)) as client:
            async with client.stream('POST', url, json=payload, headers={"X-Enzymind-Turn": token, "Accept-Encoding": "identity"}) as response:
                if response.status_code == 404:
                    raise ValueError("The workspace workflow is not active. Import and activate EnzyMind Agent Workspace v2 in n8n.")
                response.raise_for_status()
                try:
                    data = await read_workflow_response(response, flush_text)
                finally:
                    flush_text(force=True)
        if isinstance(data, list) and len(data) == 1:
            data = data[0]
        if isinstance(data, dict) and isinstance(data.get("error"), str):
            raise ValueError(data["error"])
        if model_token and (not isinstance(data, dict) or data.get('billing_mode') != 'byok'):
            raise ValueError('The workflow must be upgraded to support your DeepSeek key.')
        if not isinstance(data, dict) or not isinstance(data.get("output"), str) or not data["output"].strip():
            raise ValueError("The workflow returned no answer. Saved tool results remain available.")
        if store().turn(key, turn_id)["status"] != "running":
            return
        owned_records = dict(known)
        summary = data.get("summary", session["summary"])
        for result_id in dict.fromkeys(v.lower() for v in re.findall(RESULT_UUID, data['output'] + '\n' + summary, re.I)):
            try:
                owned_records[result_id] = store().result(key, result_id, full=False)
            except HTTPException:
                continue
        data['output'] = normalize_result_links(data['output'], owned_records)
        # Only resolve citations to actual records owned by this workspace.
        refs = []
        for result_id in cited_results(data["output"]):
            try:
                record = store().result(key, result_id, full=False)
                refs.append(record)
            except HTTPException:
                continue
        summary = normalize_result_links(summary, owned_records)
        count = data.get("summarized_count", session["summarized_count"])
        # Without compression, retain the exact stored summary for the atomic
        # memory revision check. The context above is cleaned on every read.
        if count == session['summarized_count'] and summary == normalize_result_links(session['summary'], owned_records):
            summary = session['summary']
        if data.get("memory_revision", session["memory_revision"]) != session["memory_revision"]:
            raise ValueError("The workflow returned a stale memory revision.")
        store().complete(key, turn_id, session["memory_revision"], data["output"], summary, count, refs,
                         data.get("compression_count", 0), data.get("context_tokens", 0))
    except asyncio.CancelledError:
        store().status(key, turn_id, "interrupted", error="Processing interrupted. Completed results are preserved.")
        raise
    except Exception as exc:
        if model_token:
            lease = relay.leases.get(digest(model_token))
            message = lease.error if lease and lease.error else 'The Agent could not complete this turn using your DeepSeek key. Review saved results and retry.'
        elif isinstance(exc, httpx.ConnectError):
            message = "Cannot reach n8n. Start the workflow service, then try again."
        elif isinstance(exc, httpx.TimeoutException):
            message = "The workflow timed out. Review saved results before starting another analysis."
        elif isinstance(exc, httpx.HTTPStatusError):
            message = f"The workflow service returned HTTP {exc.response.status_code}. Review saved results and service logs."
        else:
            message = str(exc)
        store().status(key, turn_id, "failed", error=message)
    finally:
        if model_token:
            await relay.revoke(model_token)
        lease_task.cancel()
        with suppress(asyncio.CancelledError):
            await lease_task


async def preserve_structure(payload):
    """Snapshot a generated PDB so references survive temporary-file cleanup."""
    if not isinstance(payload, dict) or pdb_text(payload):
        return payload
    filename = payload.get("pdb_path") or payload.get("static_path")
    if not filename:
        return payload
    name = Path(str(filename)).name
    if not name.endswith(".pdb"):
        return payload
    from gateway.structure_artifacts import read_generated_pdb
    content = read_generated_pdb(name)
    if content is not None:
        return {**payload, "structure_data": content, "structure_format": "pdb"}
    return payload


@router.post("/tools/{tool}")
async def execute_tool(tool: str, request: Request):
    if tool == 'python':
        require_agent_transport(request)
    turn = store().authorize_turn(request.headers.get("x-enzymind-turn", ""))
    inputs = await body_json(request)
    if tool == 'python':
        record, reused = await python_sandbox().execute(turn, inputs, request)
        return {**result_evidence(record), 'reused': reused}
    if tool not in TOOLS and tool != "read-result":
        raise HTTPException(404, "Unknown research tool.")
    service, path, title, _ = TOOLS.get(tool, (None, None, "Read saved result", None))
    inputs = normalize_inputs(service, inputs)
    if tool == 'blast':
        inputs = blast_jobs().inputs(inputs)
    # A bounded tool budget prevents a loop from launching unbounded predictions.
    reused_id = None
    reuse_reason = None
    fingerprint = prediction_fingerprint(tool, inputs) if tool in PREDICTION_TOOLS else None
    with store().db() as db:
        db.execute("BEGIN IMMEDIATE")
        count = db.execute("SELECT COUNT(*) FROM events WHERE turn_id=? AND kind='tool_start'", (turn["id"],)).fetchone()[0]
        if count >= 12:
            raise HTTPException(429, "Tool budget reached. Interpret saved results before running more analyses.")
        if fingerprint:
            previous = db.execute("SELECT id,status,inputs FROM results WHERE turn_id=? AND tool=? ORDER BY created", (turn['id'], tool)).fetchall()
            failed = next((r for r in previous if r['status'] == 'failed'), None)
            matching = next((r for r in previous if prediction_fingerprint(tool, json.loads(r['inputs'])) == fingerprint), None)
            if matching or failed:
                reused_id = (matching or failed)['id']
                reuse_reason = 'identical_input' if matching else 'predictor_failed'
            else:
                starts = db.execute("SELECT data FROM events WHERE turn_id=? AND kind='tool_start'", (turn['id'],)).fetchall()
                if any((event := json.loads(row['data'])).get('tool') == tool and event.get('fingerprint') == fingerprint for row in starts):
                    reuse_reason = 'already_running'
        db.execute("INSERT INTO events(turn_id,kind,data,created) VALUES(?,?,?,?)",
                   (turn["id"], "tool_start", json.dumps({"tool": tool, "label": title, 'fingerprint': fingerprint, 'reused': bool(reuse_reason)}), time.time()))
    started = time.monotonic()
    if reuse_reason:
        if reused_id:
            record = store().result(turn['owner'], reused_id)
            evidence = result_evidence(record)
            evidence.update(reused=True, reuse_reason=reuse_reason,
                reuse_message='No new job was started. Use this saved result. After a predictor fails, a new user turn is required before trying that predictor again.')
            status = record['status']
        else:
            evidence = {'status': 'pending', 'reused': True, 'reuse_reason': reuse_reason,
                'message': 'An identical prediction is already running in this turn. No duplicate job was started. Wait for the original tool response.'}
            status = 'pending'
        store().event(turn['id'], 'tool_end', {'tool': tool, 'label': 'Reused · ' + title,
            'status': status, 'result_id': reused_id, 'duration': time.monotonic()-started, 'reused': True})
        return evidence
    if tool == "read-result":
        try:
            record = store().result(turn["owner"], validate_uuid(inputs.get("result_id")))
            evidence = read_evidence(record, inputs)
        except HTTPException as exc:
            store().event(turn["id"], "tool_end", {"tool": tool, "label": title, "status": "failed",
                                                  "duration": time.monotonic() - started})
            return {"status": "failed", "error": str(exc.detail)}
        store().event(turn["id"], "tool_end", {"tool": tool, "label": title, "status": "completed",
                                              "result_id": record["id"], "duration": time.monotonic() - started})
        return evidence
    if tool == 'blast':
        record = await blast_jobs().submit(turn['owner'], inputs, turn['session_id'], turn['id'])
        store().event(turn['id'], 'tool_end', {'tool': tool, 'label': title, 'status': record['status'],
            'result_id': record['id'], 'duration': time.monotonic() - started})
        evidence = result_evidence(record)
        evidence['message'] = record['payload'].get('error') or record['payload'].get('message')
        if record['status'] in {'submitting', 'queued', 'paused'}:
            evidence['message'] = 'The search is saved and still processing. Do not infer hits or resubmit. Read this result later for alignments.'
        return evidence
    try:
        # The server derives a stable private EasIFA identity, never supplied by the model.
        headers = {"X-Easifa-Session": turn["owner"]}
        async with httpx.AsyncClient(timeout=httpx.Timeout(service_timeout(service), connect=15)) as client:
            response = await client.post(_services[service] + path, json=inputs, headers=headers)
        response.raise_for_status()
        payload = response.json()
        payload = await preserve_structure(payload)
    except (httpx.HTTPError, ValueError) as exc:
        payload = {"success": False, "error": f"{title} could not complete ({type(exc).__name__}). Please retry after checking this service."}
    record = store().save_result(turn["owner"], tool, inputs, payload, turn["session_id"], turn["id"], time.monotonic() - started)
    store().event(turn["id"], "tool_end", {"tool": tool, "label": title, "status": record["status"],
                                              "result_id": record["id"], "duration": record["duration"]})
    return result_evidence(record)


def install(app, services):
    _services.update(services)
    app.include_router(router)

    @app.on_event("startup")
    async def recover_workspace():
        global _retention_task
        store().recover()
        python_sandbox().recover()
        async def cleanup_once():
            try:
                await asyncio.to_thread(run_cleanup, store())
            except Exception:
                logging.getLogger('enzymind.retention').exception('Retention cleanup failed; it will be retried at the next hourly pass.')
        await cleanup_once()
        if 'sequence_alignment' in _services:
            blast_jobs().start()
        async def maintenance_loop():
            while True:
                await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
                await cleanup_once()
        _retention_task = asyncio.create_task(maintenance_loop())

    @app.on_event('shutdown')
    async def stop_retention():
        global _retention_task
        await python_sandbox().stop()
        if _blast_jobs:
            await _blast_jobs.stop()
        if _retention_task:
            _retention_task.cancel()
            with suppress(asyncio.CancelledError): await _retention_task
            _retention_task = None

    @app.middleware("http")
    async def workspace_headers(request, call_next):
        response = await call_next(request)
        if "/api/workspace" in request.url.path:
            response.headers["Cache-Control"] = "private, no-store"
        return response
