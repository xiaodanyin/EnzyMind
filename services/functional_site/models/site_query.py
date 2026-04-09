"""Functional Site Query Module."""
import requests
from typing import Dict, Any, List

class FunctionalSiteQuery:
    def __init__(self, timeout: int = 15):
        self.base_url = "https://rest.uniprot.org/uniprotkb"
        self.timeout = timeout
    
    def get_sites(self, uniprot_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/{uniprot_id}.json"
        try:
            response = requests.get(url, timeout=self.timeout)
            if response.status_code == 404:
                return {"success": False, "error": f"UniProt ID '{uniprot_id}' not found", "sites": []}
            if response.status_code != 200:
                return {"success": False, "error": f"HTTP {response.status_code}", "sites": []}
            
            data = response.json()
            sites = []
            for f in data.get("features", []):
                if f.get("type") in ["Binding site", "Active site"]:
                    loc = f.get("location", {})
                    sites.append({
                        "type": f.get("type"),
                        "start": loc.get("start", {}).get("value"),
                        "end": loc.get("end", {}).get("value"),
                        "description": f.get("description", "")
                    })
            
            return {"success": True, "uniprot_id": uniprot_id, "sites": sites, "count": len(sites), "error": None}
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timeout", "sites": []}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e), "sites": []}
