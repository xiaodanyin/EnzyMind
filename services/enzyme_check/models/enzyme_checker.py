"""Enzyme Checker Module."""

import requests
from typing import Dict, Any, List


class EnzymeChecker:
    """Check if a protein is annotated as an enzyme in UniProt."""
    
    def __init__(self, timeout: int = 60):
        self.base_url = "https://rest.uniprot.org/uniprotkb"
        self.timeout = timeout
    
    def check_enzyme(self, uniprot_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/{uniprot_id}.json"
        
        try:
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 404:
                return {
                    "success": False,
                    "uniprot_id": uniprot_id,
                    "is_enzyme": None,
                    "message": f"UniProt ID '{uniprot_id}' not found",
                    "ec_numbers": [],
                    "error": f"UniProt ID '{uniprot_id}' not found"
                }
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "uniprot_id": uniprot_id,
                    "is_enzyme": None,
                    "message": f"Failed to fetch data: HTTP {response.status_code}",
                    "ec_numbers": [],
                    "error": f"HTTP {response.status_code}"
                }
            
            data = response.json()
            is_enzyme, ec_numbers = self._check_catalytic_activity(data)
            
            if is_enzyme:
                message = f"The sequence with UniProt ID '{uniprot_id}' is annotated as an enzyme (catalytic activity found)."
            else:
                message = f"The sequence with UniProt ID '{uniprot_id}' is not annotated as an enzyme (no catalytic activity found)."
            
            return {
                "success": True,
                "uniprot_id": uniprot_id,
                "is_enzyme": is_enzyme,
                "message": message,
                "ec_numbers": ec_numbers,
                "error": None
            }
            
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "uniprot_id": uniprot_id,
                "is_enzyme": None,
                "message": "Request timeout",
                "ec_numbers": [],
                "error": "Request timeout"
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "uniprot_id": uniprot_id,
                "is_enzyme": None,
                "message": f"Request failed: {str(e)}",
                "ec_numbers": [],
                "error": str(e)
            }
    
    def _check_catalytic_activity(self, data: Dict[str, Any]) -> tuple:
        ec_numbers = []
        has_catalytic = False
        
        for comment in data.get("comments", []):
            if comment.get("commentType") == "CATALYTIC ACTIVITY":
                has_catalytic = True
                reaction = comment.get("reaction", {})
                ec = reaction.get("ecNumber")
                if ec and ec not in ec_numbers:
                    ec_numbers.append(ec)
        
        return has_catalytic, ec_numbers
    
    def batch_check(self, uniprot_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        results = {}
        for uid in uniprot_ids:
            results[uid] = self.check_enzyme(uid)
        return results
