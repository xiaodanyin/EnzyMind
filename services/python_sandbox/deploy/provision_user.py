"""Non-root phase of the administrator installer. Never contacts rootful Docker."""
import argparse
import grp
import json
import os
from pathlib import Path
import pwd
import secrets
import shutil
import subprocess
import time
from urllib.error import URLError
from urllib.request import Request, build_opener, ProxyHandler


def run(*command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--proxy', default='')
    parser.add_argument('--rootless-only', action='store_true')
    parser.add_argument('--update', action='store_true')
    parser.add_argument('--runner-python', default='/usr/bin/python3')
    args = parser.parse_args()
    user = pwd.getpwuid(os.geteuid())
    if user.pw_name != 'enzymind-python' or any(grp.getgrgid(g).gr_name == 'docker' for g in {*os.getgroups(), os.getgid()}):
        raise SystemExit('Use the dedicated non-root account without docker group access.')
    if os.access('/var/run/docker.sock', os.R_OK | os.W_OK):
        raise SystemExit('Dedicated account must not be able to access production Docker.')
    task_home = Path(user.pw_dir)
    root = task_home / 'enzymind-sandbox'
    package = root / 'services/python_sandbox'
    config = task_home / '.config/enzymind-python'
    units = task_home / '.config/systemd/user'
    state = task_home / '.local/share/enzymind-python'
    for path in (config, units, state, task_home / '.config/docker'):
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chdir(root)
    socket = f'/run/user/{os.geteuid()}/docker.sock'
    docker = ['docker', '--host', 'unix://' + socket]
    daemon = task_home / '.config/docker/daemon.json'
    old_daemon_config = json.loads(daemon.read_text()) if daemon.exists() else {}
    daemon_config = dict(old_daemon_config)
    if args.proxy:
        daemon_config['proxies'] = {'http-proxy': args.proxy, 'https-proxy': args.proxy,
                                   'no-proxy': 'localhost,127.0.0.1,::1'}
    daemon_config['log-driver'] = 'none'
    daemon.write_text(json.dumps(daemon_config, indent=2) + '\n')
    daemon.chmod(0o600)
    if not args.update:
        run('dockerd-rootless-setuptool.sh', 'install', '--force')
    # Only this dedicated user's services are stopped or restarted.
    subprocess.run(['systemctl', '--user', 'stop', 'enzymind-python-runner.service',
                    'enzymind-python-reaper.timer'], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    run('systemctl', '--user', 'enable', 'docker.service')
    run('systemctl', '--user', 'restart' if not args.update or daemon_config != old_daemon_config else 'start', 'docker.service')
    info = json.loads(subprocess.check_output(docker + ['info', '--format', '{{json .}}']))
    if (not any('rootless' in s for s in info.get('SecurityOptions', []))
            or info.get('CgroupVersion') != '2' or info.get('CgroupDriver') != 'systemd'
            or 'name=seccomp,profile=builtin' not in info.get('SecurityOptions', [])):
        raise SystemExit('Rootless/cgroup v2/systemd/default seccomp checks failed.')
    ids = subprocess.check_output(docker + ['ps', '-aq']).decode().split()
    if ids:
        containers = json.loads(subprocess.check_output(docker + ['inspect', *ids]))
        if any(c['Config'].get('Labels', {}).get('org.enzymind.python-sandbox') != 'v1' for c in containers):
            raise SystemExit('Dedicated daemon has foreign containers; investigate before deployment.')
        run(*docker, 'rm', '-f', *ids)  # Runner was stopped; only our abandoned jobs remain.
    report = {'account': user.pw_name, 'uid': user.pw_uid, 'socket': socket,
              'docker_version': info['ServerVersion'], 'rootless': True,
              'cgroup_version': info['CgroupVersion'], 'cgroup_driver': info['CgroupDriver'],
              'runner_ready': False, 'gateway_enabled': False}
    (config / 'deployment.json').write_text(json.dumps(report, indent=2) + '\n')
    if args.rootless_only:
        print('Dedicated Rootless Docker is running; Runner not installed.')
        return
    venv = root / '.venv'
    if not (venv / 'bin/python').exists():
        run(args.runner_python, '-c', 'import sys; assert sys.version_info >= (3,11), "Runner requires Python 3.11+"')
        run(args.runner_python, '-m', 'venv', str(venv))
    python = str(venv / 'bin/python')
    run(python, '-c', 'import sys; assert sys.version_info >= (3,11), "Existing Runner environment requires Python 3.11+"')
    pip = [python, '-m', 'pip', 'install', '--require-hashes', '--only-binary=:all:',
           '-r', str(package / 'runner-requirements.lock')]
    if args.proxy:
        pip += ['--proxy', args.proxy]
    run(*pip)
    build = [python, '-m', 'services.python_sandbox.build_image', '--reuse', '--output', str(root / 'image-manifest.json')]
    if args.proxy:
        build += ['--build-proxy', args.proxy]
    run(*build)
    manifest = json.loads((root / 'image-manifest.json').read_text())
    env_path = config / 'runner.env'
    prior = dict(line.split('=', 1) for line in env_path.read_text().splitlines() if '=' in line) if env_path.exists() else {}
    token = prior.get('PYTHON_SANDBOX_TOKEN') or secrets.token_urlsafe(48)
    environment = {'PYTHON_SANDBOX_SOCKET': socket, 'PYTHON_SANDBOX_STATE': str(state),
                   'PYTHON_SANDBOX_IMAGE': manifest['image_id'], 'PYTHON_SANDBOX_TOKEN': token}
    env_path.write_text(''.join(f'{key}={value}\n' for key, value in environment.items()))
    env_path.chmod(0o600)
    env = os.environ | environment
    # This suite creates only bounded, labelled disposable containers, and fails closed.
    run(python, '-m', 'services.python_sandbox.acceptance', env=env)
    for name in ('runner.service', 'reaper.service', 'reaper.timer'):
        shutil.copyfile(package / 'deploy' / name, units / ('enzymind-python-' + name))
    run('systemctl', '--user', 'daemon-reload')
    run('systemctl', '--user', 'enable', '--now', 'enzymind-python-reaper.timer', 'enzymind-python-runner.service')
    opener = build_opener(ProxyHandler({}))
    request = Request('http://127.0.0.1:8091/health', headers={'Authorization': 'Bearer ' + token})
    health = None
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            with opener.open(request, timeout=3) as response:
                health = json.load(response)
            if health.get('ready'):
                break
        except URLError:
            pass
        time.sleep(2)
    if not health or not health.get('ready'):
        raise SystemExit('Runner did not become ready; keep Gateway disabled and inspect the dedicated user service.')
    run(python, '-m', 'services.python_sandbox.http_acceptance', env=env)
    with opener.open(request, timeout=3) as response:
        health = json.load(response)
    report.update(runner_ready=True, image_id=manifest['image_id'],
                  acceptance=json.loads((state / 'acceptance.json').read_text()),
                  http_acceptance=json.loads((state / 'http-acceptance.json').read_text()), health=health)
    (config / 'deployment.json').write_text(json.dumps(report, indent=2) + '\n')
    gateway = config / 'gateway.env'
    gateway.write_text('ENZYMIND_PYTHON_ENABLED=false\nENZYMIND_PYTHON_RUNNER_URL=http://127.0.0.1:8091\nENZYMIND_PYTHON_AGENT_IPS=\n'
                       + 'PYTHON_SANDBOX_TOKEN=' + token + '\n')
    gateway.chmod(0o600)
    print('Rootless Docker, resource acceptance, Runner readiness and reaper timer: passed.')


if __name__ == '__main__':
    main()
