"""Exercise legacy deploy selection with disposable fake package installers."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class DeployEntryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        (self.root / 'scripts').mkdir()
        shutil.copyfile(ROOT / 'scripts/deploy.sh', self.root / 'scripts/deploy.sh')
        package = self.root / 'services/python_sandbox/deploy'
        package.mkdir(parents=True)
        shutil.copyfile(ROOT / 'services/python_sandbox/deploy/integrate.py', package / 'integrate.py')
        self.log = self.root / 'calls'
        self.env = {**os.environ, 'ENZYMIND_ENV_FILE': str(self.root / '.env.production'), 'DEPLOY_CALL_LOG': str(self.log)}
        for name in ('enzyme_check', 'ecnumber_predict'):
            directory = self.root / 'services' / name
            (directory / 'venv/bin').mkdir(parents=True)
            (directory / 'requirements.txt').touch()
            python = directory / 'venv/bin/python'
            python.write_text('#!/bin/bash\nprintf "%s\\n" "$PWD:$*" >> "$DEPLOY_CALL_LOG"\nexit "${FAKE_PIP_FAILURE:-0}"\n')
            python.chmod(0o755)

    def run_script(self, *args):
        return subprocess.run(['bash', str(self.root / 'scripts/deploy.sh'), *args],
                              cwd='/tmp', env=self.env, text=True, capture_output=True, timeout=10)

    def test_selected_legacy_services_only_and_no_duplicate_work(self):
        result = self.run_script('enzyme_check', 'enzyme_check')
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.log.read_text().splitlines()
        self.assertEqual(len(calls), 1)
        self.assertIn('enzyme_check:-m pip install -r requirements.txt', calls[0])

    def test_install_failure_returns_nonzero(self):
        self.env['FAKE_PIP_FAILURE'] = '7'
        result = self.run_script('enzyme_check')
        self.assertEqual(result.returncode, 1)
        self.assertIn('FAILED: enzyme_check', result.stderr)

    def test_uniprot_stage_only_updates_shared_query_dependencies_and_checks_snapshot(self):
        result = self.run_script('uniprot')
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.log.read_text().splitlines()
        self.assertEqual(len(calls), 2)
        self.assertIn('shared/requirements-uniprot.txt', calls[0])
        self.assertIn('scripts/check_uniprot.py --env-file', calls[1])
        self.assertNotIn('install_torch', result.stdout)

    def test_default_optional_sandbox_and_dry_run_have_no_install_side_effects(self):
        result = self.run_script('--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('  gateway\n  frontend\n', result.stdout)
        self.assertNotIn('  python_sandbox\n', result.stdout)
        (self.root / '.env.production').write_text('ENZYMIND_PYTHON_ENABLED=true\n')
        result = self.run_script('--dry-run')
        self.assertIn('  python_sandbox\n', result.stdout)
        self.assertFalse(self.log.exists())
        self.assertFalse((self.root / '.pids').exists())

    def test_invalid_service_or_missing_flag_value_never_installs(self):
        for args in [('typo_service',), ('--proxy',), ('--unknown',), ('gateway', '--check')]:
            with self.subTest(args=args):
                self.assertEqual(self.run_script(*args).returncode, 2)
                self.assertFalse(self.log.exists())


if __name__ == '__main__':
    unittest.main()
