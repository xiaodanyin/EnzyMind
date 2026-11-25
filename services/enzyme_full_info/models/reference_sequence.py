"""Read-only reference sequence for inspecting historical result cards."""
from datetime import datetime, timezone
import threading

from shared.uniprot import uniprot_sequence_client, UniProtDownloadError

_slots = threading.BoundedSemaphore(4)


def reference_sequence(accession):
    if not _slots.acquire(blocking=False):
        return {'success': False, 'http_status': 429, 'error': 'Reference sequences are busy. Please retry shortly.'}
    try:
        requested = accession.strip().upper()
        item = uniprot_sequence_client.fetch(requested, budget_seconds=15)
        source = item.source or {}
        return {'success': True, 'requested_accession': requested, 'uniprot_id': item.accession,
                'sequence_info': {'sequence': item.sequence, 'length': len(item.sequence)},
                'source': {**{k: source[k] for k in ('name', 'method', 'snapshot_created_at', 'release') if k in source},
                           'name': source.get('name', 'UniProt'), 'method': source.get('method', 'uniprot_api'),
                           'retrieved_at': datetime.fromtimestamp(item.retrieved_at, timezone.utc).isoformat(),
                           'cache_hit': item.cache_hit}}
    except UniProtDownloadError as exc:
        status = 422 if exc.code == 'uniprot_invalid_accession' else 404 if exc.code == 'uniprot_not_found' else 503
        return {'success': False, 'http_status': status, 'error': str(exc)}
    finally:
        _slots.release()
