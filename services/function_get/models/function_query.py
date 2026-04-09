# function_get/models/function_query.py
"""UniProt Protein Function Query Module."""

import requests
from typing import Optional, Dict, Any


class FunctionQuery:
    """Query protein function information from UniProt database."""
    
    def __init__(self, timeout: int = 30):
        """
        Initialize the FunctionQuery.
        
        Args:
            timeout: Request timeout in seconds
        """
        self.base_url = "https://rest.uniprot.org/uniprotkb"
        self.timeout = timeout
    
    def get_function(self, uniprot_id: str) -> Dict[str, Any]:
        """
        Get protein function from UniProt database.
        
        Args:
            uniprot_id: UniProt accession ID (e.g., P12345)
            
        Returns:
            Dictionary containing function information and metadata
        """
        url = f"{self.base_url}/{uniprot_id}.json"
        
        try:
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 404:
                return {
                    "success": False,
                    "uniprot_id": uniprot_id,
                    "error": f"UniProt ID '{uniprot_id}' not found",
                    "function": None,
                    "protein_name": None,
                    "organism": None
                }
            
            response.raise_for_status()
            data = response.json()
            
            # Extract function from comments
            function_text = self._extract_function(data)
            protein_name = self._extract_protein_name(data)
            organism = self._extract_organism(data)
            gene_names = self._extract_gene_names(data)
            
            return {
                "success": True,
                "uniprot_id": uniprot_id,
                "function": function_text,
                "protein_name": protein_name,
                "organism": organism,
                "gene_names": gene_names,
                "error": None
            }
            
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "uniprot_id": uniprot_id,
                "error": "Request timeout",
                "function": None,
                "protein_name": None,
                "organism": None
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "uniprot_id": uniprot_id,
                "error": f"Request failed: {str(e)}",
                "function": None,
                "protein_name": None,
                "organism": None
            }
    
    def _extract_function(self, data: Dict[str, Any]) -> Optional[str]:
        """
        Extract function text from UniProt JSON response.
        
        Args:
            data: UniProt JSON response
            
        Returns:
            Function description or None if not found
        """
        comments = data.get("comments", [])
        
        for comment in comments:
            if comment.get("commentType") == "FUNCTION":
                texts = comment.get("texts", [])
                if texts:
                    # Join all function texts
                    function_parts = [t.get("value", "") for t in texts if t.get("value")]
                    if function_parts:
                        return " ".join(function_parts)
        
        return None
    
    def _extract_protein_name(self, data: Dict[str, Any]) -> Optional[str]:
        """
        Extract protein name from UniProt JSON response.
        
        Args:
            data: UniProt JSON response
            
        Returns:
            Protein name or None if not found
        """
        protein_desc = data.get("proteinDescription", {})
        
        # Try recommended name first
        rec_name = protein_desc.get("recommendedName", {})
        if rec_name:
            full_name = rec_name.get("fullName", {})
            if full_name:
                return full_name.get("value")
        
        # Try submitted name
        sub_names = protein_desc.get("submissionNames", [])
        if sub_names:
            full_name = sub_names[0].get("fullName", {})
            if full_name:
                return full_name.get("value")
        
        return None
    
    def _extract_organism(self, data: Dict[str, Any]) -> Optional[str]:
        """
        Extract organism name from UniProt JSON response.
        
        Args:
            data: UniProt JSON response
            
        Returns:
            Scientific organism name or None if not found
        """
        organism = data.get("organism", {})
        return organism.get("scientificName")
    
    def _extract_gene_names(self, data: Dict[str, Any]) -> list:
        """
        Extract gene names from UniProt JSON response.
        
        Args:
            data: UniProt JSON response
            
        Returns:
            List of gene names
        """
        genes = data.get("genes", [])
        gene_names = []
        
        for gene in genes:
            # Primary gene name
            gene_name = gene.get("geneName", {})
            if gene_name:
                name = gene_name.get("value")
                if name:
                    gene_names.append(name)
            
            # Synonyms
            synonyms = gene.get("synonyms", [])
            for syn in synonyms:
                value = syn.get("value")
                if value and value not in gene_names:
                    gene_names.append(value)
        
        return gene_names
    
    def batch_get_functions(self, uniprot_ids: list) -> Dict[str, Dict[str, Any]]:
        """
        Get functions for multiple UniProt IDs.
        
        Args:
            uniprot_ids: List of UniProt accession IDs
            
        Returns:
            Dictionary mapping UniProt IDs to their function information
        """
        results = {}
        for uid in uniprot_ids:
            results[uid] = self.get_function(uid)
        return results
