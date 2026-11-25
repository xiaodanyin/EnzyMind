#!/usr/bin/env python3
"""Adopt/stop only EnzyMind processes; never signal clients connected to a port."""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def identity(pid, directory, service):
    """Return Linux start time only for the expected executable and working directory."""
    try:
        proc = Path('/proc') / str(pid)
        if proc.stat().st_uid != os.getuid() or (proc / 'cwd').resolve() != directory:
            return None
        stat = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
        if stat[0] == 'Z':
            return None
        args = (proc / 'cmdline').read_bytes().decode(errors='replace').strip('\0').split('\0')
        executable = Path(args[0]).name
        if service == 'frontend':
            valid = (executable.startswith('npm run dev') or
                     executable in ('node', 'nodejs') and any(Path(a).name in ('vite', 'vite.js', 'npm-cli.js') for a in args[1:]))
        else:
            valid = executable.startswith(('python', 'uvicorn')) and (
                any(Path(a).name == 'main.py' for a in args[1:]) or
                any(a in ('main:app', 'gateway.main:app') for a in args[1:]))
        return stat[19] if valid else None
    except (OSError, IndexError, ValueError):
        return None


def listeners(port):
    result = subprocess.run(['lsof', '-t', f'-iTCP:{port}', '-sTCP:LISTEN'], capture_output=True, text=True)
    if result.returncode not in (0, 1):
        raise RuntimeError('Could not inspect listening processes')
    return {int(pid) for pid in result.stdout.split()}


def manage(action, service, directory, port, pidfile):
    directory = directory.resolve()
    active = listeners(port)
    owned = {pid: identity(pid, directory, service) for pid in active}
    if any(value is None for value in owned.values()):
        print(f'{service}: port {port} belongs to another process; left unchanged.', file=sys.stderr)
        return 1
    try:
        saved = int(pidfile.read_text().strip())
    except (OSError, ValueError):
        saved = None
    if saved and (stamp := identity(saved, directory, service)):
        owned[saved] = stamp
    if action == 'adopt':
        if not active:
            return 1
        pidfile.parent.mkdir(parents=True, exist_ok=True)
        pidfile.write_text(f'{saved if saved in owned else min(active)}\n')
        return 0
    # Validate again before every signal to protect against stale/reused PID files.
    for pid, stamp in owned.items():
        if identity(pid, directory, service) == stamp:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    deadline = time.monotonic() + float(os.environ.get('ENZYMIND_STOP_TIMEOUT', '30'))
    while any(identity(pid, directory, service) == stamp for pid, stamp in owned.items()):
        if time.monotonic() >= deadline:
            print(f'{service}: still shutting down; left running rather than force-killed. Retry stop.', file=sys.stderr)
            return 1
        time.sleep(.1)
    if listeners(port):
        print(f'{service}: port {port} was occupied during shutdown; left unchanged.', file=sys.stderr)
        return 1
    pidfile.unlink(missing_ok=True)
    print(f'{service}: stopped (or already stopped).')
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['adopt', 'stop'])
    parser.add_argument('service')
    parser.add_argument('directory', type=Path)
    parser.add_argument('port', type=int)
    parser.add_argument('pidfile', type=Path)
    options = parser.parse_args()
    try:
        sys.exit(manage(**vars(options)))
    except (OSError, ValueError, RuntimeError) as error:
        print(f'{options.service}: {error}', file=sys.stderr)
        sys.exit(1)
