"""Kinetic Params Query Module."""
import requests
import sys
from pathlib import Path

root = str(Path(__file__).resolve().parents[3])
if root not in sys.path:
    sys.path.insert(0, root)
from shared.uniprot import uniprot_json_client, UniProtDownloadError
from typing import Dict, Any, List

class KineticParamsQuery:
    def __init__(self, timeout: int = 60):
        self.base_url = "https://rest.uniprot.org/uniprotkb"
        self.timeout = timeout
    
    def get_kinetics(self, uniprot_id: str) -> Dict[str, Any]:
        try:
            data = uniprot_json_client.fetch_json(uniprot_id, capability='kinetics')
            km_list, vmax_list, kcat_note = [], [], ""
            
            for c in data.get("comments", []):
                if c.get("commentType") == "BIOPHYSICOCHEMICAL PROPERTIES" and c.get("kineticParameters"):
                    kp = c.get("kineticParameters", {})
                    for km in kp.get("michaelisConstants", []):
                        km_list.append({"value": km.get("constant"), "unit": km.get("unit"), "substrate": km.get("substrate")})
                    for vmax in kp.get("maximumVelocities", []):
                        vmax_list.append({"value": vmax.get("velocity"), "unit": vmax.get("unit")})
                    kcat_note = "\n".join(t.get("value", "") for t in kp.get("note", {}).get("texts", [])).strip()
                    break
            
            return {"success": True, "uniprot_id": uniprot_id, "km": km_list, "vmax": vmax_list, "kcat_note": kcat_note, "error": None, "source": data.get('enzymindSource')}
        except UniProtDownloadError as exc:
            return {"success": False, "error": str(exc), "km": [], "vmax": []}
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timeout", "km": [], "vmax": []}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e), "km": [], "vmax": []}
