# protparam/models/protparam_analyzer.py
"""
ProtParam Analyzer - Protein Physicochemical Properties

This module provides functionality to analyze protein physicochemical
properties using the ExPASy ProtParam service.
"""

import re
import logging
import requests
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup
from Bio import __version__ as biopython_version
from Bio.SeqUtils.ProtParam import ProteinAnalysis

root = str(Path(__file__).resolve().parents[3])
if root not in sys.path:
    sys.path.insert(0, root)
from shared.uniprot import uniprot_client


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============== Sequence Processing ==============

def classify_input_v2(raw: str) -> str:
    """
    Process user input:
    - If UniProt ID, fetch sequence from UniProt API
    - If FASTA format, strip header
    - If raw sequence, return cleaned version
    """
    raw = raw.strip()

    # Check if UniProt ID
    if re.fullmatch(r"(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})(?:-[1-9][0-9]*)?", raw, re.I):
        logger.info("Detected UniProt ID")
        return _clean_sequence(uniprot_client.fetch(raw).sequence)

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
    if sum(line.lstrip().startswith('>') for line in lines) != 1:
        raise ValueError('Select one FASTA record. Multiple sequences cannot be concatenated.')
    seq_lines = [line.strip() for line in lines if not line.startswith(">")]
    return _clean_sequence("".join(seq_lines))


def _clean_sequence(seq: str) -> str:
    """Normalize whitespace only; report invalid residues instead of deleting them."""
    sequence = re.sub(r"\s+", "", seq.upper())
    if not sequence or re.search(r"[^ACDEFGHIKLMNPQRSTVWY]", sequence):
        raise ValueError('Use a nonempty sequence of the 20 standard amino acids.')
    return sequence


# ============== ExPASy ProtParam API ==============

def send_expasy_param_request(url: str, data: dict) -> Optional[str]:
    """
    Send request to ExPASy ProtParam service.
    
    Args:
        url: ExPASy ProtParam URL
        data: Form data to send
        
    Returns:
        HTML response content or None
    """
    session = requests.Session()
    session.headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://web.expasy.org",
        "Referer": "https://web.expasy.org/protparam/",
        "Connection": "keep-alive",
    }

    try:
        response = session.post(url, files=data, headers=session.headers, timeout=(5, 20))
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"Network request error: {e}")
        return None
    finally:
        session.close()


