"""
Enzyme Retriever: Query interface for M-CSA database

This module provides the EnzymeRetriever class for querying enzyme information
from the SQLite database using various identifier types (MCSA ID, UniProt ID, PDB ID).
"""

import json
from typing import Any, Dict, List, Optional
from pathlib import Path

from sqlalchemy import create_engine, or_
from sqlalchemy.orm import Session, sessionmaker, joinedload

from models import (
    Base, Enzyme, Identifier, ProteinSequence, Residue, ResidueRole,
    ResidueUniProt, ResiduePDB, Reaction, ReactionCompound, Mechanism,
    MechanismStep, MechanismReference
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
    
    def get_enzyme_info(self, query_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve comprehensive enzyme information by any identifier.
        
        Args:
            query_id: MCSA ID, UniProt ID, or PDB ID
            
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
            enzyme = session.query(Enzyme).options(
                joinedload(Enzyme.residues).joinedload(Residue.roles),
                joinedload(Enzyme.residues).joinedload(Residue.uniprot_positions),
                joinedload(Enzyme.residues).joinedload(Residue.pdb_positions),
                joinedload(Enzyme.reaction).joinedload(Reaction.compounds),
                joinedload(Enzyme.reaction).joinedload(Reaction.mechanisms).joinedload(Mechanism.steps),
            ).filter(Enzyme.mcsa_id == mcsa_id).first()
            
            if enzyme is None:
                return None
            
            # Build response
            result = {
                "basic_info": self._build_basic_info(enzyme),
                "active_sites_uniprot": self._build_uniprot_sites(enzyme),
                "active_sites_pdb": self._build_pdb_sites(enzyme),
                "reaction": self._build_reaction(enzyme),
                "mechanism": self._build_mechanism(enzyme)
            }
            
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
                    "roles_summary": residue.roles_summary
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
                    "roles_summary": residue.roles_summary
                }
                sites.append(site)
        
        return sites
    
    def _build_reaction(self, enzyme: Enzyme) -> Optional[Dict[str, Any]]:
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
    
    def _build_mechanism(self, enzyme: Enzyme) -> Optional[Dict[str, Any]]:
        """Build the mechanism section of the response."""
        if enzyme.reaction is None or not enzyme.reaction.mechanisms:
            return None
        
        mechanisms = []
        
        for mech in enzyme.reaction.mechanisms:
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
            mechanisms.append(mechanism_info)
        
        # Return first mechanism if only one, else return list
        if len(mechanisms) == 1:
            return mechanisms[0]
        return {"mechanisms": mechanisms}
    
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
