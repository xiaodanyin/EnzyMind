"""Bounded, verified downloads of public AlphaFold reference models.

No prediction service is invoked. The EasIFA snapshot and its services are
never modified; this cache belongs solely to EnzyMind.
"""
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import threading
import time

import requests
from shared.uniprot import ACCESSION, P256Adapter, TLS12Adapter
from shared.uniprot_cache import UniProtJSONCache

HOST = 'https://alphafold.ebi.ac.uk'


class StructureCache(UniProtJSONCache):
    MAX_RECORD_BYTES = 6 * 1024 * 1024
    MAX_ENTRIES = 32
    FRESH_AGE = 7 * 86400

    def __init__(self):
        self.path = os.environ.get('ENZYMIND_REFERENCE_STRUCTURE_CACHE_PATH',
                                   str(Path(__file__).resolve().parents[3] / 'files' / 'reference-structures.sqlite')).strip()

    def _path(self):
        path = super()._path()
        other = os.environ.get('ENZYMIND_UNIPROT_CACHE_PATH', '').strip()
        if other:
            reference = Path(other).expanduser().resolve()
            if path == reference or (path.exists() and reference.exists() and path.samefile(reference)):
                raise ValueError('Structure and annotation caches must be separate.')
        return path


class ModelUnavailable(ValueError):
    pass


def validate_model(text):
    """Require finite coordinates, without inventing or renumbering residues."""
    count = 0
    for line in text.splitlines():
        if line.startswith('ATOM  ') and line[12:16].strip() == 'CA':
            if len(line) < 54 or not all(math.isfinite(float(line[a:b])) for a, b in ((30, 38), (38, 46), (46, 54))):
                raise ValueError('Invalid coordinates')
            int(line[22:26])
            count += 1
    if not count:
        raise ValueError('No protein coordinates')


def model_url(record, accession):
    url = record.get('pdbUrl', '')
    if (record.get('uniprotAccession') != accession or record.get('isComplex') is True
            or not re.fullmatch(re.escape(HOST) + '/files/AF-' + re.escape(accession) + r'-F[1-9]\d*-model_v[1-9]\d*\.pdb', url)):
        raise ValueError('Unexpected model identity or URL')
    return url


class ReferenceStructure:
    def __init__(self):
        self.cache = StructureCache()
        self.lock = threading.Lock()
        self.active = set()

    def _cached(self, accession, stale=False):
        item = self.cache.get(accession, stale=stale)
        if not item:
            return None
        try:
            data = json.loads(item[0])
            if data['uniprot_id'] != accession or data['structure_format'] != 'pdb':
                return None
            validate_model(data['structure_data'])
            data['source']['stale'] = stale
            data['source']['cache_hit'] = True
            return data
        except (ValueError, KeyError, TypeError):
            return None

    @staticmethod
    def _read(session, url, limit, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise requests.Timeout()
        with session.get(url, timeout=(min(4, remaining), min(7, remaining)), stream=True, allow_redirects=False) as response:
            if response.status_code == 404:
                raise ModelUnavailable()
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError('Unexpected redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(32768):
                size += len(chunk)
                if size > limit or time.monotonic() > deadline:
                    raise ValueError('Download exceeds limits')
                chunks.append(chunk)
            return b''.join(chunks).decode('utf-8')

    def fetch(self, accession):
        accession = accession.strip().upper()
        if not re.fullmatch(ACCESSION, accession):
            return {'success': False, 'http_status': 422, 'error': 'Invalid UniProt accession.'}
        cached = self._cached(accession)
        if cached:
            return cached
        with self.lock:
            if accession in self.active or len(self.active) >= 2:
                return {'success': False, 'http_status': 429, 'error': 'Reference models are busy. Try loading the structure again shortly.'}
            self.active.add(accession)
        try:
            deadline = time.monotonic() + 22
            for adapter in (P256Adapter, TLS12Adapter):
                try:
                    with requests.Session() as session:
                        session.mount(HOST + '/', adapter(max_retries=0))
                        records = json.loads(self._read(session, f'{HOST}/api/prediction/{accession}', 1024 * 1024, deadline))
                        if not isinstance(records, list):
                            raise ValueError('Invalid metadata')
                        candidates = [r for r in records if isinstance(r, dict) and r.get('uniprotAccession') == accession and not r.get('isComplex')]
                        if not candidates:
                            raise ModelUnavailable()
                        # Prefer the first monomer fragment; retain coverage in metadata.
                        record = next((r for r in candidates if r.get('entryId') == f'AF-{accession}-F1'), candidates[0])
                        url = model_url(record, accession)
                        structure = self._read(session, url, 5 * 1024 * 1024, deadline)
                        validate_model(structure)
                        now = time.time()
                        data = {'success': True, 'uniprot_id': accession, 'structure_data': structure, 'structure_format': 'pdb',
                                'source': {'name': 'AlphaFold DB', 'kind': 'predicted', 'url': f'{HOST}/entry/{accession}',
                                           'model_url': url, 'version': record.get('latestVersion'),
                                           'sequence_start': record.get('uniprotStart'), 'sequence_end': record.get('uniprotEnd'),
                                           'mean_plddt': record.get('globalMetricValue'),
                                           'retrieved_at': datetime.fromtimestamp(now, timezone.utc).isoformat(), 'stale': False}}
                        self.cache.put(accession, json.dumps(data), now)
                        return data
                except ModelUnavailable:
                    return {'success': False, 'http_status': 404, 'error': 'No AlphaFold reference model is available for this accession. Sequence and annotations remain available.'}
                except (requests.RequestException, ValueError, TypeError, KeyError):
                    if time.monotonic() >= deadline:
                        break
            cached = self._cached(accession, stale=True)
            if cached:
                return cached
            return {'success': False, 'http_status': 502, 'error': 'The reference structure could not be retrieved. Sequence and annotations remain available; you can retry the structure separately.'}
        finally:
            with self.lock:
                self.active.discard(accession)


reference_structure = ReferenceStructure()
