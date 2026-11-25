"""Deployment failures must not enable execution, expose secrets or erase settings."""
import argparse
import asyncio
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import httpx

from services.python_sandbox.build_image import build_fingerprint
from services.python_sandbox import build_image
from services.python_sandbox.deploy import integrate as deploy
from services.python_sandbox.http_acceptance import gateway_under_load


class IntegrationDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(patch.stopall)
        patch.object(deploy, 'ROOT', self.root).start()
        self.handoff = self.root / 'handoff'
        self.handoff.mkdir()
        patch.object(deploy, 'HANDOFF', self.handoff).start()
        python = self.root / 'gateway/venv/bin/python'
        python.parent.mkdir(parents=True)
        python.touch()
        self.token = 'synthetic-test-token-' + 'k' * 40
        deploy.atomic_private(self.handoff / 'gateway.env',
            'PYTHON_SANDBOX_TOKEN=' + self.token + '\nENZYMIND_PYTHON_RUNNER_URL=http://127.0.0.1:8091\n')
        self.env = self.root / '.env.production'
        self.text = '# keep comments\nOTHER_SETTING="original value"\nENZYMIND_PYTHON_ENABLED=true\nPYTHON_SANDBOX_TOKEN=' + self.token + '\n'
        deploy.atomic_private(self.env, self.text)
        self.args = argparse.Namespace(agent_ip='172.17.0.2', n8n_container='n8n',
            gateway_url='http://host.docker.internal:8080', check=False, proxy='', enable=False, runner_python=None)
        self.health = patch.object(deploy, 'health', return_value={
            'ready': True, 'active': 0, 'image_digest': 'sha256:' + 'a' * 64}).start()
        self.commands = []

    def run_deployment(self, fail=None):
        def command(args, **kwargs):
            self.commands.append(args)
            if fail and fail(args):
                raise subprocess.CalledProcessError(1, args)
            return subprocess.CompletedProcess(args, 0)
        with patch.object(deploy.subprocess, 'run', side_effect=command), contextlib.redirect_stdout(io.StringIO()) as output:
            deploy.deploy(self.args, self.env, self.text, deploy.settings(self.text))
        self.assertNotIn(self.token, output.getvalue())

    def test_success_preserves_enablement_settings_token_and_removes_only_owned_switch(self):
        self.run_deployment()
        text = deploy.private_text(self.env)
        self.assertIn('# keep comments\nOTHER_SETTING="original value"\n', text)
        config = deploy.settings(text)
        self.assertEqual(config['ENZYMIND_PYTHON_ENABLED'], 'true')
        self.assertEqual(config['ENZYMIND_PYTHON_AGENT_IPS'], '172.17.0.2')
        self.assertEqual(config['PYTHON_SANDBOX_TOKEN'], self.token)
        self.assertFalse(deploy.marker_path(config).exists())
        self.assertTrue(any('services.python_sandbox.gateway_acceptance' in cmd for cmd in self.commands))
        self.assertEqual(len(list(self.root.glob('files/workspace/backups/*/gateway.env.before'))), 1)

    def test_first_install_remains_disabled_unless_explicitly_enabled(self):
        for enable in (False, True):
            with self.subTest(enable=enable):
                self.text = 'OTHER_SETTING=keep\n'
                deploy.atomic_private(self.env, self.text)
                self.args.enable = enable
                self.run_deployment()
                self.assertEqual(deploy.settings(self.env.read_text())['ENZYMIND_PYTHON_ENABLED'], str(enable).lower())

    def test_installer_or_acceptance_failure_preserves_config_and_blocks_admission(self):
        for phase in ('sudo', 'services.python_sandbox.gateway_acceptance'):
            with self.subTest(phase=phase):
                with self.assertRaises(subprocess.CalledProcessError):
                    self.run_deployment(fail=lambda args: phase in args)
                self.assertEqual(self.env.read_text(), self.text)
                self.assertEqual(deploy.marker_path({}).read_text(), deploy.GUARD)
        self.run_deployment()  # The exact same command can resume after failure.
        self.assertFalse(deploy.marker_path({}).exists())

    def test_existing_operator_switch_survives_success(self):
        marker = deploy.marker_path({})
        marker.parent.mkdir(parents=True)
        marker.write_text('operator disabled for investigation\n')
        self.run_deployment()
        self.assertEqual(marker.read_text(), 'operator disabled for investigation\n')

    def test_existing_install_uses_update_and_keeps_service_token(self):
        deploy.atomic_private(self.handoff / 'deployment.json', json.dumps({'runner_ready': True}))
        self.run_deployment()
        command = next(command for command in self.commands if command[0] == 'sudo')
        self.assertIn('--update', command)

    def test_independent_runner_python_is_forwarded_without_changing_gateway(self):
        self.args.runner_python = '/opt/enzymind-python/python/bin/python3.12'
        self.run_deployment()
        command = next(command for command in self.commands if command[0] == 'sudo')
        self.assertEqual(command[command.index('--runner-python') + 1], self.args.runner_python)
        self.assertNotIn('RUNNER_PYTHON', self.env.read_text())

    def test_unexpected_token_change_is_rejected_before_publication(self):
        deploy.atomic_private(self.handoff / 'gateway.env', 'PYTHON_SANDBOX_TOKEN=' + 'z' * 64 + '\n')
        with self.assertRaisesRegex(deploy.DeploymentError, 'credential changed'):
            self.run_deployment()
        self.assertEqual(self.env.read_text(), self.text)
        self.assertTrue(deploy.marker_path({}).exists())

    def test_untrusted_file_permissions_and_symlinks_are_rejected(self):
        self.env.chmod(0o644)
        with self.assertRaises(deploy.DeploymentError):
            deploy.private_text(self.env)
        self.env.chmod(0o600)
        link = self.root / 'link'
        link.symlink_to(self.env)
        with self.assertRaises(deploy.DeploymentError):
            deploy.private_text(link)
        with self.assertRaises(deploy.DeploymentError):
            deploy.atomic_private(link, 'replacement')

    def test_exact_ip_policy_never_expands_trust_to_a_subnet(self):
        for value in ('', '172.17.0.0/16', 'n8n', '*', '0.0.0.0', '::', '224.0.0.1'):
            with self.subTest(value=value), self.assertRaises(deploy.DeploymentError):
                deploy.exact_ips(value)
        self.assertEqual(deploy.exact_ips('172.17.0.2, 172.17.0.2'), '172.17.0.2')

    def test_source_discovery_only_reads_route_not_credentials(self):
        with patch.object(deploy.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '172.17.0.2\n', '')) as run:
            self.assertEqual(deploy.discover_agent_ip('n8n', self.args.gateway_url), '172.17.0.2')
            args = run.call_args.args[0]
            self.assertEqual(args[:4], ['docker', 'exec', 'n8n', 'node'])
            self.assertNotIn('process.env', args[5])
            self.assertNotIn('fetch(', args[5])

    def test_custom_workspace_switch_and_duplicate_config_keys(self):
        config = {'ENZYMIND_WORKSPACE_DB': '${PROJECT_DIR}/private/research.sqlite'}
        self.assertEqual(deploy.marker_path(config), self.root / 'private/python.disabled')
        updated = deploy.merge_settings('export ENZYMIND_PYTHON_ENABLED=true\nENZYMIND_PYTHON_ENABLED=false\nKEEP=yes\n',
                                        {'ENZYMIND_PYTHON_ENABLED': 'true'})
        self.assertEqual(updated.count('ENZYMIND_PYTHON_ENABLED='), 1)
        self.assertIn('KEEP=yes', updated)

    def test_runtime_status_cannot_claim_ready_when_maintenance_is_active(self):
        config = deploy.settings(self.text) | {'ENZYMIND_PYTHON_AGENT_IPS': '172.17.0.2'}
        marker = deploy.marker_path(config)
        marker.parent.mkdir(parents=True)
        marker.touch()
        with self.assertRaisesRegex(deploy.DeploymentError, 'maintenance'):
            deploy.status(config)
        self.health.assert_not_called()


