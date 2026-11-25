"""Fixed Docker Engine API policy. No Docker CLI, shell, host bind or user options."""
import asyncio
import base64
from dataclasses import dataclass
import json
import os
import re
import time
from uuid import uuid4

import httpx

from .protocol import ARCHIVE_BYTES, OUTPUT_BYTES, Rejected, input_archive, output_archive

LABEL = 'org.enzymind.python-sandbox'


@dataclass(frozen=True)
class Limits:
    seconds: float = 60
    memory: int = 1024 ** 3
    cpus: int = 1_000_000_000
    pids: int = 64
    workspace: int = 128 * 1024 ** 2


def volume_config(job_id, limits):
    # A daemon-managed tmpfs volume is visible to the archive API. Container
    # HostConfig.Tmpfs mounts have separate filesystem views in that API.
    return {'Name': 'enzymind-python-' + job_id, 'Driver': 'local',
            'DriverOpts': {'type': 'tmpfs', 'device': 'tmpfs',
                           'o': f'rw,noexec,nosuid,nodev,size={limits.workspace},uid=10001,gid=10001,mode=0700'},
            'Labels': {LABEL: 'v1', LABEL + '.job': job_id,
                       LABEL + '.expires': str(time.time() + limits.seconds + 30)}}


def container_config(image, job_id, limits):
    return {
        'Image': image, 'User': '10001:10001', 'WorkingDir': '/work',
        'Entrypoint': ['/usr/local/bin/python', '-I', '-B', '-c'],
        'Cmd': ['import time; time.sleep(86400)'],
        'Env': ['PATH=/usr/local/bin:/usr/bin:/bin', 'HOME=/work', 'TMPDIR=/work',
                'MPLCONFIGDIR=/work/.mpl', 'MPLBACKEND=Agg', 'OPENBLAS_NUM_THREADS=1',
                'OMP_NUM_THREADS=1', 'MKL_NUM_THREADS=1', 'NUMEXPR_NUM_THREADS=1'],
        'NetworkDisabled': True, 'OpenStdin': False, 'Tty': False,
        'Labels': {LABEL: 'v1', LABEL + '.job': job_id,
                   LABEL + '.expires': str(time.time() + limits.seconds + 30)},
        'HostConfig': {
            'ReadonlyRootfs': True, 'NetworkMode': 'none', 'CapDrop': ['ALL'],
            'SecurityOpt': ['no-new-privileges:true'], 'Memory': limits.memory,
            'MemorySwap': limits.memory, 'NanoCpus': limits.cpus, 'PidsLimit': limits.pids,
            'Mounts': [{'Type': 'volume', 'Source': 'enzymind-python-' + job_id, 'Target': '/work',
                        'ReadOnly': False, 'VolumeOptions': {'NoCopy': True}}],
            'ShmSize': 64 * 1024, 'IpcMode': 'none', 'CgroupnsMode': 'private',
            'LogConfig': {'Type': 'none'}, 'RestartPolicy': {'Name': 'no'},
            'Ulimits': [{'Name': 'nofile', 'Soft': 256, 'Hard': 256},
                        {'Name': 'core', 'Soft': 0, 'Hard': 0}],
        },
    }


