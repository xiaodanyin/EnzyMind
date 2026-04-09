# structure_predict/client.py
"""
Structure Prediction Service Client

Provides a Python client for interacting with the Structure Prediction Service API.
"""

import requests
from typing import Optional, Dict, Any
from pathlib import Path


class StructurePredictClient:
    """Client for the Structure Prediction Service."""
    
    def __init__(self, base_url: str = "http://localhost:18906"):
        """
        Initialize the client.
        
        Args:
            base_url: Base URL of the structure prediction service
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
    
    def get_config(self) -> dict:
        """
        Get ESMFold configuration status.
        
        Returns:
            Configuration status dict
        """
        response = requests.get(f"{self.base_url}/api/config")
        response.raise_for_status()
        return response.json()
    
    def predict(
        self,
        query: str,
        input_type: str = "auto",
        output_name: str = "query"
    ) -> Dict[str, Any]:
        """
        Predict protein structure.
        
        Args:
            query: Protein sequence, UniProt ID, or FASTA content
            input_type: Type of input (auto, sequence, uniprot, fasta)
            output_name: Name for output files
            
        Returns:
            Prediction result dict
        """
        response = requests.post(
            f"{self.base_url}/api/predict/structure",
            json={
                "query": query,
                "input_type": input_type,
                "output_name": output_name
            },
            timeout=3600  # 1 hour timeout for large sequences
        )
        response.raise_for_status()
        return response.json()
    
    def predict_form(
        self,
        query: str,
        input_type: str = "auto",
        output_name: str = "query"
    ) -> Dict[str, Any]:
        """
        Predict protein structure using form input.
        
        Args:
            query: Protein sequence, UniProt ID, or FASTA content
            input_type: Type of input
            output_name: Name for output files
            
        Returns:
            Prediction result dict
        """
        response = requests.post(
            f"{self.base_url}/api/predict/structure/form",
            data={
                "query": query,
                "input_type": input_type,
                "output_name": output_name
            },
            timeout=3600
        )
        response.raise_for_status()
        return response.json()
    
    def predict_file(
        self,
        file_path: str,
        output_name: str = "query"
    ) -> Dict[str, Any]:
        """
        Predict protein structure from FASTA file.
        
        Args:
            file_path: Path to FASTA file
            output_name: Name for output files
            
        Returns:
            Prediction result dict
        """
        with open(file_path, "rb") as f:
            response = requests.post(
                f"{self.base_url}/api/predict/structure/file",
                files={"file": f},
                data={"output_name": output_name},
                timeout=3600
            )
        response.raise_for_status()
        return response.json()
    
    def predict_from_uniprot(
        self,
        uniprot_id: str,
        output_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Predict protein structure from UniProt ID.
        
        Args:
            uniprot_id: UniProt accession ID
            output_name: Name for output files (defaults to UniProt ID)
            
        Returns:
            Prediction result dict
        """
        return self.predict(
            query=uniprot_id,
            input_type="uniprot",
            output_name=output_name or uniprot_id
        )
    
    def predict_from_sequence(
        self,
        sequence: str,
        output_name: str = "query"
    ) -> Dict[str, Any]:
        """
        Predict protein structure from amino acid sequence.
        
        Args:
            sequence: Amino acid sequence
            output_name: Name for output files
            
        Returns:
            Prediction result dict
        """
        return self.predict(
            query=sequence,
            input_type="sequence",
            output_name=output_name
        )
    
    def process_sequence(self, query: str) -> Dict[str, Any]:
        """
        Process and validate input sequence without prediction.
        
        Args:
            query: Input to process
            
        Returns:
            Processed sequence info
        """
        response = requests.post(
            f"{self.base_url}/api/sequence/process",
            json={"query": query},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    
    def predict_legacy(
        self,
        query: str,
        input_type: str = "sequence"
    ) -> Dict[str, Any]:
        """
        Use legacy endpoint for backward compatibility.
        
        Args:
            query: Protein sequence or FASTA content
            input_type: Type of input
            
        Returns:
            Legacy format result
        """
        response = requests.post(
            f"{self.base_url}/predict/structure",
            data={
                "input_type": input_type,
                "query": query
            },
            timeout=3600
        )
        response.raise_for_status()
        return response.json()
    
    def download_pdb(
        self,
        static_path: str,
        save_path: str
    ) -> str:
        """
        Download predicted PDB file.
        
        Args:
            static_path: Static path returned from prediction
            save_path: Local path to save PDB file
            
        Returns:
            Path to saved file
        """
        # Construct full URL
        if static_path.startswith("/"):
            url = f"{self.base_url}{static_path}"
        else:
            url = f"{self.base_url}/{static_path}"
        
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        
        with open(save_path, "wb") as f:
            f.write(response.content)
        
        return save_path


if __name__ == "__main__":
    # Example usage
    client = StructurePredictClient()
    
    # Check health
    print("Health check:", client.health_check())
    
    # Check configuration
    print("\nConfiguration:", client.get_config())
    
    # Test sequence processing
    test_seq = "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"
    print(f"\nProcessing sequence: {test_seq[:30]}...")
    result = client.process_sequence(test_seq)
    print(f"Result: {result}")
