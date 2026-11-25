#!/usr/bin/env python3
"""Read-only deployment check. Read only UniProt settings, never print secrets."""
import argparse
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.uniprot_local import LocalUniProt, LocalUniProtError
from shared.uniprot_index import fetch_index
from shared.uniprot_cache import UniProtJSONCache


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--accession', default='P12345')
    args = parser.parse_args()
    key = 'ENZYMIND_UNIPROT_LOCAL_DB_PATH'
    cache_key = 'ENZYMIND_UNIPROT_CACHE_PATH'
    index_key = 'ENZYMIND_UNIPROT_SEQUENCE_INDEX'
    settings = {key, cache_key, index_key, 'ENZYMIND_BLAST_DB', 'ENZYMIND_BLAST_BIN_DIR'}
    if args.env_file and args.env_file.exists():
        for line in args.env_file.read_text().splitlines():
            name, separator, value = line.removeprefix('export ').partition('=')
            if separator and name.strip() in settings:
                parts = shlex.split(value, comments=True)
                os.environ[name.strip()] = parts[0] if parts else ''
    path = os.environ.get(key)
    if os.environ.get(cache_key):
        cache_path = UniProtJSONCache()._path()
        cache_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if cache_path.exists() and (not cache_path.is_file() or not os.access(cache_path, os.W_OK)):
            raise ValueError('UniProt API cache is not a writable file.')
        with tempfile.TemporaryFile(dir=cache_path.parent):
            pass
        print('UniProt: separate API annotation cache configured; writable directory verified.')
    index = os.environ.get(index_key) or os.environ.get('ENZYMIND_BLAST_DB')
    if index:
        record = fetch_index(args.accession, annotations=True)
        if not record:
            raise LocalUniProtError('The deployment probe accession is absent from the configured sequence index.')
        print(json.dumps({'status': 'ready', 'mode': 'sequence_index', 'accession': record[0],
                          'release': record[2]['release'], 'annotation_scope': record[2]['annotation_scope']}))
    if not path:
        if not index:
            print('UniProt: no local reference dataset configured.')
        return
    provider = LocalUniProt(path)
    seq = provider.fetch(args.accession)
    doc = provider.fetch(args.accession, annotations=True)
    if not seq or not doc:
        raise LocalUniProtError('The deployment probe accession is absent from the configured snapshot.')
    print(json.dumps({'status': 'ready', 'mode': 'read_only', 'lookup_order': 'local_then_api', 'accession': seq[0],
                      'sequence_length': len(seq[1]), 'snapshot_created_at': seq[2]['snapshot_created_at'],
                      'annotations_verified': True}))


if __name__ == '__main__':
    try:
        main()
    except (LocalUniProtError, ValueError, OSError) as error:
        print(f'UniProt preflight failed: {error}', file=sys.stderr)
        sys.exit(1)
