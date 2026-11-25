"""Install this workflow separately, optionally reusing an existing model binding.

N8N_API_KEY is read from the environment or a hidden prompt, never printed or stored.
Only an explicitly supplied target with the expected name may be updated.
"""
import argparse
import copy
import getpass
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from build_workflow import build


def workflow_body(workflow):
    allowed = {'executionOrder', 'executionTimeout', 'saveDataSuccessExecution', 'saveDataErrorExecution',
               'saveManualExecutions', 'saveExecutionProgress', 'timezone', 'errorWorkflow'}
    return {**{k: workflow[k] for k in ('name', 'nodes', 'connections')},
            'settings': {k: v for k, v in workflow.get('settings', {}).items() if k in allowed}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default=os.getenv('N8N_URL', 'http://localhost:5678'))
    parser.add_argument('--model-workflow', required=True, help='Existing workflow to read a model binding from; never modified')
    parser.add_argument('--model-node', help='Required when the source contains several model nodes')
    parser.add_argument('--target', help='Explicit workspace workflow ID to update; omit to create a new workflow')
    parser.add_argument('--gateway-url', default='http://host.docker.internal:8080')
    parser.add_argument('--activate', action='store_true', help='Activate the installed workflow')
    parser.add_argument('--relay-credential-id', help='Existing EnzyMind relay credential; otherwise reuse target binding or create an expression-only credential')
    parser.add_argument('--backup-dir', default='files/n8n-deployment', help='Private rollback files; never commit this directory')
    args = parser.parse_args()
    key = os.getenv('N8N_API_KEY') or getpass.getpass('n8n management API key (not saved): ')
    for value in (args.url, args.gateway_url):
        parsed = urlparse(value)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.username or parsed.password:
            parser.error('Use an HTTP(S) service URL without embedded credentials.')

    def api(method, path, body=None):
        request = Request(args.url.rstrip('/') + '/api/v1' + path,
                          data=json.dumps(body).encode() if body is not None else None,
                          headers={'X-N8N-API-KEY': key, 'Content-Type': 'application/json'}, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            raise RuntimeError(f'n8n {method} {path} returned HTTP {exc.code}; check permissions and workflow state.') from None

    source = api('GET', '/workflows/' + quote(args.model_workflow, safe=''))
    candidates = [n for n in source['nodes'] if '.lmChat' in n['type'] and
                  (not args.model_node or n['name'] == args.model_node)]
    if len(candidates) != 1:
        parser.error('Specify --model-node with the exact name of one existing language model node.')
    source_model = candidates[0]
    model_name = source_model.get('parameters', {}).get('model', '')
    if isinstance(model_name, dict):
        model_name = model_name.get('value', '')
    compatible_anthropic = (
        source_model['type'] == '@n8n/n8n-nodes-langchain.lmChatAnthropic'
        and isinstance(model_name, str) and model_name.startswith('deepseek-')
    )
    if source_model['type'] != '@n8n/n8n-nodes-langchain.lmChatDeepSeek' and not compatible_anthropic:
        parser.error('Use an existing DeepSeek node or an Anthropic-compatible node explicitly configured for a deepseek-* model.')
    workflow = build()
    model = next(n for n in workflow['nodes'] if n['name'] == 'Research language model')
    for field in ('type', 'typeVersion', 'parameters', 'credentials'):
        if field in candidates[0]:
            model[field] = copy.deepcopy(candidates[0][field])
    for node in workflow['nodes']:
        if node['name'] == 'Report memory progress':
            node['parameters']['url'] = args.gateway_url.rstrip('/') + '/api/workspace/memory-progress'
        if node['type'] == 'n8n-nodes-base.httpRequestTool':
            tool = node['parameters']['url'].split('/api/workspace/tools/')[1].split("'")[0]
            node['parameters']['url'] = args.gateway_url.rstrip('/') + '/api/workspace/tools/' + tool
    current = None
    directory = Path(args.backup_dir)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if args.target:
        path = '/workflows/' + quote(args.target, safe='')
        current = api('GET', path)
        if current['name'] != workflow['name']:
            parser.error('The target name differs from this workspace. Refusing to replace another workflow.')
        backup = directory / ('workflow-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.json')
        with os.fdopen(os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as output:
            json.dump(current, output)
    relay_id = args.relay_credential_id
    if not relay_id and current:
        old_relay = next((n for n in current['nodes'] if n['name'] == 'User DeepSeek relay'), {})
        relay_id = old_relay.get('credentials', {}).get('openAiApi', {}).get('id')
    if not relay_id:
        credential = api('POST', '/credentials', {
            'name': 'EnzyMind request-only DeepSeek relay', 'type': 'openAiApi',
            'data': {'allowedDomains': 'all', 'header': False, 'organizationId': '',
                     'apiKey': "={{ $('Workspace Webhook').first(0,0).json.body.model_relay_token || 'inactive-request-only-relay' }}",
                     'url': args.gateway_url.rstrip('/') + '/api/workspace/model'}})
        relay_id = credential['id']
    next(n for n in workflow['nodes'] if n['name'] == 'User DeepSeek relay')['credentials'] = {
        'openAiApi': {'id': relay_id, 'name': 'EnzyMind request-only DeepSeek relay'}}
    payload = workflow_body(workflow)
    was_active = bool(current and current.get('active'))
    try:
        if was_active:
            api('POST', path + '/deactivate', {})
        deployed = api('PUT', path, payload) if current else api('POST', '/workflows', payload)
        if was_active or args.activate:
            deployed = api('POST', '/workflows/' + quote(deployed['id'], safe='') + '/activate', {})
    except Exception:
        if current:
            api('PUT', path, workflow_body(current))
            if was_active:
                api('POST', path + '/activate', {})
        raise
    (directory / 'deployment.json').write_text(json.dumps({'workflow_id': deployed['id'], 'relay_credential_id': relay_id}))
    print(json.dumps({'id': deployed['id'], 'name': deployed['name'], 'active': deployed.get('active', False)}))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
