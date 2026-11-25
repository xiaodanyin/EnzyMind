"""Exercise real Gateway routes against the live Runner, using an isolated workspace DB.

Run from the project Python environment as the Gateway owner. It never invokes
n8n/the model or writes the production workspace database.
"""
import asyncio
import json
import os
from pathlib import Path
import secrets
import tempfile
from unittest.mock import patch
from uuid import uuid4

import httpx
from fastapi import FastAPI

from gateway import workspace
from gateway.workspace_store import WorkspaceStore, digest


async def main(config_file=Path('/var/lib/enzymind-python-deploy/gateway.env'), report_file=Path('files/workspace/python-gateway-acceptance.json')):
    config = dict(line.split('=', 1) for line in config_file.read_text().splitlines() if '=' in line)
    config['ENZYMIND_PYTHON_ENABLED'] = 'true'
    # Isolated in-process client only; production trusts the exact n8n peer.
    config['ENZYMIND_PYTHON_AGENT_IPS'] = '127.0.0.1'
    passed = []
    with tempfile.TemporaryDirectory(prefix='enzymind-gateway-acceptance-') as directory, patch.dict(os.environ, config):
        # A production maintenance switch must never be removed/bypassed by tests.
        # Test against an independent, absent switch in the disposable workspace.
        os.environ['ENZYMIND_PYTHON_DISABLE_FILE'] = str(Path(directory) / 'python.disabled')
        workspace._store = WorkspaceStore(Path(directory) / 'workspace.sqlite')
        client_key = secrets.token_hex(32)
        owner = digest(client_key)

        def new_turn():
            session = workspace.store().create_session(owner)
            turn, token = workspace.store().begin(owner, session['id'], str(uuid4()), 'sandbox deployment acceptance', [],
                                                source_ip_hash=digest('127.0.0.1'), billing_mode='byok')
            workspace.store().status(owner, turn['id'], 'running')
            return turn, token

        turn, token = new_turn()
        app = FastAPI()
        app.include_router(workspace.router)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test', timeout=90) as client:
            async def call(code, **extra):
                return await client.post('/api/workspace/tools/python', headers={'X-Enzymind-Turn': token},
                                         json={'code': code, **extra})

            assert (await client.post('/api/workspace/tools/python', json={'code': 'pass'})).status_code == 403
            code = "import pandas as pd\nfrom rdkit import Chem\nfrom rdkit.Chem import Draw\npd.DataFrame({'value':data['values']}).to_csv(output_dir/'values.csv',index=False)\nDraw.MolToFile(Chem.MolFromSmiles('CCO'),str(output_dir/'ethanol.png'))\nresult={'sum':sum(data['values'])}"
            first = await call(code, data={'values': [1, 2, 3]})
            first.raise_for_status()
            record = workspace.store().result(owner, first.json()['id'])
            assert record['payload']['success'], record['payload']['execution_status']
            assert record['payload']['result'] == {'sum': 6}
            repeated = await call(code, data={'values': [1, 2, 3]})
            assert repeated.json()['id'] == record['id'] and repeated.json()['reused']
            with workspace.store().db() as db:
                assert db.execute('SELECT count(*) FROM python_runs').fetchone()[0] == 1
            passed.append('Gateway turn authentication, real pandas/RDKit execution, same-turn record reuse')

            artifacts = record['payload']['files']
            csv = next(file for file in artifacts if file['name'].endswith('.csv'))
            for file in artifacts:
                download = await client.get(file['url'], headers={'X-Enzymind-Client': client_key})
                assert download.status_code == 200 and download.headers['x-content-type-options'] == 'nosniff'
                assert download.headers['content-disposition'].startswith('attachment')
                if file['name'].endswith('.png'):
                    assert download.content.startswith(b'\x89PNG\r\n\x1a\n')
                assert (await client.get(file['url'], headers={'X-Enzymind-Client': secrets.token_hex(32)})).status_code == 404
            passed.append('Private CSV/PNG downloads and cross-workspace denial')

            reference = "import pandas as pd\nresult={'source': results[data['source']]['result']['sum'], 'csv_sum': int(pd.read_csv(input_files[data['file']])['value'].sum())}"
            reused_input = await call(reference, data={'source': record['id'], 'file': csv['id']},
                                      result_ids=[record['id']], file_ids=[csv['id']])
            reused_input.raise_for_status()
            saved = workspace.store().result(owner, reused_input.json()['id'])
            assert saved['payload']['result'] == {'source': 6, 'csv_sum': 6}
            assert len(saved['payload']['input_sources']) == 2
            assert (await call('result=3')).status_code == 200
            assert (await call('result=4')).status_code == 429
            for _ in range(8):
                assert (await call(code, data={'values': [1, 2, 3]})).status_code == 200
            assert (await call(code, data={'values': [1, 2, 3]})).status_code == 429
            workspace.store().status(owner, turn['id'], 'completed')
            passed.append('Saved JSON/file inputs, provenance, 3-execution and 12-tool budgets')

            turn, token = new_turn()
            executing = asyncio.create_task(call('while True: pass'))
            for _ in range(100):
                with workspace.store().db() as db:
                    count = db.execute("SELECT count(*) FROM python_runs WHERE state='running'").fetchone()[0]
                if count:
                    break
                await asyncio.sleep(.1)
            await asyncio.sleep(1)
            stopped = await client.post(f"/api/workspace/turns/{turn['id']}/cancel", headers={'X-Enzymind-Client': client_key})
            assert stopped.status_code == 200
            cancelled = await asyncio.wait_for(executing, 15)
            assert cancelled.json()['data']['execution_status'] == 'cancelled'
            passed.append('Workspace Stop cancels live Runner execution')

    report = {'passed': passed, 'production_workspace_unchanged': True}
    target = report_file
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    target.write_text(json.dumps(report, indent=2) + '\n')
    target.chmod(0o600)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config-file', type=Path, default=Path('/var/lib/enzymind-python-deploy/gateway.env'))
    parser.add_argument('--report-file', type=Path, default=Path('files/workspace/python-gateway-acceptance.json'))
    args = parser.parse_args()
    asyncio.run(main(args.config_file, args.report_file))
