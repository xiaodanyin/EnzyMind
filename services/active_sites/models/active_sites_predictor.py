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
from urllib.parse import quote
from .easifa_access import configured_api_base, load_owner_key, request_owner, SESSION_HEADER


class ActiveSitesPredictor:
    """
    Predicts enzyme active sites using the EasIFA API.
    
    The EasIFA (Easy Identification of Functional Active sites) service
    identifies enzyme active sites based on UniProt ID, sequence, or structure.
    
    The API is asynchronous - submitting a task returns a job_id,
    and results must be polled for completion.
    """
    
    # EasIFA API URLs in failover order.
    API_BASES = (
        "https://cadd.drugflow.com/easifa/api",
        "https://cadd.zju.edu.cn/easifa/api",
        "https://cadd.iddd.group/easifa/api",
    )
    API_BASE = API_BASES[0]
    
    def __init__(self, api_base: str = None, timeout: int = 30, *, session_key=None, session_file=None):
        """
        Initialize the predictor.
        
        Args:
            api_base: EasIFA API base URL (default: https://cadd.drugflow.com/easifa/api)
            timeout: Request timeout in seconds (default: 30)
        """
        api_base = api_base or configured_api_base()
        if api_base:
            # Preserve the existing custom-endpoint behavior when explicitly set.
            self.api_bases = (api_base.rstrip("/"),)
        else:
            self.api_bases = tuple(base.rstrip("/") for base in self.API_BASES)
        self.api_base = self.api_bases[0]
        self.timeout = timeout
        self._session_key = session_key
        self._session_file = session_file
        self._saved_owner = None

    def _ordered_api_bases(self) -> List[str]:
        """Return API bases with the last successful endpoint tried first."""
        return [self.api_base] + [
            base for base in self.api_bases if base != self.api_base
        ]

    def _rewind_request_files(self, files: Optional[Dict[str, Any]]) -> None:
        """Rewind uploaded files before retrying a request on a backup endpoint."""
        if not files:
            return

        for file_value in files.values():
            file_object = (
                file_value[1]
                if isinstance(file_value, tuple) and len(file_value) > 1
                else file_value
            )
            if hasattr(file_object, "seek"):
                file_object.seek(0)

    def _request_json_with_fallback(
        self,
        request_func,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Request JSON from EasIFA, falling back across the configured API URLs."""
        owner = request_owner.get()
        if owner is None:
            if self._saved_owner is None:
                self._saved_owner = load_owner_key(self.api_bases, session_key=self._session_key,
                                                   session_file=self._session_file)
            owner = self._saved_owner
        # Per-call headers keep concurrent users isolated on the shared predictor.
        headers = requests.structures.CaseInsensitiveDict(kwargs.pop("headers", None) or {})
        headers[SESSION_HEADER] = owner
        kwargs["headers"] = headers
        kwargs["allow_redirects"] = False
        last_error = None

        for api_base in self._ordered_api_bases():
            try:
                self._rewind_request_files(kwargs.get("files"))
                response = request_func(f"{api_base}/{endpoint.lstrip('/')}", **kwargs)
            except Exception as exc:
                last_error = {"success": False, "error": str(exc)}
                continue

            if response.status_code != 200:
                last_error = {
                    "success": False,
                    "error": self._format_http_error(response)
                }
                continue

            parse_result = self._parse_json_response(response, api_base=api_base)
            if not parse_result.get("success"):
                last_error = parse_result
                continue

            self.api_base = api_base
            return parse_result

        return last_error or {
            "success": False,
            "error": "No EasIFA API endpoint is configured"
        }

    def _response_preview(self, response: requests.Response, max_length: int = 200) -> str:
        """Return a short single-line preview of the response body."""
        text = getattr(response, "text", "")
        if text is None:
            return "<empty body>"

        preview = " ".join(str(text).split())
        if not preview:
            return "<empty body>"

        if len(preview) > max_length:
            return f"{preview[:max_length]}..."
        return preview

    def _format_http_error(self, response: requests.Response) -> str:
        """Build a readable error message for non-200 downstream responses."""
        parts = [f"Status code {response.status_code}"]

        location = getattr(response, "headers", {}).get("location")
        if location:
            parts.append(f"location={location}")

        body_preview = self._response_preview(response)
        if body_preview:
            parts.append(f"body={body_preview}")
        if response.status_code == 404:
            parts.append("Private jobs require the original X-Easifa-Session key or session cookie; a new key cannot restore lost access")

        return "; ".join(parts)

    def _parse_json_response(
        self,
        response: requests.Response,
        api_base: Optional[str] = None
    ) -> Dict[str, Any]:
        """Safely parse a downstream JSON response with a helpful error message."""
        try:
            return {"success": True, "data": response.json()}
        except ValueError:
            content_type = getattr(response, "headers", {}).get("content-type", "unknown")
            response_url = getattr(
                response,
                "url",
                f"{api_base or self.api_base}/<unknown>"
            )
            return {
                "success": False,
                "error": (
                    "Expected JSON from EasIFA but received a non-JSON response "
                    f"(status={response.status_code}, content_type={content_type}, "
                    f"url={response_url}, body={self._response_preview(response)})"
                )
            }
    
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
            parse_result = self._request_json_with_fallback(
                requests.post,
                "from_uniprot",
                headers={"Content-Type": "application/json"},
                json={
                    "uniprot_id": uniprot_id,
                    "use_celery": use_celery
                },
                timeout=self.timeout,
                allow_redirects=False
            )
            if not parse_result.get("success"):
                return parse_result

            data = parse_result["data"]
            
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
            
            parse_result = self._request_json_with_fallback(
                requests.post,
                "from_sequence",
                data=form_data,
                timeout=self.timeout,
                allow_redirects=False
            )
            if not parse_result.get("success"):
                return parse_result

            data = parse_result["data"]
            
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
                
                parse_result = self._request_json_with_fallback(
                    requests.post,
                    "from_structure",
                    files=files,
                    data=form_data,
                    timeout=self.timeout,
                    allow_redirects=False
                )
            if not parse_result.get("success"):
                return parse_result

            data = parse_result["data"]
            
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
            parse_result = self._request_json_with_fallback(
                requests.get,
                f"job/{quote(job_id, safe='')}",
                timeout=self.timeout,
                allow_redirects=False
            )
            if not parse_result.get("success"):
                return parse_result

            data = parse_result["data"]
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
            parse_result = self._request_json_with_fallback(
                requests.get,
                f"results/{quote(job_id, safe='')}",
                timeout=60,
                allow_redirects=False
            )
            if not parse_result.get("success"):
                return parse_result

            return {"success": True, "data": parse_result["data"]}
            
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
