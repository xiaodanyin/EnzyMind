"""Bounded, verified UniProt FASTA/JSON downloads; no global TLS changes."""
from collections import OrderedDict
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import logging
import json
import re
import ssl
import threading
import time
from urllib.parse import urljoin, urlsplit

import requests
from requests.adapters import HTTPAdapter
from .uniprot_local import LocalUniProt, LocalUniProtError
from .uniprot_cache import UniProtJSONCache
from .uniprot_index import fetch_index
from .uniprot_sections import OVERVIEW, combine

logger = logging.getLogger(__name__)
ACCESSION = r'(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})(?:-[1-9][0-9]*)?'
BASE_URL = 'https://rest.uniprot.org/uniprotkb/'


class UniProtDownloadError(ValueError):
    def __init__(self, message, code='uniprot_unavailable', retryable=True):
        super().__init__(message)
        self.code, self.retryable = code, retryable


class TLS12Adapter(HTTPAdapter):
    """Constrain only this adapter; certificate and hostname checks stay on."""
    def init_poolmanager(self, *args, **kwargs):
        # Let requests load its CA bundle (including REQUESTS_CA_BUNDLE).
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = context.maximum_version = ssl.TLSVersion.TLSv1_2
        self.tls_context = context
        kwargs['ssl_context'] = context
        super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, proxy, **kwargs):
        # Preserve deployment proxy settings; the context is for the destination.
        kwargs['ssl_context'] = self.tls_context
        return super().proxy_manager_for(proxy, **kwargs)


class P256Adapter(TLS12Adapter):
    """Smaller, compatible ClientHello with verified TLS 1.2/1.3."""
    def init_poolmanager(self, *args, **kwargs):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.set_ecdh_curve('prime256v1')
        self.tls_context = context
        kwargs['ssl_context'] = context
        HTTPAdapter.init_poolmanager(self, *args, **kwargs)


@dataclass(frozen=True)
class UniProtSequence:
    accession: str
    sequence: str
    source_url: str
    retrieved_at: float
    cache_hit: bool = False
    source: dict | None = None

    @property
    def size(self):
        return len(self.sequence)


@dataclass(frozen=True)
class UniProtDocument:
    accession: str
    text: str
    source_url: str
    retrieved_at: float
    cache_hit: bool = False
    source: dict | None = None

    @property
    def size(self):
        return len(self.text.encode('utf-8'))


def parse_fasta(text, accession):
    """Reject HTML, multiple records, wrong accessions and damaged sequences."""
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    header = re.match(rf'^>(?:sp|tr)\|({ACCESSION})\|', lines[0]) if lines else None
    if not header or header[1] != accession or any(line.startswith('>') for line in lines[1:]):
        raise UniProtDownloadError('UniProt returned an unexpected FASTA record.', 'uniprot_invalid_response')
    sequence = ''.join(lines[1:])
    if not sequence or not re.fullmatch(r'[ACDEFGHIKLMNPQRSTVWYBXZJUO]+', sequence):
        raise UniProtDownloadError('UniProt returned an empty or invalid protein sequence.', 'uniprot_invalid_response')
    return sequence


