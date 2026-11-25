# sequence_alignment/models/blast_searcher.py
"""
BLAST Sequence Alignment Service

This module provides functionality to perform NCBI BLAST searches
for protein sequence alignment.
"""

import re
import logging
import io
import time
import threading
import requests
import hashlib
import subprocess
from html import escape
from . import local_blast
import json
from collections import OrderedDict
from xml.parsers.expat import ExpatError
from typing import Dict, Any, List, Optional
from .uniprot_client import ACCESSION, UniProtDownloadError, uniprot_client

try:
    from Bio.Blast import NCBIXML
    BIO_AVAILABLE = True
except ImportError:
    BIO_AVAILABLE = False
    logging.warning("Biopython not available. BLAST functionality will be limited.")


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============== Sequence Processing ==============

def classify_input_v2(raw: str) -> str:
    """Keep the existing sequence-only helper contract."""
    return _resolve_input(raw)[0]


def _resolve_input(raw: str):
    """Resolve once and retain the exact downloaded sequence's provenance."""
    raw = raw.strip()

    # Check if UniProt ID
    if re.fullmatch(ACCESSION, raw, re.I):
        logger.info("Detected UniProt ID")
        resolved = uniprot_client.fetch(raw)
        return resolved.sequence, resolved

    # Check if FASTA format
    if raw.startswith(">") or "\n>" in raw:
        logger.info("Detected FASTA content")
        return _extract_sequence_from_fasta(raw), None

    # Assume raw sequence
    logger.info("Detected raw amino acid sequence")
    return _clean_sequence(raw), None


def _extract_sequence_from_fasta(fasta_text: str) -> str:
    """Extract sequence from FASTA text."""
    lines = fasta_text.strip().splitlines()
    seq_lines = [line.strip() for line in lines if not line.startswith(">")]
    return _clean_sequence("".join(seq_lines))


def _clean_sequence(seq: str) -> str:
    """Remove non-amino acid characters."""
    return re.sub(r"[^A-Z]", "", seq.upper())


# ============== BLAST Searcher Class ==============

class BlastPending(TimeoutError):
    """A submitted search still exists at NCBI; never submit it again."""
    def __init__(self, rid, message):
        super().__init__(message)
        self.rid = rid


