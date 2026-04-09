# active_sites/conftest.py
"""
Pytest configuration for active_sites service tests.
"""

import sys
from pathlib import Path

# Add the service root directory to Python path
service_root = Path(__file__).parent
if str(service_root) not in sys.path:
    sys.path.insert(0, str(service_root))