def retry_after(value):
    try:
        return max(0., float(value))
    except (TypeError, ValueError):
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            return max(0., (date - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return 0.


class UniProtClient:
    # P-256 avoids the reproduced default-ClientHello stalls on OpenSSL 3.5.
    # Retain TLS 1.2 compatibility and one default-TLS attempt, always verified.
    TLS_MODES = ('P256', 'TLS1.2', 'P256', 'default')
    BUDGET_SECONDS = 60
    CACHE_TTL = 6 * 3600
    CACHE_ENTRIES = 128
    CACHE_BYTES = 4 * 1024 * 1024
    RESPONSE_BYTES = 1024 * 1024
    FORMAT = 'fasta'
    ACCEPT = 'text/plain'
    LOCAL_CACHE_TTL = 60

    def __init__(self):
        self._cache = OrderedDict()
        self._cache_bytes = 0
        self._cache_lock = threading.Lock()
        # Fixed-size locks coalesce concurrent requests without an unbounded map.
        self._downloads = [threading.Lock() for _ in range(64)]

    def _cached(self, accession):
        with self._cache_lock:
            now = time.monotonic()
            for key, (expires, value) in list(self._cache.items()):
                if expires <= now:
                    self._cache.pop(key)
                    self._cache_bytes -= value.size
            if accession in self._cache:
                self._cache.move_to_end(accession)
                return replace(self._cache[accession][1], cache_hit=True)

    def _remember(self, accession, value):
        with self._cache_lock:
            old = self._cache.pop(accession, None)
            if old:
                self._cache_bytes -= old[1].size
            source = value.source or {}
            if source.get('method') == 'local_snapshot' or source.get('stale'):
                ttl = self.LOCAL_CACHE_TTL
            elif source.get('method') == 'uniprot_cache':
                ttl = max(0, min(self.CACHE_TTL, self.CACHE_TTL - (time.time() - value.retrieved_at)))
            else:
                ttl = self.CACHE_TTL
            self._cache[accession] = (time.monotonic() + ttl, value)
            self._cache_bytes += value.size
            while len(self._cache) > self.CACHE_ENTRIES or self._cache_bytes > self.CACHE_BYTES:
                _, (_, removed) = self._cache.popitem(last=False)
                self._cache_bytes -= removed.size

    def fetch(self, accession, local_capability=None, budget_seconds=None):
        accession = accession.strip().upper()
        if not re.fullmatch(ACCESSION, accession):
            raise UniProtDownloadError('Enter a valid UniProt accession.', 'uniprot_invalid_accession', False)
        budget = min(self.BUDGET_SECONDS, budget_seconds or self.BUDGET_SECONDS)
        deadline = time.monotonic() + budget
        lock = self._downloads[hash(accession) % len(self._downloads)]
        if not lock.acquire(timeout=budget):
            raise UniProtDownloadError('Sequence retrieval is busy. Retry shortly, or upload a FASTA file.')
        try:
            if local_capability != 'full':
                local = self.local_record(accession)
                if local and (local_capability is None or local_capability in local.source['annotation_scope']):
                    return local
            cached = self._cached(accession)
            if cached:
                return cached
            value = self._stored(accession)
            if value is None:
                value = self._download(accession, deadline)
            self._remember(accession, value)
            return value
        finally:
            lock.release()

    def _stored(self, accession, *, stale=False):
        # Sequence-only consumers can reuse a verified JSON response saved by another service.
        record = uniprot_json_client._stored(accession, stale=stale)
        if record is None or ('-' in accession and record.accession != accession):
            return None
        block = json.loads(record.text).get('sequence', {})
        sequence = block.get('value', '')
        if not isinstance(sequence, str) or len(sequence) > self.RESPONSE_BYTES or not re.fullmatch(r'[ACDEFGHIKLMNPQRSTVWYBXZJUO]+', sequence):
            return None
        if block.get('length', len(sequence)) != len(sequence):
            return None
        return UniProtSequence(record.accession, sequence, record.source_url, record.retrieved_at, source=record.source)

    def _session(self, mode):
        session = requests.Session()
        if mode == 'P256':
            session.mount('https://rest.uniprot.org/', P256Adapter(max_retries=0))
        elif mode == 'TLS1.2':
            session.mount('https://rest.uniprot.org/', TLS12Adapter(max_retries=0))
        session.headers.update({'Accept': self.ACCEPT, 'Accept-Encoding': 'identity',
                                'User-Agent': 'EnzyMind/1.0 (+https://cadd.zju.edu.cn/enzymind/)'})
        return session

    def _get(self, session, accession, deadline):
        url = f'{BASE_URL}{accession}.{self.FORMAT}'
        for _ in range(4):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise requests.Timeout('UniProt download deadline reached')
            with session.get(url, timeout=(min(8, remaining / 2), min(15, remaining / 2)),
                             stream=True, allow_redirects=False) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    target = urljoin(url, response.headers.get('Location', ''))
                    parts = urlsplit(target)
                    match = re.fullmatch(rf'/uniprotkb/({ACCESSION})\.{self.FORMAT}', parts.path)
                    if (parts.scheme != 'https' or parts.netloc != 'rest.uniprot.org' or
                            not match or parts.query or parts.fragment or target == url):
                        raise UniProtDownloadError('UniProt returned an unsupported redirect.', 'uniprot_invalid_response', False)
                    url = target
                    continue
                if response.status_code in (404, 410):
                    raise UniProtDownloadError(f'UniProt accession {accession} was not found. Check the accession or upload a FASTA file.', 'uniprot_not_found', False)
                if response.status_code in (408, 429) or response.status_code >= 500:
                    return None, retry_after(response.headers.get('Retry-After'))
                if response.status_code != 200:
                    raise UniProtDownloadError(f'UniProt could not provide {accession} (HTTP {response.status_code}). Upload a FASTA file or paste the sequence.', 'uniprot_http_error', False)
                chunks, size = [], 0
                for chunk in response.iter_content(chunk_size=16384):
                    size += len(chunk)
                    if size > self.RESPONSE_BYTES:
                        raise UniProtDownloadError('The UniProt response exceeds the supported size.', 'uniprot_response_too_large', False)
                    if time.monotonic() >= deadline:
                        raise requests.Timeout('UniProt download deadline reached')
                    chunks.append(chunk)
                try:
                    text = b''.join(chunks).decode('utf-8')
                except UnicodeDecodeError:
                    raise UniProtDownloadError('UniProt returned an invalid response encoding.', 'uniprot_invalid_response') from None
                # Secondary accessions may redirect to a primary accession.
                resolved = urlsplit(url).path.rsplit('/', 1)[-1].removesuffix('.' + self.FORMAT)
                return self._parse_record(text, resolved, url), 0
        raise UniProtDownloadError('UniProt redirected the sequence request too many times.', 'uniprot_invalid_response', False)

    def _parse_record(self, text, accession, url):
        return UniProtSequence(accession, parse_fasta(text, accession), url, time.time())

    def local_record(self, accession):
        key = ('local', accession)
        cached = self._cached(key)
        if cached:
            return cached
        record = self._local(accession)
        if record:
            self._remember(key, record)
        return record

    def _local(self, accession):
        if not re.fullmatch(ACCESSION, accession):
            return None
        annotations = self.FORMAT == 'json'
        for provider in (LocalUniProt().fetch, fetch_index):
            try:
                value = provider(accession, annotations=annotations)
                if value is None:
                    continue
                primary, content, source = value
                if not re.fullmatch(ACCESSION, primary):
                    raise LocalUniProtError('Invalid local primary accession.')
                if annotations:
                    self._parse_record(content, accession, '')
                record_type = UniProtDocument if annotations else UniProtSequence
                return record_type(primary, content, f'https://www.uniprot.org/uniprotkb/{primary}', time.time(), source=source)
            except (LocalUniProtError, UniProtDownloadError) as exc:
                logger.warning('UniProt local record unavailable: accession=%s category=%s', accession, type(exc).__name__)
        return None

    def _download(self, accession, deadline):
        last_code = 'uniprot_unavailable'
        for attempt, mode in enumerate(self.TLS_MODES, 1):
            if time.monotonic() >= deadline:
                break
            delay = 2 ** (attempt - 1)
            try:
                # A new connection after an interruption; never disable TLS checks.
                with self._session(mode) as session:
                    value, wait = self._get(session, accession, deadline)
                if value:
                    logger.info('UniProt record retrieved: accession=%s resolved=%s format=%s attempt=%s tls=%s',
                                accession, value.accession, self.FORMAT, attempt, mode)
                    return value
                delay = max(delay, wait)
                reason, last_code = 'HTTP 429/5xx', 'uniprot_unavailable'
            except UniProtDownloadError as exc:
                if not exc.retryable:
                    raise
                reason, last_code = exc.code, exc.code
            except requests.RequestException as exc:
                if 'CERTIFICATE_VERIFY_FAILED' in str(exc):
                    raise UniProtDownloadError('The secure connection to UniProt could not be verified. Upload a FASTA file or paste the sequence while the service connection is checked.', 'uniprot_certificate_error', False) from None
                reason, last_code = type(exc).__name__, 'uniprot_unavailable'
            logger.warning('UniProt download interrupted: accession=%s attempt=%s/%s tls=%s reason=%s',
                           accession, attempt, len(self.TLS_MODES), mode, reason)
            if attempt == len(self.TLS_MODES) or delay >= deadline - time.monotonic():
                break
            time.sleep(delay)
        if self.FORMAT == 'json':
            if self._local(accession):
                raise UniProtDownloadError(
                    f'Live UniProt annotations for {accession} are unavailable. The local snapshot does not include '
                    'all sections required for this query; missing fields are not evidence of absence.',
                    'uniprot_local_incomplete', True)
            raise UniProtDownloadError(f'Could not retrieve annotations for {accession} from UniProt after bounded retries. Retry shortly; no annotation result was inferred.', last_code)
        raise UniProtDownloadError(
            f'Could not download the sequence for {accession} from UniProt after bounded retries. '
            'The analysis has not been submitted. No usable local snapshot record was available. '
            'Retry shortly, or paste the sequence / upload a FASTA file.', last_code)


uniprot_client = UniProtClient()


class UniProtJSONClient(UniProtClient):
    FORMAT = 'json'
    ACCEPT = 'application/json'
    RESPONSE_BYTES = 4 * 1024 * 1024
    CACHE_BYTES = 8 * 1024 * 1024

    def _stored(self, accession, *, stale=False):
        cached = UniProtJSONCache().get(accession, stale=stale)
        if cached is None:
            return None
        text, fetched_at = cached
        try:
            record = self._parse_record(text, accession, f'{BASE_URL}{accession}.json')
        except UniProtDownloadError:
            return None
        data = json.loads(text)
        # Never reuse reduced local records as complete API annotations.
        if 'enzymindSource' in data or 'easifaLocal' in data:
            return None
        source = {'name': 'UniProt API response cache', 'method': 'uniprot_cache',
                  'retrieved_at': datetime.fromtimestamp(fetched_at, timezone.utc).isoformat(),
                  'stale': stale, 'annotation_scope': ['full'],
                  'note': ('Live UniProt could not be reached. Showing previously retrieved annotations; they may have changed.'
                           if stale else 'Previously retrieved UniProt API annotations; retrieved time is shown for provenance.')}
        data['enzymindSource'] = source
        return replace(record, text=json.dumps(data, ensure_ascii=False), retrieved_at=fetched_at, source=source)

    def _download(self, accession, deadline):
        try:
            record = super()._download(accession, deadline)
        except UniProtDownloadError as exc:
            if exc.retryable or exc.code == 'uniprot_certificate_error':
                cached = self._stored(accession, stale=True)
                if cached:
                    return cached
            raise
        UniProtJSONCache().put(accession, record.text, record.retrieved_at)
        return record

    def _parse_record(self, text, accession, url):
        try:
            data = json.loads(text)
        except ValueError:
            raise UniProtDownloadError('UniProt returned invalid annotation JSON.', 'uniprot_invalid_response') from None
        if not isinstance(data, dict) or not re.fullmatch(ACCESSION, str(data.get('primaryAccession', ''))):
            raise UniProtDownloadError('UniProt returned an invalid annotation record.', 'uniprot_invalid_response')
        secondary = data.get('secondaryAccessions', [])
        if not isinstance(secondary, list) or (data['primaryAccession'] != accession and accession not in secondary):
            raise UniProtDownloadError('UniProt returned an unexpected annotation accession.', 'uniprot_invalid_response')
        if '-' in accession and data['primaryAccession'] != accession:
            raise UniProtDownloadError('UniProt returned a different isoform.', 'uniprot_invalid_response')
        if not isinstance(data.get('sequence', {}), dict) or any(not isinstance(data.get(field, []), list) for field in ('comments', 'features')):
            raise UniProtDownloadError('UniProt returned malformed annotations.', 'uniprot_invalid_response')
        return UniProtDocument(data['primaryAccession'], text, url, time.time())

    @staticmethod
    def _with_source(record):
        data = json.loads(record.text)
        data.setdefault('enzymindSource', {
            'method': 'uniprot_api', 'name': 'UniProt API',
            'retrieved_at': datetime.fromtimestamp(record.retrieved_at, timezone.utc).isoformat()})
        return data

    def cached_json(self, accession):
        """A validated, fresh complete API entry available on this machine."""
        record = self._cached(accession) or self._stored(accession)
        if record and not (record.source or {}).get('stale'):
            return self._with_source(record)
        return None

    def fetch_json(self, accession, capability='full', *, allow_partial=False):
        accession = accession.strip().upper()
        if not allow_partial and capability == 'full':
            return json.loads(self.fetch(accession, local_capability='full').text)
        local = self.local_record(accession)
        if local is None:
            return self._with_source(self.fetch(accession, local_capability='full'))
        data = json.loads(local.text)
        scope = local.source['annotation_scope']
        if capability in scope and not allow_partial:
            return data
        if allow_partial and all(key in scope for key in OVERVIEW):
            return combine(data)
        key = ('partial', accession)
        if allow_partial and (cached := self._cached(key)):
            if self.cached_json(local.accession) is None:
                return json.loads(cached.text)
        try:
            record = self.fetch(local.accession, local_capability='full', budget_seconds=12 if allow_partial else None)
        except UniProtDownloadError as exc:
            if not allow_partial or not (exc.retryable or exc.code == 'uniprot_certificate_error'):
                raise
            data = combine(data, note='Supplemental UniProt annotations are unavailable. Showing the sections covered by the local release.')
            self._remember(key, replace(local, text=json.dumps(data), source=data['enzymindSource']))
            return data
        data = combine(data, self._with_source(record))
        if not allow_partial and data['enzymindSource']['partial']:
            raise UniProtDownloadError('Supplemental UniProt annotations do not match the local sequence version.',
                                       'uniprot_local_incomplete')
        return data


uniprot_sequence_client = uniprot_client
uniprot_json_client = UniProtJSONClient()
