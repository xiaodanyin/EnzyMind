"""Enzyme Full Info Query Module."""

import requests
import re
from typing import Dict, Any, List


class EnzymeFullInfoQuery:
    """Query comprehensive enzyme information from UniProt."""
    
    def __init__(self, timeout: int = 30):
        self.base_url = "https://rest.uniprot.org/uniprotkb"
        self.timeout = timeout
    
    def get_full_info(self, uniprot_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/{uniprot_id}.json"
        
        try:
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 404:
                return {"success": False, "is_enzyme": False, "error": f"UniProt ID '{uniprot_id}' not found"}
            
            if response.status_code != 200:
                return {"success": False, "error": f"HTTP {response.status_code}"}
            
            data = response.json()
            comments = data.get("comments", [])
            features = data.get("features", [])
            
            is_enzyme = any(c.get("commentType") == "CATALYTIC ACTIVITY" for c in comments)
            if not is_enzyme:
                return {"success": True, "is_enzyme": False, "uniprot_id": uniprot_id, "message": "Not annotated as enzyme"}
            
            seq_block = data.get("sequence", {})
            sequence_info = {
                "length": seq_block.get("length"),
                "mol_weight": seq_block.get("molWeight"),
                "sequence": seq_block.get("value")
            }
            
            catalytic_activities = []
            for c in comments:
                if c.get("commentType") == "CATALYTIC ACTIVITY":
                    r = c.get("reaction", {})
                    if r:
                        rhea_id = None
                        for ref in r.get("reactionCrossReferences", []):
                            if ref.get("database") == "Rhea":
                                rhea_id = ref.get("id", "").replace("RHEA:", "")
                                break
                        catalytic_activities.append({
                            "ec_number": r.get("ecNumber"),
                            "reaction": r.get("name"),
                            "rhea_id": rhea_id
                        })
            
            kinetics = {"km": [], "vmax": [], "kcat_note": ""}
            for c in comments:
                if c.get("commentType") == "BIOPHYSICOCHEMICAL PROPERTIES":
                    kp = c.get("kineticParameters", {})
                    for km in kp.get("michaelisConstants", []):
                        kinetics["km"].append({
                            "value": km.get("constant"),
                            "unit": km.get("unit"),
                            "substrate": km.get("substrate")
                        })
                    for vmax in kp.get("maximumVelocities", []):
                        kinetics["vmax"].append({
                            "value": vmax.get("velocity"),
                            "unit": vmax.get("unit")
                        })
                    kcat_text = "\n".join(t.get("value", "") for t in kp.get("note", {}).get("texts", [])).strip()
                    if kcat_text:
                        kinetics["kcat_note"] = kcat_text
                    break
            
            functional_sites = []
            for f in features:
                if f.get("type") in ["Binding site", "Active site"]:
                    desc = f.get("description", "")
                    loc = f.get("location", {})
                    start = loc.get("start", {}).get("value")
                    end = loc.get("end", {}).get("value")
                    functional_sites.append({
                        "type": f.get("type"),
                        "start": start,
                        "end": end,
                        "description": desc
                    })
            
            return {
                "success": True,
                "is_enzyme": True,
                "uniprot_id": uniprot_id,
                "sequence_info": sequence_info,
                "catalytic_activities": catalytic_activities,
                "kinetic_parameters": kinetics,
                "functional_sites": functional_sites,
                "error": None
            }
            
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timeout"}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}
