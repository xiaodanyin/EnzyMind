"""
SQLAlchemy ORM Models for M-CSA Enzyme Database

This module defines the database schema for storing enzyme mechanism data
from the M-CSA (Mechanism and Catalytic Site Atlas) database.
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float, 
    ForeignKey, DateTime, Enum as SQLEnum, Table, JSON
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import enum


class Base(DeclarativeBase):
    """SQLAlchemy Declarative Base"""
    pass


class IdentifierType(enum.Enum):
    """Enum for different identifier types"""
    MCSA = "mcsa"
    UNIPROT = "uniprot"
    PDB = "pdb"


class Enzyme(Base):
    """
    Main enzyme table storing basic enzyme information.
    Primary key is mcsa_id.
    """
    __tablename__ = "enzyme"
    
    mcsa_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enzyme_name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_reference_uniprot_id: Mapped[bool] = mapped_column(Boolean, default=True)
    reference_uniprot_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    all_ecs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON serialized list
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    identifiers: Mapped[List["Identifier"]] = relationship(
        "Identifier", back_populates="enzyme", cascade="all, delete-orphan"
    )
    sequences: Mapped[List["ProteinSequence"]] = relationship(
        "ProteinSequence", back_populates="enzyme", cascade="all, delete-orphan"
    )
    residues: Mapped[List["Residue"]] = relationship(
        "Residue", back_populates="enzyme", cascade="all, delete-orphan"
    )
    reaction: Mapped[Optional["Reaction"]] = relationship(
        "Reaction", back_populates="enzyme", uselist=False, cascade="all, delete-orphan"
    )
    cofactors: Mapped[List["Cofactor"]] = relationship(
        "Cofactor", back_populates="enzyme", cascade="all, delete-orphan"
    )


class Identifier(Base):
    """
    Index table for multi-ID retrieval.
    Stores all UniProt IDs and PDB IDs for reverse lookup.
    """
    __tablename__ = "identifier"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mcsa_id: Mapped[int] = mapped_column(Integer, ForeignKey("enzyme.mcsa_id"), nullable=False)
    identifier_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'mcsa', 'uniprot', 'pdb'
    identifier_value: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # Relationship
    enzyme: Mapped["Enzyme"] = relationship("Enzyme", back_populates="identifiers")


class ProteinSequence(Base):
    """
    Stores protein sequence information from the protein.sequences field.
    """
    __tablename__ = "protein_sequence"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mcsa_id: Mapped[int] = mapped_column(Integer, ForeignKey("enzyme.mcsa_id"), nullable=False)
    uniprot_id: Mapped[str] = mapped_column(String(50), nullable=False)
    sequence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Protein sequence from UniProt
    
    # Relationship
    enzyme: Mapped["Enzyme"] = relationship("Enzyme", back_populates="sequences")


class Residue(Base):
    """
    Main table for catalytic residues/active sites.
    """
    __tablename__ = "residue"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mcsa_id: Mapped[int] = mapped_column(Integer, ForeignKey("enzyme.mcsa_id"), nullable=False)
    roles_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    function_location_abv: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    main_annotation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ptm: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Relationships
    enzyme: Mapped["Enzyme"] = relationship("Enzyme", back_populates="residues")
    roles: Mapped[List["ResidueRole"]] = relationship(
        "ResidueRole", back_populates="residue", cascade="all, delete-orphan"
    )
    uniprot_positions: Mapped[List["ResidueUniProt"]] = relationship(
        "ResidueUniProt", back_populates="residue", cascade="all, delete-orphan"
    )
    pdb_positions: Mapped[List["ResiduePDB"]] = relationship(
        "ResiduePDB", back_populates="residue", cascade="all, delete-orphan"
    )


class ResidueRole(Base):
    """
    Stores the functional roles of each residue.
    """
    __tablename__ = "residue_role"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    residue_id: Mapped[int] = mapped_column(Integer, ForeignKey("residue.id"), nullable=False)
    group_function: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    function_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    function: Mapped[str] = mapped_column(String(200), nullable=False)
    emo: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Relationship
    residue: Mapped["Residue"] = relationship("Residue", back_populates="roles")


class ResidueUniProt(Base):
    """
    Stores UniProt-perspective position information for residues.
    """
    __tablename__ = "residue_uniprot"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    residue_id: Mapped[int] = mapped_column(Integer, ForeignKey("residue.id"), nullable=False)
    uniprot_id: Mapped[str] = mapped_column(String(50), nullable=False)
    code: Mapped[str] = mapped_column(String(10), nullable=False)  # Amino acid code (e.g., 'Asp')
    resid: Mapped[int] = mapped_column(Integer, nullable=False)  # Residue number
    is_reference: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationship
    residue: Mapped["Residue"] = relationship("Residue", back_populates="uniprot_positions")


class ResiduePDB(Base):
    """
    Stores PDB-perspective position information for residues.
    """
    __tablename__ = "residue_pdb"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    residue_id: Mapped[int] = mapped_column(Integer, ForeignKey("residue.id"), nullable=False)
    pdb_id: Mapped[str] = mapped_column(String(10), nullable=False)
    chain_name: Mapped[str] = mapped_column(String(10), nullable=False)
    assembly_chain_name: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    assembly: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    resid: Mapped[int] = mapped_column(Integer, nullable=False)
    auth_resid: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_reference: Mapped[bool] = mapped_column(Boolean, default=False)
    domain_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    domain_cath_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Relationship
    residue: Mapped["Residue"] = relationship("Residue", back_populates="pdb_positions")


class Reaction(Base):
    """
    Stores reaction information for an enzyme.
    """
    __tablename__ = "reaction"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mcsa_id: Mapped[int] = mapped_column(Integer, ForeignKey("enzyme.mcsa_id"), nullable=False, unique=True)
    ec: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_polymeric: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Atom mapping fields
    reaction_smiles: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # reactants>>products
    mapped_rxn: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Atom-mapped reaction SMILES
    mapping_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Mapping confidence score
    
    # Relationships
    enzyme: Mapped["Enzyme"] = relationship("Enzyme", back_populates="reaction")
    compounds: Mapped[List["ReactionCompound"]] = relationship(
        "ReactionCompound", back_populates="reaction", cascade="all, delete-orphan"
    )
    mechanisms: Mapped[List["Mechanism"]] = relationship(
        "Mechanism", back_populates="reaction", cascade="all, delete-orphan"
    )


class ReactionCompound(Base):
    """
    Stores reactants and products for reactions.
    """
    __tablename__ = "reaction_compound"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reaction_id: Mapped[int] = mapped_column(Integer, ForeignKey("reaction.id"), nullable=False)
    compound_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'reactant' or 'product'
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=1)
    chebi_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    mol_file: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    smiles: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # SMILES from ChEBI
    
    # Relationship
    reaction: Mapped["Reaction"] = relationship("Reaction", back_populates="compounds")


class Mechanism(Base):
    """
    Stores mechanism information including summary text.
    """
    __tablename__ = "mechanism"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reaction_id: Mapped[int] = mapped_column(Integer, ForeignKey("reaction.id"), nullable=False)
    mechanism_id: Mapped[int] = mapped_column(Integer, nullable=False)
    is_detailed: Mapped[bool] = mapped_column(Boolean, default=False)
    mechanism_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    components_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    reaction: Mapped["Reaction"] = relationship("Reaction", back_populates="mechanisms")
    steps: Mapped[List["MechanismStep"]] = relationship(
        "MechanismStep", back_populates="mechanism", cascade="all, delete-orphan"
    )
    references: Mapped[List["MechanismReference"]] = relationship(
        "MechanismReference", back_populates="mechanism", cascade="all, delete-orphan"
    )


class MechanismStep(Base):
    """
    Stores individual steps of the mechanism.
    """
    __tablename__ = "mechanism_step"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mechanism_id: Mapped[int] = mapped_column(Integer, ForeignKey("mechanism.id"), nullable=False)
    step_id: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    figure: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_product: Mapped[bool] = mapped_column(Boolean, default=False)
    marvin_xml: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Relationship
    mechanism: Mapped["Mechanism"] = relationship("Mechanism", back_populates="steps")


class MechanismReference(Base):
    """
    Stores literature references for mechanisms.
    """
    __tablename__ = "mechanism_reference"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mechanism_id: Mapped[int] = mapped_column(Integer, ForeignKey("mechanism.id"), nullable=False)
    pubmed_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    doi: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_types: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON serialized list
    
    # Relationship
    mechanism: Mapped["Mechanism"] = relationship("Mechanism", back_populates="references")


class Cofactor(Base):
    """
    Stores cofactor information for enzymes.
    Cofactors are non-protein molecules that assist in enzyme catalysis.
    Data source: curated_data.csv (entries with residue/reactant/product/cofactor == 'cofactor')
    """
    __tablename__ = "cofactor"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mcsa_id: Mapped[int] = mapped_column(Integer, ForeignKey("enzyme.mcsa_id"), nullable=False)
    uniprot_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    pdb_id: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    ec: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    pdb_code: Mapped[str] = mapped_column(String(20), nullable=False)  # Cofactor abbreviation (e.g., FAD, NAD, CU)
    kegg_compound: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # KEGG compound ID
    chebi_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # ChEBI ID
    name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Cofactor full name
    smiles: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # SMILES from ChEBI
    
    # Relationships
    enzyme: Mapped["Enzyme"] = relationship("Enzyme", back_populates="cofactors")
    roles: Mapped[List["CofactorRole"]] = relationship(
        "CofactorRole", back_populates="cofactor", cascade="all, delete-orphan"
    )


class CofactorRole(Base):
    """
    Stores the functional roles of each cofactor in the catalytic mechanism.
    """
    __tablename__ = "cofactor_role"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cofactor_id: Mapped[int] = mapped_column(Integer, ForeignKey("cofactor.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(200), nullable=False)  # e.g., 'hydride acceptor', 'proton donor'
    role_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g., 'reactant', 'spectator', 'interaction'
    role_group: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # e.g., 'hydride shuttle', 'proton shuttle'
    
    # Relationship
    cofactor: Mapped["Cofactor"] = relationship("Cofactor", back_populates="roles")


class MechanismParsedStep(Base):
    """
    Stores parsed mechanism steps with CXSMILES and electron flow information.
    This table contains detailed catalytic attack information extracted from MRV files.
    """
    __tablename__ = "mechanism_parsed_step"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Link to original data
    mechanism_step_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    mcsa_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    mechanism_id: Mapped[int] = mapped_column(Integer, nullable=False)
    original_step_id: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Step information
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=reactants, 1=step1, etc.
    cxsmiles: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Can be None for error records
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # 'reactant', 'intermediate', 'product'
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # File path
    mrv_file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Electron flow information (stored as JSON)
    electron_flows: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of electron flow data
    involved_residues: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of residue names
    
    # Alignment quality
    alignment_match_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    alignment_warnings: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Processing status
    processing_status: Mapped[str] = mapped_column(String(50), nullable=False, default="success")  # 'success', 'warning', 'error'
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Atom mapping status
    mechanism_atoms_fully_mapped: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
