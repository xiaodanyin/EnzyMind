"""Bounded EnzyMind-owned cache of validated public UniProt JSON responses."""
from contextlib import closing
import hashlib
import logging
import os
from pathlib import Path
import sqlite3
import time

logger = logging.getLogger(__name__)


class UniProtJSONCache:
    MAX_RECORD_BYTES = 4 * 1024 * 1024
    MAX_BYTES = 64 * 1024 * 1024
    MAX_ENTRIES = 256
    MAX_AGE = 30 * 86400
    FRESH_AGE = 6 * 3600

    def __init__(self):
        self.path = os.environ.get('ENZYMIND_UNIPROT_CACHE_PATH', '').strip()

    def _path(self):
        path = Path(self.path).expanduser().resolve()
        snapshot = os.environ.get('ENZYMIND_UNIPROT_LOCAL_DB_PATH', '').strip()
        if snapshot:
            reference = Path(snapshot).expanduser().resolve()
            if path == reference or (path.exists() and reference.exists() and path.samefile(reference)):
                raise ValueError('Cache must be separate from the read-only snapshot.')
        return path

    def get(self, accession, *, stale=False):
        if not self.path:
            return None
        try:
            with closing(sqlite3.connect(self._path().as_uri() + '?mode=ro', uri=True, timeout=1)) as db:
                db.execute('PRAGMA query_only=ON')
                row = db.execute('SELECT payload,checksum,fetched_at FROM entries WHERE accession=? AND length(CAST(payload AS BLOB))<=?',
                                 (accession, self.MAX_RECORD_BYTES)).fetchone()
            if not row:
                return None
            text, checksum, fetched_at = row
            if not isinstance(text, str) or not isinstance(fetched_at, (int, float)):
                return None
            age = time.time() - fetched_at
            if not 0 <= age <= (self.MAX_AGE if stale else self.FRESH_AGE):
                return None
            if hashlib.sha256(text.encode()).hexdigest() != checksum:
                return None
            return text, fetched_at
        except (OSError, sqlite3.Error, ValueError, TypeError):
            return None

    def put(self, accession, text, fetched_at):
        if not self.path or len(text.encode()) > self.MAX_RECORD_BYTES:
            return
        try:
            path = self._path()
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if not path.exists():
                try:
                    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                    os.close(fd)
                except FileExistsError:
                    pass
            with closing(sqlite3.connect(path, timeout=1)) as db, db:
                # 128 MiB physical ceiling including free pages; logical contents
                # are kept below 64 MiB. No journal-mode changes on other databases.
                page_size = db.execute('PRAGMA page_size').fetchone()[0]
                db.execute(f'PRAGMA max_page_count={self.MAX_BYTES * 2 // page_size}')
                db.execute('CREATE TABLE IF NOT EXISTS entries (accession TEXT PRIMARY KEY, payload TEXT NOT NULL, checksum TEXT NOT NULL, fetched_at REAL NOT NULL, size INTEGER NOT NULL)')
                db.execute('DELETE FROM entries WHERE fetched_at<?', (time.time() - self.MAX_AGE,))
                db.execute('INSERT OR REPLACE INTO entries VALUES (?,?,?,?,?)',
                           (accession, text, hashlib.sha256(text.encode()).hexdigest(), fetched_at, len(text.encode())))
                sizes = db.execute('SELECT accession,size FROM entries ORDER BY fetched_at DESC,accession').fetchall()
                total = 0
                for index, (key, size) in enumerate(sizes):
                    total += size
                    if index >= self.MAX_ENTRIES or total > self.MAX_BYTES:
                        db.execute('DELETE FROM entries WHERE accession=?', (key,))
        except (OSError, sqlite3.Error, ValueError):
            # A cache outage must never fail an otherwise successful lookup.
            logger.warning('UniProt response cache write unavailable')
