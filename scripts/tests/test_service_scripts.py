"""Exercise the unchanged launch commands on isolated, lightweight services."""
import importlib.util
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('service_process', ROOT / 'scripts/service_process.py')
processes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(processes)


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def wait_port(port):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if processes.listeners(port):
            return
        time.sleep(.1)
    raise AssertionError(f'Port {port} did not start')


def server_code(port):
    return f'''import os
assert 'PYTHON_SANDBOX_TOKEN' not in os.environ
from http.server import BaseHTTPRequestHandler, HTTPServer
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b'{{"status":"ok"}}')
    do_POST = do_GET
HTTPServer(('127.0.0.1', {port}), Handler).serve_forever()
'''


class ScriptCompatibility(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='enzymind-script-test-')
        self.root = Path(self.temp.name)
        self.child_processes = []
        self.services = {}

    def tearDown(self):
        for name, (directory, port) in self.services.items():
            processes.manage('stop', name, directory, port, self.root / '.pids' / f'{name}.pid')
        for process in self.child_processes:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=10)
        self.temp.cleanup()

    def script(self, name, *args, expected=0):
        result = subprocess.run(['bash', str(self.root / 'scripts' / name), *args],
                                cwd='/tmp', env=self.env, text=True, capture_output=True, timeout=100)
        logs = '\n'.join(p.read_text()[-3000:] for p in (self.root / '.logs').glob('*.log')) if result.returncode != expected else ''
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr + logs)
        return result

    def launch_python(self, directory, port):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'main.py').write_text(server_code(port))
        process = subprocess.Popen([sys.executable, '-u', 'main.py'], cwd=directory,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.child_processes.append(process)
        wait_port(port)
        return process

    def test_legacy_commands_adopt_restart_and_stop_without_pid_files(self):
        shutil.copytree(ROOT / 'scripts', self.root / 'scripts', ignore=shutil.ignore_patterns('tests', '__pycache__'))
        source = (self.root / 'scripts/start.sh').read_text()
        replacements = {}
        for name, old in re.findall(r'\["(\w+)"\]="(189\d\d)"', source):
            port = free_port()
            while port in replacements.values():
                port = free_port()
            replacements[old] = port
            directory = self.root / 'services' / name
            (directory / 'venv/bin').mkdir(parents=True)
            (directory / 'venv/bin/python').symlink_to(sys.executable)
            (directory / 'main.py').write_text(server_code(port))
            self.services[name] = (directory, port)
        for name in ('start.sh', 'stop.sh', 'status.sh'):
            path = self.root / 'scripts' / name
            content = path.read_text()
            for old, port in replacements.items():
                content = content.replace(f'"{old}"', f'"{port}"')
            path.write_text(content)
        gateway = self.root / 'gateway'
        (gateway / 'venv/bin').mkdir(parents=True)
        interpreter = gateway / 'venv/bin/python'
        interpreter.write_text('#!/bin/bash\nexec ' + str(ROOT / 'gateway/venv/bin/python') + ' "$@"\n')
        interpreter.chmod(0o755)
        (gateway / 'main.py').write_text('''import os
async def app(scope, receive, send):
    assert os.environ['SCRIPT_TEST_ENV'] == 'loaded'
    assert os.environ['PYTHON_SANDBOX_TOKEN'] == 'synthetic-runner-test-token'
    await send({'type':'http.response.start','status':200,'headers':[]})
    await send({'type':'http.response.body','body':b'{"status":"ok"}'})
''')
        frontend = self.root / 'frontend'
        (frontend / 'node_modules').mkdir(parents=True)
        (frontend / 'package.json').write_text(json.dumps({'scripts': {'dev': 'node vite.js'}}))
        (frontend / 'vite.js').write_text("if(process.env.PYTHON_SANDBOX_TOKEN)process.exit(71); require('http').createServer((req,res)=>res.end('ready')).listen(Number(process.argv[process.argv.indexOf('--port')+1]),'127.0.0.1');")
        self.services.update(gateway=(gateway, free_port()), frontend=(frontend, free_port()))
        web_script = self.root / 'scripts/start_web.sh'
        web_script.write_text(web_script.read_text().replace('GATEWAY_PORT=8080', f'GATEWAY_PORT={self.services["gateway"][1]}').replace('FRONTEND_PORT=3010', f'FRONTEND_PORT={self.services["frontend"][1]}'))
        (self.root / '.env.production').write_text('SCRIPT_TEST_ENV=loaded\nPYTHON_SANDBOX_TOKEN=synthetic-runner-test-token\n')
        self.env = {**os.environ, 'ENZYMIND_ENV_FILE': str(self.root / '.env.production'),
                    'ENZYMIND_START_TIMEOUT': '15', 'ENZYMIND_STOP_TIMEOUT': '10'}
        self.script('enzymind.sh')
        original = {name: processes.listeners(port) for name, (_, port) in self.services.items()}
        self.assertTrue(all(original.values()))
        for pidfile in (self.root / '.pids').glob('*.pid'):
            pidfile.unlink()
        self.script('start_remote.sh')
        self.assertEqual(original, {name: processes.listeners(port) for name, (_, port) in self.services.items()})
        self.assertEqual(len(list((self.root / '.pids').glob('*.pid'))), 21)
        self.script('start_web.sh', 'status')
        self.script('start_web.sh', 'gateway')
        self.script('start_web.sh', 'frontend')
        self.script('start_web.sh', 'restart')
        for name, (_, port) in self.services.items():
            if name not in ('gateway', 'frontend'):
                self.assertEqual(original[name], processes.listeners(port))
        self.script('stop.sh', 'enzy_recognize')
        self.script('start.sh', 'enzy_recognize')
        # Missing PID files must not prevent old stop commands from working.
        for pidfile in (self.root / '.pids').glob('*.pid'):
            pidfile.unlink()
        self.script('start_web.sh', 'stop')
        # Scientific services are healthy, but the combined status must fail.
        self.script('enzymind.sh', 'status', expected=1)
        self.script('enzymind.sh', 'restart')
        self.script('enzymind.sh', 'status')
        with (self.root / '.pids/enzymind-control.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.script('enzymind.sh', 'stop', expected=75)
        self.script('enzymind.sh', 'stop')
        self.script('stop.sh')
        self.script('start_web.sh', 'stop')
        self.script('stop.sh')
        self.assertTrue(all(not processes.listeners(port) for _, port in self.services.values()))

    def test_foreign_listener_and_stale_pid_are_never_stopped(self):
        directory = self.root / 'gateway'
        directory.mkdir()
        port = free_port()
        foreign = self.launch_python(self.root / 'other-service', port)
        pidfile = self.root / 'gateway.pid'
        pidfile.write_text(str(foreign.pid))
        for action in ('adopt', 'stop'):
            self.assertEqual(processes.manage(action, 'gateway', directory, port, pidfile), 1)
            self.assertIsNone(foreign.poll())
        # An unrelated PID file on a free port is discarded, without signaling it.
        self.assertEqual(processes.manage('stop', 'gateway', directory, free_port(), pidfile), 0)
        self.assertIsNone(foreign.poll())
        self.assertFalse(pidfile.exists())

    def test_stop_ignores_connected_clients_and_recovers_missing_pid(self):
        port = free_port()
        directory = self.root / 'gateway'
        own = self.launch_python(directory, port)
        client = subprocess.Popen([sys.executable, '-c',
            f'import socket,time; s=socket.create_connection(("127.0.0.1",{port})); time.sleep(60)'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.child_processes.append(client)
        time.sleep(.2)
        self.assertEqual(processes.manage('stop', 'gateway', directory, port, self.root / 'missing.pid'), 0)
        own.wait(timeout=5)
        self.assertIsNone(client.poll(), 'A connected client belonging to another service was killed')


if __name__ == '__main__':
    unittest.main()
