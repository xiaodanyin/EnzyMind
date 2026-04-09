# active_sites/models/active_sites_predictor.py
"""
Active Sites Predictor using EasIFA API

EasIFA API endpoints:
- POST /from_uniprot - Submit UniProt ID task (JSON body with use_celery)
- POST /from_sequence - Submit sequence task (Form data with use_celery)
- POST /from_structure - Submit PDB structure task (Form data with file upload)
- GET /job/{job_id} - Check job status
- GET /results/{job_id} - Get job results
- GET /database/detail/{uniprot_id} - Get cached results from database
"""

import requests
import pandas as pd
import time
from typing import Optional, List, Tuple, Set, Dict, Any


class ActiveSitesPredictor:
    """
    Predicts enzyme active sites using the EasIFA API.
    
    The EasIFA (Easy Identification of Functional Active sites) service
    identifies enzyme active sites based on UniProt ID, sequence, or structure.
    
    The API is asynchronous - submitting a task returns a job_id,
    and results must be polled for completion.
    """
    
    # API Base URL
    API_BASE = "https://cadd.zju.edu.cn/easifa/api"
    
    def __init__(self, api_base: str = None, timeout: int = 30):
        """
        Initialize the predictor.
        
        Args:
            api_base: EasIFA API base URL (default: https://cadd.zju.edu.cn/easifa/api)
            timeout: Request timeout in seconds (default: 30)
        """
        self.api_base = api_base or self.API_BASE
        self.timeout = timeout
    
    # ============== Public Submission Methods ==============
    
    def submit_uniprot(self, uniprot_id: str, use_celery: bool = True) -> Dict[str, Any]:
        """
        Submit a prediction task using UniProt ID.
        Uses JSON body with Content-Type: application/json
        
        Args:
            uniprot_id: UniProt ID of the enzyme
            use_celery: Whether to use async (celery) mode
            
        Returns:
            Dictionary with job_id or error
        """
        try:
            response = requests.post(
                f"{self.api_base}/from_uniprot",
                headers={"Content-Type": "application/json"},
                json={
                    "uniprot_id": uniprot_id,
                    "use_celery": use_celery
                },
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Status code {response.status_code}: {response.text}"
                }
            
            data = response.json()
            
            if "error" in data:
                return {"success": False, "error": data["error"]}
            
            job_id = data.get("job_id")
            if not job_id:
                return {"success": False, "error": "No job_id returned from API"}
            
            return {
                "success": True,
                "job_id": job_id,
                "task_manager": data.get("task_manager", "celery")
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def submit_sequence(self, aa_sequence: str, rxn_smiles: str = None, 
                        use_celery: bool = True) -> Dict[str, Any]:
        """
        Submit a prediction task using amino acid sequence.
        Uses Form data (multipart/form-data)
        
        Args:
            aa_sequence: Amino acid sequence
            rxn_smiles: Optional reaction SMILES
            use_celery: Whether to use async (celery) mode
            
        Returns:
            Dictionary with job_id or error
        """
        try:
            form_data = {
                "aa_sequence": aa_sequence,
                "use_celery": str(use_celery).lower()
            }
            if rxn_smiles:
                form_data["rxn_smiles"] = rxn_smiles
            
            response = requests.post(
                f"{self.api_base}/from_sequence",
                data=form_data,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Status code {response.status_code}: {response.text}"
                }
            
            data = response.json()
            
            if "error" in data:
                return {"success": False, "error": data["error"]}
            
            job_id = data.get("job_id")
            if not job_id:
                return {"success": False, "error": "No job_id returned from API"}
            
            return {
                "success": True,
                "job_id": job_id,
                "task_manager": data.get("task_manager", "celery")
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def submit_structure(self, pdb_file_path: str, rxn_smiles: str = None,
                         use_celery: bool = True) -> Dict[str, Any]:
        """
        Submit a prediction task using PDB structure file.
        Uses Form data with file upload (multipart/form-data)
        
        Args:
            pdb_file_path: Path to PDB file
            rxn_smiles: Optional reaction SMILES
            use_celery: Whether to use async (celery) mode
            
        Returns:
            Dictionary with job_id or error
        """
        try:
            with open(pdb_file_path, 'rb') as f:
                files = {
                    "pdb_file": (pdb_file_path.split('/')[-1], f, "chemical/x-pdb")
                }
                form_data = {
                    "use_celery": str(use_celery).lower()
                }
                if rxn_smiles:
                    form_data["rxn_smiles"] = rxn_smiles
                
                response = requests.post(
                    f"{self.api_base}/from_structure",
                    files=files,
                    data=form_data,
                    timeout=self.timeout
                )
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Status code {response.status_code}: {response.text}"
                }
            
            data = response.json()
            
            if "error" in data:
                return {"success": False, "error": data["error"]}
            
            job_id = data.get("job_id")
            if not job_id:
                return {"success": False, "error": "No job_id returned from API"}
            
            return {
                "success": True,
                "job_id": job_id,
                "task_manager": data.get("task_manager", "celery")
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ============== Job Status and Results ==============
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get the status of a submitted job.
        
        Args:
            job_id: Job ID returned from submit
            
        Returns:
            Dictionary with job status
        """
        try:
            response = requests.get(
                f"{self.api_base}/job/{job_id}",
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Status code {response.status_code}: {response.text}"
                }
            
            data = response.json()
            status = data.get("status", "unknown")
            
            return {
                "success": True,
                "status": status,
                "data": data
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_job_results(self, job_id: str) -> Dict[str, Any]:
        """
        Get the results of a completed job.
        
        Args:
            job_id: Job ID returned from submit
            
        Returns:
            Dictionary with job results
        """
        try:
            response = requests.get(
                f"{self.api_base}/results/{job_id}",
                timeout=60
            )
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Status code {response.status_code}: {response.text}"
                }
            
            return {"success": True, "data": response.json()}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ============== Wait for Completion ==============
    
    def wait_for_completion(self, job_id: str, timeout: int = 600, 
                            poll_interval: int = 5) -> Dict[str, Any]:
        """
        Wait for a job to complete and return results.
        
        Args:
            job_id: Job ID to wait for
            timeout: Maximum wait time in seconds
            poll_interval: Seconds between status polls
            
        Returns:
            Dictionary with results or error
        """
        start_time = time.time()
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                return {
                    "success": False,
                    "error": f"Job timed out after {timeout} seconds",
                    "job_id": job_id
                }
            
            status_result = self.get_job_status(job_id)
            if not status_result.get("success"):
                return status_result
            
            status = status_result.get("status", "unknown")
            
            if status == "completed":
                # Get results
                return self.get_job_results(job_id)
            elif status == "failed":
                return {
                    "success": False,
                    "error": f"Job failed: {status_result.get('data', {}).get('error', 'Unknown error')}",
                    "job_id": job_id
                }
            
            # Still pending or running
            time.sleep(poll_interval)
    
    # ============== Result Formatting ==============
    
    def format_results_to_markdown(self, data: Dict[str, Any]) -> str:
        """
        Format job results to markdown table.
        
        Supports multiple data formats:
        1. Direct active_data format: {"active_data": [[11, "GLN", "#FF0000", "Binding Site", "0.6844"], ...]}
        2. Results list format: {"results": [[idx, rxn, active_data], ...]}
        3. Results dict format: {"results": [{"active_data": [...]}, ...]}
        
        Args:
            data: Results data from get_job_results
            
        Returns:
            Markdown table string
        """
        # Collect all unique active sites
        all_active_sites: Set[Tuple] = set()
        
        # Format 1: Direct active_data in top level (new format)
        # Example: {"job_id": "...", "status": "completed", "active_data": [[11, "GLN", "#FF0000", "Binding Site", "0.6844"]], ...}
        if "active_data" in data and isinstance(data["active_data"], list):
            active_data = data["active_data"]
            for site in active_data:
                site_info = self._parse_site_info(site)
                if site_info:
                    all_active_sites.add(site_info)
        
        # Format 2 & 3: Results list format (legacy format)
        results = data.get("results", [])
        if results:
            for item in results:
                # Handle different possible formats
                if isinstance(item, (list, tuple)) and len(item) >= 3:
                    # Format: [idx, rxn, active_data]
                    active_data = item[2] if len(item) > 2 else []
                elif isinstance(item, dict):
                    active_data = item.get("active_data", [])
                else:
                    continue
                
                for site in active_data:
                    site_info = self._parse_site_info(site)
                    if site_info:
                        all_active_sites.add(site_info)
        
        if not all_active_sites:
            return "No active sites predicted."
        
        return self._format_sites_to_markdown(all_active_sites)
    
    def _parse_site_info(self, site: list) -> Optional[Tuple]:
        """
        Parse site information from various formats.
        
        Args:
            site: Site data list
            
        Returns:
            Tuple of (residue_idx, residue_name, active_type, confidence) or None
        """
        if not site or len(site) < 4:
            return None
        
        # site format may be:
        # [residue_idx, residue_name, color, active_type, confidence]
        # [residue_idx, residue_name, color, confidence, active_type]
        if len(site) >= 5:
            # Try to determine format based on data types
            if isinstance(site[3], (int, float)) or (isinstance(site[3], str) and site[3].replace('.', '').replace('-', '').isdigit()):
                # Format: [idx, name, color, confidence, type]
                return (site[0], site[1], site[4], site[3])
            else:
                # Format: [idx, name, color, type, confidence]
                return (site[0], site[1], site[3], site[4])
        elif len(site) >= 4:
            return (site[0], site[1], site[3], "N/A")
        
        return None
    
    def _format_sites_to_markdown(self, all_active_sites: Set[Tuple]) -> str:
        """
        Convert active sites set to markdown table.
        
        Args:
            all_active_sites: Set of (residue_idx, residue_name, active_type, confidence)
            
        Returns:
            Markdown table string
        """
        if not all_active_sites:
            return "No active sites predicted."
        
        # Sort by residue index
        sorted_sites = sorted(all_active_sites, key=lambda x: x[0])
        
        # Create DataFrame and convert to markdown
        df = pd.DataFrame(
            sorted_sites,
            columns=["Residue Index", "Residue Name", "Active Type", "Confidence"]
        )
        markdown_table = df.to_markdown(index=False)
        
        return markdown_table
    
    # ============== Legacy/Convenience Methods ==============
    
    def predict(self, uniprot_id: str) -> str:
        """
        Predict active sites from UniProt ID (synchronous).
        Submits task and waits for completion.
        
        Args:
            uniprot_id: UniProt ID of the enzyme
            
        Returns:
            Markdown table or error message
        """
        submit_result = self.submit_uniprot(uniprot_id)
        if not submit_result.get("success"):
            return f"[ERROR] Failed to submit task: {submit_result.get('error')}"
        
        job_id = submit_result["job_id"]
        wait_result = self.wait_for_completion(job_id)
        
        if not wait_result.get("success"):
            return f"[ERROR] {wait_result.get('error')}"
        
        return self.format_results_to_markdown(wait_result.get("data", {}))
    
    def predict_from_sequence(self, aa_sequence: str, rxn_smiles: str = None) -> str:
        """
        Predict active sites from amino acid sequence (synchronous).
        
        Args:
            aa_sequence: Amino acid sequence
            rxn_smiles: Optional reaction SMILES
            
        Returns:
            Markdown table or error message
        """
        submit_result = self.submit_sequence(aa_sequence, rxn_smiles)
        if not submit_result.get("success"):
            return f"[ERROR] Failed to submit task: {submit_result.get('error')}"
        
        job_id = submit_result["job_id"]
        wait_result = self.wait_for_completion(job_id)
        
        if not wait_result.get("success"):
            return f"[ERROR] {wait_result.get('error')}"
        
        return self.format_results_to_markdown(wait_result.get("data", {}))
    
    def predict_from_structure(self, pdb_file_path: str, rxn_smiles: str = None) -> str:
        """
        Predict active sites from PDB structure file (synchronous).
        
        Args:
            pdb_file_path: Path to PDB file
            rxn_smiles: Optional reaction SMILES
            
        Returns:
            Markdown table or error message
        """
        submit_result = self.submit_structure(pdb_file_path, rxn_smiles)
        if not submit_result.get("success"):
            return f"[ERROR] Failed to submit task: {submit_result.get('error')}"
        
        job_id = submit_result["job_id"]
        wait_result = self.wait_for_completion(job_id)
        
        if not wait_result.get("success"):
            return f"[ERROR] {wait_result.get('error')}"
        
        return self.format_results_to_markdown(wait_result.get("data", {}))
