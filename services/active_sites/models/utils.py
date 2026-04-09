# active_sites/models/utils.py
"""
Utility functions for Active Sites Prediction Service
"""

import re
import requests
from typing import Tuple, Optional


def is_amino_acid_sequence(text: str) -> bool:
    """
    Check if the input is a valid amino acid sequence.
    
    Args:
        text: Input text to check
        
    Returns:
        True if valid amino acid sequence, False otherwise
    """
    if not text or len(text) < 10:
        return False
    
    # Standard amino acid characters
    amino_acids = set("ACDEFGHIKLMNPQRSTVWY")
    
    # Clean the text
    cleaned = text.strip().upper()
    
    # Remove common whitespace and newlines
    cleaned = re.sub(r'\s+', '', cleaned)
    
    # Check if all characters are amino acids
    if not cleaned:
        return False
    
    return all(c in amino_acids for c in cleaned)


def is_uniprot_id(text: str) -> bool:
    """
    Check if the input is a valid UniProt ID format.
    
    UniProt IDs follow these patterns:
    - [OPQ][0-9][A-Z0-9]{3}[0-9] (6 characters)
    - [A-NR-Z][0-9][A-Z][A-Z0-9]{2}[0-9] (6 characters)
    - [A-NR-Z][0-9][A-Z][A-Z0-9]{2}[0-9][A-Z][A-Z0-9]{2}[0-9] (10 characters)
    
    Args:
        text: Input text to check
        
    Returns:
        True if valid UniProt ID format, False otherwise
    """
    if not text:
        return False
    
    cleaned = text.strip().upper()
    
    # Check length (6 or 10 characters for UniProt IDs)
    if len(cleaned) not in [6, 10]:
        return False
    
    # Pattern for 6-character UniProt IDs
    pattern_6_1 = r'^[OPQ][0-9][A-Z0-9]{3}[0-9]$'
    pattern_6_2 = r'^[A-NR-Z][0-9][A-Z][A-Z0-9]{2}[0-9]$'
    
    # Pattern for 10-character UniProt IDs
    pattern_10 = r'^[A-NR-Z][0-9][A-Z][A-Z0-9]{2}[0-9][A-Z][A-Z0-9]{2}[0-9]$'
    
    return (re.match(pattern_6_1, cleaned) is not None or
            re.match(pattern_6_2, cleaned) is not None or
            re.match(pattern_10, cleaned) is not None)


def is_fasta_content(text: str) -> bool:
    """
    Check if the input is in FASTA format.
    
    Args:
        text: Input text to check
        
    Returns:
        True if FASTA format, False otherwise
    """
    if not text:
        return False
    
    lines = text.strip().split('\n')
    
    if len(lines) < 2:
        return False
    
    # First line should start with '>'
    if not lines[0].startswith('>'):
        return False
    
    # Remaining lines should be amino acid sequence
    sequence = ''.join(lines[1:])
    return is_amino_acid_sequence(sequence)


def clean_sequence(sequence: str) -> str:
    """
    Clean an amino acid sequence by removing whitespace and converting to uppercase.
    
    Args:
        sequence: Input sequence
        
    Returns:
        Cleaned sequence
    """
    if not sequence:
        return ""
    
    # Remove whitespace and newlines
    cleaned = re.sub(r'\s+', '', sequence)
    
    # Convert to uppercase
    return cleaned.upper()


def extract_sequence_from_fasta_content(fasta_content: str) -> str:
    """
    Extract the sequence from FASTA format content.
    
    Args:
        fasta_content: FASTA format content
        
    Returns:
        Extracted sequence
    """
    if not fasta_content:
        return ""
    
    lines = fasta_content.strip().split('\n')
    
    # Skip header line (starts with '>')
    sequence_lines = [line for line in lines if not line.startswith('>')]
    
    # Join and clean
    sequence = ''.join(sequence_lines)
    return clean_sequence(sequence)


def get_uniprot_sequence(uniprot_id: str) -> Optional[str]:
    """
    Fetch protein sequence from UniProt database.
    
    Args:
        uniprot_id: UniProt ID
        
    Returns:
        Protein sequence or None if not found
    """
    url = f"https://www.uniprot.org/uniprot/{uniprot_id}.fasta"
    
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return extract_sequence_from_fasta_content(response.text)
        return None
    except Exception:
        return None


def classify_input(input_data: str) -> Tuple[str, str]:
    """
    Classify the input type and return cleaned data.
    
    Args:
        input_data: Input data to classify
        
    Returns:
        Tuple of (input_type, cleaned_data)
        input_type can be: "uniprot_id", "sequence", "fasta", "unknown"
    """
    if not input_data:
        return ("unknown", "")
    
    cleaned = input_data.strip()
    
    # Check for UniProt ID first
    if is_uniprot_id(cleaned):
        return ("uniprot_id", cleaned.upper())
    
    # Check for FASTA format
    if is_fasta_content(cleaned):
        sequence = extract_sequence_from_fasta_content(cleaned)
        return ("fasta", sequence)
    
    # Check for raw amino acid sequence
    if is_amino_acid_sequence(cleaned):
        return ("sequence", clean_sequence(cleaned))
    
    return ("unknown", cleaned)
