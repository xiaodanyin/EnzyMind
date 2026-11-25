"""Authenticated, loopback-only sandbox debugging; never executes code on the host."""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import stat
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from .protocol import CODE_BYTES, INPUT_BYTES, Rejected, input_archive, strict_json, validate_files


def local_config(env_file):
    config = dict(os.environ)
    if env_file is not None:
        info = env_file.stat()
        if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError('The configuration must belong to you and have mode 0600.')
        for line in env_file.read_text().splitlines():
            key, sep, value = line.partition('=')
            if sep and key.strip() in {'PYTHON_SANDBOX_TOKEN', 'ENZYMIND_PYTHON_RUNNER_URL'}:
                config[key.strip()] = value.strip().strip('\"\'')
    url = config.get('ENZYMIND_PYTHON_RUNNER_URL', 'http://127.0.0.1:8091')
    parsed = urlsplit(url)
    if (parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', '::1'} or
            parsed.username is not None or parsed.password is not None or parsed.query or
            parsed.fragment or parsed.path not in {'', '/'}):
        raise ValueError('Debugging requires a literal loopback HTTP Runner URL.')
    token = config.get('PYTHON_SANDBOX_TOKEN', '')
    if len(token) < 32:
        raise ValueError('Configure the local Runner service token first.')
    return url.rstrip('/'), token


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('code_file', type=Path)
    parser.add_argument('--data-file', type=Path, help='Optional JSON object exposed as data')
    parser.add_argument('--env-file', type=Path, help='Private Runner/Gateway configuration; otherwise use environment')
    parser.add_argument('--output-dir', type=Path, help='New private directory; existing directories are never overwritten')
    args = parser.parse_args()
    url, token = local_config(args.env_file)
    if args.code_file.stat().st_size > CODE_BYTES:
        raise ValueError('Code exceeds 64 KiB.')
    code = args.code_file.read_text(encoding='utf-8')
    data = {}
    if args.data_file:
        if args.data_file.stat().st_size > INPUT_BYTES:
            raise ValueError('Data exceeds 6 MiB.')
        data = strict_json(args.data_file.read_bytes())
        if not isinstance(data, dict):
            raise ValueError('Data must be a JSON object.')
    inputs = {'data': data, 'results': {}, 'files': {}}
    input_archive(code, inputs, [])  # Same bounds and formats as production.
    job = str(uuid4())
    output = args.output_dir or Path('files/workspace/python-debug') / job
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    artifacts = output / 'artifacts'
    artifacts.mkdir(mode=0o700)
    payload = {'job_id': job, 'owner': hashlib.sha256(f'local-debug:{os.geteuid()}'.encode()).hexdigest(),
               'code': code, 'inputs': inputs, 'files': []}
    async with httpx.AsyncClient(timeout=httpx.Timeout(85, connect=3), trust_env=False,
                                 follow_redirects=False, headers={'Authorization': 'Bearer ' + token}) as client:
        try:
            raw = bytearray()
            async with client.stream('POST', url + '/jobs', json=payload) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    raw.extend(chunk)
                    if len(raw) > 9 * 1024 ** 2:
                        raise Rejected('Runner response exceeds the size limit.')
        except BaseException:
            # Cancel this exact job, including races before creation. Never retry POST.
            try:
                await client.delete(url + '/jobs/' + job, timeout=5)
            except Exception:
                pass
            raise
    result = strict_json(raw)
    files = validate_files(result.get('files', []))
    for name, _, content in files:
        with (artifacts / name).open('xb') as target:
            os.fchmod(target.fileno(), 0o600)
            target.write(content)
    result['files'] = [{'name': name, 'mime': mime, 'size': len(content)} for name, mime, content in files]
    result['job_id'] = job
    with (output / 'execution.json').open('x') as target:
        os.fchmod(target.fileno(), 0o600)
        json.dump(result, target, ensure_ascii=False, indent=2)
    print(json.dumps({'job_id': job, 'status': result.get('execution_status'),
                      'output_dir': str(output.resolve()), 'files': len(files)}))
    return 0 if result.get('success') else 1


if __name__ == '__main__':
    try:
        raise SystemExit(asyncio.run(main()))
    except (ValueError, OSError, httpx.HTTPError) as exc:
        # Service credentials, request headers and scientific data stay out of errors.
        raise SystemExit(f'Local sandbox debug failed: {type(exc).__name__}. Check local configuration and Runner health; the job was not retried.') from None
