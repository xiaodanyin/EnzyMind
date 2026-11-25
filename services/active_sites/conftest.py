# active_sites/conftest.py
"""
Pytest configuration for active_sites service tests.
"""

import sys
import pytest
from pathlib import Path

# Add the service root directory to Python path
service_root = Path(__file__).parent
if str(service_root) not in sys.path:
    sys.path.insert(0, str(service_root))


@pytest.fixture(autouse=True)
def isolated_easifa_identity(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("ENZYMIND_EASIFA_COOKIE_SECURE", "false")
    for name in ("ENZYMIND_EASIFA_SESSION_KEY", "ENZYMIND_EASIFA_SESSION_FILE", "ENZYMIND_EASIFA_API_BASE", "EASIFA_API_BASE"):
        monkeypatch.delenv(name, raising=False)
    import main
    monkeypatch.setattr(main, "predictor", None)
