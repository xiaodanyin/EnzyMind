"""Functional Site Query Module."""
import requests
import sys
from pathlib import Path

root = str(Path(__file__).resolve().parents[3])
if root not in sys.path:
    sys.path.insert(0, root)
from shared.uniprot import uniprot_json_client, UniProtDownloadError
from typing import Dict, Any, List

class FunctionalSiteQuery:
    def __init__(self, timeout: int = 15):
        self.base_url = "https://rest.uniprot.org/uniprotkb"
        self.timeout = timeout
    
    def get_sites(self, uniprot_id: str) -> Dict[str, Any]:
        try:
            data = uniprot_json_client.fetch_json(uniprot_id, capability='functional_sites')
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
            
            return {"success": True, "source": data.get("enzymindSource"), "uniprot_id": uniprot_id, "sites": sites, "count": len(sites), "error": None}
        except UniProtDownloadError as exc:
            return {"success": False, "error": str(exc), "sites": []}
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timeout", "sites": []}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e), "sites": []}
