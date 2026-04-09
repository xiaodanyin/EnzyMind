# enzyme_type/client.py
"""
Enzyme Type Recommendation Service Client

Provides a Python client for interacting with the Enzyme Type Recommendation
Service API.
"""

import requests
from typing import Optional, Dict, Any, List


class EnzymeTypeClient:
    """Client for the Enzyme Type Recommendation Service."""
    
    def __init__(self, base_url: str = "http://localhost:18908"):
        """
        Initialize the client.
        
        Args:
            base_url: Base URL of the enzyme type service
        """
        self.base_url = base_url.rstrip("/")
    
    def health_check(self) -> dict:
        """
        Check service health.
        
        Returns:
            Health status dict
        """
        response = requests.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
    
    def recommend(self, reaction: str) -> Dict[str, Any]:
        """
        Get enzyme type recommendations for a reaction.
        
        Args:
            reaction: Reaction SMILES string (format: reactants>>products)
            
        Returns:
            Dictionary with recommendations
        """
        response = requests.post(
            f"{self.base_url}/api/query/enzyme-type",
            json={"query": reaction},
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    
    def recommend_form(self, reaction: str) -> Dict[str, Any]:
        """
        Get enzyme type recommendations using form input.
        
        Args:
            reaction: Reaction SMILES string
            
        Returns:
            Dictionary with recommendations
        """
        response = requests.post(
            f"{self.base_url}/api/query/enzyme-type/form",
            data={"query": reaction},
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    
    def recommend_top_k(self, reaction: str, k: int = 5) -> Dict[str, Any]:
        """
        Get top K enzyme type recommendations.
        
        Args:
            reaction: Reaction SMILES string
            k: Number of top recommendations
            
        Returns:
            Dictionary with top K recommendations
        """
        response = requests.post(
            f"{self.base_url}/api/query/enzyme-type/top-k",
            json={"query": reaction, "k": k},
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    
    def recommend_formatted(self, reaction: str) -> str:
        """
        Get enzyme type recommendations as formatted string.
        
        Args:
            reaction: Reaction SMILES string
            
        Returns:
            Formatted string with recommendations
        """
        response = requests.post(
            f"{self.base_url}/api/query/enzyme-type/formatted",
            json={"query": reaction},
            timeout=60
        )
        response.raise_for_status()
        return response.json()["result"]
    
    def recommend_markdown(self, reaction: str) -> str:
        """
        Get enzyme type recommendations as markdown table.
        
        Args:
            reaction: Reaction SMILES string
            
        Returns:
            Markdown formatted table
        """
        response = requests.post(
            f"{self.base_url}/api/query/enzyme-type/markdown",
            json={"query": reaction},
            timeout=60
        )
        response.raise_for_status()
        return response.json()["result"]
    
    def recommend_legacy(self, reaction: str) -> Dict[str, Any]:
        """
        Get recommendations using legacy endpoint.
        
        Args:
            reaction: Reaction SMILES string
            
        Returns:
            Dictionary with result list or error
        """
        response = requests.post(
            f"{self.base_url}/query/enzyme-type",
            json={"query": reaction},
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    
    def get_ec_numbers(self, reaction: str) -> List[str]:
        """
        Get just the EC numbers from recommendations.
        
        Args:
            reaction: Reaction SMILES string
            
        Returns:
            List of EC numbers
        """
        result = self.recommend(reaction)
        if not result.get("success"):
            return []
        
        recommendations = result.get("recommendations", [])
        return [rec["ec_number"] for rec in recommendations]
    
    def get_top_ec(self, reaction: str) -> Optional[str]:
        """
        Get the top recommended EC number.
        
        Args:
            reaction: Reaction SMILES string
            
        Returns:
            Top EC number or None if no recommendations
        """
        result = self.recommend(reaction)
        if not result.get("success"):
            return None
        
        recommendations = result.get("recommendations", [])
        if not recommendations:
            return None
        
        return recommendations[0]["ec_number"]


if __name__ == "__main__":
    # Example usage
    client = EnzymeTypeClient()
    
    # Check health
    print("Health check:", client.health_check())
    
    # Test with a sample reaction
    test_reaction = "CC(=O)O>>CCO"
    
    print(f"\nRecommendations for {test_reaction}:")
    result = client.recommend(test_reaction)
    print(f"Success: {result.get('success')}")
    
    if result.get("success"):
        for rec in result.get("recommendations", []):
            print(f"  EC: {rec['ec_number']} | Confidence: {rec['confidence']}")
    else:
        print(f"Error: {result.get('error')}")
    
    # Get markdown table
    print("\nMarkdown table:")
    print(client.recommend_markdown(test_reaction))
