#!/bin/bash
# Administrator entry point. Never changes the existing rootful Docker daemon.
set -Eeuo pipefail
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(dirname -- "$SCRIPT_DIR")"
SANDBOX_ACCOUNT=enzymind-python
SANDBOX_HOME=/home/enzymind-python
BUILD_PROXY=
RUNNER_PYTHON=/usr/bin/python3
ROOTLESS_ONLY=false
CHECK_ONLY=false
CHECK_APT=false
UPDATE_ONLY=false
while [ "$#" -gt 0 ]; do
    case "$1" in
        --proxy) BUILD_PROXY="${2:?Missing proxy URL}"; shift 2 ;;
        --runner-python) RUNNER_PYTHON="${2:?Missing Python executable}"; shift 2 ;;
        --rootless-only) ROOTLESS_ONLY=true; shift ;;
        --check) CHECK_ONLY=true; shift ;;
        --check-apt) CHECK_APT=true; shift ;;
        --update) UPDATE_ONLY=true; shift ;;
        -h|--help) echo 'Usage: sudo bash install_rootless.sh [--proxy http://127.0.0.1:7890] [--runner-python /absolute/python3.12] [--update|--rootless-only] [--check|--check-apt]'; exit 0 ;;
        *) echo 'Unknown option. Use --help.' >&2; exit 2 ;;
    esac
