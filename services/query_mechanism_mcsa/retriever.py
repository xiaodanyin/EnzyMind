"""
Enzyme Retriever: Query interface for M-CSA database

This module provides the EnzymeRetriever class for querying enzyme information
from the SQLite database using various identifier types (MCSA ID, UniProt ID, PDB ID).
"""

import json
from typing import Any, Dict, List, Optional
from pathlib import Path

from sqlalchemy import create_engine, or_
from sqlalchemy.orm import Session, sessionmaker, joinedload, selectinload

from models import (
    Base, Enzyme, Identifier, ProteinSequence, Residue, ResidueRole,
    ResidueUniProt, ResiduePDB, Reaction, ReactionCompound, Mechanism,
    MechanismStep, MechanismReference, Cofactor, CofactorRole,
    MechanismParsedStep
)


class EnzymeRetriever:
    """
    A class for retrieving enzyme information from the M-CSA database.
    
    Supports querying by:
    - MCSA ID (e.g., "1", "M1", "MCSA:1")
    - UniProt ID (e.g., "P56868")
    - PDB ID (e.g., "1b73")
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the EnzymeRetriever with a database connection.
        
        Args:
            db_path: Path to the SQLite database file. If None, uses default path.
        """
        if db_path is None:
            db_path = str(Path(__file__).parent / "db" / "mcsa.db")
        
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def _get_session(self) -> Session:
        """Create and return a new database session."""
        return self.SessionLocal()
    
    def _normalize_query(self, query_id: str) -> tuple:
        """
        Normalize the query ID and detect its type.
        
        Args:
            query_id: The input query string
            
        Returns:
            Tuple of (normalized_value, detected_type)
            detected_type can be 'mcsa', 'uniprot', 'pdb', or 'unknown'
        """
        query_id = query_id.strip()
        
        # Check for MCSA ID formats
        if query_id.upper().startswith("MCSA:"):
            return query_id[5:], "mcsa"
        if query_id.upper().startswith("M") and query_id[1:].isdigit():
            return query_id[1:], "mcsa"
        if query_id.isdigit():
            return query_id, "mcsa"
        
        # Check for PDB ID format (4 characters, starts with digit)
        if len(query_id) == 4 and query_id[0].isdigit():
            return query_id.lower(), "pdb"
        
        # Check for UniProt ID format (typically starts with letter, contains digits)
        if len(query_id) >= 6 and query_id[0].isalpha():
            return query_id.upper(), "uniprot"
        
        # Try to match against any identifier
        return query_id, "unknown"
    
    def _filter_cxsmiles_fields(self, obj: Any) -> Any:
        """
        Recursively filter out CXSMILES-related fields from electron flow data.
        
        This helps reduce token usage when CXSMILES information is not needed.
        Removes fields containing 'cxsmiles' in their name.
        
        Args:
            obj: The object to filter (dict, list, or primitive)
            
        Returns:
            Filtered object with cxsmiles-related fields removed
        """
        if isinstance(obj, dict):
            return {
                k: self._filter_cxsmiles_fields(v) 
                for k, v in obj.items() 
                if 'cxsmiles' not in k.lower()
            }
        elif isinstance(obj, list):
            return [self._filter_cxsmiles_fields(item) for item in obj]
        else:
            return obj
    
    def _find_mcsa_id(self, session: Session, query_id: str) -> Optional[int]:
        """
        Find the MCSA ID corresponding to any identifier.
        
        Args:
            session: Database session
            query_id: The query string
            
        Returns:
            The MCSA ID if found, None otherwise
        """
        normalized, id_type = self._normalize_query(query_id)
        
        if id_type == "mcsa":
            try:
                return int(normalized)
            except ValueError:
                pass
        
        # Search in Identifier table
        query = session.query(Identifier.mcsa_id)
        
        if id_type != "unknown":
            query = query.filter(
                Identifier.identifier_type == id_type,
                Identifier.identifier_value == normalized
            )
        else:
            # Search across all identifier types
            query = query.filter(
                or_(
                    Identifier.identifier_value == normalized,
                    Identifier.identifier_value == normalized.upper(),
                    Identifier.identifier_value == normalized.lower()
                )
            )
        
        result = query.first()
        return result[0] if result else None
    
    def get_enzyme_info(self, query_id: str, include_smiles: bool = False, include_visualization: bool = False) -> Optional[Dict[str, Any]]:
        """
        Retrieve comprehensive enzyme information by any identifier.
        
        Args:
            query_id: MCSA ID, UniProt ID, or PDB ID
            include_smiles: Whether to include SMILES strings for compounds
            
        Returns:
            Dictionary containing:
            - basic_info: Enzyme name and description
            - active_sites_uniprot: List of active sites with UniProt positions
            - active_sites_pdb: List of active sites with PDB positions
            - reaction: Reactants and products
            - mechanism: Summary and steps
            
            Returns None if enzyme not found.
        """
        session = self._get_session()
        
        try:
            # Find MCSA ID
            mcsa_id = self._find_mcsa_id(session, query_id)
            if mcsa_id is None:
                return None
            
            # Load enzyme with all relationships
            query = session.query(Enzyme).options(
                joinedload(Enzyme.residues).joinedload(Residue.roles),
                joinedload(Enzyme.residues).joinedload(Residue.uniprot_positions),
                joinedload(Enzyme.residues).joinedload(Residue.pdb_positions),
                joinedload(Enzyme.reaction).joinedload(Reaction.compounds),
                joinedload(Enzyme.reaction).joinedload(Reaction.mechanisms).joinedload(Mechanism.steps),
                joinedload(Enzyme.cofactors).joinedload(Cofactor.roles),
            ).filter(Enzyme.mcsa_id == mcsa_id)
            if include_visualization:
                query = query.options(selectinload(Enzyme.sequences),
                    joinedload(Enzyme.reaction).joinedload(Reaction.mechanisms).selectinload(Mechanism.references))
            enzyme = query.first()
            
            if enzyme is None:
                return None
            
            # Build response
            result = {
                "basic_info": self._build_basic_info(enzyme),
                "active_sites_uniprot": self._build_uniprot_sites(enzyme),
                "active_sites_pdb": self._build_pdb_sites(enzyme),
                "reaction": self._build_reaction(enzyme, include_smiles=include_smiles),
                "mechanism": self._build_mechanism(enzyme, include_references=include_visualization),
                "cofactors": self._build_cofactors(enzyme, include_smiles=include_smiles)
            }
            if include_visualization:
                # A homolog's sequence must never be labelled as the reference.
                sequences = {s.sequence for s in enzyme.sequences
                             if s.uniprot_id == enzyme.reference_uniprot_id and s.sequence}
                sequence = next(iter(sequences)) if len(sequences) == 1 else None
                result['sequence_info'] = ({'uniprot_id': enzyme.reference_uniprot_id,
                    'sequence': sequence, 'length': len(sequence), 'source': 'M-CSA reference sequence'}
                    if sequence else None)
            
            return result
        
        finally:
            session.close()
    
    def _build_basic_info(self, enzyme: Enzyme) -> Dict[str, Any]:
        """Build the basic_info section of the response."""
        ec_numbers = []
        if enzyme.all_ecs:
            try:
                ec_numbers = json.loads(enzyme.all_ecs)
            except json.JSONDecodeError:
                ec_numbers = []
        
        return {
            "mcsa_id": enzyme.mcsa_id,
            "enzyme_name": enzyme.enzyme_name,
            "description": enzyme.description,
            "reference_uniprot_id": enzyme.reference_uniprot_id,
            "ec_numbers": ec_numbers,
            "url": enzyme.url
        }
    
    def _build_uniprot_sites(self, enzyme: Enzyme) -> List[Dict[str, Any]]:
        """Build the active_sites_uniprot section of the response."""
        sites = []
        
        for residue in enzyme.residues:
            for uniprot_pos in residue.uniprot_positions:
                # Get unique roles for this residue
                roles = list(set(role.function for role in residue.roles))
                
                site = {
                    "uniprot_id": uniprot_pos.uniprot_id,
                    "code": uniprot_pos.code,
                    "resid": uniprot_pos.resid,
                    "is_reference": uniprot_pos.is_reference,
                    "roles": roles,
                    "roles_summary": residue.roles_summary,
                    "main_annotation": residue.main_annotation
                }
                sites.append(site)
        
        return sites
    
    def _build_pdb_sites(self, enzyme: Enzyme) -> List[Dict[str, Any]]:
        """Build the active_sites_pdb section of the response."""
        sites = []
        
        for residue in enzyme.residues:
            for pdb_pos in residue.pdb_positions:
                # Get unique roles for this residue
                roles = list(set(role.function for role in residue.roles))
                
                site = {
                    "pdb_id": pdb_pos.pdb_id,
                    "chain": pdb_pos.chain_name,
                    "code": pdb_pos.code,
                    "resid": pdb_pos.resid,
                    "auth_resid": pdb_pos.auth_resid,
                    "is_reference": pdb_pos.is_reference,
                    "domain_name": pdb_pos.domain_name,
                    "domain_cath_id": pdb_pos.domain_cath_id,
                    "roles": roles,
                    "roles_summary": residue.roles_summary,
                    "main_annotation": residue.main_annotation
                }
                sites.append(site)
        
        return sites
    
    def _build_reaction(self, enzyme: Enzyme, include_smiles: bool = False) -> Optional[Dict[str, Any]]:
        """Build the reaction section of the response."""
        if enzyme.reaction is None:
            return None
        
        reaction = enzyme.reaction
        
        reactants = []
        products = []
        
        for compound in reaction.compounds:
            compound_info = {
                "name": compound.name,
                "count": compound.count,
                "chebi_id": compound.chebi_id
            }
            
            # Optionally include SMILES
            if include_smiles:
                compound_info["smiles"] = compound.smiles
            
            if compound.compound_type == "reactant":
                reactants.append(compound_info)
            else:
                products.append(compound_info)
        
        return {
            "ec": reaction.ec,
            "is_polymeric": reaction.is_polymeric,
            "reactants": reactants,
            "products": products
        }
    
    def _build_mechanism(self, enzyme: Enzyme, include_references: bool = False) -> Optional[Dict[str, Any]]:
        """Build the mechanism section of the response."""
        if enzyme.reaction is None or not enzyme.reaction.mechanisms:
            return None
        
        mechanisms = []
        
        for mech in sorted(enzyme.reaction.mechanisms, key=lambda item: item.mechanism_id):
            steps = []
            for step in sorted(mech.steps, key=lambda x: x.step_id):
                steps.append({
                    "step_id": step.step_id,
                    "description": step.description,
                    "is_product": step.is_product,
                    "figure": step.figure
                })
            
            mechanism_info = {
                "mechanism_id": mech.mechanism_id,
                "summary_text": mech.mechanism_text,
                "is_detailed": mech.is_detailed,
                "rating": mech.rating,
                "components_summary": mech.components_summary,
                "steps": steps
            }
            if include_references:
                references = []
                for reference in mech.references:
                    try:
                        evidence = json.loads(reference.evidence_types or '[]')
                    except (ValueError, TypeError):
                        evidence = []
                    references.append({'pubmed_id': reference.pubmed_id, 'doi': reference.doi,
                        'title': reference.title, 'evidence_types':
                        [value for value in evidence if isinstance(value, str)] if isinstance(evidence, list) else []})
                mechanism_info['references'] = references
            mechanisms.append(mechanism_info)
        
        # Return first mechanism if only one, else return list
        if len(mechanisms) == 1:
            return mechanisms[0]
        return {"mechanisms": mechanisms}
    
    def _build_cofactors(self, enzyme: Enzyme, include_smiles: bool = False) -> List[Dict[str, Any]]:
        """Build the cofactors section of the response.
        
        Args:
            enzyme: The enzyme object
            include_smiles: Whether to include SMILES strings
        """
        cofactors = []
        
        for cofactor in enzyme.cofactors:
            # Get roles for this cofactor
            roles = []
            for role in cofactor.roles:
                role_info = {
                    "role": role.role,
                    "role_type": role.role_type,
                    "role_group": role.role_group
                }
                roles.append(role_info)
            
            cofactor_info = {
                "pdb_code": cofactor.pdb_code,
                "name": cofactor.name,
                "chebi_id": cofactor.chebi_id,
                "kegg_compound": cofactor.kegg_compound,
                "uniprot_id": cofactor.uniprot_id,
                "pdb_id": cofactor.pdb_id,
                "ec": cofactor.ec,
                "roles": roles
            }
            
            if include_smiles:
                cofactor_info["smiles"] = cofactor.smiles
            
            cofactors.append(cofactor_info)
        
        return cofactors
    
    def get_cofactors(self, query_id: str, include_smiles: bool = False) -> Optional[Dict[str, Any]]:
        """
        Retrieve cofactor information for an enzyme by any identifier.
        
        Args:
            query_id: MCSA ID, UniProt ID, or PDB ID
            include_smiles: Whether to include SMILES strings
            
        Returns:
            Dictionary containing cofactor information, or None if not found.
        """
        session = self._get_session()
        
        try:
            # Find MCSA ID
            mcsa_id = self._find_mcsa_id(session, query_id)
            if mcsa_id is None:
                return None
            
            # Load enzyme with cofactors
            enzyme = session.query(Enzyme).options(
                joinedload(Enzyme.cofactors).joinedload(Cofactor.roles),
            ).filter(Enzyme.mcsa_id == mcsa_id).first()
            
            if enzyme is None:
                return None
            
            return {
                "mcsa_id": enzyme.mcsa_id,
                "enzyme_name": enzyme.enzyme_name,
                "cofactors": self._build_cofactors(enzyme, include_smiles)
            }
        
        finally:
            session.close()
    
    def get_sequence(self, query_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve protein sequence for an enzyme by any identifier.
        
        Args:
            query_id: MCSA ID, UniProt ID, or PDB ID
            
        Returns:
            Dictionary containing sequence information, or None if not found.
        """
        session = self._get_session()
        
        try:
            # Find MCSA ID
            mcsa_id = self._find_mcsa_id(session, query_id)
            if mcsa_id is None:
                return None
            
            # Load enzyme with sequences
            enzyme = session.query(Enzyme).options(
                joinedload(Enzyme.sequences),
            ).filter(Enzyme.mcsa_id == mcsa_id).first()
            
            if enzyme is None:
                return None
            
            # Get the first sequence that has sequence data
            sequence = None
            uniprot_id = None
            for seq in enzyme.sequences:
                if seq.sequence:
                    sequence = seq.sequence
                    uniprot_id = seq.uniprot_id
                    break
            
            # If no sequence with data, try reference uniprot id
            if sequence is None and enzyme.reference_uniprot_id:
                for seq in enzyme.sequences:
                    if seq.uniprot_id.upper() == enzyme.reference_uniprot_id.upper():
                        sequence = seq.sequence
                        uniprot_id = seq.uniprot_id
                        break
            
            return {
                "mcsa_id": enzyme.mcsa_id,
                "enzyme_name": enzyme.enzyme_name,
                "uniprot_id": uniprot_id,
                "sequence": sequence
            }
        
        finally:
            session.close()
    
    def search_by_name(self, name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search enzymes by name (partial match).
        
        Args:
            name: Partial enzyme name to search
            limit: Maximum number of results
            
        Returns:
            List of matching enzymes with basic info
        """
        session = self._get_session()
        
        try:
            enzymes = session.query(Enzyme).filter(
                Enzyme.enzyme_name.ilike(f"%{name}%")
            ).limit(limit).all()
            
            return [
                {
                    "mcsa_id": e.mcsa_id,
                    "enzyme_name": e.enzyme_name,
                    "reference_uniprot_id": e.reference_uniprot_id
                }
                for e in enzymes
            ]
        finally:
            session.close()
    
    def list_all_enzymes(self, page: int = 1, per_page: int = 50) -> Dict[str, Any]:
        """
        List all enzymes with pagination.
        
        Args:
            page: Page number (1-indexed)
            per_page: Number of results per page
            
        Returns:
            Dictionary with pagination info and enzyme list
        """
        session = self._get_session()
        
        try:
            total = session.query(Enzyme).count()
            offset = (page - 1) * per_page
            
            enzymes = session.query(Enzyme).order_by(
                Enzyme.mcsa_id
            ).offset(offset).limit(per_page).all()
            
            return {
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page,
                "results": [
                    {
                        "mcsa_id": e.mcsa_id,
                        "enzyme_name": e.enzyme_name,
                        "reference_uniprot_id": e.reference_uniprot_id
                    }
                    for e in enzymes
                ]
            }
        finally:
            session.close()
    
    def get_identifiers(self, mcsa_id: int) -> Dict[str, List[str]]:
        """
        Get all identifiers for an enzyme.
        
        Args:
            mcsa_id: The MCSA ID of the enzyme
            
        Returns:
            Dictionary with identifier types as keys and lists of values
        """
        session = self._get_session()
        
        try:
            identifiers = session.query(Identifier).filter(
                Identifier.mcsa_id == mcsa_id
            ).all()
            
            result = {"mcsa": [], "uniprot": [], "pdb": []}
            
            for ident in identifiers:
                if ident.identifier_type in result:
                    result[ident.identifier_type].append(ident.identifier_value)
            
            return result
        finally:
            session.close()

    def get_mechanism_electron_flows(
        self, 
        query_id: str, 
        mechanism_id: Optional[int] = None,
        step_index: Optional[int] = None,
        include_cxsmiles: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve electron flow information for mechanism steps.
        
        This method returns detailed electron flow data extracted from MRV mechanism diagrams,
        including the source and target of electron movements in each step.
        
        Args:
            query_id: MCSA ID, UniProt ID, or PDB ID
            mechanism_id: Optional mechanism ID to filter by specific mechanism
            step_index: Optional step index to retrieve specific step (0=reactant, 1=step1, etc.)
            include_cxsmiles: Whether to include CXSMILES strings (default True)
            
        Returns:
            Dictionary containing:
            - mcsa_id: MCSA ID of the enzyme
            - enzyme_name: Name of the enzyme
            - steps: List of mechanism steps with electron flow data
            
            Returns None if enzyme not found.
        """
        session = self._get_session()
        
        try:
            # Find MCSA ID
            mcsa_id = self._find_mcsa_id(session, query_id)
            if mcsa_id is None:
                return None
            
            # Get enzyme name
            enzyme = session.query(Enzyme).filter(Enzyme.mcsa_id == mcsa_id).first()
            if enzyme is None:
                return None
            
            # Build query for parsed steps - include ALL steps regardless of status
            query = session.query(MechanismParsedStep).filter(
                MechanismParsedStep.mcsa_id == mcsa_id
            )
            
            if mechanism_id is not None:
                query = query.filter(MechanismParsedStep.mechanism_id == mechanism_id)
            
            if step_index is not None:
                query = query.filter(MechanismParsedStep.step_index == step_index)
            
            # Order by mechanism_id and step_index
            steps = query.order_by(
                MechanismParsedStep.mechanism_id,
                MechanismParsedStep.step_index
            ).all()
            
            # Build response
            steps_data = []
            for step in steps:
                # Parse electron flows and optionally filter CXSMILES-related fields
                electron_flows_raw = json.loads(step.electron_flows) if step.electron_flows else []
                
                if not include_cxsmiles and electron_flows_raw:
                    # Filter out cxsmiles-related fields from electron flows to save tokens
                    electron_flows = []
                    for ef in electron_flows_raw:
                        filtered_ef = self._filter_cxsmiles_fields(ef)
                        electron_flows.append(filtered_ef)
                else:
                    electron_flows = electron_flows_raw
                
                # Generate status message for non-success steps
                status_message = None
                if step.processing_status == "error":
                    status_message = step.error_message or "Data conversion failed, electron flow information is unavailable"
                elif step.processing_status == "warning":
                    status_message = step.error_message or "Data conversion has warnings, electron flow information may be incomplete"
                
                step_data = {
                    "step_index": step.step_index,
                    "role": step.role,
                    "description": step.description,
                    "mechanism_id": step.mechanism_id,
                    "processing_status": step.processing_status,
                    "status_message": status_message,
                    "electron_flows": electron_flows,
                    "involved_residues": json.loads(step.involved_residues) if step.involved_residues else [],
                    "alignment_match_rate": step.alignment_match_rate,
                    "alignment_warnings": step.alignment_warnings
                }
                
                if include_cxsmiles:
                    step_data["cxsmiles"] = step.cxsmiles
                
                steps_data.append(step_data)
            
            return {
                "mcsa_id": mcsa_id,
                "enzyme_name": enzyme.enzyme_name,
                "total_steps": len(steps_data),
                "steps": steps_data
            }
        
        finally:
            session.close()

    def get_mechanism_electron_flow_summary(self, query_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a summary of electron flows for an enzyme's mechanisms.
        
        Returns an overview of all mechanisms with step counts and involved residues.
        
        Args:
            query_id: MCSA ID, UniProt ID, or PDB ID
            
        Returns:
            Dictionary with mechanism summary information, or None if not found.
        """
        session = self._get_session()
        
        try:
            # Find MCSA ID
            mcsa_id = self._find_mcsa_id(session, query_id)
            if mcsa_id is None:
                return None
            
            # Get enzyme name
            enzyme = session.query(Enzyme).filter(Enzyme.mcsa_id == mcsa_id).first()
            if enzyme is None:
                return None
            
            # Get all parsed steps
            steps = session.query(MechanismParsedStep).filter(
                MechanismParsedStep.mcsa_id == mcsa_id,
                MechanismParsedStep.processing_status == "success"
            ).order_by(
                MechanismParsedStep.mechanism_id,
                MechanismParsedStep.step_index
            ).all()
            
            # Group by mechanism_id
            mechanisms = {}
            all_residues = set()
            
            for step in steps:
                mech_id = step.mechanism_id
                if mech_id not in mechanisms:
                    mechanisms[mech_id] = {
                        "mechanism_id": mech_id,
                        "step_count": 0,
                        "steps_with_electron_flows": 0,
                        "involved_residues": set()
                    }
                
                mechanisms[mech_id]["step_count"] += 1
                
                if step.electron_flows:
                    mechanisms[mech_id]["steps_with_electron_flows"] += 1
                
                if step.involved_residues:
                    residues = json.loads(step.involved_residues)
                    mechanisms[mech_id]["involved_residues"].update(residues)
                    all_residues.update(residues)
            
            # Convert sets to lists for JSON serialization
            mechanism_list = []
            for mech_id, mech_data in sorted(mechanisms.items()):
                mech_data["involved_residues"] = sorted(mech_data["involved_residues"])
                mechanism_list.append(mech_data)
            
            return {
                "mcsa_id": mcsa_id,
                "enzyme_name": enzyme.enzyme_name,
                "mechanism_count": len(mechanisms),
                "all_involved_residues": sorted(all_residues),
                "mechanisms": mechanism_list
            }
        
        finally:
            session.close()
