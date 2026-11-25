# enzyme_type/models/enzyme_type_predictor.py
"""
Enzyme Type Predictor using RetroPlanner API

This module provides enzyme type recommendations based on reaction SMILES.
The prediction uses the RetroPlanner API to recommend suitable enzyme classes
(EC numbers) for a given chemical reaction.
"""

import requests
from typing import Dict, Any, List, Optional


class EnzymeTypePredictor:
    """
    Enzyme Type Predictor that recommends enzyme classes for chemical reactions.
    
    Uses the RetroPlanner API to predict which enzyme types (EC numbers)
    are most suitable for catalyzing a given chemical reaction.
    """
    
    # Default API URL
    DEFAULT_API_URL = "https://cadd.iddd.group/retroplanner/api/enzyme_recommender"
    
    def __init__(self, api_url: str = None, timeout: int = 60):
        """
        Initialize the predictor.
        
        Args:
            api_url: RetroPlanner API URL (default: https://cadd.iddd.group/retroplanner/api/enzyme_recommender)
            timeout: Request timeout in seconds (default: 60)
        """
        self.api_url = api_url or self.DEFAULT_API_URL
        self.timeout = timeout
    
    def predict(self, reaction: str, output_topk: int = 1) -> Dict[str, Any]:
        """
        Predict enzyme types for a given reaction.
        
        Args:
            reaction: Reaction SMILES string (format: "reactants>>products")
                     Example: "CC(=O)O>>CCO"
            output_topk: Number of top recommendations to return (default: 1)
            
        Returns:
            Dictionary containing:
            - success: bool indicating if prediction was successful
            - recommendations: list of dicts with ec_number and confidence
            - formatted: list of formatted strings for display
            - error: error message if failed
        """
        try:
            # Validate input
            if not reaction or ">>" not in reaction:
                return {
                    "success": False,
                    "error": "Invalid reaction format. Expected format: 'reactants>>products'"
                }
            
            # Call the remote API
            response = requests.post(
                self.api_url,
                headers={"Content-Type": "application/json"},
                json={"reaction": reaction},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return self._parse_success_response(response.json(), topk=output_topk)
            elif response.status_code == 400:
                error_msg = response.json().get("message", "Bad request.")
                return {"success": False, "error": error_msg}
            else:
                return {
                    "success": False,
                    "error": f"Request failed with status {response.status_code}: {response.text}"
                }
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": f"Request timed out after {self.timeout} seconds"
            }
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "error": "Failed to connect to the RetroPlanner API"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Enzyme type prediction failed: {str(e)}"
            }
    
    def _parse_success_response(self, data: Dict[str, Any], topk: int=5) -> Dict[str, Any]:
        """
        Parse the successful response from the API.
        
        Args:
            data: JSON response from the API
            topk: Number of top recommendations to include
            
        Returns:
            Parsed result dictionary
        """
        result = data.get("results", {})
        enzymes = result.get("recommended enzyme type", [[]])
        confidences = result.get("confidence", [[]])
        
        # Handle empty results
        if not enzymes or not enzymes[0]:
            return {
                "success": True,
                "recommendations": [],
                "formatted": [],
                "message": "No enzyme recommendations found for this reaction."
            }
        
        # Build recommendations list
        recommendations = []
        formatted = []
        
        for ec, conf in zip(enzymes[0], confidences[0]):
            recommendations.append({
                "ec_number": ec,
                "confidence": round(float(conf), 4)
            })
            formatted.append(f"EC: {ec} | Confidence: {conf:.4f}")
        recommendations = recommendations[:topk]
        formatted = formatted[:topk]
        return {
            "success": True,
            "recommendations": recommendations,
            "formatted": formatted,
            "total_count": len(recommendations)
        }
    
    def predict_formatted(self, reaction: str) -> str:
        """
        Predict enzyme types and return formatted string result.
        
        Args:
            reaction: Reaction SMILES string
            
        Returns:
            Formatted string with recommendations or error message
        """
        result = self.predict(reaction, output_topk=1)
        
        if not result.get("success"):
            return f"[ERROR] {result.get('error', 'Unknown error')}"
        
        formatted = result.get("formatted", [])
        if not formatted:
            return result.get("message", "No enzyme recommendations found.")
        
        return "\n".join(formatted)
    
    def predict_top_k(self, reaction: str, k: int = 5) -> Dict[str, Any]:
        """
        Predict top K enzyme types for a given reaction.
        
        Args:
            reaction: Reaction SMILES string
            k: Number of top recommendations to return
            
        Returns:
            Dictionary with top K recommendations
        """
        result = self.predict(reaction, output_topk=k)
        
        if not result.get("success"):
            return result
        
        recommendations = result.get("recommendations", [])[:k]
        formatted = result.get("formatted", [])[:k]
        
        return {
            "success": True,
            "recommendations": recommendations,
            "formatted": formatted,
            "total_count": len(recommendations),
            "k": k
        }
    
    def predict_to_markdown(self, reaction: str) -> str:
        """
        Predict enzyme types and return markdown table.
        
        Args:
            reaction: Reaction SMILES string
            
        Returns:
            Markdown formatted table
        """
        result = self.predict(reaction, output_topk=5)
        
        if not result.get("success"):
            return f"**Error**: {result.get('error', 'Unknown error')}"
        
        recommendations = result.get("recommendations", [])
        if not recommendations:
            return "No enzyme type recommendations found for this reaction."
        
        # Build markdown table
        lines = [
            "| Rank | EC Number | Confidence |",
            "|------|-----------|------------|"
        ]
        
        for i, rec in enumerate(recommendations, 1):
            ec = rec.get("ec_number", "N/A")
            conf = rec.get("confidence", 0)
            lines.append(f"| {i} | {ec} | {conf:.4f} |")
        
        return "\n".join(lines)