class BuildIdentityTests(unittest.TestCase):
    def test_reuse_identity_changes_for_each_executable_or_lock_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = ('Dockerfile', '.dockerignore', 'requirements.lock', 'bootstrap.py', 'science_smoke.py')
            for name in names:
                (root / name).write_text(name)
            original = build_fingerprint(root, 'pinned-base')
            for name in names:
                (root / name).write_text('changed')
                self.assertNotEqual(build_fingerprint(root, 'pinned-base'), original)
                (root / name).write_text(name)
            self.assertNotEqual(build_fingerprint(root, 'different-base'), original)

    def test_reuse_requires_matching_inputs_and_an_existing_exact_image(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('Dockerfile', '.dockerignore', 'requirements.lock', 'bootstrap.py', 'science_smoke.py'):
                (root / name).write_text(name)
            base = 'python:3.12-slim@sha256:' + 'a' * 64
            image = 'sha256:' + 'b' * 64
            output = root / 'image-manifest.json'
            for fingerprint_matches, image_exists in ((True, True), (False, True), (True, False)):
                with self.subTest(fingerprint_matches=fingerprint_matches, image_exists=image_exists):
                    output.write_text(json.dumps({'image_id': image, 'build_fingerprint':
                        build_fingerprint(root, base) if fingerprint_matches else 'old-inputs'}))
                    def inspected(args):
                        if 'info' in args:
                            return json.dumps({'SecurityOptions': ['name=rootless']}).encode()
                        return json.dumps([{'Id': image, 'RepoDigests': []}]).encode()
                    def called(args, **kwargs):
                        if 'inspect' in args:
                            return subprocess.CompletedProcess(args, 0 if image_exists else 1,
                                                               json.dumps([{'Id': image}]), '')
                        return subprocess.CompletedProcess(args, 0)
                    with patch('sys.argv', ['build_image', '--base', base, '--output', str(output), '--reuse']), \
                            patch.object(build_image, '__file__', str(root / 'build_image.py')), \
                            patch.object(build_image.subprocess, 'check_output', side_effect=inspected), \
                            patch.object(build_image.subprocess, 'run', side_effect=called) as run, \
                            contextlib.redirect_stdout(io.StringIO()):
                        build_image.main()
                    rebuilt = any('build' in call.args[0] for call in run.call_args_list)
                    self.assertEqual(rebuilt, not (fingerprint_matches and image_exists))


class FreshHostTests(unittest.TestCase):
    def test_gateway_absent_is_explicitly_skipped_but_unhealthy_gateway_fails(self):
        for response in (200, 503, 'absent'):
            with self.subTest(response=response):
                def handler(request):
                    self.assertNotIn('authorization', request.headers)
                    if response == 'absent':
                        raise httpx.ConnectError('not started', request=request)
                    return httpx.Response(response)
                real_client = httpx.AsyncClient
                with patch('services.python_sandbox.http_acceptance.httpx.AsyncClient',
                           side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs)):
                    if response == 503:
                        with self.assertRaises(AssertionError):
                            asyncio.run(gateway_under_load())
                    else:
                        self.assertEqual(asyncio.run(gateway_under_load()), response == 200)


if __name__ == '__main__':
    unittest.main()
