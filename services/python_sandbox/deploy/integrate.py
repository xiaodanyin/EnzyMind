"""Gateway-owner integration used by the existing scripts/deploy.sh entry point."""
import argparse
from datetime import datetime, timezone
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import tempfile
import time
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[3]
HANDOFF = Path('/var/lib/enzymind-python-deploy')
GUARD = 'EnzyMind Python deployment maintenance\n'
MANAGED = {'ENZYMIND_PYTHON_ENABLED', 'ENZYMIND_PYTHON_RUNNER_URL',
           'ENZYMIND_PYTHON_AGENT_IPS', 'PYTHON_SANDBOX_TOKEN'}


class DeploymentError(Exception):
    pass


def private_text(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise DeploymentError('Configuration must be a regular file owned by the Gateway user, with mode 0600.')
    return path.read_text()


def settings(text):
    result = {}
    for line in text.splitlines():
        match = re.match(r'^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$', line)
        if match:
            parts = shlex.split(match[2], comments=True)
            if len(parts) <= 1:
                result[match[1]] = parts[0] if parts else ''
    return result


def atomic_private(path, text):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise DeploymentError('Refusing a symlink configuration destination.')
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def merge_settings(text, values):
    kept = []
    for line in text.splitlines(keepends=True):
        match = re.match(r'^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=', line)
        if not match or match[1] not in values:
            kept.append(line)
    return ''.join(kept).rstrip('\n') + '\n' + ''.join(
        key + '=' + shlex.quote(value) + '\n' for key, value in values.items())


def exact_ips(value):
    try:
        values = [ipaddress.ip_address(item.strip()) for item in value.split(',')]
    except ValueError:
        raise DeploymentError('Agent sources must be exact IP addresses, never CIDRs, names or wildcards.') from None
    if not values or any(ip.is_unspecified or ip.is_multicast for ip in values):
        raise DeploymentError('An explicit unicast Agent IP is required.')
    return ','.join(dict.fromkeys(str(ip) for ip in values))


def discover_agent_ip(container, gateway_url):
    parsed = urlsplit(gateway_url)
    if parsed.scheme != 'http' or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
        raise DeploymentError('Use the n8n tool connection base URL, without credentials, path or query.')
    # UDP connect selects the same local route without sending a datagram or
    # requiring Gateway to be running. No workflow, credential or model is read.
    code = """const dns=require('dns'),dgram=require('dgram');
const timer=setTimeout(()=>process.exit(2),5000);
dns.lookup(process.argv[1],(error,address,family)=>{
 if(error)process.exit(2);
 const s=dgram.createSocket(family===6?'udp6':'udp4');
 s.on('error',()=>process.exit(2));
 s.connect(Number(process.argv[2]),address,()=>{
  console.log(s.address().address);s.close();clearTimeout(timer);
 });
});"""
    result = subprocess.run(['docker', 'exec', container, 'node', '-e', code,
                             parsed.hostname, str(parsed.port or 80)], capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise DeploymentError('Cannot resolve the n8n connection source. Start n8n or provide --agent-ip with its verified exact address.')
    return exact_ips(result.stdout.strip())


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def health(config):
    url = config.get('ENZYMIND_PYTHON_RUNNER_URL', 'http://127.0.0.1:8091')
    parsed = urlsplit(url)
    if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', '::1') or
            parsed.username is not None or parsed.password is not None or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        raise DeploymentError('Runner URL must be literal loopback HTTP without credentials or a path.')
    token = config.get('PYTHON_SANDBOX_TOKEN', '')
    if len(token) < 32:
        raise DeploymentError('Missing local Runner service credential; deploy python_sandbox first.')
    request = Request(url.rstrip('/') + '/health', headers={'Authorization': 'Bearer ' + token})
    with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=5) as response:
        body = json.loads(response.read(16385))
    if not body.get('ready') or not re.fullmatch('sha256:[a-f0-9]{64}', body.get('image_digest', '')):
        raise DeploymentError('Runner is not ready with a pinned image; Python remains unavailable.')
    return body


def marker_path(config):
    def local_path(value):
        value = value.replace('${PROJECT_DIR}', str(ROOT)).replace('$PROJECT_DIR', str(ROOT))
        if '$' in value or '`' in value:
            raise DeploymentError('Use an absolute path or ${PROJECT_DIR} for the workspace and maintenance switch.')
        path = Path(value)
        return path if path.is_absolute() else ROOT / path
    if config.get('ENZYMIND_PYTHON_DISABLE_FILE'):
        return local_path(config['ENZYMIND_PYTHON_DISABLE_FILE'])
    db = local_path(config.get('ENZYMIND_WORKSPACE_DB', str(ROOT / 'files/workspace/workspace.sqlite3')))
    return db.parent / 'python.disabled'


def status(config):
    if config.get('ENZYMIND_PYTHON_ENABLED', 'false').lower() != 'true':
        print('Python sandbox: disabled in Gateway configuration (optional feature).')
        return
    peers = exact_ips(config.get('ENZYMIND_PYTHON_AGENT_IPS', ''))
    if marker_path(config).exists():
        raise DeploymentError('Python admission is disabled by its maintenance switch; finish deployment or inspect the existing switch.')
    state = health(config)
    print(f'Python sandbox: ready; active={state["active"]}; Agent IPs={peers}; authenticated local debugging available.')


def wait_idle(config):
    if not config.get('PYTHON_SANDBOX_TOKEN'):
        return
    deadline = time.monotonic() + 75
    while True:
        try:
            state = health(config)
        except URLError as exc:
            if isinstance(exc.reason, ConnectionRefusedError):
                return  # Previously installed but currently stopped.
            raise
        if state.get('active') == 0:
            return
        if time.monotonic() >= deadline:
            raise DeploymentError('Sandbox jobs did not drain; no installer was started. Retry after they finish.')
        time.sleep(1)


def deploy(args, env_file, original, config):
    if os.geteuid() == 0:
        raise DeploymentError('Run scripts/deploy.sh as the Gateway owner; only the Rootless installer uses sudo.')
    python = ROOT / 'gateway/venv/bin/python'
    if not python.exists():
        raise DeploymentError('Deploy gateway first: bash scripts/deploy.sh gateway python_sandbox')
    if args.proxy and not re.fullmatch(r'http://(?:127\.0\.0\.1|localhost):[0-9]{1,5}', args.proxy):
        raise DeploymentError('Use a credential-free loopback HTTP build proxy.')
    peers = exact_ips(args.agent_ip) if args.agent_ip else discover_agent_ip(args.n8n_container, args.gateway_url)
    if args.check:
        subprocess.run(['bash', str(ROOT / 'services/python_sandbox/deploy/install_rootless.sh'), '--check'], check=True)
        state = health(config)
        if exact_ips(config.get('ENZYMIND_PYTHON_AGENT_IPS', '')) != peers:
            raise DeploymentError('Configured Agent IP differs from the current connection source; redeploy python_sandbox.')
        print(f'Python sandbox check passed: ready={state["ready"]}; Agent IPs={peers}; no changes made.')
        return
    subprocess.run([str(python), '-c', 'import fastapi, httpx, uvicorn'], check=True, cwd=ROOT)
    directory = ROOT / 'files/workspace/backups' / ('python-deploy-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ'))
    directory.mkdir(parents=True, mode=0o700)
    atomic_private(directory / 'gateway.env.before', original)
    marker = marker_path(config)
    marker.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if marker.is_symlink():
        raise DeploymentError('Refusing a symlink maintenance switch.')
    owned_marker = not marker.exists() or marker.read_text() == GUARD
    if not marker.exists():
        with marker.open('x') as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(GUARD)
    published = None
    try:
        wait_idle(config)
        command = ['sudo', 'bash', str(ROOT / 'services/python_sandbox/deploy/install_rootless.sh')]
        previous = HANDOFF / 'deployment.json'
        if previous.exists() and json.loads(private_text(previous)).get('runner_ready'):
            command.append('--update')
        if args.proxy:
            command += ['--proxy', args.proxy]
        if args.runner_python:
            command += ['--runner-python', args.runner_python]
        subprocess.run(command, check=True, cwd=ROOT)
        handoff = settings(private_text(HANDOFF / 'gateway.env'))
        if config.get('PYTHON_SANDBOX_TOKEN') and config['PYTHON_SANDBOX_TOKEN'] != handoff.get('PYTHON_SANDBOX_TOKEN'):
            raise DeploymentError('Existing Runner credential changed unexpectedly; the previous Gateway configuration is preserved.')
        state = health(handoff)
        subprocess.run([str(python), '-m', 'services.python_sandbox.gateway_acceptance',
                        '--config-file', str(HANDOFF / 'gateway.env'),
                        '--report-file', str(directory / 'gateway-acceptance.json')], cwd=ROOT, check=True)
        enabled = args.enable or config.get('ENZYMIND_PYTHON_ENABLED', 'false').lower() == 'true'
        values = {key: handoff[key] for key in ('ENZYMIND_PYTHON_RUNNER_URL', 'PYTHON_SANDBOX_TOKEN')}
        values.update(ENZYMIND_PYTHON_AGENT_IPS=peers, ENZYMIND_PYTHON_ENABLED=str(enabled).lower())
        # Preserve all unrelated settings and only publish configuration after acceptance.
        if (private_text(env_file) if env_file.exists() else '') != original:
            raise DeploymentError('Gateway configuration changed during deployment; refusing to overwrite it.')
        published = merge_settings(original, values)
        atomic_private(env_file, published)
        report = {'runner_ready': True, 'image_digest': state['image_digest'], 'agent_ips': peers,
                  'gateway_enabled': enabled, 'web_restart_required': True,
                  'manual_maintenance_preserved': not owned_marker}
        atomic_private(directory / 'deployment.json', json.dumps(report, indent=2) + '\n')
        if owned_marker and marker.read_text() == GUARD:
            marker.unlink()
        print('Python deployment and Gateway acceptance passed. Private report: ' + str(directory / 'deployment.json'))
        print('Load the updated application/configuration with: bash scripts/start_web.sh restart')
    except BaseException:
        if published is not None and env_file.exists() and private_text(env_file) == published:
            atomic_private(env_file, original)
        print('Python deployment did not complete. Admission remains closed; existing Gateway configuration and private backup are preserved.')
        print('Fix the reported cause and rerun the same deploy command; do not remove the maintenance switch to bypass acceptance.')
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=Path(os.getenv('ENZYMIND_ENV_FILE', str(ROOT / '.env.production'))))
    parser.add_argument('--proxy', default='')
    parser.add_argument('--runner-python', help='Independent Python 3.11+ executable for a new Runner venv')
    parser.add_argument('--agent-ip')
    parser.add_argument('--n8n-container', default=os.getenv('ENZYMIND_N8N_CONTAINER', 'n8n'))
    parser.add_argument('--gateway-url', default=os.getenv('ENZYMIND_N8N_GATEWAY_URL', 'http://host.docker.internal:8080'))
    parser.add_argument('--enable', action='store_true')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--check', action='store_true')
    modes.add_argument('--status', action='store_true')
    args = parser.parse_args()
    os.chdir(ROOT)
    env_file = args.env_file.absolute()
    if env_file.is_symlink():
        raise DeploymentError('Refusing a symlink Gateway configuration.')
    original = private_text(env_file) if env_file.exists() else ''
    config = settings(original)
    if args.status:
        status(config)
        return
    if args.check:
        deploy(args, env_file, original, config)
        return
    lock = ROOT / '.pids/python-deploy.lock'
    lock.parent.mkdir(mode=0o700, exist_ok=True)
    with lock.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        deploy(args, env_file, original, config)


if __name__ == '__main__':
    try:
        main()
    except DeploymentError as exc:
        raise SystemExit(str(exc)) from None
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        # Do not echo HTTP headers, environment values or private configuration.
        raise SystemExit('Python deployment failed: ' + type(exc).__name__ + '. Inspect the preceding stage; credentials were not printed.') from None
