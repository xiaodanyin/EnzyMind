"""Resolve the official Python tag to a registry digest during a reviewed image update."""
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

TAG = '3.12-slim-bookworm'


def main():
    with urlopen('https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/python:pull', timeout=30) as response:
        token = json.load(response)['token']
    request = Request('https://registry-1.docker.io/v2/library/python/manifests/' + TAG, headers={
        'Authorization': 'Bearer ' + token,
        'Accept': 'application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json',
    })
    with urlopen(request, timeout=30) as response:
        raw = response.read(1024 * 1024)
        digest = response.headers['Docker-Content-Digest']
    if digest != 'sha256:' + hashlib.sha256(raw).hexdigest():
        raise RuntimeError('Registry digest mismatch.')
    target = Path(__file__).with_name('base-image.lock.json')
    target.write_text(json.dumps({'base': 'python:' + TAG + '@' + digest}, indent=2) + '\n')
    print(target)


if __name__ == '__main__':
    main()
