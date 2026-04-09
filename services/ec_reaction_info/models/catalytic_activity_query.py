# ec_reaction_info/models/catalytic_activity_query.py
"""Catalytic Activity Query Module."""

import requests
from typing import Dict, Any, List


class CatalyticActivityQuery:
    """Query catalytic activity information from UniProt database."""
    
    def __init__(self, timeout: int = 60):
        self.base_url = "https://rest.uniprot.org/uniprotkb"
        self.timeout = timeout
    
    def get_catalytic_activities(self, uniprot_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/{uniprot_id}.json"
        
        try:
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 404:
                return {
                    "success": False,
                    "uniprot_id": uniprot_id,
                    "error": f"UniProt ID '{uniprot_id}' not found",
                    "activities": [],
                    "markdown": None
                }
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "uniprot_id": uniprot_id,
                    "error": f"Failed to fetch data: HTTP {response.status_code}",
                    "activities": [],
                    "markdown": None
                }
            
            data = response.json()
            activities = self._extract_catalytic_activities(data)
            markdown = self._generate_markdown(uniprot_id, activities)
            
            return {
                "success": True,
                "uniprot_id": uniprot_id,
                "activities": activities,
                "count": len(activities),
                "markdown": markdown,
                "error": None
            }
            
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
