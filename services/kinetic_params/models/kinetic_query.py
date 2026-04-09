"""Kinetic Params Query Module."""
import requests
from typing import Dict, Any, List

class KineticParamsQuery:
    def __init__(self, timeout: int = 60):
        self.base_url = "https://rest.uniprot.org/uniprotkb"
        self.timeout = timeout
    
    def get_kinetics(self, uniprot_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/{uniprot_id}.json"
        try:
            response = requests.get(url, timeout=self.timeout)
            if response.status_code == 404:
                return {"success": False, "error": f"UniProt ID '{uniprot_id}' not found", "km": [], "vmax": []}
            if response.status_code != 200:
                return {"success": False, "error": f"HTTP {response.status_code}", "km": [], "vmax": []}
            
            data = response.json()
            km_list, vmax_list, kcat_note = [], [], ""
            
            for c in data.get("comments", []):
                if c.get("commentType") == "BIOPHYSICOCHEMICAL PROPERTIES":
                    kp = c.get("kineticParameters", {})
                    for km in kp.get("michaelisConstants", []):
                        km_list.append({"value": km.get("constant"), "unit": km.get("unit"), "substrate": km.get("substrate")})
                    for vmax in kp.get("maximumVelocities", []):
                        vmax_list.append({"value": vmax.get("velocity"), "unit": vmax.get("unit")})
                    kcat_note = "\n".join(t.get("value", "") for t in kp.get("note", {}).get("texts", [])).strip()
                    break
            
            return {"success": True, "uniprot_id": uniprot_id, "km": km_list, "vmax": vmax_list, "kcat_note": kcat_note, "error": None}
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timeout", "km": [], "vmax": []}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e), "km": [], "vmax": []}
