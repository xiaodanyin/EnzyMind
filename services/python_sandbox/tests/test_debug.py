import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from services.python_sandbox.debug import local_config


class DebugConfigTests(unittest.TestCase):
    def test_debug_config_requires_private_local_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            config=Path(directory)/'runner.env'
            config.write_text('PYTHON_SANDBOX_TOKEN='+'k'*48+'\n')
            config.chmod(0o600)
            with patch.dict(os.environ,{},clear=True):
                self.assertEqual(local_config(config)[0],'http://127.0.0.1:8091')
                config.chmod(0o644)
                with self.assertRaisesRegex(ValueError,'0600'):
                    local_config(config)

    def test_debug_never_sends_credentials_to_remote_or_ambiguous_urls(self):
        for url in ['http://example.com:8091','http://127.0.0.1.evil:8091','http://user@127.0.0.1:8091',
                    'http://127.0.0.1:8091/jobs','http://127.0.0.1:8091?target=evil','http://127.0.0.1:8091#evil']:
            with self.subTest(url=url),patch.dict(os.environ,{'PYTHON_SANDBOX_TOKEN':'k'*48,'ENZYMIND_PYTHON_RUNNER_URL':url}):
                with self.assertRaisesRegex(ValueError,'loopback'):
                    local_config(None)


if __name__=='__main__':
    unittest.main()
