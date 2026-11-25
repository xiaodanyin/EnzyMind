"""Loopback-only FastAPI service. Start with python -m services.python_sandbox.runner."""
import asyncio
from contextlib import asynccontextmanager, contextmanager
import fcntl
import grp
import hmac
import ipaddress
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import time
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers

from .engine import Engine, Limits
from .protocol import Rejected, input_archive

log = logging.getLogger('enzymind.python')
engine = None
ready = False
active = {}
state_path = None
metrics = {'executions': 0, 'rejected': 0, 'orphans_removed': 0}


@contextmanager
def db():
    connection = sqlite3.connect(state_path)
    try:
        connection.execute('PRAGMA journal_mode=WAL')
        with connection:
            yield connection
    finally:
        connection.close()


@asynccontextmanager
async def lifespan(app):
    global engine, ready, state_path
    ready = False
    state_dir = Path(os.environ['PYTHON_SANDBOX_STATE'])
    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock = (state_dir / 'runner.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state_path = state_dir / 'jobs.sqlite3'
    with db() as connection:
        connection.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, owner TEXT, created REAL, status TEXT)')
        connection.execute("UPDATE jobs SET status='interrupted' WHERE status='running'")
    os.chmod(state_path, 0o600)
    token = os.getenv('PYTHON_SANDBOX_TOKEN', '')
    socket = os.getenv('PYTHON_SANDBOX_SOCKET', f'/run/user/{os.geteuid()}/docker.sock')
    try:
        if len(token) < 32 or os.geteuid() == 0:
            raise RuntimeError('A dedicated non-root account and service token are required.')
        if any(grp.getgrgid(g).gr_name == 'docker' for g in {*os.getgroups(), os.getgid()}):
            raise RuntimeError('Sandbox account must not belong to the production docker group.')
        if socket != f'/run/user/{os.geteuid()}/docker.sock' or Path(socket).stat().st_uid != os.geteuid():
            raise RuntimeError('Use this dedicated account’s Rootless socket.')
        engine = Engine(socket, os.environ['PYTHON_SANDBOX_IMAGE'], Limits())
        metrics['orphans_removed'] += await engine.reap(all_jobs=True)
        await engine.preflight()
        ready = True
    except Exception as exc:
        # No Docker response body, credentials, code or scientific input in logs.
        log.error('startup_unavailable category=%s', type(exc).__name__)

    async def maintenance():
        global ready
        while True:
            await asyncio.sleep(15)
            if engine:
                try:
                    metrics['orphans_removed'] += await engine.reap()
                except Exception:
                    ready = False
                    log.error('reaper_unavailable')
    cleanup = asyncio.create_task(maintenance())
    try:
        yield
    finally:
        ready = False
        for _, cancel in active.values():
            cancel.set()
        cleanup.cancel()
        await asyncio.gather(cleanup, return_exceptions=True)
        if engine:
            await engine.reap(all_jobs=True)
            await engine.client.aclose()
        lock.close()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


class ServiceAuth:
    """Keep the original ASGI receive channel so disconnect reaches the job watcher."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http':
            headers = Headers(scope=scope)
            try:
                peer = ipaddress.ip_address(scope['client'][0])
                if isinstance(peer, ipaddress.IPv6Address) and peer.ipv4_mapped:
                    peer = peer.ipv4_mapped
                local = peer.is_loopback
            except (ValueError, TypeError, KeyError):
                local = False
            proxied = any(key == 'forwarded' or key.startswith('x-forwarded-') or
                          key in {'x-real-ip', 'origin', 'sec-fetch-site'} for key in headers)
            host = headers.get('host', '').lower()
            if (not local or proxied or len(headers.getlist('host')) != 1 or
                    not re.fullmatch(r'(?:127\.0\.0\.1|localhost|\[::1\])(?::[0-9]{1,5})?', host)):
                await JSONResponse({'detail': 'Local service access required'}, status_code=403)(scope, receive, send)
                return
            expected = os.getenv('PYTHON_SANDBOX_TOKEN', '')
            # Byte comparison safely rejects malformed non-ASCII headers too.
            if (len(expected) < 32 or len(headers.getlist('authorization')) != 1 or
                    not hmac.compare_digest(headers.get('authorization', '').encode(), ('Bearer ' + expected).encode())):
                await JSONResponse({'detail': 'Unauthorized'}, status_code=401)(scope, receive, send)
                return
        await self.app(scope, receive, send)


app.add_middleware(ServiceAuth)


@app.get('/health')
async def health():
    return JSONResponse({'ready': ready, 'active': len(active), 'metrics': metrics,
                         'image_digest': engine.image if engine else None}, status_code=200 if ready else 503)


def job_uuid(value):
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(422, 'Invalid job ID.')


@app.delete('/jobs/{job_id}')
async def cancel_job(job_id: str):
    job_id = job_uuid(job_id)
    # Tombstone also wins a cancellation that races ahead of POST/create.
    with db() as connection:
        connection.execute("INSERT INTO jobs VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET status='cancelled'",
                           (job_id, '', time.time(), 'cancelled'))
    if job_id in active:
        active[job_id][1].set()
    return {'cancelled': True}


@app.post('/jobs')
async def execute(request: Request):
    global ready
    if not ready:
        raise HTTPException(503, 'Sandbox preflight has not passed.')
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 12 * 1024 * 1024:
            raise HTTPException(413, 'Input too large.')
    try:
        payload = json.loads(body)
        if not isinstance(payload, dict) or set(payload) != {'job_id', 'owner', 'code', 'inputs', 'files'}:
            raise Rejected('schema')
        job_id = job_uuid(payload['job_id'])
        owner = payload['owner']
        if not isinstance(owner, str) or not re.fullmatch('[a-f0-9]{64}', owner):
            raise Rejected('owner')
        input_archive(payload['code'], payload['inputs'], payload['files'])
    except (Rejected, ValueError, TypeError, RecursionError):
        raise HTTPException(422, 'Invalid sandbox request.')
    with db() as connection:
        connection.execute('BEGIN IMMEDIATE')
        if connection.execute('SELECT 1 FROM jobs WHERE id=?', (job_id,)).fetchone():
            raise HTTPException(409, 'Job already submitted; execution is never retried.')
        if len(active) >= 2 or any(workspace == owner for workspace, _ in active.values()):
            metrics['rejected'] += 1
            raise HTTPException(429, 'Sandbox busy.')
        connection.execute('INSERT INTO jobs VALUES(?,?,?,?)', (job_id, owner, time.time(), 'running'))
    cancel = asyncio.Event()
    active[job_id] = owner, cancel

    async def disconnect():
        while not cancel.is_set():
            if await request.is_disconnected():
                cancel.set()
                return
            await asyncio.sleep(.1)
    watcher = asyncio.create_task(disconnect())
    try:
        result = await engine.execute(job_id, payload['code'], payload['inputs'], payload['files'], cancel)
        if result['execution_status'] in ('cleanup_failed', 'isolation_check_failed'):
            ready = False
        with db() as connection:
            connection.execute('UPDATE jobs SET status=? WHERE id=?', (result['execution_status'], job_id))
        metrics['executions'] += 1
        status = result['execution_status']
        metrics[status] = metrics.get(status, 0) + 1
        log.info('job=%s duration=%.3f memory=%s category=%s', job_id, result['duration'], result['memory_bytes'], status)
        return result
    finally:
        cancel.set()
        watcher.cancel()
        await asyncio.gather(watcher, return_exceptions=True)
        active.pop(job_id, None)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8091, workers=1, proxy_headers=False, access_log=False)
