"""Exact-accession reads from a portable EnzyMind BLAST release, without a similarity search."""
import json
import os
from pathlib import Path
import re
import subprocess

from .uniprot_local import LocalUniProtError
from .uniprot_sections import local_scope


def fetch_index(accession, annotations=False):
    setting = os.getenv('ENZYMIND_UNIPROT_SEQUENCE_INDEX') or os.getenv('ENZYMIND_BLAST_DB')
    if not setting:
        return None
    prefix = Path(setting).expanduser().resolve()
    try:
        meta = json.loads(prefix.with_name('manifest.json').read_text())
        if meta['prefix'] != prefix.name or not meta['sequences']:
            raise ValueError('Invalid index manifest')
        bins = os.getenv('ENZYMIND_BLAST_BIN_DIR')
        binary = str(Path(bins).expanduser().resolve() / 'blastdbcmd') if bins else 'blastdbcmd'
        result = subprocess.run([binary, '-db', prefix.name, '-entry', accession, '-outfmt', '%i\t%a\t%t\t%s'],
                                cwd=prefix.parent, timeout=5, capture_output=True, text=True)
        if result.returncode:
            if 'Entry not found: ' + accession in result.stderr:
                return None
            raise ValueError('Index read failed')
        seqid, primary, title, sequence = result.stdout.rstrip('\n').split('\t')
        if primary != accession or len(sequence) > 1024 * 1024 or not re.fullmatch('[ACDEFGHIKLMNPQRSTVWYBXZJUO]+', sequence):
            raise ValueError('Invalid index sequence')
        name, _, species = title.partition(' OS=')
        data = {'primaryAccession': primary, 'sequence': {'value': sequence, 'length': len(sequence)}}
        if name:
            data['proteinDescription'] = {'recommendedName': {'fullName': {'value': name}}}
        if species:
            data['organism'] = {'scientificName': re.split(r' (?:OX|GN|PE|SV)=', species)[0]}
        if seqid.startswith(('sp|', 'tr|')):
            data['entryType'] = 'UniProtKB reviewed' if seqid.startswith('sp|') else 'UniProtKB unreviewed'
        src = {'name': 'Local UniProt sequence index', 'method': 'local_snapshot', 'dataset': 'blast_sequence_index',
               'accession': primary, 'requested_accession': accession, 'release': meta['release'],
               'annotation_scope': local_scope(data, ['sequence']),
               'note': 'This release provides sequence and indexed protein identity.'}
        data['enzymindSource'] = src
        return primary, json.dumps(data) if annotations else sequence, src
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        raise LocalUniProtError('Local UniProt sequence index could not be read.') from exc
