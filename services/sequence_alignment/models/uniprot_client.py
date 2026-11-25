"""Backward-compatible import path for the shared verified UniProt client."""
import sys
from pathlib import Path

root = str(Path(__file__).resolve().parents[3])
if root not in sys.path:
    sys.path.insert(0, root)

from shared.uniprot import *  # Existing BLAST imports keep the same API.