def extract_and_process_protparam_html(html_content: str) -> str:
    """
    Extract and process ProtParam results from HTML.
    
    Args:
        html_content: HTML response from ExPASy
        
    Returns:
        Processed text content
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")

        pre_tags = soup.find_all("pre")
        if not pre_tags or len(pre_tags) < 2:
            raise ValueError("Failed to locate the correct <pre> tag in the HTML content.")

        parameter_pre = pre_tags[1]
        pre_lines = parameter_pre.get_text().strip().split("\n")

        start_line = next((i for i, line in enumerate(pre_lines) if "Number of amino acids:" in line), None)
        end_line = next((i for i, line in enumerate(pre_lines) if "Grand average of hydropathicity (GRAVY):" in line), None)

        if start_line is None or end_line is None:
            raise ValueError("Failed to locate the required content in <pre>.")

        relevant_lines = pre_lines[start_line:end_line + 1]
        return "\n".join(relevant_lines)

    except Exception as e:
        return f"Error processing ProtParam HTML: {e}"


def convert_protparam_to_markdown(cleaned_content: str) -> str:
    """
    Convert ProtParam cleaned content to Markdown.
    
    Args:
        cleaned_content: Cleaned text content
        
    Returns:
        Markdown formatted string
    """
    lines = cleaned_content.strip().split("\n")
    markdown_output = "## ProtParam Results\n\n"

    for line in lines:
        markdown_output += f"- {line.strip()}\n"

    return markdown_output


# ============== ProtParam Analyzer Class ==============

class ProtParamAnalyzer:
    """
    Analyzer for protein physicochemical properties.
    
    Uses ExPASy ProtParam service to compute properties.
    """
    
    EXPASY_URL = "https://web.expasy.org/cgi-bin/protparam/protparam"
    
    def __init__(self):
        """Initialize the analyzer."""
        pass
    
    def analyze(self, sequence: str) -> Dict[str, Any]:
        """
        Analyze protein sequence physicochemical properties.
        
        Args:
            sequence: Amino acid sequence
            
        Returns:
            Dictionary with analysis results
        """
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
        
        # Prepare request data
        data = {
            "sequence": (None, clean_seq),
            "title": (None, ""),
            "output": (None, "html")
        }
        
        try:
            # Send request to ExPASy
            html_response = send_expasy_param_request(self.EXPASY_URL, data)
            
            if not html_response:
                return self._local_fallback(clean_seq, 'ExPASy did not respond within the connection/read limit.')
            
            # Process response
            processed = extract_and_process_protparam_html(html_response)
            markdown = convert_protparam_to_markdown(processed)
            
            # Parse individual values
            params = self._parse_parameters(processed)
            required = {'num_amino_acids', 'molecular_weight', 'theoretical_pi', 'gravy'}
            if not required.issubset(params) or params['num_amino_acids'] != len(clean_seq):
                return self._local_fallback(clean_seq, 'ExPASy returned an incomplete or mismatched analysis.')
            
            return {
                "success": True,
                "sequence_length": len(clean_seq),
                "markdown": markdown,
                "raw_text": processed,
                "parameters": params,
                "source": {"name": "ExPASy ProtParam", "method": "remote", "url": "https://web.expasy.org/protparam/"},
                "amino_acid_composition": [{"residue": aa, "name": aa, "count": clean_seq.count(aa), "percent": round(100 * clean_seq.count(aa) / len(clean_seq), 3)} for aa in 'ACDEFGHIKLMNPQRSTVWY']
            }
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _local_fallback(self, sequence, reason):
        """Calculate core properties locally; never label these as ExPASy data."""
        analysis = ProteinAnalysis(sequence, monoisotopic=False)
        params = {
            'num_amino_acids': len(sequence),
            'molecular_weight': round(analysis.molecular_weight(), 2),
            'theoretical_pi': round(analysis.isoelectric_point(), 2),
            'instability_index': round(analysis.instability_index(), 2),
            'gravy': round(analysis.gravy(), 3),
        }
        text = (f'Number of amino acids: {len(sequence)}\n'
                f'Molecular weight: {params["molecular_weight"]}\n'
                f'Theoretical pI: {params["theoretical_pi"]}\n'
                f'Instability index (II) is computed to be {params["instability_index"]}\n'
                f'Grand average of hydropathicity (GRAVY): {params["gravy"]}')
        note = (f'Calculation source: Biopython {biopython_version} (local fallback). '
                'Values use Biopython reference tables and may differ slightly from ExPASy. '
                'Additional ExPASy-only report fields are unavailable in this fallback.')
        return {
            'success': True, 'sequence_length': len(sequence), 'parameters': params,
            'markdown': convert_protparam_to_markdown(text) + '\n' + note,
            'raw_text': text + '\n\n' + note,
            'source': {'name': 'Biopython ProteinAnalysis', 'version': biopython_version,
                       'method': 'local_fallback', 'url': 'https://biopython.org/docs/1.86/api/Bio.SeqUtils.ProtParam.html'},
            'fallback_reason': reason,
            'amino_acid_composition': [{'residue': aa, 'name': aa, 'count': sequence.count(aa),
                                      'percent': round(100 * sequence.count(aa) / len(sequence), 3)} for aa in 'ACDEFGHIKLMNPQRSTVWY'],
        }
    
    def analyze_from_input(self, input_data: str) -> Dict[str, Any]:
        """
        Analyze from various input types (sequence, UniProt ID, FASTA).
        
        Args:
            input_data: Input data string
            
        Returns:
            Dictionary with analysis results
        """
        try:
            sequence = classify_input_v2(input_data)
            return self.analyze(sequence)
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _parse_parameters(self, text: str) -> Dict[str, Any]:
        """
        Parse individual parameters from text.
        
        Args:
            text: Processed text content
            
        Returns:
            Dictionary of parsed parameters
        """
        params = {}
        
        lines = text.strip().split("\n")
        for line in lines:
            line = line.strip()
            
            if "Number of amino acids:" in line:
                try:
                    params["num_amino_acids"] = int(line.split(":")[-1].strip())
                except:
                    pass
            
            elif "Molecular weight:" in line:
                try:
                    params["molecular_weight"] = float(line.split(":")[-1].strip())
                except:
                    pass
            
            elif "Theoretical pI:" in line:
                try:
                    params["theoretical_pi"] = float(line.split(":")[-1].strip())
                except:
                    pass
            
            elif "instability index" in line.lower():
                try:
                    # Format: "Instability index (II) is computed to be 42.08"
                    match = re.search(r"([+-]?\d+\.?\d*)", line.split("be")[-1])
                    if match:
                        params["instability_index"] = float(match.group(1))
                except:
                    pass
            
            elif "Grand average of hydropathicity" in line:
                try:
                    params["gravy"] = float(line.split(":")[-1].strip())
                except:
                    pass
        
        return params
