"""Workspace-owned sandbox admission, provenance and bounded private artifacts."""
import asyncio
import base64
from contextlib import suppress
import hashlib
import ipaddress
import json
import os
import time
from urllib.parse import urlsplit
from uuid import UUID, uuid4
from pathlib import Path

import httpx
from fastapi import HTTPException

from services.python_sandbox.protocol import (
    FILES_BYTES, INPUT_BYTES, OUTPUT_BYTES, Rejected, json_bytes, validate_code, validate_files,
)

WORKSPACE_BYTES = 100 * 1024 ** 2
GLOBAL_BYTES = 10 * 1024 ** 3
RESULT_REFERENCES = 12


def require_agent_transport(request):
    """The Python tool is an internal Agent endpoint, never a browser API.

    Check the unmodified ASGI peer, not a claimed forwarded address. The turn
    capability remains independently mandatory; an allowed IP is not identity.
    Local debugging uses the authenticated loopback Runner instead.
    """
    def address(value):
        ip = ipaddress.ip_address(value)
        return ip.ipv4_mapped if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped else ip
    try:
        allowed = {address(value.strip()) for value in
                   os.getenv('ENZYMIND_PYTHON_AGENT_IPS', '').split(',') if value.strip()}
        peer = address(request.client.host)
    except (ValueError, AttributeError):
        raise HTTPException(403, 'Python analysis requires the internal Agent connection.')
    # Reject public proxy and browser requests even when a proxy shares a local
    # address with n8n. Never use these headers to grant internal access.
    proxied = any(key == 'forwarded' or key.startswith('x-forwarded-') or
                  key in {'x-real-ip', 'origin', 'sec-fetch-site'} for key in request.headers)
    if not allowed or peer not in allowed or proxied:
        raise HTTPException(403, 'Python analysis requires the internal Agent connection.')


