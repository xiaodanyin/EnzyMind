"""Independent read-only access to an EasIFA-compatible UniProt snapshot.

No EasIFA imports, migrations, cache writes, or service calls are performed.
"""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time

from .uniprot_sections import local_scope, protein_name, reaction_smiles


class LocalUniProtError(ValueError):
    pass


class LocalUniProt:
    MAX_SEQUENCE = 1024 * 1024
    MAX_JSON = 4 * 1024 * 1024

    def __init__(self, path=None):
        self.path = path if path is not None else os.environ.get('ENZYMIND_UNIPROT_LOCAL_DB_PATH', '').strip()

    def _connect(self):
        path = Path(self.path).expanduser().resolve(strict=True)
        if not path.is_file():
            raise LocalUniProtError('Local UniProt snapshot is not a file.')
        # Do not use immutable=1: deployments may atomically replace snapshots.
        db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=2)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        db.execute('PRAGMA trusted_schema=OFF')
        db.execute('PRAGMA cache_size=-2048')
        deadline = time.monotonic() + 2
        db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        return db

    def fetch(self, accession, annotations=False):
        if not self.path:
            return None
        try:
            with closing(self._connect()) as db:
                meta = dict(db.execute("SELECT key,value FROM uniprot_meta WHERE key IN ('schema_version','created_at','uniprot_release')"))
                if meta.get('schema_version') != '1':
                    raise LocalUniProtError('Unsupported local UniProt schema.')
                # Parameterized exact-accession lookup, including secondary IDs.
                # Isoforms are never silently replaced with canonical sequences.
                row = db.execute('''SELECT e.primary_accession, e.sequence_value, e.sequence_length,
                    CASE WHEN length(e.payload_zstd) <= ? THEN e.payload_zstd END AS payload,
                    e.payload_json_sha256
                    FROM uniprot_accession a JOIN uniprot_entry e USING(primary_accession)
                    WHERE a.accession = ? AND length(e.sequence_value) <= ?''',
                    (self.MAX_JSON if annotations else 0, accession, self.MAX_SEQUENCE)).fetchone()
                numbers, reactions, identity = [], [], {}
                if annotations and row:
                    primary = row['primary_accession']
                    tables = {r[0] for r in db.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('uniprot_ec','uniprot_reaction')")}
                    if 'uniprot_ec' in tables:
                        numbers = [r[0] for r in db.execute(
                            'SELECT ec_number FROM uniprot_ec WHERE primary_accession=? ORDER BY ec_number LIMIT 256', (primary,))]
                    if 'uniprot_reaction' in tables:
                        reactions = [dict(r) for r in db.execute(
                            'SELECT ec_number AS ecNumber, rhea_id AS rheaId, rxn_smiles AS rxnSmiles '
                            'FROM uniprot_reaction WHERE primary_accession=? ORDER BY ordinal LIMIT 512', (primary,))]
                    columns = {r['name'] for r in db.execute('PRAGMA table_info(uniprot_entry)')}
                    fields = [k for k in ('protein_name', 'organism_name', 'entry_type', 'reviewed', 'alphafold_id') if k in columns]
                    if fields:
                        identity = dict(db.execute('SELECT ' + ','.join(fields) +
                            ' FROM uniprot_entry WHERE primary_accession=?', (primary,)).fetchone())
            if row is None:
                return None
            sequence = row['sequence_value']
            if not isinstance(sequence, str) or not re.fullmatch(r'[ACDEFGHIKLMNPQRSTVWYBXZJUO]+', sequence):
                raise LocalUniProtError('Invalid sequence in local UniProt snapshot.')
            if row['sequence_length'] != len(sequence):
                raise LocalUniProtError('Local UniProt sequence length mismatch.')
            primary = row['primary_accession']
            if '-' in accession and primary != accession:
                raise LocalUniProtError('Local UniProt snapshot cannot resolve this exact isoform.')
            source = {'name': 'Local UniProt snapshot', 'method': 'local_snapshot',
                      'accession': primary, 'requested_accession': accession,
                      'snapshot_created_at': meta.get('created_at'),
                      'release': meta.get('uniprot_release'),
                      'annotation_scope': ['sequence'],
                      'note': 'Read from the configured UniProt annotation snapshot.'}
            if not annotations:
                return primary, sequence, source
            if not row['payload']:
                raise LocalUniProtError('Local UniProt annotation exceeds the supported size.')
            import zstandard
            # stream_reader plus a bounded read also limits frames advertising a
            # misleading/unknown decompressed size, unlike unbounded decompress().
            with zstandard.ZstdDecompressor(max_window_size=self.MAX_JSON // 1024).stream_reader(row['payload']) as reader:
                raw = reader.read(self.MAX_JSON + 1)
            if len(raw) > self.MAX_JSON or hashlib.sha256(raw).hexdigest() != row['payload_json_sha256']:
                raise LocalUniProtError('Local UniProt annotation integrity check failed.')
            data = json.loads(raw)
            if not isinstance(data, dict) or data.get('primaryAccession') != primary or data.get('sequence', {}).get('value') != sequence:
                raise LocalUniProtError('Local UniProt annotation does not match its index.')
            if accession != primary and accession not in data.get('secondaryAccessions', []):
                raise LocalUniProtError('Local UniProt secondary accession mismatch.')
            # XML-derived snapshot labels differ in capitalization from REST JSON.
            for feature in data.get('features', []):
                if isinstance(feature, dict):
                    location = feature.get('location') or {}
                    if isinstance(location.get('position'), dict):
                        for bound in ('start', 'end'):
                            location.setdefault(bound, location['position'])
                    feature['type'] = {'Binding Site': 'Binding site', 'Active Site': 'Active site'}.get(feature.get('type'), feature.get('type'))
            # Some releases put these projections only in the indexed tables.
            if identity.get('protein_name') and not protein_name(data):
                desc = data.setdefault('proteinDescription', {}).setdefault('recommendedName', {})
                desc['fullName'] = {'value': identity['protein_name']}
            if identity.get('organism_name'):
                data.setdefault('organism', {}).setdefault('scientificName', identity['organism_name'])
            if not data.get('entryType'):
                if identity.get('entry_type'):
                    data['entryType'] = identity['entry_type']
                elif identity.get('reviewed') in (0, 1):
                    data['entryType'] = 'UniProtKB reviewed' if identity['reviewed'] else 'UniProtKB unreviewed'
            if identity.get('alphafold_id'):
                refs = data.setdefault('uniProtKBCrossReferences', [])
                if not any(r.get('database') == 'AlphaFoldDB' for r in refs):
                    refs.append({'database': 'AlphaFoldDB', 'id': identity['alphafold_id']})
            if reactions:
                rows = data.setdefault('easifaLocal', {}).setdefault('reactions', [])
                known = set(reaction_smiles(data))
                for reaction in reactions:
                    rhea = str(reaction['rheaId'] or '').removeprefix('RHEA:')
                    if rhea and reaction['rxnSmiles'] and rhea not in known:
                        rows.append(reaction)
                        known.add(rhea)
            if numbers:
                data['enzymindEcNumbers'] = numbers
            source['annotation_scope'] = local_scope(data, ['sequence'])
            data['enzymindSource'] = source
            return primary, json.dumps(data, ensure_ascii=False), source
        except LocalUniProtError:
            raise
        except Exception as exc:
            # Do not expose host paths, SQLite internals, or payloads to callers.
            raise LocalUniProtError(f'Local UniProt snapshot could not be read ({type(exc).__name__}).') from None
