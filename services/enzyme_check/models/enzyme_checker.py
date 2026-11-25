"""Enzyme Checker Module."""

import requests
import sys
from pathlib import Path

root = str(Path(__file__).resolve().parents[3])
if root not in sys.path:
    sys.path.insert(0, root)
from shared.uniprot import uniprot_json_client, UniProtDownloadError
from shared.uniprot_sections import ec_numbers as annotated_ec_numbers
from typing import Dict, Any, List


class EnzymeChecker:
    """Check if a protein is annotated as an enzyme in UniProt."""
    
    def __init__(self, timeout: int = 60):
        self.base_url = "https://rest.uniprot.org/uniprotkb"
        self.timeout = timeout
    
    def check_enzyme(self, uniprot_id: str) -> Dict[str, Any]:
        try:
            data = uniprot_json_client.fetch_json(uniprot_id, capability='enzyme_status')
            is_enzyme, ec_numbers = self._check_catalytic_activity(data)
            
            if is_enzyme:
                message = f"The sequence with UniProt ID '{uniprot_id}' is annotated as an enzyme (EC or catalytic activity annotation found)."
            else:
                message = f"The sequence with UniProt ID '{uniprot_id}' is not annotated as an enzyme (no catalytic activity found)."
            
            return {
                "success": True, "source": data.get("enzymindSource"),
                "uniprot_id": uniprot_id,
                "is_enzyme": is_enzyme,
                "message": message,
                "ec_numbers": ec_numbers,
                "error": None
            }
            
        except UniProtDownloadError as exc:
            return {"success": False, "uniprot_id": uniprot_id, "is_enzyme": None, "message": str(exc), "ec_numbers": [], "error": str(exc)}
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
        numbers = annotated_ec_numbers(data)
        has_catalytic = any(c.get('commentType') == 'CATALYTIC ACTIVITY' for c in data.get('comments', []))
        return bool(numbers) or has_catalytic, numbers
    
    def batch_check(self, uniprot_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        results = {}
        for uid in uniprot_ids:
            results[uid] = self.check_enzyme(uid)
        return results
