from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from services.python_sandbox.deploy import apt_prerequisites as apt


class AptDeploymentTests(unittest.TestCase):
    def test_resume_skips_apt_when_all_prerequisites_are_installed(self):
        with patch('sys.argv', ['apt_prerequisites.py']), \
                patch.object(apt.os, 'geteuid', return_value=0), \
                patch.object(apt.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'ii \n' * 4, '')) as run, \
                patch.object(apt, 'download') as download:
            apt.main()
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][0], 'dpkg-query')
            download.assert_not_called()

    def test_unconfigured_or_missing_dependency_does_not_skip_installation(self):
        for code, output in [(0, 'ii \nii \nii \niU \n'), (1, 'ii \n' * 3), (0, 'ii \n' * 3)]:
            with patch.object(apt.subprocess, 'run', return_value=subprocess.CompletedProcess([], code, output, '')):
                self.assertFalse(apt.prerequisites_installed())

    def test_sources_pin_distribution_keyring_and_reject_injected_codename(self):
        sources, keyring = apt.official_sources({'ID': 'debian', 'VERSION_CODENAME': 'trixie'}, 'amd64')
        self.assertIn('Signed-By: ' + keyring, sources)
        self.assertNotIn('trusted=yes', sources)
        for codename in ('', 'trixie\nTrusted: yes', 'trixie main'):
            with self.assertRaises(ValueError):
                apt.official_sources({'ID': 'debian', 'VERSION_CODENAME': codename}, 'amd64')

    def test_real_apt_config_excludes_host_sources_and_update_hooks(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            env = apt.configure(directory, 'Types: deb\n', 'http://127.0.0.1:7890', check=True)
            config = subprocess.check_output(['apt-config', 'dump'], env=env, text=True)
            self.assertIn(f'Dir::Etc::sourcelist "{directory}/official.sources"', config)
            self.assertIn(f'Dir::State::lists "{directory}/lists"', config)
            self.assertIn(f'Dir::State::extended_states "{directory}/extended_states"', config)
            self.assertIn('APT::Get::AllowUnauthenticated "false"', config)
            self.assertIn('Acquire::Retries "0"', config)
            self.assertNotIn('Post-Invoke', config)
            self.assertNotIn('/etc/apt/sources.list', config)
            self.assertNotIn('/var/lib/apt/lists', config)

    def test_metadata_failure_never_reaches_dependency_install(self):
        with patch('sys.argv', ['apt_prerequisites.py', '--check']), \
                patch.object(apt.platform, 'freedesktop_os_release', return_value={'ID': 'debian', 'VERSION_CODENAME': 'trixie'}), \
                patch.object(apt.subprocess, 'check_output', return_value='amd64\n'), \
                patch.object(apt.time, 'sleep'), \
                patch.object(apt.subprocess, 'run', side_effect=subprocess.CalledProcessError(100, 'apt-get')) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                apt.main()
            self.assertEqual(run.call_count, 3)
            self.assertTrue(all(call.args[0] == ['apt-get', 'update'] for call in run.call_args_list))

    def test_transient_download_retry_stops_after_success(self):
        with patch.object(apt.time, 'sleep'), patch.object(apt.subprocess, 'run',
                side_effect=[subprocess.CalledProcessError(100, 'apt-get'), None]) as run:
            apt.download(['apt-get', 'update'], {})
            self.assertEqual(run.call_count, 2)

    def test_proxy_rejection_precedes_package_operations(self):
        with tempfile.TemporaryDirectory() as temporary:
            for proxy in ('http://user:secret@localhost:7890', 'http://example.com:80', 'http://127.0.0.1:7890/\n'):
                with self.assertRaises(ValueError):
                    apt.configure(Path(temporary), '', proxy)
            self.assertEqual(list(Path(temporary).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