done
if [ -n "$BUILD_PROXY" ] && ! [[ "$BUILD_PROXY" =~ ^http://(127\.0\.0\.1|localhost):[0-9]{1,5}$ ]]; then
    echo 'Only a credential-free loopback HTTP proxy is accepted.' >&2; exit 2
fi
[ -x /usr/bin/dockerd-rootless-setuptool.sh ] || { echo 'Install matching docker-ce-rootless-extras first.' >&2; exit 1; }
[ -f /sys/fs/cgroup/cgroup.controllers ] || { echo 'cgroup v2 is required.' >&2; exit 1; }
for controller in cpu memory pids; do
    [[ " $(cat /sys/fs/cgroup/cgroup.controllers) " == *" $controller "* ]] || { echo "Missing controller: $controller" >&2; exit 1; }
done
[ -f "$SOURCE_DIR/base-image.lock.json" ] || { echo 'Resolve base-image.lock.json before installation.' >&2; exit 1; }
if "$CHECK_APT"; then
    exec /usr/bin/python3 "$SCRIPT_DIR/apt_prerequisites.py" --check --proxy "$BUILD_PROXY"
fi
if "$CHECK_ONLY"; then
    echo 'Rootless components and cgroup v2: present'
    echo "Dedicated account: $(getent passwd "$SANDBOX_ACCOUNT" | cut -d: -f1 || true)"
    for package in uidmap dbus-user-session python3-venv slirp4netns; do
        dpkg-query -W -f='${binary:Package}: ${db:Status-Abbrev}\n' "$package" 2>/dev/null || true
    done
    echo 'Check only; no changes made.'
    exit 0
fi
[ "$EUID" -eq 0 ] || { echo 'Run this script with sudo in your terminal. No password is accepted by the application.' >&2; exit 1; }
[ "${SUDO_UID:-0}" -gt 0 ] || { echo 'Invoke with sudo from the Gateway owner account.' >&2; exit 1; }
CALLER_UID="$SUDO_UID"
CALLER_GID="$SUDO_GID"
if ! "$ROOTLESS_ONLY" && [ ! -x "$SANDBOX_HOME/enzymind-sandbox/.venv/bin/python" ]; then
    [[ "$RUNNER_PYTHON" = /* ]] && [ -x "$RUNNER_PYTHON" ] || { echo 'Runner Python must be an absolute executable path.' >&2; exit 2; }
    "$RUNNER_PYTHON" -c 'import sys; assert sys.version_info >= (3,11), "Runner requires Python 3.11+; use --runner-python with an independent interpreter."'
fi
HANDOFF_DIR=/var/lib/enzymind-python-deploy
[ ! -L "$HANDOFF_DIR" ] || { echo 'Refusing symlink handoff directory.' >&2; exit 1; }
install -d -m 0755 -o root -g root "$HANDOFF_DIR"
exec 9>"$HANDOFF_DIR/install.lock"
flock -n 9 || { echo 'Another sandbox installer is running.' >&2; exit 1; }
MARKER="$SANDBOX_HOME/.config/enzymind-python/managed-install.json"
if getent passwd "$SANDBOX_ACCOUNT" >/dev/null && [ ! -f "$MARKER" ]; then
    echo 'An unmanaged enzymind-python account already exists; refusing to reuse it.' >&2; exit 1
fi
if "$UPDATE_ONLY"; then
    [ -f "$MARKER" ] && [ -x "$SANDBOX_HOME/enzymind-sandbox/.venv/bin/python" ] || {
        echo 'A managed Runner installation is required for --update.' >&2; exit 1;
    }
    if "$ROOTLESS_ONLY"; then echo '--update and --rootless-only cannot be combined.' >&2; exit 2; fi
fi
if [ -f "$MARKER" ]; then
    /usr/bin/python3 - "$MARKER" "$CALLER_UID" <<'PY'
import json, pathlib, sys
if json.loads(pathlib.Path(sys.argv[1]).read_text()).get('gateway_uid') != int(sys.argv[2]):
    raise SystemExit('This sandbox belongs to a different Gateway owner.')
PY
fi

if ! "$UPDATE_ONLY"; then
    /usr/bin/python3 "$SCRIPT_DIR/apt_prerequisites.py" --proxy "$BUILD_PROXY"
fi
if ! getent passwd "$SANDBOX_ACCOUNT" >/dev/null; then
    adduser --disabled-password --gecos '' --home "$SANDBOX_HOME" "$SANDBOX_ACCOUNT"
fi
SANDBOX_UID="$(id -u "$SANDBOX_ACCOUNT")"
SANDBOX_GID="$(id -g "$SANDBOX_ACCOUNT")"
[ "$SANDBOX_UID" -ne 0 ] && [ "$SANDBOX_UID" -ne "$CALLER_UID" ]
[ "$(getent passwd "$SANDBOX_ACCOUNT" | cut -d: -f6)" = "$SANDBOX_HOME" ]
if [[ " $(id -nG "$SANDBOX_ACCOUNT") " == *' docker '* ]]; then
    echo 'Dedicated account must not have production docker group access.' >&2; exit 1
fi
# install -d applies ownership to its named targets, not missing intermediate
# parents. Name every parent explicitly, including on a resumed installation.
# Do not recursively chown Docker data: subordinate UID ownership must survive.
for directory in "$SANDBOX_HOME" "$SANDBOX_HOME/.config" \
    "$SANDBOX_HOME/.config/enzymind-python" "$SANDBOX_HOME/.config/systemd" \
    "$SANDBOX_HOME/.config/systemd/user" "$SANDBOX_HOME/.config/docker" \
    "$SANDBOX_HOME/.local" "$SANDBOX_HOME/.local/share" \
    "$SANDBOX_HOME/.local/share/enzymind-python"; do
    [ ! -L "$directory" ] || { echo "Refusing symlink directory: $directory" >&2; exit 1; }
    install -d -m 0700 -o "$SANDBOX_UID" -g "$SANDBOX_GID" "$directory"
done
if [ ! -f "$MARKER" ]; then
    printf '{"managed_by":"EnzyMind Python sandbox installer","gateway_uid":%s}\n' "$CALLER_UID" > "$MARKER"
    chown "$SANDBOX_UID:$SANDBOX_GID" "$MARKER"
fi
/usr/bin/python3 - "$SANDBOX_ACCOUNT" <<'PY'
import pathlib, sys
account = sys.argv[1]
for name in ('subuid', 'subgid'):
    ranges = []
    for line in pathlib.Path('/etc/' + name).read_text().splitlines():
        owner, start, count = line.split(':')
        ranges.append((owner, int(start), int(start) + int(count)))
    own = [r for r in ranges if r[0] == account and r[2] - r[1] >= 65536]
    if not own or any(a < y and x < b for _, a, b in own for owner, x, y in ranges if owner != account):
        raise SystemExit('Missing or overlapping subordinate IDs in ' + name)
PY

install -d -m 0755 "/etc/systemd/system/user@$SANDBOX_UID.service.d"
printf '[Service]\nDelegate=cpu cpuset io memory pids\n' > "/etc/systemd/system/user@$SANDBOX_UID.service.d/enzymind-delegate.conf"
systemctl daemon-reload
loginctl enable-linger "$SANDBOX_ACCOUNT"
systemctl start "user@$SANDBOX_UID.service"

# Stop before replacing imported modules, never while a known job is running.
# The high-level deploy entry closes Gateway admission before reaching this phase.
runuser -u "$SANDBOX_ACCOUNT" -- env XDG_RUNTIME_DIR="/run/user/$SANDBOX_UID" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$SANDBOX_UID/bus" /usr/bin/python3 - "$SANDBOX_HOME" <<'PY'
import json, pathlib, subprocess, sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, ProxyHandler, build_opener
config = pathlib.Path(sys.argv[1]) / '.config/enzymind-python/runner.env'
if config.exists():
    values = dict(line.split('=', 1) for line in config.read_text().splitlines() if '=' in line)
    request = Request('http://127.0.0.1:8091/health', headers={'Authorization': 'Bearer ' + values['PYTHON_SANDBOX_TOKEN']})
    try:
        with build_opener(ProxyHandler({})).open(request, timeout=5) as response:
            health = json.load(response)
        if health.get('active', 1):
            raise SystemExit('Active sandbox jobs exist; close admission and retry after they finish.')
    except HTTPError:
        raise SystemExit('Runner health authorization/readiness failed; investigate before replacing files.') from None
    except URLError as exc:
        if not isinstance(exc.reason, ConnectionRefusedError):
            raise SystemExit('Runner health unavailable; refusing to interrupt unknown jobs.') from None
subprocess.run(['systemctl', '--user', 'stop', 'enzymind-python-runner.service',
                'enzymind-python-reaper.timer', 'enzymind-python-reaper.service'], check=False,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
PY
if [ -d "$SANDBOX_HOME/enzymind-sandbox/services/python_sandbox" ]; then
    BACKUP_DIR="$(mktemp -d "$HANDOFF_DIR/backup-XXXXXXXX")"
    /usr/bin/python3 - "$SANDBOX_HOME/enzymind-sandbox/services/python_sandbox" "$BACKUP_DIR/package" <<'PY'
import shutil, sys
shutil.copytree(sys.argv[1], sys.argv[2], symlinks=True,
                ignore=shutil.ignore_patterns('wheelhouse', '__pycache__', '.pytest_cache', '.venv'))
PY
    if [ -f "$SANDBOX_HOME/.config/enzymind-python/runner.env" ]; then
        cp -a "$SANDBOX_HOME/.config/enzymind-python/runner.env" "$BACKUP_DIR/runner.env"
    fi
    echo "Prior Runner package and configuration backed up: $BACKUP_DIR"
fi

# Copy only the sandbox package, never the project tree, environment or data.
/usr/bin/python3 - "$SOURCE_DIR" "$SANDBOX_HOME" "$SANDBOX_UID" "$SANDBOX_GID" <<'PY'
import os, pathlib, shutil, sys
source, home = map(pathlib.Path, sys.argv[1:3])
uid, gid = map(int, sys.argv[3:])
root = home / 'enzymind-sandbox'
target = root / 'services/python_sandbox'
for path in source.rglob('*'):
    rel = path.relative_to(source)
    if any(part in ('__pycache__', '.pytest_cache', '.venv') for part in rel.parts):
        continue
    if path.is_symlink():
        raise SystemExit('Symlinks are not allowed in deployment source: ' + str(rel))
    if path.is_file():
        dest = target / rel
        # Never follow a destination symlink when this phase runs as root.
        for parent in [dest, *dest.parents]:
            if parent.is_symlink():
                raise SystemExit('Unexpected symlink in deployment destination.')
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest, follow_symlinks=False)
        dest.chmod(0o600)
for path in [root, root / 'services', target, *target.rglob('*')]:
    if path.is_symlink():
        raise SystemExit('Unexpected symlink in deployment destination.')
    os.chown(path, uid, gid)
    if path.is_dir():
        path.chmod(0o700)
PY

USER_STAGE_ARGS=(--proxy "$BUILD_PROXY" --runner-python "$RUNNER_PYTHON")
if "$ROOTLESS_ONLY"; then USER_STAGE_ARGS+=(--rootless-only); fi
if "$UPDATE_ONLY"; then USER_STAGE_ARGS+=(--update); fi
runuser -u "$SANDBOX_ACCOUNT" -- env \
    -u DOCKER_HOST -u DOCKER_CONTEXT -u PYTHONPATH -u PYTHONHOME \
    -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy \
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    XDG_RUNTIME_DIR="/run/user/$SANDBOX_UID" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$SANDBOX_UID/bus" \
    /usr/bin/python3 "$SANDBOX_HOME/enzymind-sandbox/services/python_sandbox/deploy/provision_user.py" \
    "${USER_STAGE_ARGS[@]}"

# Private credential handoff; no secret appears in terminal output.
install -d -m 0755 -o root -g root "$HANDOFF_DIR"
install -m 0600 -o "$CALLER_UID" -g "$CALLER_GID" \
    "$SANDBOX_HOME/.config/enzymind-python/deployment.json" "$HANDOFF_DIR/deployment.json"
if ! "$ROOTLESS_ONLY"; then
    install -m 0600 -o "$CALLER_UID" -g "$CALLER_GID" \
        "$SANDBOX_HOME/.config/enzymind-python/gateway.env" "$HANDOFF_DIR/gateway.env"
    install -m 0600 -o "$CALLER_UID" -g "$CALLER_GID" \
        "$SANDBOX_HOME/.local/share/enzymind-python/acceptance.json" "$HANDOFF_DIR/acceptance.json"
    install -m 0600 -o "$CALLER_UID" -g "$CALLER_GID" \
        "$SANDBOX_HOME/.local/share/enzymind-python/http-acceptance.json" "$HANDOFF_DIR/http-acceptance.json"
fi
echo "Deployment completed. Report: $HANDOFF_DIR/deployment.json"
echo 'Runner handoff is ready. Gateway configuration/enablement requires integration acceptance via scripts/deploy.sh python_sandbox.'