class Engine:
    def __init__(self, socket, image, limits=None):
        if not re.fullmatch(r'(?:[^\s]+@)?sha256:[a-f0-9]{64}', image):
            raise ValueError('PYTHON_SANDBOX_IMAGE must be an immutable SHA256 image ID or repository digest.')
        self.image, self.limits = image, limits or Limits()
        self.client = httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds=socket, retries=0),
            base_url='http://docker/v1.45', timeout=httpx.Timeout(10, read=70), trust_env=False)
        self.versions = {}

    async def api(self, method, path, **kwargs):
        response = await self.client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json() if response.content else None

    async def remove(self, name):
        response = await self.client.delete('/containers/' + name, params={'force': 'true', 'v': 'true'})
        if response.status_code != 404:
            response.raise_for_status()

    async def remove_volume(self, name):
        response = await self.client.delete('/volumes/' + name)
        if response.status_code != 404:
            response.raise_for_status()

    async def reap(self, all_jobs=False):
        containers = await self.api('GET', '/containers/json', params={
            'all': 'true', 'filters': json.dumps({'label': [LABEL + '=v1']})})
        count = 0
        for container in containers:
            expires = container.get('Labels', {}).get(LABEL + '.expires', '0')
            try:
                stale = float(expires) < time.time()
            except ValueError:
                stale = True
            if all_jobs or stale:
                await self.remove(container['Id'])
                count += 1
        volumes = await self.api('GET', '/volumes', params={'filters': json.dumps({'label': [LABEL + '=v1']})})
        for volume in volumes.get('Volumes') or []:
            try:
                stale = float(volume.get('Labels', {}).get(LABEL + '.expires', '0')) < time.time()
            except ValueError:
                stale = True
            if all_jobs or stale:
                await self.remove_volume(volume['Name'])
                count += 1
        return count

    async def exec_stream(self, container, command, stdout, stderr):
        execution = await self.api('POST', f'/containers/{container}/exec', json={
            'AttachStdout': True, 'AttachStderr': True, 'Tty': False,
            'User': '10001:10001', 'Cmd': command, 'WorkingDir': '/work'})
        buffer = bytearray()
        async with self.client.stream('POST', '/exec/' + execution['Id'] + '/start',
                json={'Detach': False, 'Tty': False}) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes(chunk_size=4096):
                buffer.extend(chunk)
                while len(buffer) >= 8:
                    stream, size = buffer[0], int.from_bytes(buffer[4:8], 'big')
                    if stream not in (1, 2) or buffer[1:4] != b'\0\0\0':
                        raise Rejected('invalid_docker_stream')
                    remaining = OUTPUT_BYTES - len(stdout) - len(stderr)
                    if size > remaining:
                        target = stdout if stream == 1 else stderr
                        target.extend(buffer[8:8 + remaining])
                        raise Rejected('output_limit')
                    if len(buffer) < size + 8:
                        break
                    (stdout if stream == 1 else stderr).extend(buffer[8:8 + size])
                    del buffer[:size + 8]
        if buffer:
            raise Rejected('incomplete_docker_stream')
        info = await self.api('GET', '/exec/' + execution['Id'] + '/json')
        if info['Running']:
            raise Rejected('incomplete_execution')
        return info['ExitCode']

    async def execute(self, job_id, code, inputs, files, cancel, *, limits=None):
        limits = limits or self.limits
        name, started = 'enzymind-python-' + job_id, time.monotonic()
        stdout, stderr, value, artifacts = bytearray(), bytearray(), None, []
        status, exit_code, cleanup_failed = 'completed', None, False
        memory_peak = None

        async def work():
            nonlocal value, artifacts, exit_code, memory_peak
            archive = input_archive(code, inputs, files)
            # Explicit creation prevents Docker from silently substituting a
            # disk-backed volume. Inspect the returned policy before using it.
            expected = volume_config(job_id, limits)
            volume = await self.api('POST', '/volumes/create', json=expected)
            if (not isinstance(volume, dict) or volume.get('Driver') != expected['Driver']
                    or volume.get('Options') != expected['DriverOpts']
                    or (volume.get('Labels') or {}).get(LABEL + '.job') != job_id):
                raise Rejected('isolation_check_failed')
            # Name is known before create: a lost create response can still be cleaned up.
            await self.api('POST', '/containers/create', params={'name': name},
                           json=container_config(self.image, job_id, limits))
            await self.api('POST', '/containers/' + name + '/start')
            # A daemon can restart after startup preflight. Verify this container's
            # effective cgroups before copying or executing any user code.
            check = f'''import os
from pathlib import Path
c=Path('/sys/fs/cgroup')
assert int((c/'memory.max').read_text()) == {limits.memory}
assert int((c/'memory.swap.max').read_text()) == 0
assert int((c/'pids.max').read_text()) == {limits.pids}
q,p=map(int,(c/'cpu.max').read_text().split()); assert q/p == {limits.cpus / 1e9}
s=Path('/proc/self/status').read_text()
assert 'NoNewPrivs:\\t1' in s and 'Seccomp:\\t2' in s and 'CapEff:\\t0000000000000000' in s
assert os.getuid()==10001
mount=next(line.split() for line in Path('/proc/self/mountinfo').read_text().splitlines() if line.split()[4]=='/')
assert 'ro' in mount[5].split(',')
assert set(os.listdir('/sys/class/net')) == {{'lo'}}
work=next(line.split() for line in Path('/proc/self/mountinfo').read_text().splitlines() if line.split()[4]=='/work')
assert work[work.index('-')+1]=='tmpfs'
assert {{'noexec','nosuid','nodev'}} <= set(work[5].split(','))
assert os.stat('/work').st_uid==10001
v=os.statvfs('/work'); assert v.f_blocks*v.f_frsize <= {limits.workspace}
'''
            if await self.exec_stream(name, ['/usr/local/bin/python', '-I', '-B', '-c', check], bytearray(), bytearray()):
                raise Rejected('isolation_check_failed')
            await self.api('PUT', '/containers/' + name + '/archive', params={'path': '/work', 'copyUIDGID': 'true'},
                           content=archive, headers={'Content-Type': 'application/x-tar'})
            exit_code = await self.exec_stream(name,
                ['/usr/local/bin/python', '-I', '-B', '-u', '/opt/bootstrap.py'], stdout, stderr)
            if exit_code:
                raise Rejected('oom' if exit_code == 137 else 'execution_error')
            await self.api('POST', '/containers/' + name + '/pause')
            info = await self.api('GET', '/containers/' + name + '/json')
            if not info['State']['Paused']:
                raise Rejected('freeze_failed')
            stats = await self.api('GET', '/containers/' + name + '/stats', params={'stream': 'false', 'one-shot': 'true'})
            memory_peak = stats.get('memory_stats', {}).get('max_usage') or stats.get('memory_stats', {}).get('usage')
            snapshot = bytearray()
            async with self.client.stream('GET', '/containers/' + name + '/archive', params={'path': '/work'}) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    snapshot.extend(chunk)
                    if len(snapshot) > ARCHIVE_BYTES:
                        raise Rejected('snapshot_size')
            value, artifacts = output_archive(snapshot)

        work_task = asyncio.create_task(work())
        cancel_task = asyncio.create_task(cancel.wait())
        try:
            done, _ = await asyncio.wait({work_task, cancel_task}, timeout=limits.seconds,
                                         return_when=asyncio.FIRST_COMPLETED)
            if cancel_task in done:
                status = 'cancelled'
            elif work_task in done:
                await work_task
            else:
                status = 'timeout'
        except Rejected as exc:
            status = str(exc)
        except (httpx.HTTPError, KeyError, ValueError):
            status = 'runner_transport_error'
        except asyncio.CancelledError:
            status = 'cancelled'
            raise
        finally:
            work_task.cancel()
            cancel_task.cancel()
            await asyncio.gather(work_task, cancel_task, return_exceptions=True)
            try:
                await asyncio.shield(self.remove(name))
            except (httpx.HTTPError, asyncio.CancelledError):
                cleanup_failed = True
            try:
                await asyncio.shield(self.remove_volume(name))
            except (httpx.HTTPError, asyncio.CancelledError):
                cleanup_failed = True
        # Replacement of invalid UTF-8 can expand bytes; keep the wire limit too.
        out = stdout.decode('utf-8', 'replace').encode()[:OUTPUT_BYTES].decode('utf-8', 'ignore')
        err = stderr.decode('utf-8', 'replace').encode()[:OUTPUT_BYTES - len(out.encode())].decode('utf-8', 'ignore')
        return {'success': status == 'completed' and not cleanup_failed,
                'execution_status': 'cleanup_failed' if cleanup_failed else status,
                'error': None if status == 'completed' and not cleanup_failed else ('cleanup_failed' if cleanup_failed else status),
                'stdout': out, 'stderr': err,
                'result': value, 'files': artifacts, 'exit_code': exit_code,
                'duration': time.monotonic() - started, 'memory_bytes': memory_peak,
                'image_digest': self.image, 'versions': self.versions}

    async def preflight(self):
        info = await self.api('GET', '/info')
        security = ' '.join(info.get('SecurityOptions', []))
        if ('rootless' not in security or 'name=seccomp,profile=builtin' not in info.get('SecurityOptions', []) or
                info.get('CgroupVersion') != '2' or info.get('CgroupDriver') != 'systemd'):
            raise RuntimeError('Rootless Docker, default seccomp and cgroup v2/systemd are required.')
        containers = await self.api('GET', '/containers/json', params={'all': 'true'})
        if any(c.get('Labels', {}).get(LABEL) != 'v1' for c in containers):
            raise RuntimeError('This Docker daemon must be dedicated to the Python sandbox.')
        volumes = await self.api('GET', '/volumes')
        if any((v.get('Labels') or {}).get(LABEL) != 'v1' for v in volumes.get('Volumes') or []):
            raise RuntimeError('This Docker daemon must not contain foreign volumes.')
        image = await self.api('GET', '/images/' + self.image + '/json')
        if image['Config'].get('Volumes'):
            raise RuntimeError('Image-declared volumes are prohibited.')
        allowed_env = {'PATH', 'LANG', 'GPG_KEY', 'PYTHON_VERSION', 'PYTHON_SHA256'}
        if any(v.split('=', 1)[0] not in allowed_env for v in image['Config'].get('Env', [])):
            raise RuntimeError('Unexpected image environment.')
        # Resolve repository digest to local immutable image ID before every create.
        self.image = image['Id']
        from .selftest import resource_probe
        result = await self.execute(str(uuid4()), resource_probe(self.limits),
                                    {'data': {}, 'results': {}, 'files': {}}, [], asyncio.Event())
        if not result['success'] or not isinstance(result['result'], dict):
            raise RuntimeError('Actual resource/isolation/library probe failed: ' + result['execution_status'])
        self.versions = result['result']['versions']
        self.versions['python'] = result['result']['python']
        # Exercise out-of-process timeout and output kill paths with fresh containers.
        for code, seconds, expected in [('while True: pass', .5, 'timeout'),
                ('import os\nwhile True: os.write(1, b"x"*4096)', 10, 'output_limit'),
                ('x=[]\nwhile True: x.append(bytearray(16*1024*1024))', 20, 'oom')]:
            probe_limits = Limits(seconds=seconds, memory=self.limits.memory,
                cpus=self.limits.cpus, pids=self.limits.pids, workspace=self.limits.workspace)
            tested = await self.execute(str(uuid4()), code, {'data': {}, 'results': {}, 'files': {}},
                                        [], asyncio.Event(), limits=probe_limits)
            if tested['execution_status'] != expected:
                raise RuntimeError('Actual resource enforcement failed: ' + expected)
