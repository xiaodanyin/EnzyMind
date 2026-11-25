"""Resolve generated PDBs using the structure service's directory settings."""
import os
import re
from pathlib import Path

MAX_PDB_BYTES = 20_000_000


def valid_pdb_name(name):
    return bool(re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,200}\.pdb", name, re.I))


def read_generated_pdb(name, *, legacy=False):
    """Read a bounded regular file, never following a job/file symlink.

    New jobs use output/<job>/<job>.pdb and static/<job>.pdb. Older
    installations wrote directly to /tmp/esmfold_output. No recursive scan
    or client-supplied directory is needed to support either layout.
    """
    if not valid_pdb_name(name):
        return None
    roots = [
        Path(os.getenv("STATIC_PDB_DIR", "/tmp/static/pdb")),
        Path(os.getenv("ESMFOLD_OUTPUT_DIR", "/tmp/esmfold_output")),
    ]
    if legacy:
        roots.extend((Path("/tmp/static/pdb"), Path("/tmp/esmfold_output")))
    for root in dict.fromkeys(path.resolve() for path in roots):
        for candidate in (root / name, root / Path(name).stem / name):
            try:
                if candidate.resolve() != candidate or not candidate.is_file():
                    continue
                if candidate.stat().st_size > MAX_PDB_BYTES:
                    continue
                # Bound the read as well, in case the file grows after stat().
                with candidate.open("rb") as stream:
                    content = stream.read(MAX_PDB_BYTES + 1)
                if len(content) <= MAX_PDB_BYTES:
                    return content.decode("utf-8")
            except (OSError, UnicodeDecodeError, RuntimeError):
                continue
    return None
