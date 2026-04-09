# sequence_alignment/models/blast_searcher.py
"""
BLAST Sequence Alignment Service

This module provides functionality to perform NCBI BLAST searches
for protein sequence alignment.
"""

import re
import logging
import socket
import ssl
import urllib.request
import urllib.error
import requests
from typing import Dict, Any, List, Optional

try:
    from Bio.Blast import NCBIWWW, NCBIXML
    BIO_AVAILABLE = True
except ImportError:
    BIO_AVAILABLE = False
    logging.warning("Biopython not available. BLAST functionality will be limited.")


# ============== SSL Configuration ==============

def configure_ssl_context():
    """
    Configure SSL context to handle NCBI connection issues.
    Creates a more permissive SSL context for older server configurations.
    """
    try:
        # Create a custom SSL context
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        # Set to use TLS 1.2 minimum
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        
        # Install the custom opener
        https_handler = urllib.request.HTTPSHandler(context=ctx)
        opener = urllib.request.build_opener(https_handler)
        urllib.request.install_opener(opener)
        
        logging.info("SSL context configured successfully")
        return True
    except Exception as e:
        logging.warning(f"Failed to configure SSL context: {e}")
        return False


# Configure SSL on module load
configure_ssl_context()


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============== Sequence Processing ==============

def classify_input_v2(raw: str) -> str:
    """
    Process user input to get protein sequence.
    """
    raw = raw.strip()

    # Check if UniProt ID
    if re.match(r"^[OPQ][0-9][A-Z0-9]{3}[0-9]$", raw) or re.match(r"^[A-NR-Z][0-9][A-Z0-9]{3}[0-9]$", raw):
        logger.info("Detected UniProt ID")
        url = f"https://rest.uniprot.org/uniprotkb/{raw}.fasta"
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            raise ValueError("Failed to fetch sequence from UniProt.")
        return _extract_sequence_from_fasta(response.text)

    # Check if FASTA format
    if raw.startswith(">") or "\n>" in raw:
        logger.info("Detected FASTA content")
        return _extract_sequence_from_fasta(raw)

    # Assume raw sequence
    logger.info("Detected raw amino acid sequence")
    return _clean_sequence(raw)


def _extract_sequence_from_fasta(fasta_text: str) -> str:
    """Extract sequence from FASTA text."""
    lines = fasta_text.strip().splitlines()
    seq_lines = [line.strip() for line in lines if not line.startswith(">")]
    return _clean_sequence("".join(seq_lines))


def _clean_sequence(seq: str) -> str:
    """Remove non-amino acid characters."""
    return re.sub(r"[^A-Z]", "", seq.upper())


# ============== BLAST Searcher Class ==============

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
        e_value: float = DEFAULT_E_VALUE
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
        
        last_error = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                # Set socket timeout
                socket.setdefaulttimeout(self.timeout)
                
                logger.info(f"Starting BLAST search (attempt {attempt + 1}/{self.MAX_RETRIES}) for sequence of length {len(clean_seq)}")
                
                # Re-configure SSL before each attempt
                configure_ssl_context()
                
                # Perform BLAST search
                result_handle = NCBIWWW.qblast(
                    program="blastp",
                    database="nr",
                    sequence=clean_seq,
                    hitlist_size=max_results,
                    expect=e_value,
                    format_type="XML"
                )
                
                # Parse results
                blast_record = NCBIXML.read(result_handle)
                
                alignments = []
                for alignment in blast_record.alignments:
                    for hsp in alignment.hsps:
                        if hsp.expect < e_value:
                            alignments.append({
                                "title": alignment.title,
                                "length": alignment.length,
                                "e_value": hsp.expect,
                                "score": hsp.score,
                                "bits": hsp.bits,
                                "identities": hsp.identities,
                                "positives": hsp.positives,
                                "gaps": hsp.gaps,
                                "query": hsp.query[:100] + "..." if len(hsp.query) > 100 else hsp.query,
                                "match": hsp.match[:100] + "..." if len(hsp.match) > 100 else hsp.match,
                                "subject": hsp.sbjct[:100] + "..." if len(hsp.sbjct) > 100 else hsp.sbjct
                            })
                            
                            if len(alignments) >= max_results:
                                break
                    
                    if len(alignments) >= max_results:
                        break
                
                logger.info(f"BLAST search successful, found {len(alignments)} alignments")
                
                return {
                    "success": True,
                    "query_length": len(clean_seq),
                    "num_results": len(alignments),
                    "alignments": alignments
                }
                
            except socket.timeout:
                last_error = f"BLAST search timed out after {self.timeout} seconds"
                logger.warning(f"Attempt {attempt + 1} failed: {last_error}")
                
            except ssl.SSLError as e:
                last_error = f"SSL error: {str(e)}"
                logger.warning(f"Attempt {attempt + 1} failed with SSL error: {e}")
                # Re-configure SSL for next attempt
                configure_ssl_context()
                
            except urllib.error.URLError as e:
                last_error = f"Network error: {str(e)}"
                logger.warning(f"Attempt {attempt + 1} failed with URL error: {e}")
                
            except Exception as e:
                last_error = str(e)
                logger.error(f"Attempt {attempt + 1} failed: {e}")
            
            # Wait before retry (exponential backoff)
            if attempt < self.MAX_RETRIES - 1:
                import time
                wait_time = 2 ** attempt  # 1, 2, 4 seconds
                logger.info(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
        
        return {
            "success": False,
            "error": f"BLAST search failed after {self.MAX_RETRIES} attempts. Last error: {last_error}"
        }
    
    def search_from_input(
        self, 
        input_data: str, 
        max_results: int = 3
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
            sequence = classify_input_v2(input_data)
            return self.search(sequence, max_results)
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
                f"<li><b>Sequence:</b> <span style='font-weight: normal; color: #222;'>{alignment['title']}</span></li>"
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
