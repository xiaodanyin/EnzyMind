# ec_reaction_info/models/catalytic_activity_query.py
"""Catalytic Activity Query Module."""

import requests
import sys
from pathlib import Path

root = str(Path(__file__).resolve().parents[3])
if root not in sys.path:
    sys.path.insert(0, root)
from shared.uniprot import uniprot_json_client, UniProtDownloadError
from shared.uniprot_sections import ec_numbers, reaction_smiles
from typing import Dict, Any, List


class CatalyticActivityQuery:
    """Query catalytic activity information from UniProt database."""
    
    def __init__(self, timeout: int = 60):
        self.base_url = "https://rest.uniprot.org/uniprotkb"
        self.timeout = timeout
    
    def get_catalytic_activities(self, uniprot_id: str, *, capability='catalytic_activity') -> Dict[str, Any]:
        try:
            data = uniprot_json_client.fetch_json(uniprot_id, capability=capability)
            activities = self._extract_catalytic_activities(data)
            numbers = ec_numbers(data)
            markdown = self._generate_markdown(uniprot_id, activities)
            if numbers and not activities:
                markdown = f"Annotated EC numbers for `{uniprot_id}`: " + ", ".join(numbers) + ". No reaction description is available in this record."
            
            return {
                "success": True, "source": data.get("enzymindSource"),
                "uniprot_id": uniprot_id,
                "activities": activities, "ec_numbers": numbers,
                "count": len(activities),
                "markdown": markdown,
                "error": None
            }
            
        except UniProtDownloadError as exc:
            return {"success": False, "uniprot_id": uniprot_id, "error": str(exc), "activities": [], "markdown": None}
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "uniprot_id": uniprot_id,
                "error": "Request timeout",
                "activities": [],
                "markdown": None
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "uniprot_id": uniprot_id,
                "error": f"Request failed: {str(e)}",
                "activities": [],
                "markdown": None
            }
    
    def _extract_catalytic_activities(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        activities = []
        smiles = reaction_smiles(data)
        
        for comment in data.get('comments', []):
            if comment.get('commentType') == "CATALYTIC ACTIVITY":
                reaction = comment.get('reaction')
                if reaction:
                    activity = {
                        "reaction_name": reaction.get('name', 'N/A'),
                        "ec_number": reaction.get('ecNumber'),
                        "rhea_id": None,
                        "evidence": []
                    }
                    
                    cross_references = reaction.get('reactionCrossReferences', [])
                    for ref in cross_references:
                        if ref.get('database') == 'Rhea':
                            rhea_id = ref.get('id', '')
                            activity["rhea_id"] = rhea_id.replace('RHEA:', '') if rhea_id else None
                            break
                    
                    evidences = comment.get('evidences', [])
                    for ev in evidences:
                        ev_code = ev.get('evidenceCode', '')
                        if ev_code:
                            activity["evidence"].append(ev_code)
                    
                    activity["reaction_smiles"] = smiles.get(activity["rhea_id"])
                    activities.append(activity)
        
        return activities
    
    def _generate_markdown(self, uniprot_id: str, activities: List[Dict[str, Any]]) -> str:
        if not activities:
            return f"No catalytic activities found for `{uniprot_id}`."
        
        markdown_output = f"### Catalytic Activities for `{uniprot_id}`\n\n"
        markdown_output += "| Index | Rhea ID | Reaction | EC Number |\n"
        markdown_output += "|-------|---------|----------|-----------|\n"
        
        for index, activity in enumerate(activities, 1):
            rhea_id = activity.get('rhea_id', 'N/A') or 'N/A'
            reaction_name = activity.get('reaction_name', 'N/A')
            ec_number = activity.get('ec_number', 'N/A') or 'N/A'
            
            markdown_output += f"| {index} | {rhea_id} | {reaction_name} | {ec_number} |\n"
        
        return markdown_output
    
    def batch_get_activities(self, uniprot_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        results = {}
        for uid in uniprot_ids:
            results[uid] = self.get_catalytic_activities(uid)
        return results
