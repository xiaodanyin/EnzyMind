# enzyme_subclass/models/subclass_query.py
"""Enzyme Subclass Query Module."""

import os
import random
from typing import Dict, Any, List, Optional


class EnzymeSubclassQuery:
    """Query enzyme subclass information from local database."""
    
    # Alias mapping for enzyme class names (lowercase → standard)
    ENZYME_CLASS_ALIASES = {
        "oxidoreductase": "Oxidoreductases",
        "oxidoreductases": "Oxidoreductases",
        "Oxidoreductase": "Oxidoreductases",
        "transferase": "Transferases",
        "transferases": "Transferases",
        "Transferase": "Transferases",
        "hydrolase": "Hydrolases",
        "hydrolases": "Hydrolases",
        "Hydrolase": "Hydrolases",
        "lyase": "Lyases",
        "lyases": "Lyases",
        "Lyase": "Lyases",
        "isomerase": "Isomerases",
        "isomerases": "Isomerases",
        "Isomerase": "Isomerases",
        "ligase": "Ligases",
        "ligases": "Ligases",
        "Ligase": "Ligases",
        "translocase": "Translocases",
        "translocases": "Translocases",
        "Translocase": "Translocases",
    }
    
    # Mapping from class name to EC number prefix
    ENZYME_CLASS_TO_NUMBER = {
        "Oxidoreductases": 1,
        "Transferases": 2,
        "Hydrolases": 3,
        "Lyases": 4,
        "Isomerases": 5,
        "Ligases": 6,
        "Translocases": 7
    }
    
    def __init__(self, data_file: Optional[str] = None):
        """
        Initialize the EnzymeSubclassQuery.
        
        Args:
            data_file: Path to the enzyme database file.
                      If None, uses default path.
        """
        if data_file is None:
            # Default data file location
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.data_file = os.path.join(base_dir, "data", "enzy_database_processed.txt")
        else:
            self.data_file = data_file
        
        self._class_dict = None
    
    def _load_data(self) -> Dict[int, List[Dict[str, Any]]]:
        """
        Load and parse enzyme database file.
        
        Returns:
            Dictionary mapping EC class number to list of entries
        """
        if self._class_dict is not None:
            return self._class_dict
        
        if not os.path.exists(self.data_file):
            raise FileNotFoundError(f"Enzyme database file not found: {self.data_file}")
        
        class_dict = {}
        
        with open(self.data_file, 'r') as file:
            content = file.read()
        
        entries = content.strip().split('//\n')
        
        for entry in entries:
            if not entry.strip():
                continue
                
            lines = entry.strip().split('\n')
            entry_data = {"ID": "", "DE": "", "CA": [], "DR": []}
            ec_class_line = None
            
            for line in lines:
                if line.startswith('ID'):
                    parts = line.split()
                    if len(parts) > 1:
                        entry_data['ID'] = parts[1]
                        try:
                            ec_class_line = int(entry_data['ID'].split('.')[0])
                        except ValueError:
                            continue
                elif line.startswith('DE'):
                    entry_data['DE'] = line[5:].strip()
                elif line.startswith('CA'):
                    entry_data['CA'].append(line[5:].strip())
                elif line.startswith('DR'):
                    dr_content = line[5:].strip()
                    if dr_content:
                        # Split by '; ' and remove empty strings
                        dr_items = [item.strip() for item in dr_content.split('; ') if item.strip()]
                        entry_data['DR'].extend(dr_items)
            
            if ec_class_line is not None:
                if ec_class_line not in class_dict:
                    class_dict[ec_class_line] = []
                class_dict[ec_class_line].append(entry_data)
        
        self._class_dict = class_dict
        return class_dict
    
    def normalize_class_name(self, query: str) -> Optional[str]:
        """
        Normalize enzyme class name to standard form.
        
        Args:
            query: User input enzyme class name
            
        Returns:
            Normalized class name or None if invalid
        """
        # Try exact match first
        if query in self.ENZYME_CLASS_ALIASES:
            return self.ENZYME_CLASS_ALIASES[query]
        
        # Try lowercase match
        query_lower = query.strip().lower()
        for key, value in self.ENZYME_CLASS_ALIASES.items():
            if key.lower() == query_lower:
                return value
        
        return None
    
    def get_subclasses(
        self,
        query: str,
        num_samples: int = 5,
        seed: int = 42
    ) -> Dict[str, Any]:
        """
        Get enzyme subclass information.
        
        Args:
            query: Enzyme class name (e.g., "Oxidoreductases", "hydrolase")
            num_samples: Number of random samples to return
            seed: Random seed for reproducibility
            
        Returns:
            Dictionary containing result or error
        """
        # Normalize class name
        norm_name = self.normalize_class_name(query)
        if norm_name is None:
            return {
                "success": False,
                "error": f"Invalid enzyme class name: {query}",
                "valid_classes": list(self.ENZYME_CLASS_TO_NUMBER.keys()),
                "result": None,
                "subclasses": []
            }
        
        try:
            class_dict = self._load_data()
        except FileNotFoundError as e:
            return {
                "success": False,
                "error": str(e),
                "result": None,
                "subclasses": []
            }
        
        ec_class = self.ENZYME_CLASS_TO_NUMBER[norm_name]
        subclasses = class_dict.get(ec_class, [])
        
        if not subclasses:
            return {
                "success": True,
                "enzyme_class": norm_name,
                "ec_prefix": ec_class,
                "result": f"No subclasses found for {norm_name}.",
                "subclasses": [],
                "total_available": 0,
                "sampled": 0
            }
        
        # Sample subclasses
        random.seed(seed)
        total_available = len(subclasses)
        
        if len(subclasses) > num_samples:
            sampled_subclasses = random.sample(subclasses, num_samples)
        else:
            sampled_subclasses = subclasses
        
        # Generate markdown output
        markdown_output = self._generate_markdown(norm_name, sampled_subclasses)
        
        return {
            "success": True,
            "enzyme_class": norm_name,
            "ec_prefix": ec_class,
            "result": markdown_output,
            "subclasses": sampled_subclasses,
            "total_available": total_available,
            "sampled": len(sampled_subclasses)
        }
    
    def _generate_markdown(self, class_name: str, subclasses: List[Dict[str, Any]]) -> str:
        """
        Generate markdown formatted output.
        
        Args:
            class_name: Enzyme class name
            subclasses: List of subclass entries
            
        Returns:
            Markdown formatted string
        """
        markdown_output = f"**Selected {class_name} subclasses:**\n\n"
        
        for subclass in subclasses:
            ec_number = subclass.get('ID', 'N/A')
            description = subclass.get('DE', 'N/A')
            catalytic_activity = subclass.get('CA', [])
            uniprot_ids = subclass.get('DR', [])[:5]  # Limit to 5 UniProt IDs
            
            markdown_output += f"### EC number: {ec_number}\n"
            markdown_output += f"**Description:** {description}\n"
            
            for idx, ca in enumerate(catalytic_activity, 1):
                markdown_output += f"**Catalytic activity ({idx}):** {ca}\n"
            
            if uniprot_ids:
                markdown_output += "**UniProt ID:**\n"
                for dr in uniprot_ids:
                    markdown_output += f"- {dr}\n"
            
            markdown_output += "\n" + "-" * 30 + "\n"
        
        return markdown_output
    
    def get_all_classes(self) -> Dict[str, int]:
        """
        Get all available enzyme classes.
        
        Returns:
            Dictionary mapping class names to EC numbers
        """
        return self.ENZYME_CLASS_TO_NUMBER.copy()
    
    def get_class_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the loaded enzyme database.
        
        Returns:
            Dictionary with statistics
        """
        try:
            class_dict = self._load_data()
        except FileNotFoundError:
            return {
                "success": False,
                "error": "Database file not found",
                "statistics": {}
            }
        
        stats = {}
        for class_name, ec_num in self.ENZYME_CLASS_TO_NUMBER.items():
            entries = class_dict.get(ec_num, [])
            stats[class_name] = {
                "ec_prefix": ec_num,
                "count": len(entries)
            }
        
        total = sum(s["count"] for s in stats.values())
        
        return {
            "success": True,
            "total_entries": total,
            "by_class": stats
        }
