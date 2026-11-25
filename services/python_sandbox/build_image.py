"""Build only on the dedicated Rootless daemon and write an immutable image manifest."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit


def build_fingerprint(root, base):
    digest = hashlib.sha256(base.encode())
    # All executable/configuration inputs copied into the image. Wheel caches
    # are already authenticated by requirements.lock and do not change identity.
    for name in ('Dockerfile', '.dockerignore', 'requirements.lock', 'bootstrap.py', 'science_smoke.py'):
        digest.update(name.encode() + b'\0' + (root / name).read_bytes())
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', help='python:3.12-slim-bookworm@sha256:... (defaults to base-image.lock.json)')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--build-proxy', help='Credential-free loopback proxy for trusted image construction only')
    parser.add_argument('--reuse', action='store_true', help='Reuse an inspected immutable image only when build inputs match')
    args = parser.parse_args()
    if args.base is None:
        lock = Path(__file__).with_name('base-image.lock.json')
        if not lock.exists():
            parser.error('Resolve and review base-image.lock.json using lock_base.py first, or supply --base.')
        args.base = json.loads(lock.read_text())['base']
    if not re.fullmatch(r'python:3\.12[^@\s]*@sha256:[a-f0-9]{64}', args.base):
        parser.error('Supply the reviewed Python 3.12 base repository digest.')
    socket = f'unix:///run/user/{os.geteuid()}/docker.sock'
    docker = ['docker', '--host', socket]
    info = json.loads(subprocess.check_output(docker + ['info', '--format', '{{json .}}']))
    if os.geteuid() == 0 or not any('rootless' in value for value in info.get('SecurityOptions', [])):
        parser.error('Build under the dedicated Rootless Docker account.')
    root = Path(__file__).resolve().parent
    fingerprint = build_fingerprint(root, args.base)
    if args.reuse and args.output.exists():
        previous = json.loads(args.output.read_text())
        image = previous.get('image_id', '')
        if previous.get('build_fingerprint') == fingerprint and re.fullmatch(r'sha256:[a-f0-9]{64}', image):
            inspected = subprocess.run(docker + ['image', 'inspect', image], capture_output=True, text=True)
            if inspected.returncode == 0 and json.loads(inspected.stdout)[0]['Id'] == image:
                print('Reusing verified immutable sandbox image: ' + image)
                return
    tag = 'enzymind-python:locked'
    build = docker + ['build', '--progress=plain', '--pull', '--build-arg', 'PYTHON_BASE=' + args.base]
    build_environment = dict(os.environ)
    if args.build_proxy:
        proxy = urlsplit(args.build_proxy)
        if (proxy.scheme != 'http' or proxy.hostname not in ('127.0.0.1', 'localhost')
                or proxy.username or proxy.password or proxy.path or proxy.query or proxy.fragment or not proxy.port):
            parser.error('Build proxy must be a credential-free HTTP loopback address with a port.')
        # Docker 29.5+ detached-netns allows the trusted builder to reach a loopback
        # proxy. These predefined build args do not become image ENV or history.
        # The execution policy in engine.py always uses network=none.
        build += ['--network=host']
        for name in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy'):
            build += ['--build-arg', name + '=' + args.build_proxy]
            # BuildKit's client-side registry auth also needs the proxy. The
            # daemon's proxy config and Dockerfile build args do not cover it.
            build_environment[name] = args.build_proxy
    subprocess.run(build + ['-t', tag, str(root)], check=True, env=build_environment)
    inspect = json.loads(subprocess.check_output(docker + ['image', 'inspect', tag]))[0]
    manifest = {'base': args.base, 'image_id': inspect['Id'], 'repo_digests': inspect['RepoDigests'],
                'build_fingerprint': fingerprint}
    args.output.write_text(json.dumps(manifest, indent=2) + '\n')
    print('PYTHON_SANDBOX_IMAGE=' + inspect['Id'])


if __name__ == '__main__':
    main()
