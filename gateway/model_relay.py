"""Turn-scoped DeepSeek relay for the single-worker EnzyMind gateway.

The provider key stays in memory. n8n receives a separate random capability,
revoked when the turn ends. Neither capability nor key is stored in SQLite.
"""
from contextlib import suppress
from dataclasses import dataclass, field
import hashlib
import json
import os
import re
import secrets
import time

import httpx
from fastapi import HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

ERRORS = {
    401: 'DeepSeek could not authenticate your key. Choose Forget and enter a valid key.',
    402: 'Your DeepSeek account has insufficient API balance. Check your balance and retry.',
    429: 'Your DeepSeek account reached its rate limit. Wait and retry.',
    502: 'DeepSeek is temporarily unavailable. Please retry.',
}


def validate_key(key):
    if not re.fullmatch(r'[A-Za-z0-9_-]{20,256}', key or ''):
        raise HTTPException(422, 'Enter a valid DeepSeek API key.')
    return key


@dataclass(repr=False)
class Lease:
    key: str
    owner: str
    turn_id: str
    expires: float
    calls: int = 0
    error: str = ''
    clients: set = field(default_factory=set)


class ModelRelay:
    def __init__(self):
        self.leases = {}

    def register(self, key, owner, turn_id):
        validate_key(key)
        token = secrets.token_hex(32)
        self.leases[hashlib.sha256(token.encode()).hexdigest()] = Lease(key, owner, turn_id, time.time()+7200)
        return token

    def get(self, token, store):
        lease = self.leases.get(hashlib.sha256(token.encode()).hexdigest())
        if not lease or not lease.key or lease.expires <= time.time():
            raise HTTPException(401, 'The temporary model session has expired.')
        with store.db() as db:
            valid = db.execute("SELECT 1 FROM turns WHERE owner=? AND id=? AND status='running' AND lease_expires>? AND billing_mode='byok'", (lease.owner, lease.turn_id, time.time())).fetchone()
        if not valid:
            raise HTTPException(401, 'The temporary model session has expired.')
        return lease

    async def revoke(self, token):
        lease = self.leases.pop(hashlib.sha256(token.encode()).hexdigest(), None)
        if lease:
            lease.key = ''
            for client in list(lease.clients):
                with suppress(Exception):
                    await client.aclose()

    async def forward(self, token, payload, store):
        lease = self.get(token, store)
        if not isinstance(payload, dict) or not isinstance(payload.get('messages'), list) or not payload['messages']:
            raise HTTPException(422, 'Invalid model request.')
        allowed = {'messages', 'tools', 'tool_choice', 'stream', 'stream_options', 'temperature', 'max_tokens', 'response_format', 'stop', 'top_p', 'presence_penalty', 'frequency_penalty'}
        payload = {k: v for k, v in payload.items() if k in allowed}
        try:
            payload['max_tokens'] = min(4096, max(1, int(payload.get('max_tokens') or 4096)))
        except (ValueError, TypeError):
            raise HTTPException(422, 'Invalid token limit.') from None
        payload['model'] = os.getenv('ENZYMIND_AGENT_DEEPSEEK_MODEL', 'deepseek-chat')
        # Non-thinking mode matches EasIFA's chat model and tool-call protocol.
        payload['thinking'] = {'type': 'disabled'}
        if lease.calls >= 24:
            raise HTTPException(429, 'This turn reached its model call limit.')
        lease.calls += 1
        client = httpx.AsyncClient(trust_env=False, timeout=httpx.Timeout(150, connect=15))
        lease.clients.add(client)
        async def close():
            lease.clients.discard(client)
            await client.aclose()
        try:
            request = client.build_request('POST', 'https://api.deepseek.com/chat/completions',
                                           json=payload, headers={'Authorization': 'Bearer '+lease.key})
            response = await client.send(request, stream=True)
            if response.status_code != 200:
                code = response.status_code if response.status_code in ERRORS else 502
                lease.error = ERRORS[code]
                await close()
                return JSONResponse({'error': {'message': lease.error, 'type': 'deepseek_error', 'code': code}}, status_code=code)
            if not payload.get('stream'):
                body = await response.aread()
                return JSONResponse(json.loads(body), headers={'Cache-Control': 'no-store'})
        except (httpx.HTTPError, ValueError):
            lease.error = ERRORS[502]
            await close()
            raise HTTPException(502, lease.error) from None
        finally:
            if not payload.get('stream'):
                await close()

        async def chunks():
            try:
                async for chunk in response.aiter_bytes():
                    self.get(token, store)
                    yield chunk
            except (httpx.HTTPError, HTTPException):
                lease.error = ERRORS[502]
                # Never emit a provider exception which might contain headers.
                yield b'data: {"error":{"message":"DeepSeek stream interrupted"}}\n\n'
            finally:
                await close()
        return StreamingResponse(chunks(), media_type='text/event-stream',
                                 headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})


relay = ModelRelay()
