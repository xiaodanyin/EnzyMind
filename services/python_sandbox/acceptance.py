"""Run the real Docker acceptance suite under the dedicated account, with Runner stopped.

Never run against the production daemon. Only this module's disposable labelled
containers are created/removed. This is deliberately separate from offline tests.
"""
import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

from .engine import Engine, Limits, LABEL, volume_config


async def main():
    socket = f'/run/user/{os.geteuid()}/docker.sock'
    if os.geteuid() == 0 or os.environ['PYTHON_SANDBOX_SOCKET'] != socket:
        raise RuntimeError('Use the dedicated account and its Rootless socket.')
    engine = Engine(socket, os.environ['PYTHON_SANDBOX_IMAGE'])
    report = []
    inputs = {'data': {'sequence': '>one\nMKWVTF\n'}, 'results': {'source': {'length': 6}}, 'files': {}}
    try:
        await engine.reap(all_jobs=True)
        # Includes actual cgroups, fork exhaustion, disk fill, CPU throttling,
        # OOM, timeout, no-network probes, BioPython/RDKit/PNG and CSV.
        await engine.preflight()
        report.append('startup resource, isolation and scientific-library probes')
        cases = [
            ('saved-input', "assert results['source']['length'] == 6\nresult={'length':6}", 'completed'),
            ('previous-task-file', "from pathlib import Path\nassert not Path('/work/secret.txt').exists()\nPath('/work/secret.txt').write_text('private')", 'completed'),
            ('fresh-filesystem', "from pathlib import Path\nassert not Path('/work/secret.txt').exists()", 'completed'),
            ('symlink', "(output_dir/'link.txt').symlink_to('/etc/passwd')", 'unsafe_archive'),
            ('hardlink', "import os\nos.link('/work/code.py', output_dir/'link.txt')", 'unsafe_archive'),
            ('fifo', "import os\nos.mkfifo(output_dir/'pipe.txt')", 'unsafe_archive'),
            ('oversize-file', "(output_dir/'big.txt').write_bytes(b'x'*(2*1024*1024+1))", 'output_file'),
            ('too-many-files', "[(output_dir/f'{i}.txt').write_text('x') for i in range(11)]", 'file_count'),
            ('total-size', "[(output_dir/f'{i}.txt').write_bytes(b'x'*(2*1024*1024)) for i in range(3)]", 'file_size'),
            ('credentials', "import os\nassert not any(any(x in k.upper() for x in ['TOKEN','SECRET','API_KEY','PASSWORD']) for k in os.environ)", 'completed'),
        ]
        for name, code, status in cases:
            result = await engine.execute(str(uuid4()), code, inputs, [], asyncio.Event())
            if result['execution_status'] != status:
                raise RuntimeError(name + ': ' + result['execution_status'])
            report.append(name)
        injection = "'; __import__('os').system('id'); $(id) <script>alert(1)</script>"
        result = await engine.execute(str(uuid4()), 'result = data["text"]',
                                      {'data': {'text': injection}, 'results': {}, 'files': {}}, [], asyncio.Event())
        assert result['success'] and result['result'] == injection
        report.append('command and HTML strings in data remain inert')
        cancel = asyncio.Event()
        task = asyncio.create_task(engine.execute(str(uuid4()), 'while True: pass', inputs, [], cancel))
        await asyncio.sleep(2)
        cancel.set()
        assert (await task)['execution_status'] == 'cancelled'
        report.append('cancel kills whole container')
        # Simulate a lost process after container creation; startup and timer cleanup.
        from .engine import container_config
        job_id = str(uuid4())
        config = container_config(engine.image, job_id, Limits())
        config['Labels'][LABEL+'.expires'] = '1'
        volume = volume_config(job_id, Limits())
        volume['Labels'][LABEL+'.expires'] = '1'
        await engine.api('POST', '/volumes/create', json=volume)
        await engine.api('POST', '/containers/create', params={'name':'enzymind-python-'+job_id}, json=config)
        await engine.reap()  # The independent timer may win this race.
        report.append('independent orphan reclamation')
        containers = await engine.api('GET', '/containers/json', params={'all':'true', 'filters':json.dumps({'label':[LABEL+'=v1']})})
        assert not containers, 'Containers remained after acceptance tests.'
        volumes = await engine.api('GET', '/volumes', params={'filters': json.dumps({'label': [LABEL+'=v1']})})
        assert not volumes.get('Volumes'), 'Tmpfs volumes remained after acceptance tests.'
        result = {'passed':report, 'image_digest':engine.image, 'versions':engine.versions}
        target = Path(os.environ['PYTHON_SANDBOX_STATE']) / 'acceptance.json'
        target.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2))
    finally:
        await engine.client.aclose()


if __name__ == '__main__':
    asyncio.run(main())
