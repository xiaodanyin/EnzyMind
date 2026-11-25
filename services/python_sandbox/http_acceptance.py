"""Real Runner HTTP/lifecycle acceptance under its dedicated account, before enabling Gateway."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4

import httpx

from .engine import Engine, LABEL


def job(code='result=42', owner=None):
    return {'job_id': str(uuid4()), 'owner': owner or hashlib.sha256(os.urandom(32)).hexdigest(),
            'code': code, 'inputs': {'data': {}, 'results': {}, 'files': {}}, 'files': []}


async def wait_health(client, active=None, seconds=120):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            response = await client.get('/health', timeout=3)
            if response.status_code == 200:
                body = response.json()
                if body['ready'] and (active is None or body['active'] == active):
                    return body
        except httpx.HTTPError:
            pass
        await asyncio.sleep(.2)
    raise RuntimeError('Runner health/active-count deadline exceeded.')


async def gateway_under_load():
    # Keep Runner credentials off the Gateway connection.
    async with httpx.AsyncClient(trust_env=False, timeout=5) as web:
        try:
            response = await web.get('http://127.0.0.1:8080/health')
        except httpx.ConnectError:
            return False  # Fresh host: verified later via in-process Gateway routes.
        assert response.status_code == 200
        return True


async def main():
    if os.geteuid() == 0 or os.environ['PYTHON_SANDBOX_SOCKET'] != f'/run/user/{os.geteuid()}/docker.sock':
        raise RuntimeError('Run only under the dedicated Rootless account.')
    engine = Engine(os.environ['PYTHON_SANDBOX_SOCKET'], os.environ['PYTHON_SANDBOX_IMAGE'])
    passed = []
    headers = {'Authorization': 'Bearer ' + os.environ['PYTHON_SANDBOX_TOKEN']}
    async with httpx.AsyncClient(base_url='http://127.0.0.1:8091', headers=headers,
                                trust_env=False, timeout=75) as client:
        try:
            before = await wait_health(client, 0)
            assert (await client.get('/health', headers={'Authorization': ''})).status_code == 401
            assert (await client.post('/jobs', json={**job(), 'network': 'host'})).status_code == 422
            first = job("print('sandbox-ok')\n(output_dir/'answer.csv').write_text('value\\n42\\n')\nresult={'answer':42}")
            response = await client.post('/jobs', json=first)
            response.raise_for_status()
            result = response.json()
            assert result['success'] and result['result'] == {'answer': 42}, result['execution_status']
            assert len(result['files']) == 1 and result['stdout'].strip() == 'sandbox-ok'
            assert (await client.post('/jobs', json=first)).status_code == 409
            after = await wait_health(client, 0)
            assert after['metrics']['executions'] == before['metrics']['executions'] + 1
            passed.append('HTTP authentication, allowlist, CSV and durable duplicate rejection')

            one, two = job('while True: pass'), job('while True: pass')
            running = asyncio.create_task(client.post('/jobs', json=one))
            await wait_health(client, 1, 15)
            assert (await client.post('/jobs', json=job(owner=one['owner']))).status_code == 429
            second = asyncio.create_task(client.post('/jobs', json=two))
            await wait_health(client, 2, 15)
            assert (await client.post('/jobs', json=job())).status_code == 429
            # Fresh installations may precede Gateway startup. Its real routes
            # are always tested separately by gateway_acceptance during integration.
            gateway_checked = await gateway_under_load()
            for item in (one, two):
                (await client.delete('/jobs/' + item['job_id'])).raise_for_status()
            completed = await asyncio.gather(running, second)
            assert all(r.json()['execution_status'] == 'cancelled' for r in completed)
            await wait_health(client, 0, 15)
            passed.append('2 global/1 workspace concurrency and cancellation')
            if gateway_checked:
                passed.append('Running Gateway responsive under CPU load')

            orphan = job('while True: pass')
            async with httpx.AsyncClient(base_url='http://127.0.0.1:8091', headers=headers,
                                        trust_env=False, timeout=75) as disconnected:
                inflight = asyncio.create_task(disconnected.post('/jobs', json=orphan))
                await wait_health(client, 1, 15)
                inflight.cancel()
                await asyncio.gather(inflight, return_exceptions=True)
            await wait_health(client, 0, 15)
            assert (await client.post('/jobs', json=orphan)).status_code == 409
            passed.append('HTTP disconnect kills job; repeating it cannot re-execute code')

            early = job()
            assert (await client.delete('/jobs/' + early['job_id'])).status_code == 200
            assert (await client.post('/jobs', json=early)).status_code == 409
            passed.append('cancel-before-submit tombstone')

            interrupted = job('while True: pass')
            inflight = asyncio.create_task(client.post('/jobs', json=interrupted))
            await wait_health(client, 1, 15)
            # --kill-who is also accepted by newer systemd and works on Ubuntu
            # 22.04 (systemd 249), which predates the --kill-whom spelling.
            subprocess.run(['systemctl', '--user', 'kill', '--kill-who=main', '--signal=KILL',
                            'enzymind-python-runner.service'], check=True)
            await asyncio.gather(inflight, return_exceptions=True)
            await wait_health(client, 0)
            assert (await client.post('/jobs', json=interrupted)).status_code == 409
            assert (await client.post('/jobs', json=first)).status_code == 409
            passed.append('Runner crash/restart cleans orphan and preserves durable no-replay ledger')

            filters = {'filters': json.dumps({'label': [LABEL + '=v1']})}
            assert not await engine.api('GET', '/containers/json', params={'all': 'true', **filters})
            assert not (await engine.api('GET', '/volumes', params=filters)).get('Volumes')
            report = {'passed': passed, 'image_digest': engine.image, 'ready': True,
                      'orphan_containers': 0, 'orphan_volumes': 0,
                      'gateway_checked_under_load': gateway_checked}
            (Path(os.environ['PYTHON_SANDBOX_STATE']) / 'http-acceptance.json').write_text(json.dumps(report, indent=2) + '\n')
            print(json.dumps(report, indent=2))
        finally:
            await engine.client.aclose()


if __name__ == '__main__':
    asyncio.run(main())