class BlastSearcher:
    """
    NCBI BLAST Searcher for protein sequence alignment.
    """
    
    DEFAULT_TIMEOUT = 120  # seconds (increased for stability)
    DEFAULT_E_VALUE = 0.01
    MAX_RETRIES = 3
    
    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        """
        Initialize BLAST searcher.
        
        Args:
            timeout: Socket timeout in seconds
        """
        self.timeout = timeout
        
        if not BIO_AVAILABLE:
            logger.warning("Biopython not installed. Install with: pip install biopython")
    
    def search(
        self, 
        sequence: str, 
        max_results: int = 3,
        e_value: float = DEFAULT_E_VALUE,
        database: str = "nr", wait_for_result: bool = True
    ) -> Dict[str, Any]:
        """
        Perform BLAST search with retry mechanism.
        
        Args:
            sequence: Protein sequence to search
            max_results: Maximum number of results to return
            e_value: E-value threshold
            
        Returns:
            Dictionary with search results
        """
        if not BIO_AVAILABLE:
            return {
                "success": False,
                "error": "Biopython not installed. Install with: pip install biopython"
            }
        
        if not sequence or not sequence.strip():
            return {
                "success": False,
                "error": "Empty sequence provided"
            }
        
        # Clean sequence
        clean_seq = _clean_sequence(sequence)
        
        if not clean_seq:
            return {
                "success": False,
                "error": "No valid amino acids found in sequence"
            }
        
        if database == "local_uniprot":
            return local_blast.search(clean_seq, max_results, e_value, self.parse_result)
        try:
            if database not in {"nr", "swissprot"}:
                raise ValueError("Choose nr or swissprot as the BLAST database.")
            if not wait_for_result:
                return self.submit(clean_seq, max_results, e_value, database)
            xml, rid = self._query_ncbi(clean_seq, max_results, e_value, database=database)
            return self.parse_result(xml, rid, max_results, e_value, database, len(clean_seq))
        except BlastPending as exc:
            return self.pending(exc.rid, database, query_length=len(clean_seq), message=str(exc))
        except (requests.RequestException, ValueError, TimeoutError) as exc:
            logger.warning("BLAST search failed: %s", exc)
            return {"success": False, "error": str(exc)}

    def parse_result(self, xml, rid, max_results, e_value, database, query_length=None):
        blast_record = NCBIXML.read(io.StringIO(xml))
        alignments = []
        for alignment in blast_record.alignments:
            for hsp in alignment.hsps:
                if hsp.expect < e_value:
                    alignments.append({
                        "title": alignment.title, "length": alignment.length,
                        "e_value": hsp.expect, "score": hsp.score, "bits": hsp.bits,
                        "identities": hsp.identities, "positives": hsp.positives,
                        "gaps": hsp.gaps, "query": hsp.query, "match": hsp.match,
                        "subject": hsp.sbjct, "query_start": hsp.query_start,
                        "query_end": hsp.query_end, "subject_start": hsp.sbjct_start,
                        "subject_end": hsp.sbjct_end, "alignment_length": hsp.align_length,
                    })
                    if len(alignments) >= max_results:
                        break
            if len(alignments) >= max_results:
                break
        return {"success": True, "query_length": query_length or blast_record.query_length,
                "num_results": len(alignments), "alignments": alignments,
                "request_id": rid, "database": database, "status": "completed", "source": "NCBI BLAST"}

    @staticmethod
    def pending(rid, database="nr", **fields):
        return {"success": True, "status": "queued", "request_id": rid,
                "database": database, "source": "NCBI BLAST",
                "message": "NCBI is processing this search. No alignment results are available yet. Do not resubmit this task.",
                "ncbi_url": f"https://blast.ncbi.nlm.nih.gov/Blast.cgi?CMD=Get&RID={rid}",
                "next_poll_at": time.time() + 60, **fields}

    def submit(self, sequence, max_results=3, e_value=DEFAULT_E_VALUE, database="nr"):
        with requests.Session() as session:
            submitted = self._ncbi_request(session, {
                "CMD": "Put", "PROGRAM": "blastp", "DATABASE": database,
                "QUERY": sequence, "HITLIST_SIZE": max_results, "EXPECT": e_value,
            })
        match = re.search(r"RID\s*=\s*([A-Z0-9-]{5,40})", submitted)
        if not match:
            raise ValueError("NCBI did not return a request ID. Submission was not retried automatically.")
        rid = match.group(1)
        with self._request_lock:
            self._last_poll[rid] = time.monotonic()
        return self.pending(rid, database, query_length=len(sequence), submitted_at=time.time())

    _poll_lock = threading.Lock()
    _poll_cache = OrderedDict()

    def poll(self, rid, max_results=3, database="nr"):
        if not re.fullmatch(r"[A-Z0-9-]{5,40}", rid):
            raise ValueError("Invalid NCBI BLAST request ID.")
        if database not in {"nr", "swissprot"}:
            raise ValueError("Invalid BLAST database.")
        # Coalesce duplicate callers, including legacy / API callers, per RID.
        with self._poll_lock:
            now = time.time()
            cached = self._poll_cache.get(rid)
            if cached and cached[0] > now:
                result = {**cached[1], "database": database}
            else:
                try:
                    with requests.Session() as session:
                        raw = self._ncbi_request(session, {
                            "CMD": "Get", "RID": rid, "FORMAT_TYPE": "XML2_S", "HITLIST_SIZE": 50,
                        })
                    state = re.search(r"Status\s*=\s*(\w+)", raw)
                    if state and state.group(1) in {"FAILED", "UNKNOWN"}:
                        result = {"success": False, "status": "failed", "request_id": rid,
                                  "database": database, "error_code": "ncbi_" + state.group(1).lower(),
                                  "error": f"NCBI reports this search as {state.group(1).lower()}. Its results are no longer available; you may submit a new search."}
                    elif raw.lstrip().startswith("<?xml"):
                        result = self.parse_result(raw, rid, 50, self.DEFAULT_E_VALUE, database)
                    else:
                        result = self.pending(rid, database)
                        if not state or state.group(1) not in {"WAITING", "READY"}:
                            result["last_poll_error"] = "Unexpected NCBI response; the saved request will be checked again."
                except (requests.RequestException, ValueError, OSError, ExpatError, AttributeError) as exc:
                    result = self.pending(rid, database, last_poll_error=f"NCBI retrieval interrupted ({type(exc).__name__}); the same request will be checked again.")
                result["last_checked_at"] = time.time()
                result["next_poll_at"] = time.time() + 60
                # Bound the response cache, including large alignment payloads.
                self._poll_cache[rid] = (time.time() + 60, result)
                while len(self._poll_cache) > 128 or sum(len(json.dumps(v[1])) for v in self._poll_cache.values()) > 8_000_000:
                    self._poll_cache.popitem(last=False)
            result = dict(result)
            if "alignments" in result:
                result["alignments"] = result["alignments"][:max_results]
                result["num_results"] = len(result["alignments"])
            return result

    # Follow NCBI's public API limits: >=10 s between requests across this
    # process, >=60 s between polls for a RID. Never resubmit a queued job.
    _request_lock = threading.Lock()
    _last_request = 0.0
    _last_poll = OrderedDict()
    MAX_WAIT = 840
    URL = "https://blast.ncbi.nlm.nih.gov/Blast.cgi"

    def _ncbi_request(self, session, parameters):
        with self._request_lock:
            delay = type(self)._last_request + 10 - time.monotonic()
            rid = parameters.get("RID") if parameters.get("CMD") == "Get" else None
            if rid:
                delay = max(delay, self._last_poll.get(rid, 0) + 60 - time.monotonic())
            if delay > 0:
                time.sleep(delay)
            type(self)._last_request = time.monotonic()
            if rid:
                self._last_poll[rid] = time.monotonic()
                self._last_poll.move_to_end(rid)
                while len(self._last_poll) > 4096:
                    self._last_poll.popitem(last=False)
            response = session.post(self.URL, data={**parameters, "TOOL": "EnzyMind"},
                                    timeout=(15, self.timeout))
            response.raise_for_status()
            return response.text

    def _query_ncbi(self, sequence, max_results, e_value, request_id=None, database="nr"):
        with requests.Session() as session:
            if request_id:
                if not re.fullmatch(r"[A-Z0-9-]{5,40}", request_id):
                    raise ValueError("Invalid NCBI BLAST request ID.")
                rid = request_id
            else:
                submitted = self._ncbi_request(session, {
                    "CMD": "Put", "PROGRAM": "blastp", "DATABASE": database,
                    "QUERY": sequence, "HITLIST_SIZE": max_results, "EXPECT": e_value,
                })
                match = re.search(r"RID\s*=\s*([A-Z0-9-]+)", submitted)
                if not match:
                    raise ValueError("NCBI did not accept the BLAST search. Please retry later.")
                rid = match.group(1)
            logger.info("NCBI BLAST submitted: RID=%s", rid)
            deadline = time.monotonic() + self.MAX_WAIT
            failures = 0
            while time.monotonic() + 60 < deadline:
                time.sleep(60)
                try:
                    result = self._ncbi_request(session, {
                        "CMD": "Get", "RID": rid, "FORMAT_TYPE": "XML2_S",
                        "HITLIST_SIZE": max_results,
                    })
                    failures = 0
                except requests.RequestException:
                    failures += 1
                    logger.warning("NCBI result retrieval interrupted; retaining RID=%s (attempt %s)", rid, failures)
                    if failures >= self.MAX_RETRIES:
                        raise BlastPending(rid, f"Cannot retrieve NCBI BLAST request {rid} right now. "
                                           f"Resume at https://blast.ncbi.nlm.nih.gov/Blast.cgi?CMD=Get&RID={rid}") from None
                    continue
                status = re.search(r"Status\s*=\s*(\w+)", result)
                if status:
                    state = status.group(1)
                    logger.info("NCBI BLAST RID=%s status=%s", rid, state)
                    if state in {"FAILED", "UNKNOWN"}:
                        raise ValueError(f"NCBI BLAST request {rid} is {state.lower()}.")
                    continue
                if result.lstrip().startswith("<?xml"):
                    return result, rid
                if result.strip():
                    raise ValueError(f"NCBI returned an unexpected response for BLAST request {rid}.")
            raise BlastPending(rid,
                f"NCBI BLAST is still queued after {self.MAX_WAIT // 60} minutes. "
                f"Request ID: {rid}. Retrieve it at https://blast.ncbi.nlm.nih.gov/Blast.cgi?CMD=Get&RID={rid}")

    def search_from_input(
        self, 
        input_data: str, 
        max_results: int = 3, database: str = "nr", wait_for_result: bool = True
    ) -> Dict[str, Any]:
        """
        Search from various input types.
        
        Args:
            input_data: Input data (sequence, UniProt ID, FASTA)
            max_results: Maximum number of results
            
        Returns:
            Dictionary with search results
        """
        try:
            if database == "local_uniprot" and re.fullmatch(ACCESSION, input_data.strip(), re.I):
                if local_blast.default_database() != "local_uniprot":
                    return {"success": False, "error_code": "blast_unavailable", "error": "Local UniProt BLAST is disabled."}
                try:
                    indexed = local_blast.resolve(input_data.strip().upper())
                except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
                    return {"success": False, "error_code": "blast_unavailable",
                            "error": "The local UniProt index could not be opened."}
                if indexed:
                    sequence, source = indexed
                    result = self.search(sequence, max_results, database=database)
                    result.update(sequence=sequence, sequence_source=source)
                    return result
            sequence, resolved = _resolve_input(input_data)
            if not sequence and database == "local_uniprot":
                return {"success": False, "error_code": "invalid_input", "error": "A protein sequence is required."}
            result = (self.search(sequence, max_results) if database == "nr" and wait_for_result
                      else self.search(sequence, max_results, database=database, wait_for_result=wait_for_result))
            if resolved:
                result.update(sequence=sequence, sequence_source={
                    **(resolved.source or {}), "provider": "UniProt", "requested_accession": input_data.strip().upper(),
                    "resolved_accession": resolved.accession, "url": resolved.source_url,
                    "retrieved_at": resolved.retrieved_at, "cache_hit": resolved.cache_hit,
                    "sha256": hashlib.sha256(sequence.encode('ascii')).hexdigest(),
                })
            return result
        except UniProtDownloadError as exc:
            return {"success": False, "error": str(exc), "error_code": exc.code,
                    "error_stage": "sequence_download", "retryable": exc.retryable}
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def format_as_html(self, results: Dict[str, Any]) -> str:
        """
        Format results as HTML.
        
        Args:
            results: Search results dictionary
            
        Returns:
            HTML formatted string
        """
        if results.get("status") == "queued":
            rid = results["request_id"]
            return f"NCBI BLAST is queued. Request ID: {rid}. No results are available yet. Retrieve: {self.URL}?CMD=Get&RID={rid}"
        if not results.get("success"):
            return f"<div class='pred-class error'>❌ {results.get('error', 'Unknown error')}</div>"
        
        alignments = results.get("alignments", [])
        
        if not alignments:
            return "<div class='pred-class error'>❌ No significant alignments found.</div>"
        
        html_output = ""
        for i, alignment in enumerate(alignments, 1):
            html_output += (
                f"<div class='blast-block'>"
                f"<h4 style='color: #2f8f2f; font-weight: 600; margin-top: 32px;'>"
                f"<span style='font-size: 1.25rem;'>✅ Alignment {i}</span></h4>"
                f"<ul style='font-size: 1rem; line-height: 1.8;'>"
                f"<li><b>Sequence:</b> <span style='font-weight: normal; color: #222;'>{escape(alignment['title'])}</span></li>"
                f"<li><b>Length:</b> {alignment['length']}</li>"
                f"<li><b>E-value:</b> {alignment['e_value']:.2e}</li>"
                f"<li><b>Query:</b> <span style='color: #222;'>{alignment['query'][:75]}...</span></li>"
                f"<li><b>Match:</b> <span style='color: #222;'>{alignment['match'][:75]}...</span></li>"
                f"<li><b>Subject:</b> <span style='color: #222;'>{alignment['subject'][:75]}...</span></li>"
                f"</ul></div>"
            )
        
        return html_output
    
    def format_as_markdown(self, results: Dict[str, Any]) -> str:
        """
        Format results as Markdown.
        
        Args:
            results: Search results dictionary
            
        Returns:
            Markdown formatted string
        """
        if results.get("status") == "queued":
            rid = results["request_id"]
            return f"NCBI BLAST is queued. Request ID: {rid}. No results are available yet. Retrieve: {self.URL}?CMD=Get&RID={rid}"
        if not results.get("success"):
            return f"❌ Error: {results.get('error', 'Unknown error')}"
        
        alignments = results.get("alignments", [])
        
        if not alignments:
            return "❌ No significant alignments found."
        
        md_output = f"## BLAST Results\n\n"
        md_output += f"Query length: {results.get('query_length', 'N/A')}\n\n"
        
        for i, alignment in enumerate(alignments, 1):
            md_output += f"### Alignment {i}\n\n"
            md_output += f"- **Sequence:** {alignment['title']}\n"
            md_output += f"- **Length:** {alignment['length']}\n"
            md_output += f"- **E-value:** {alignment['e_value']:.2e}\n"
            md_output += f"- **Score:** {alignment.get('score', 'N/A')}\n"
            md_output += f"\n```\nQuery:   {alignment['query']}\nMatch:   {alignment['match']}\nSubject: {alignment['subject']}\n```\n\n"
        
        return md_output