def init_schema(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS python_runs (
          id TEXT PRIMARY KEY, result_id TEXT NOT NULL, owner TEXT NOT NULL,
          turn_id TEXT NOT NULL, fingerprint TEXT NOT NULL, created REAL NOT NULL,
          state TEXT NOT NULL, reserved_bytes INTEGER NOT NULL DEFAULT 0,
          UNIQUE(turn_id,fingerprint));
        CREATE INDEX IF NOT EXISTS python_runs_state ON python_runs(state,owner);
        CREATE TABLE IF NOT EXISTS python_attempts (
          id TEXT PRIMARY KEY, owner TEXT NOT NULL, ip TEXT NOT NULL, created REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS python_attempts_time ON python_attempts(created);
        CREATE TABLE IF NOT EXISTS python_files (
          id TEXT PRIMARY KEY, result_id TEXT NOT NULL, owner TEXT NOT NULL,
          name TEXT NOT NULL, mime TEXT NOT NULL, size INTEGER NOT NULL,
          sha256 TEXT NOT NULL, content BLOB NOT NULL);
        CREATE INDEX IF NOT EXISTS python_files_result ON python_files(result_id);
        CREATE INDEX IF NOT EXISTS python_files_owner ON python_files(owner,size);
    ''')


def source_ip(request):
    """Only the actual ASGI peer can authorize forwarded headers.

    Uvicorn must run with --no-proxy-headers so it cannot rewrite this peer first.
    Walk XFF from the trusted edge; never accept the leftmost address blindly.
    """
    try:
        peer = ipaddress.ip_address(request.client.host)
        trusted = [ipaddress.ip_network(item.strip()) for item in
                   os.getenv('ENZYMIND_TRUSTED_PROXIES', '').split(',') if item.strip()]
        def allowed(ip):
            return any(ip in network for network in trusted)
        if allowed(peer):
            forwarded = request.headers.get('x-forwarded-for', '')
            if len(forwarded) > 2048:
                raise ValueError('header')
            for address in reversed(forwarded.split(',')):
                if not allowed(peer):
                    break
                peer = ipaddress.ip_address(address.strip())
        return hashlib.sha256(str(peer).encode()).hexdigest()
    except (ValueError, AttributeError):
        # All unresolvable peers share one conservative bucket; no model fallback.
        return hashlib.sha256(b'unknown-peer').hexdigest()


def normalize(body):
    if set(body) - {'code', 'data', 'result_ids', 'file_ids'}:
        raise HTTPException(422, 'Use only code, data, result_ids and file_ids.')
    try:
        validate_code(body.get('code'))
        if not isinstance(body.get('data', {}), dict):
            raise Rejected('data must be a JSON object.')
        json_bytes(body.get('data', {}))
        normalized = {'code': body['code'], 'data': body.get('data', {})}
        for key, limit in [('result_ids', RESULT_REFERENCES), ('file_ids', 10)]:
            values = body.get(key, [])
            if not isinstance(values, list) or len(values) > limit:
                raise Rejected(f'{key} permits at most {limit} references.')
            normalized[key] = sorted(set(str(UUID(value)) for value in values))
        return normalized
    except (Rejected, ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(422, str(exc) if isinstance(exc, Rejected) else 'Invalid reference ID.')


class PythonSandbox:
    def __init__(self, store):
        self.store = store
        self.tasks = {}

    def recover(self):
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            for row in db.execute("SELECT result_id,turn_id FROM python_runs WHERE state='running'").fetchall():
                saved = db.execute('SELECT payload FROM results WHERE id=?', (row[0],)).fetchone()
                if saved is None:
                    continue
                payload = json.loads(saved[0])
                payload.update(success=False, execution_status='interrupted', error='Gateway restarted; this execution will not be repeated.')
                db.execute("UPDATE results SET status='failed',payload=? WHERE id=?", (json.dumps(payload), row[0]))
                db.execute('INSERT INTO events(turn_id,kind,data,created) VALUES(?,?,?,?)', (row[1], 'tool_end',
                    json.dumps({'tool':'python', 'label':'Python analysis', 'status':'failed', 'result_id':row[0], 'duration':0}), time.time()))
            db.execute("UPDATE python_runs SET state='interrupted',reserved_bytes=0 WHERE state='running'")

    def file(self, owner, file_id, result_id=None):
        with self.store.db() as db:
            row = db.execute('SELECT f.* FROM python_files f JOIN results r ON r.id=f.result_id WHERE f.id=? AND f.owner=? AND r.owner=?',
                             (file_id, owner, owner)).fetchone()
        if not row or (result_id and row['result_id'] != result_id):
            raise HTTPException(404, 'File not found in this workspace.')
        return dict(row)

    def inputs(self, owner, body):
        results, sources, files, paths = {}, [], [], {}
        for result_id in body['result_ids']:
            record = self.store.result(owner, result_id)
            results[result_id] = record['payload']
            sources.append({'result_id': result_id, 'sha256': hashlib.sha256(json_bytes(record['payload'])).hexdigest()})
        total = 0
        for file_id in body['file_ids']:
            record = self.file(owner, file_id)
            total += record['size']
            if total > FILES_BYTES:
                raise HTTPException(413, 'Referenced files exceed 5 MiB.')
            # Server-assigned UUID prevents two display names from overwriting each other.
            name = file_id + '.' + record['name'].rsplit('.', 1)[-1]
            files.append({'name': name, 'content': base64.b64encode(record['content']).decode()})
            paths[file_id] = '/work/inputs/' + name
            sources.append({'file_id': file_id, 'result_id': record['result_id'], 'sha256': record['sha256']})
        inputs = {'data': body['data'], 'results': results, 'files': paths}
        if len(json_bytes(inputs)) + total > INPUT_BYTES:
            raise HTTPException(413, 'Copied inputs exceed 6 MiB; select smaller saved inputs.')
        return inputs, files, sources

    def admit(self, turn, body, sources):
        fingerprint = hashlib.sha256(json_bytes({'input': body, 'sources': sources})).hexdigest()
        now, job_id, result_id = time.time(), str(uuid4()), str(uuid4())
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            current = db.execute("SELECT * FROM turns WHERE id=? AND owner=? AND status='running' AND lease_expires>? AND created>?",
                                 (turn['id'], turn['owner'], now, now - 7200)).fetchone()
            if not current:
                raise HTTPException(403, 'Turn is no longer active.')
            budget = db.execute("SELECT count(*) FROM events WHERE turn_id=? AND kind='tool_start'", (turn['id'],)).fetchone()[0]
            if budget >= 12:
                raise HTTPException(429, 'The shared 12-tool budget is exhausted.')
            old = db.execute('SELECT * FROM python_runs WHERE turn_id=? AND fingerprint=?', (turn['id'], fingerprint)).fetchone()
            if old:
                db.execute('INSERT INTO events(turn_id,kind,data,created) VALUES(?,?,?,?)',
                    (turn['id'], 'tool_start', json.dumps({'tool':'python', 'label':'Python analysis', 'job_id':old['id'], 'reused':True}), now))
                return dict(old), True
            calls = db.execute('SELECT count(*) FROM python_runs WHERE turn_id=?', (turn['id'],)).fetchone()[0]
            if calls >= 3:
                raise HTTPException(429, 'Python permits 3 executions per turn within the 12-tool budget.')
            ip = current['source_ip_hash'] or hashlib.sha256(b'unknown-peer').hexdigest()
            for where, params, limit in [('owner=?', [turn['owner']], 10), ('ip=?', [ip], 20), ('1=1', [], 120)]:
                count = db.execute(f'SELECT count(*) FROM python_attempts WHERE created>? AND {where}', [now - 3600] + params).fetchone()[0]
                if count >= limit:
                    raise HTTPException(429, 'Python hourly execution limit reached.')
            db.execute('INSERT INTO python_attempts VALUES(?,?,?,?)', (job_id, turn['owner'], ip, now))
            running = db.execute("SELECT owner FROM python_runs WHERE state='running'").fetchall()
            error = 'busy' if len(running) >= 2 or any(r[0] == turn['owner'] for r in running) else None
            for owner_filter, params, limit in [('WHERE owner=?', [turn['owner']], WORKSPACE_BYTES), ('', [], GLOBAL_BYTES)]:
                used = db.execute(f'SELECT coalesce(sum(size),0) FROM python_files {owner_filter}', params).fetchone()[0]
                reserved = db.execute(f'SELECT coalesce(sum(reserved_bytes),0) FROM python_runs {owner_filter}', params).fetchone()[0]
                if used + reserved + FILES_BYTES > limit:
                    error = 'storage_quota'
            payload = {'success': False, 'execution_status': error or 'running', 'files': [], 'input_sources': sources,
                       'code_sha256': hashlib.sha256(body['code'].encode()).hexdigest(), 'job_id': job_id}
            if error:
                payload['error'] = error
            db.execute('INSERT INTO results(id,owner,session_id,turn_id,tool,title,status,inputs,payload,created,duration) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (result_id, turn['owner'], turn['session_id'], turn['id'], 'python', 'Python analysis',
                 'failed' if error else 'pending', json.dumps(body), json.dumps(payload), now, 0))
            db.execute('INSERT INTO python_runs VALUES(?,?,?,?,?,?,?,?)',
                (job_id, result_id, turn['owner'], turn['id'], fingerprint, now, error or 'running', 0 if error else FILES_BYTES))
            db.execute('INSERT INTO events(turn_id,kind,data,created) VALUES(?,?,?,?)',
                (turn['id'], 'tool_start', json.dumps({'tool': 'python', 'label': 'Python analysis', 'job_id': job_id}), now))
        return {'id': job_id, 'result_id': result_id, 'state': error or 'running'}, False

    def finish(self, turn, run, result):
        decoded = validate_files(result.get('files', []))
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            state = db.execute('SELECT state FROM python_runs WHERE id=?', (run['id'],)).fetchone()
            if not state or state[0] != 'running':
                return  # A committed finish or restart recovery is final.
            old = db.execute('SELECT payload FROM results WHERE id=?', (run['result_id'],)).fetchone()
            if old is None:
                return
            payload = json.loads(old[0])
            payload.update(result)
            payload['files'] = []
            for name, mime, raw in decoded:
                file_id = str(uuid4())
                sha = hashlib.sha256(raw).hexdigest()
                db.execute('INSERT INTO python_files VALUES(?,?,?,?,?,?,?,?)',
                           (file_id, run['result_id'], turn['owner'], name, mime, len(raw), sha, raw))
                payload['files'].append({'id': file_id, 'name': name, 'mime': mime, 'size': len(raw), 'sha256': sha,
                    'url': f"/api/workspace/results/{run['result_id']}/files/{file_id}"})
            db.execute('UPDATE results SET status=?,payload=?,duration=? WHERE id=?',
                       ('completed' if result.get('success') else 'failed', json.dumps(payload), result.get('duration', 0), run['result_id']))
            db.execute('UPDATE python_runs SET state=?,reserved_bytes=0 WHERE id=?', (result['execution_status'], run['id']))

    def runner_config(self):
        url = os.getenv('ENZYMIND_PYTHON_RUNNER_URL', 'http://127.0.0.1:8091')
        parsed = urlsplit(url)
        if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', '::1') or
                parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment or
                parsed.path not in ('', '/')):
            raise HTTPException(503, 'Python Runner must use a loopback URL.')
        token = os.getenv('PYTHON_SANDBOX_TOKEN', '')
        if len(token) < 32:
            raise HTTPException(503, 'Python Runner credential is not configured.')
        return url.rstrip('/'), {'Authorization': 'Bearer ' + token}

    async def invoke(self, payload, url, headers):
        async with httpx.AsyncClient(timeout=httpx.Timeout(85, connect=3), trust_env=False) as client:
            raw = bytearray()
            async with client.stream('POST', url + '/jobs', json=payload, headers=headers) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    raw.extend(chunk)
                    if len(raw) > 9 * 1024 * 1024:
                        raise Rejected('runner_response_size')
        result = json.loads(raw)
        allowed = {'success', 'execution_status', 'error', 'stdout', 'stderr', 'result', 'files',
                   'exit_code', 'duration', 'memory_bytes', 'image_digest', 'versions'}
        if not isinstance(result, dict) or set(result) - allowed or not isinstance(result.get('success'), bool):
            raise Rejected('runner_response_schema')
        if len(json_bytes(result.get('result'))) > OUTPUT_BYTES:
            raise Rejected('json_size')
        if sum(len(result.get(k, '').encode()) for k in ('stdout', 'stderr')) > OUTPUT_BYTES:
            raise Rejected('output_limit')
        validate_files(result.get('files', []))
        return result

    async def execute(self, turn, body, request):
        disabled = Path(os.getenv('ENZYMIND_PYTHON_DISABLE_FILE', str(self.store.path.parent / 'python.disabled')))
        if os.getenv('ENZYMIND_PYTHON_ENABLED', 'false').lower() != 'true' or disabled.exists():
            raise HTTPException(503, 'Python analysis is disabled.')
        url, headers = self.runner_config()
        body = normalize(body)
        inputs, files, sources = self.inputs(turn['owner'], body)
        run, reused = self.admit(turn, body, sources)
        if reused:
            record = self.store.result(turn['owner'], run['result_id'])
            self.end_event(turn, record, reused=True)
            return record, True
        if run['state'] != 'running':
            record = self.store.result(turn['owner'], run['result_id'])
            self.end_event(turn, record)
            return record, False
        payload = {'job_id': run['id'], 'owner': turn['owner'], 'code': body['code'], 'inputs': inputs, 'files': files}
        started = time.monotonic()
        task = asyncio.create_task(self.invoke(payload, url, headers))
        self.tasks[run['id']] = task
        try:
            async with asyncio.timeout(90):
                while not task.done():
                    current = self.store.turn(turn['owner'], turn['id'])
                    if current['status'] != 'running' or current['lease_expires'] <= time.time() or await request.is_disconnected():
                        raise asyncio.CancelledError()
                    await asyncio.sleep(.1)
                result = await task
            self.finish(turn, run, result)
        except (Exception, asyncio.CancelledError) as exc:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            with suppress(Exception):
                async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
                    await client.delete(url + '/jobs/' + run['id'], headers=headers)
            status = 'cancelled' if isinstance(exc, asyncio.CancelledError) else 'transport_or_output_error'
            # Never retry POST after a transport failure: the durable run remains authoritative.
            self.finish(turn, run, {'success': False, 'execution_status': status, 'error': status,
                                   'duration': time.monotonic() - started, 'files': []})
        finally:
            self.tasks.pop(run['id'], None)
        record = self.store.result(turn['owner'], run['result_id'])
        self.end_event(turn, record)
        return record, False

    def end_event(self, turn, record, reused=False):
        self.store.event(turn['id'], 'tool_end', {'tool': 'python', 'label': 'Python analysis',
            'status': record['status'], 'result_id': record['id'], 'duration': record['duration'], 'reused':reused})

    async def stop(self):
        for task in self.tasks.values():
            task.cancel()


def purge(db, cutoff):
    # BLOBs and their quota accounting are removed in the result-retention transaction.
    db.execute('DELETE FROM python_files WHERE result_id IN (SELECT id FROM expired_results)')
    db.execute('DELETE FROM python_runs WHERE result_id IN (SELECT id FROM expired_results)')
    db.execute('DELETE FROM python_attempts WHERE created<?', (cutoff,))
