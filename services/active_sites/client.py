# active_sites/client.py
"""
Active Sites Prediction Service Client

Supports both synchronous and asynchronous prediction modes.
Supports three input types: UniProt ID, Amino Acid Sequence, PDB Structure.
"""

import requests
import time
from typing import Optional, Dict, Any


class ActiveSitesClient:
    """Client for the Active Sites Prediction Service."""
    
    def __init__(self, base_url: str = "http://localhost:18907"):
        """
        Initialize the client.
        
        Args:
            base_url: Base URL of the active sites service
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
    
    # ============== UniProt Submission Methods ==============
    
    def submit_uniprot(self, uniprot_id: str, use_celery: bool = True) -> Dict[str, Any]:
        """
        Submit a prediction task using UniProt ID.
        
        Args:
            uniprot_id: UniProt ID of the enzyme
            use_celery: Whether to use async (celery) mode
            
        Returns:
            Task submission result with job_id
        """
        response = requests.post(
            f"{self.base_url}/api/predict/active-sites/submit/uniprot",
            json={"uniprot_id": uniprot_id, "use_celery": use_celery},
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    
    # ============== Sequence Submission Methods ==============
    
    def submit_sequence(self, aa_sequence: str, rxn_smiles: Optional[str] = None,
                        use_celery: bool = True) -> Dict[str, Any]:
        """
        Submit a prediction task using amino acid sequence.
        
        Args:
            aa_sequence: Amino acid sequence
            rxn_smiles: Optional reaction SMILES
            use_celery: Whether to use async (celery) mode
            
        Returns:
            Task submission result with job_id
        """
        response = requests.post(
            f"{self.base_url}/api/predict/active-sites/submit/sequence",
            json={
                "aa_sequence": aa_sequence,
                "rxn_smiles": rxn_smiles,
                "use_celery": use_celery
            },
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    
    def submit_sequence_form(self, aa_sequence: str, rxn_smiles: Optional[str] = None,
                             use_celery: bool = True) -> Dict[str, Any]:
        """
        Submit a prediction task using amino acid sequence (form input).
        
        Args:
            aa_sequence: Amino acid sequence
            rxn_smiles: Optional reaction SMILES
            use_celery: Whether to use async (celery) mode
            
        Returns:
            Task submission result with job_id
        """
        data = {
            "aa_sequence": aa_sequence,
            "use_celery": str(use_celery).lower()
        }
        if rxn_smiles:
            data["rxn_smiles"] = rxn_smiles
            
        response = requests.post(
            f"{self.base_url}/api/predict/active-sites/submit/sequence/form",
            data=data,
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    
    # ============== Structure Submission Methods ==============
    
    def submit_structure(self, pdb_file_path: str, rxn_smiles: Optional[str] = None,
                         use_celery: bool = True) -> Dict[str, Any]:
        """
        Submit a prediction task using PDB structure file.
        
        Args:
            pdb_file_path: Path to PDB file
            rxn_smiles: Optional reaction SMILES
            use_celery: Whether to use async (celery) mode
            
        Returns:
            Task submission result with job_id
        """
        with open(pdb_file_path, 'rb') as f:
            files = {'pdb_file': (pdb_file_path.split('/')[-1], f, 'application/octet-stream')}
            data = {"use_celery": str(use_celery).lower()}
            if rxn_smiles:
                data["rxn_smiles"] = rxn_smiles
            
            response = requests.post(
                f"{self.base_url}/api/predict/active-sites/submit/structure",
                files=files,
                data=data,
                timeout=60
            )
        response.raise_for_status()
        return response.json()
    
    # ============== Job Status and Results Methods ==============
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get the status of a submitted job.
        
        Args:
            job_id: Job ID returned from submit methods
            
        Returns:
            Job status information
        """
        response = requests.get(
            f"{self.base_url}/api/predict/active-sites/job/{job_id}",
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    
    def get_job_results(self, job_id: str) -> Dict[str, Any]:
        """
        Get the results of a completed job.
        
        Args:
            job_id: Job ID returned from submit methods
            
        Returns:
            Job results if completed
        """
        response = requests.get(
            f"{self.base_url}/api/predict/active-sites/results/{job_id}",
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    
    # ============== Auto-detect Methods ==============
    
    def submit_auto(self, input_data: str, rxn_smiles: Optional[str] = None,
                    use_celery: bool = True) -> Dict[str, Any]:
        """
        Auto-detect input type and submit prediction task.
        
        Supports UniProt ID or amino acid sequence.
        
        Args:
            input_data: Input data (UniProt ID or sequence)
            rxn_smiles: Optional reaction SMILES (for sequence input)
            use_celery: Whether to use async mode
            
        Returns:
            Task submission result with job_id
        """
        data = {
            "input_data": input_data,
            "use_celery": str(use_celery).lower()
        }
        if rxn_smiles:
            data["rxn_smiles"] = rxn_smiles
            
        response = requests.post(
            f"{self.base_url}/api/predict/active-sites/auto",
            data=data,
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    
    # ============== Synchronous Prediction Methods ==============
    
    def predict_active_sites(self, uniprot_id: str, use_celery: bool = True) -> str:
        """
        Predict enzyme active sites from UniProt ID (synchronous).
        
        This method submits the task and waits for the result.
        May take several minutes for new predictions.
        
        Args:
            uniprot_id: UniProt ID of the enzyme
            use_celery: Whether to use async mode
            
        Returns:
            Active sites prediction result as markdown table
        """
        response = requests.post(
            f"{self.base_url}/api/predict/active-sites",
            json={"uniprot_id": uniprot_id, "use_celery": use_celery},
            timeout=700  # Long timeout for sync operation
        )
        response.raise_for_status()
        return response.json()["result"]
    
    def predict_sequence(self, aa_sequence: str, rxn_smiles: Optional[str] = None,
                         use_celery: bool = True, timeout: int = 600) -> str:
        """
        Predict enzyme active sites from amino acid sequence (synchronous).
        
        Args:
            aa_sequence: Amino acid sequence
            rxn_smiles: Optional reaction SMILES
            use_celery: Whether to use async mode
            timeout: Maximum wait time in seconds
            
        Returns:
            Active sites prediction result as markdown table
        """
        data = {
            "aa_sequence": aa_sequence,
            "use_celery": str(use_celery).lower(),
            "timeout": str(timeout)
        }
        if rxn_smiles:
            data["rxn_smiles"] = rxn_smiles
            
        response = requests.post(
            f"{self.base_url}/api/predict/active-sites/sequence",
            data=data,
            timeout=timeout + 30
        )
        response.raise_for_status()
        return response.json()["result"]
    
    def predict_structure(self, pdb_file_path: str, rxn_smiles: Optional[str] = None,
                          use_celery: bool = True, timeout: int = 600) -> str:
        """
        Predict enzyme active sites from PDB structure file (synchronous).
        
        Args:
            pdb_file_path: Path to PDB file
            rxn_smiles: Optional reaction SMILES
            use_celery: Whether to use async mode
            timeout: Maximum wait time in seconds
            
        Returns:
            Active sites prediction result as markdown table
        """
        with open(pdb_file_path, 'rb') as f:
            files = {'pdb_file': (pdb_file_path.split('/')[-1], f, 'application/octet-stream')}
            data = {
                "use_celery": str(use_celery).lower(),
                "timeout": str(timeout)
            }
            if rxn_smiles:
                data["rxn_smiles"] = rxn_smiles
            
            response = requests.post(
                f"{self.base_url}/api/predict/active-sites/structure",
                files=files,
                data=data,
                timeout=timeout + 30
            )
        response.raise_for_status()
        return response.json()["result"]
    
    # ============== Helper Methods ==============
    
    def submit_and_wait(self, uniprot_id: str, poll_interval: int = 5, 
                        max_wait_time: int = 600) -> Dict[str, Any]:
        """
        Submit a UniProt task and wait for completion.
        
        Args:
            uniprot_id: UniProt ID of the enzyme
            poll_interval: Seconds between status polls
            max_wait_time: Maximum seconds to wait
            
        Returns:
            Job results
        """
        # Submit task
        submit_result = self.submit_uniprot(uniprot_id)
        if not submit_result.get("success"):
            return submit_result
        
        return self._wait_for_job(submit_result["job_id"], poll_interval, max_wait_time)
    
    def _wait_for_job(self, job_id: str, poll_interval: int = 5,
                      max_wait_time: int = 600) -> Dict[str, Any]:
        """
        Wait for a job to complete.
        
        Args:
            job_id: Job ID to wait for
            poll_interval: Seconds between status polls
            max_wait_time: Maximum seconds to wait
            
        Returns:
            Job results
        """
        start_time = time.time()
        while True:
            elapsed = time.time() - start_time
            if elapsed > max_wait_time:
                return {
                    "success": False,
                    "error": f"Job timed out after {max_wait_time} seconds",
                    "job_id": job_id
                }
            
            status_result = self.get_job_status(job_id)
            if not status_result.get("success"):
                return status_result
            
            status = status_result.get("status", "unknown")
            
            if status == "completed":
                return self.get_job_results(job_id)
            elif status == "failed":
                return {
                    "success": False,
                    "error": status_result.get("data", {}).get("error", "Job failed"),
                    "job_id": job_id
                }
            
            time.sleep(poll_interval)
    
    # ============== Legacy Methods (for backward compatibility) ==============
    
    def submit_task(self, uniprot_id: str, use_celery: bool = True) -> Dict[str, Any]:
        """
        Legacy method - use submit_uniprot instead.
        """
        return self.submit_uniprot(uniprot_id, use_celery)
    
    def get_from_database(self, uniprot_id: str) -> Dict[str, Any]:
        """
        Legacy method - database endpoint removed in new API.
        Use submit_uniprot for all queries.
        """
        # Try to submit and get results instead
        return self.submit_uniprot(uniprot_id)


if __name__ == "__main__":
    # Example usage
    client = ActiveSitesClient()
    
    # Check health
    print("Health check:", client.health_check())
    
    # Test with a sample UniProt ID
    test_uniprot_id = "F6KCZ5"
    
    # Submit async task
    print(f"\nSubmitting prediction task for {test_uniprot_id}:")
    submit_result = client.submit_uniprot(test_uniprot_id)
    if submit_result.get("success"):
        print(f"Job submitted: {submit_result.get('job_id')}")
        print(f"Input type: {submit_result.get('input_type')}")
    else:
        print(f"Submit failed: {submit_result.get('error')}")
    
    # Example with sequence
    test_sequence = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAV"
    print(f"\nSubmitting sequence prediction:")
    seq_result = client.submit_sequence(test_sequence, rxn_smiles="CC(=O)O>>CC(=O)OC")
    if seq_result.get("success"):
        print(f"Sequence job submitted: {seq_result.get('job_id')}")
    else:
        print(f"Sequence submit failed: {seq_result.get('error')}")
